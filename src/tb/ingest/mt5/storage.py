"""Append-only bounded Parquet commits with SQLite deduplication and restart checkpoints."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import polars as pl

from tb.core.timeutil import datetime_to_ns
from tb.ingest.history.core import (
    BronzeManifest,
    atomic_write_bytes,
    atomic_write_json,
    sha256_bytes,
    sha256_file,
)
from tb.ingest.mt5.models import TIMEFRAMES, FeedConfig, Observation, StorageRefused
from tb.silver.market import clean_minute_bars


def record_id(row: Observation, identity: str) -> str:
    """Receipt time and evidence label cannot turn an old source tick into a new record."""
    payload = row.model_dump(
        mode="json", exclude={"received_at", "evidence", "coverage_started_at"}
    )
    stamp = payload.pop("clock_stamp", None)
    if stamp:
        # A new conversion/profile version cannot make the same raw fact new evidence.
        payload.pop("source_at")
        payload["raw_source_clock"] = {
            k: stamp[k] for k in ("provider", "server", "raw_representation")
        }
    return sha256_bytes((identity + json.dumps(payload, sort_keys=True)).encode())


def parquet_bytes(frame: pl.DataFrame) -> bytes:
    """Serialize only one bounded batch, reusing the existing atomic byte writer."""
    buffer = BytesIO()
    frame.write_parquet(buffer)
    return buffer.getvalue()


class FeedStore:
    """One writer transaction per bounded batch; only committed SQLite entries are visible."""

    def __init__(
        self,
        root: Path,
        config: FeedConfig,
        *,
        code_version: str,
        provider: Literal["mt5_demo", "oanda_practice"] = "mt5_demo",
    ) -> None:
        self.root, self.config, self.code_version = root.resolve(), config, code_version
        self.provider = provider
        self.namespace = "mt5_feed" if provider == "mt5_demo" else "oanda_practice"
        state = self.root / "data" / self.namespace
        state.mkdir(parents=True, exist_ok=True)
        self.db_path = state / "checkpoint.sqlite"
        self.db = sqlite3.connect(self.db_path, timeout=1)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, identity TEXT NOT NULL,
                started TEXT NOT NULL, origin TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS watermarks(key TEXT PRIMARY KEY, source_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS batches(seq INTEGER PRIMARY KEY, session TEXT NOT NULL,
                manifest TEXT NOT NULL, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS health(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        """)
        self.db.commit()

    def session(self, identity: str, now: datetime, *, synthetic: bool) -> tuple[str, datetime]:
        """Resume the immutable same-identity collection session; never backdate its start."""
        origin = "synthetic" if synthetic else self.provider
        row = self.db.execute(
            "SELECT id,started FROM sessions WHERE identity=? AND origin=? ORDER BY rowid DESC LIMIT 1",
            (identity, origin),
        ).fetchone()
        if row:
            return str(row[0]), datetime.fromisoformat(row[1])
        session = uuid4().hex
        self.db.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)", (session, identity, now.isoformat(), origin)
        )
        self.db.commit()
        return session, now

    def _check_quota(self, reserve_bytes: int = 0) -> None:
        # The bounded file population is checked without reading observations into RAM.
        roots = (
            self.root / "data/bronze" / self.namespace,
            self.root / "data/silver" / self.namespace,
            self.db_path.parent,
            self.root / "reports/market_feed",
        )
        total = sum(
            p.stat().st_size
            for base in roots
            if base.exists()
            for p in base.rglob("*")
            if p.is_file()
        )
        if total + reserve_bytes >= self.config.max_storage_mb * 1024 * 1024:
            raise StorageRefused("Market-data storage quota reached; explicit archival required")

    def commit(
        self,
        session: str,
        rows: list[Observation],
        raw: list[dict[str, Any]],
        *,
        received_at: datetime,
        warnings: list[str],
    ) -> dict[str, Any]:
        """Commit a single symbol/kind/timeframe group; orphan files never imply a checkpoint."""
        if len(rows) > self.config.max_rows or len(raw) > self.config.max_rows:
            raise StorageRefused("Market batch exceeds configured bound")
        self._check_quota()
        session_row = self.db.execute(
            "SELECT identity,started,origin FROM sessions WHERE id=?", (session,)
        ).fetchone()
        if session_row is None:
            raise StorageRefused("Unknown immutable collection session")
        identity, started, origin = session_row
        if rows and len({(r.symbol, r.kind, r.timeframe) for r in rows}) != 1:
            raise StorageRefused("Mixed market batch refused")
        for row in rows:
            if row.evidence == "forward_observed" and (
                origin != self.provider or row.source_at < datetime.fromisoformat(started)
            ):
                raise StorageRefused(
                    "Historical or synthetic record cannot claim prospective evidence"
                )
            if origin == "synthetic" and row.evidence != "synthetic":
                raise StorageRefused("Synthetic session evidence mismatch")
            if row.clock_stamp and (
                row.clock_stamp.provider != self.provider
                or row.clock_stamp.identity_fingerprint != identity
            ):
                raise StorageRefused("Provider/profile/session identity mismatch")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            unique: list[Observation] = []
            ids: set[str] = set()
            quality = list(warnings)
            for row in rows:
                key = record_id(row, identity)
                if (
                    key in ids
                    or self.db.execute("SELECT 1 FROM seen WHERE id=?", (key,)).fetchone()
                ):
                    continue
                ids.add(key)
                watermark_key = f"{identity}:{row.symbol}:{row.kind}:{row.timeframe}"
                previous = self.db.execute(
                    "SELECT source_at FROM watermarks WHERE key=?", (watermark_key,)
                ).fetchone()
                if previous and row.source_at < datetime.fromisoformat(previous[0]):
                    quality.append("out_of_order_source_observation")
                    if row.evidence == "forward_observed":
                        row = row.model_copy(update={"evidence": "historical_backfill"})
                elif previous:
                    elapsed = (row.source_at - datetime.fromisoformat(previous[0])).total_seconds()
                    cadence = TIMEFRAMES.get(row.timeframe, self.config.poll_seconds)
                    if elapsed > cadence * 3:
                        quality.append("source_time_gap_detected")
                self.db.execute("INSERT INTO seen VALUES(?)", (key,))
                self.db.execute(
                    "INSERT INTO watermarks VALUES(?,?) ON CONFLICT(key) DO UPDATE SET source_at=MAX(source_at,excluded.source_at)",
                    (watermark_key, row.source_at.isoformat()),
                )
                unique.append(row)
            seq = int(self.db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM batches").fetchone()[0])
            batch_id = f"{seq:012d}-{uuid4().hex}"
            relative = Path(self.namespace) / session / batch_id
            bronze = self.root / "data/bronze" / relative
            silver = self.root / "data/silver" / relative
            raw_bytes = (json.dumps(raw, sort_keys=True, default=str) + "\n").encode()
            frame = pl.DataFrame(
                {
                    "raw_json": [json.dumps(v, sort_keys=True, default=str) for v in raw],
                    "received_at": [received_at] * len(raw),
                }
            )
            bronze_bytes = parquet_bytes(frame)
            silver_bytes = parquet_bytes(self._silver(unique))
            self._check_quota(len(raw_bytes) + len(bronze_bytes) + len(silver_bytes) + 65536)
            bronze.mkdir(parents=True)
            silver.mkdir(parents=True)
            atomic_write_bytes(bronze / "source.json", raw_bytes)
            atomic_write_bytes(bronze / "observations.parquet", bronze_bytes)
            manifest = BronzeManifest(
                source=self.provider if origin != "synthetic" else "mt5_fixture",
                symbol=rows[0].symbol if rows else "UNAVAILABLE",
                timeframe=rows[0].timeframe if rows else "tick",
                source_url="mt5://pinned-demo/read-only"
                if self.provider == "mt5_demo"
                else "https://api-fxpractice.oanda.com/read-only",
                requested_from=received_at,
                requested_to=received_at,
                actual_from=min((r.source_at for r in rows), default=None),
                actual_to=max((r.source_at for r in rows), default=None),
                rows=len(raw),
                byte_count=(bronze / "observations.parquet").stat().st_size,
                source_sha256=sha256_bytes(raw_bytes),
                parquet_sha256=sha256_file(bronze / "observations.parquet"),
                downloaded_at=received_at,
                code_version=self.code_version,
            )
            atomic_write_json(bronze / "observations.manifest.json", manifest)
            atomic_write_bytes(silver / "observations.parquet", silver_bytes)
            files = {
                str(p.relative_to(self.root).as_posix()): sha256_file(p)
                for p in (
                    bronze / "source.json",
                    bronze / "observations.parquet",
                    bronze / "observations.manifest.json",
                    silver / "observations.parquet",
                )
            }
            commit = {
                "schema_version": 1,
                "session_id": session,
                "session_started": started,
                "origin": origin,
                "identity_fingerprint": identity,
                "received_at": received_at.isoformat(),
                "rows": len(unique),
                "raw_rows": len(raw),
                "duplicates": len(rows) - len(unique),
                "warnings": sorted(set(quality)),
                "files": files,
                "code_version": self.code_version,
                "evidence_counts": {
                    kind: sum(r.evidence == kind for r in unique)
                    for kind in (
                        "forward_observed",
                        "historical_backfill",
                        "historical_research",
                        "synthetic",
                    )
                },
            }
            commit_path = bronze / "commit.json"
            atomic_write_json(commit_path, commit)
            self.db.execute(
                "INSERT INTO batches VALUES(?,?,?,?)",
                (seq, session, str(commit_path.relative_to(self.root)), sha256_file(commit_path)),
            )
            self.db.commit()
            # Ephemeral receipt: callers must display only normalized, unique committed rows.
            # This list is never serialized into the immutable commit manifest.
            return {**commit, "_accepted_rows": unique}
        except BaseException:
            self.db.rollback()
            raise

    def _silver(self, rows: list[Observation]) -> pl.DataFrame:
        if not rows:
            return pl.DataFrame({"timestamp_ns": pl.Series([], dtype=pl.Int64)})
        values = [
            {
                **row.model_dump(mode="python"),
                "timestamp_ns": datetime_to_ns(row.source_at),
                "source": "mt5_fixture" if row.evidence == "synthetic" else self.provider,
                "volume_kind": "broker_tick_count"
                if row.kind == "candle"
                else "source_trade_volume_unverified",
            }
            for row in rows
        ]
        frame = pl.DataFrame(values).sort("timestamp_ns")
        if rows[0].kind == "candle" and rows[0].timeframe == "M1":
            if any(row.tick_volume is None for row in rows):
                raise StorageRefused("Missing broker tick volume; candle batch quarantined")
            frame = clean_minute_bars(
                frame.with_columns(pl.col("tick_volume").cast(pl.Float64).alias("volume")),
                market_kind="weekday",
            ).frame
        return frame

    def last_commit(self) -> dict[str, Any] | None:
        """Verify committed bytes on restart; never repair or relabel a corrupt genuine batch."""
        row = self.db.execute(
            "SELECT manifest,digest FROM batches ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        path = (self.root / row[0]).resolve()
        if not path.is_relative_to(self.root) or sha256_file(path) != row[1]:
            raise StorageRefused("Committed checkpoint integrity failed")
        commit: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        for name, digest in commit["files"].items():
            file = (self.root / name).resolve()
            if not file.is_relative_to(self.root) or sha256_file(file) != digest:
                raise StorageRefused("Committed market data integrity failed")
        return commit

    def health(self, value: dict[str, Any]) -> None:
        """Keep an append-only health/restart journal without account numbers or credentials."""
        self.db.execute("INSERT INTO health(payload) VALUES(?)", (json.dumps(value),))
        self.db.commit()

    def close(self) -> None:
        self.db.close()
