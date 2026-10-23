"""SQLite WAL append-only decision evidence and Gold exports."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import polars as pl
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from tb.ingest.history.core import atomic_write_json, sha256_file

LedgerTable = Literal["decisions", "model_calls", "outcomes", "hypotheses", "interventions"]
_TABLES: tuple[LedgerTable, ...] = (
    "decisions",
    "model_calls",
    "outcomes",
    "hypotheses",
    "interventions",
)
LEDGER_SCHEMA_VERSION = "ledger-v1"


class LedgerVersions(BaseModel):
    """Version identifiers required on every immutable evidence row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_version: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    question_set_version: str = Field(min_length=1, max_length=100)
    features_version: str = Field(min_length=1, max_length=100)


class LedgerExportManifest(BaseModel):
    """Integrity metadata for one immutable-table Gold snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source_database: str
    table: LedgerTable
    rows: int = Field(ge=0)
    byte_count: int = Field(ge=0)
    parquet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exported_at: AwareDatetime
    code_version: str = LEDGER_SCHEMA_VERSION


def _utc_text(instant: datetime | None = None) -> str:
    value = datetime.now(UTC) if instant is None else instant.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _canonical(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


class DecisionLedger:
    """Own an on-host SQLite WAL database whose evidence rows cannot be changed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        """Open one configured connection; callers own its context lifetime."""

        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        common = """
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            decision_id TEXT,
            payload_json TEXT NOT NULL,
            content_sha256 TEXT NOT NULL CHECK(length(content_sha256) = 64),
            model_version TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            question_set_version TEXT NOT NULL,
            features_version TEXT NOT NULL
        """
        with self.connect() as connection:
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).casefold() != "wal":
                raise RuntimeError("SQLite refused WAL mode")
            connection.execute("PRAGMA synchronous = FULL")
            for table in _TABLES:
                extra = ""
                if table == "model_calls":
                    extra = (
                        ", provider TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL, "
                        "input_tokens INTEGER NOT NULL CHECK(input_tokens >= 0), "
                        "output_tokens INTEGER NOT NULL CHECK(output_tokens >= 0), "
                        "cost_usd REAL NOT NULL CHECK(cost_usd >= 0), cache_key TEXT"
                    )
                connection.execute(f"CREATE TABLE IF NOT EXISTS {table} ({common}{extra})")
                connection.execute(
                    f"""CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'append-only table'); END"""
                )
                connection.execute(
                    f"""CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'append-only table'); END"""
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS model_calls_budget_idx "
                "ON model_calls(provider, created_at_utc, status)"
            )

    def _append(
        self,
        table: LedgerTable,
        payload: Mapping[str, object],
        versions: LedgerVersions,
        *,
        decision_id: str | None = None,
        row_id: str | None = None,
        created_at: datetime | None = None,
        call_fields: Mapping[str, object] | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> str:
        identifier = uuid4().hex if row_id is None else row_id
        created = _utc_text(created_at)
        payload_json = _canonical(payload)
        evidence: dict[str, object] = {
            "id": identifier,
            "created_at_utc": created,
            "decision_id": decision_id,
            "payload": json.loads(payload_json),
            **versions.model_dump(),
        }
        base_columns = [
            "id",
            "created_at_utc",
            "decision_id",
            "payload_json",
            "content_sha256",
            "model_version",
            "prompt_version",
            "question_set_version",
            "features_version",
        ]
        values: list[object] = [
            identifier,
            created,
            decision_id,
            payload_json,
            _hash(evidence),
            versions.model_version,
            versions.prompt_version,
            versions.question_set_version,
            versions.features_version,
        ]
        if table == "model_calls":
            if call_fields is None:
                raise ValueError("model_calls require accounting fields")
            evidence.update(call_fields)
            values[4] = _hash(evidence)
            names = [
                "provider",
                "model",
                "status",
                "input_tokens",
                "output_tokens",
                "cost_usd",
                "cache_key",
            ]
            base_columns.extend(names)
            values.extend(call_fields[name] for name in names)
        placeholders = ", ".join("?" for _ in values)
        statement = f"INSERT INTO {table} ({', '.join(base_columns)}) VALUES ({placeholders})"
        if connection is None:
            with self.connect() as active:
                active.execute(statement, values)
        else:
            connection.execute(statement, values)
        return identifier

    def append_atomic_decision(
        self,
        connection: sqlite3.Connection,
        payload: Mapping[str, object],
        versions: LedgerVersions,
        *,
        row_id: str,
        created_at: datetime,
    ) -> str:
        """Join the caller's same-database transaction without committing its checkpoint."""
        database = connection.execute("PRAGMA database_list").fetchone()[2]
        if not connection.in_transaction or Path(database).resolve() != self.path.resolve():
            raise ValueError("Atomic evidence requires an active same-database transaction")
        return self._append(
            "decisions",
            payload,
            versions,
            row_id=row_id,
            created_at=created_at,
            connection=connection,
        )

    def append_decision(
        self, payload: Mapping[str, object], versions: LedgerVersions, *, row_id: str | None = None
    ) -> str:
        """Append an arena decision and return its immutable identifier."""

        return self._append("decisions", payload, versions, row_id=row_id)

    def append_model_call(
        self,
        payload: Mapping[str, object],
        versions: LedgerVersions,
        *,
        decision_id: str | None,
        provider: str,
        model: str,
        status: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        cache_key: str | None = None,
        created_at: datetime | None = None,
    ) -> str:
        """Append provider usage, including failures, skips, and cache hits."""

        return self._append(
            "model_calls",
            payload,
            versions,
            decision_id=decision_id,
            created_at=created_at,
            call_fields={
                "provider": provider,
                "model": model,
                "status": status,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "cache_key": cache_key,
            },
        )

    def append_outcome(
        self, decision_id: str, payload: Mapping[str, object], versions: LedgerVersions
    ) -> str:
        """Resolve a setup by appending an outcome; never mutate its decision row."""

        return self._append("outcomes", payload, versions, decision_id=decision_id)

    def append_hypothesis(
        self, payload: Mapping[str, object], versions: LedgerVersions, *, decision_id: str | None
    ) -> str:
        """Append one fixed-schema research hypothesis."""

        return self._append("hypotheses", payload, versions, decision_id=decision_id)

    def append_intervention(
        self, payload: Mapping[str, object], versions: LedgerVersions, *, decision_id: str | None
    ) -> str:
        """Append a human/system intervention without rewriting prior evidence."""

        return self._append("interventions", payload, versions, decision_id=decision_id)

    def rows(self, table: LedgerTable) -> list[dict[str, object]]:
        """Read one table in stable insertion order for audits and exports."""

        with self.connect() as connection:
            result = connection.execute(
                f"SELECT * FROM {table} ORDER BY created_at_utc, id"
            ).fetchall()
        return [dict(row) for row in result]

    def usage(self, *, provider: str | None, since_prefix: str) -> float:
        """Sum actual charged usage in a UTC date/month prefix."""

        predicate = "created_at_utc LIKE ? AND status IN ('ok', 'cost_exceeded')"
        values: list[object] = [f"{since_prefix}%"]
        if provider is not None:
            predicate += " AND provider = ?"
            values.append(provider)
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT COALESCE(SUM(cost_usd), 0.0) FROM model_calls WHERE {predicate}", values
            ).fetchone()
        return float(row[0])

    def export_gold(self, root: Path, *, exported_at: datetime | None = None) -> list[Path]:
        """Atomically export all ledger tables to checksummed Parquet snapshots."""

        instant = datetime.now(UTC) if exported_at is None else exported_at.astimezone(UTC)
        partition = root / f"date={instant.date().isoformat()}"
        partition.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        for table in _TABLES:
            records = self.rows(table)
            frame = pl.DataFrame(records) if records else pl.DataFrame({"id": []})
            path = partition / f"{table}.parquet"
            temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            try:
                frame.write_parquet(temporary, compression="zstd", statistics=True)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            atomic_write_json(
                path.with_name(f"{path.stem}_manifest.json"),
                LedgerExportManifest(
                    source_database=self.path.name,
                    table=table,
                    rows=len(records),
                    byte_count=path.stat().st_size,
                    parquet_sha256=sha256_file(path),
                    exported_at=instant,
                ),
            )
            outputs.append(path)
        return outputs
