"""Bounded report/Parquet reads and WAL-aware SQLite reads without writer initialization."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import ValidationError

from tb.backtest.validation import FINAL_TEST_START
from tb.dashboard.models import (
    AccountRecord,
    DecisionPage,
    DecisionView,
    EvidenceSource,
    LedgerTotals,
)


class EvidenceUnavailable(ValueError):
    """Safe displayable failure without payloads, credentials or stack traces."""


def safe_text(value: object, maximum: int = 180) -> str:
    """Mask credential-shaped text and omit markup/control characters."""

    text = str(value)
    text = re.sub(r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+", "[redacted]", text)
    text = re.sub(r"(?i)Bearer\s+\S+", "[redacted]", text)
    text = re.sub(r"\b(?:sk-|ghp_)[A-Za-z0-9_-]{12,}", "[redacted]", text)
    return re.sub(r"[\x00-\x1f<>`\[\]]", "", text)[:maximum]


def safe_path(root: Path, relative: str, suffix: str) -> Path:
    """Resolve only a file within this evidence root with the required suffix."""

    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix != suffix:
        raise EvidenceUnavailable("Evidence path refused")
    return path


def read_json(path: Path) -> dict[str, Any]:
    """Read small explicit metadata only, rejecting huge or malformed inputs."""

    try:
        if path.stat().st_size > 1_000_000:
            raise EvidenceUnavailable("Metadata exceeds the read limit")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise EvidenceUnavailable("Metadata must be an object")
        return value
    except (OSError, ValueError) as exc:
        raise EvidenceUnavailable("Evidence metadata unavailable or invalid") from exc


def catalog(root: Path) -> tuple[EvidenceSource, ...]:
    """Load a small source index; absence is an ordinary empty-dataset state."""

    if not (root / "index.json").exists():
        return ()
    raw = read_json(root / "index.json")
    try:
        sources = tuple(EvidenceSource.model_validate(v) for v in raw["sources"])
        if len(sources) > 100 or len({v.id for v in sources}) != len(sources):
            raise ValueError("Invalid catalog bounds")
        for source in sources:
            safe_path(root, source.path + "/account.json", ".json")
        return sources
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceUnavailable("Evidence index invalid") from exc


def account_record(folder: Path, source: EvidenceSource) -> AccountRecord | None:
    """Validate the writer snapshot and its evidence/currency identity."""

    try:
        account = AccountRecord.model_validate(read_json(folder / "account.json"))
        if account.mode != source.mode or account.currency != source.currency:
            return None
        return account
    except (EvidenceUnavailable, ValidationError):
        return None


def file_stamp(path: Path) -> tuple[int, ...]:
    """Cache key includes DB, WAL and manifest changes rather than DB mtime alone."""

    values: list[int] = []
    for item in (path, Path(str(path) + "-wal"), path.with_suffix(".manifest.json")):
        try:
            stat = item.stat()
            values.extend((stat.st_mtime_ns, stat.st_size))
        except OSError:
            values.extend((0, 0))
    return tuple(values)


@contextmanager
def readonly_connection(path: Path) -> Iterator[sqlite3.Connection]:
    """Read active WAL commits with normal locking and an OS-enforced read-only handle."""

    if not path.is_file() or path.suffix not in (".sqlite", ".db"):
        raise EvidenceUnavailable("Journal unavailable")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        yield connection
    finally:
        connection.close()


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


_STATUS_SQL = "COALESCE(json_extract(d.payload_json, '$.status'), CASE WHEN json_type(d.payload_json, '$.rejected') IS NOT NULL THEN 'rejected' WHEN json_type(d.payload_json, '$.candidate') IS NOT NULL THEN 'accepted' ELSE 'skipped' END)"


def _object(text: str | None) -> dict[str, Any]:
    if text is None:
        return {}
    if len(text) > 1_000_000:
        raise ValueError("Oversized row")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Invalid row")
    return value


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite numeric record")
    return result


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Naive stored timestamp")
    return result.astimezone(UTC)


def _decision(row: sqlite3.Row) -> DecisionView:
    value, outcome = _object(row["payload_json"]), _object(row["outcome_json"])
    candidate = value.get("candidate") or {}
    status = value.get("status") or (
        "rejected" if "rejected" in value else "accepted" if candidate else "skipped"
    )
    return DecisionView(
        rowid=row["rowid"],
        id=safe_text(row["id"]),
        timestamp=_timestamp(
            value.get("timestamp") or candidate.get("timestamp") or row["created_at_utc"]
        ),
        symbol=safe_text(value.get("symbol") or candidate.get("symbol") or "Unavailable"),
        strategy=safe_text(value.get("strategy") or "Unavailable"),
        status=safe_text(status),
        direction=safe_text(candidate.get("side") or value.get("direction") or "Unavailable"),
        intended_size=_decimal(value.get("intended_size") or candidate.get("requested_lots")),
        entry=_decimal(value.get("entry")),
        stop=_decimal(candidate.get("stop") or value.get("stop")),
        target=_decimal(candidate.get("target") or value.get("target")),
        fill=_decimal(outcome.get("entry_price")),
        filled_size=_decimal(outcome.get("lots") or outcome.get("quantity")),
        fill_time=_timestamp(outcome.get("entry_time")),
        exit=_decimal(outcome.get("exit_price")),
        exit_time=_timestamp(outcome.get("exit_time")),
        fees=_decimal(outcome.get("fees")),
        pnl=_decimal(outcome.get("pnl")),
        reason=safe_text(value.get("reason") or value.get("rejected") or ""),
        outcome_id=safe_text(row["outcome_id"]) if row["outcome_id"] else None,
    )


def decision_page(
    path: Path,
    *,
    limit: int = 50,
    before: int | None = None,
    symbol: str | None = None,
    strategy: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mode: str | None = None,
) -> DecisionPage:
    """Fetch one keyset page with bound filters and the latest linked outcome."""

    if not 1 <= limit <= 200 or (before is not None and before <= 0):
        raise ValueError("Invalid page bounds")
    try:
        with readonly_connection(path) as connection:
            tables = _tables(connection)
            if "decisions" not in tables:
                return DecisionPage(issues=("Decisions table unavailable",))
            predicates = ["json_valid(d.payload_json)"]
            bindings: list[object] = []
            if before is not None:
                predicates.append("d.rowid < ?")
                bindings.append(before)
            for field, val in (("symbol", symbol), ("strategy", strategy), ("status", status)):
                if val is not None:
                    expression = f"json_extract(d.payload_json, '$.{field}')"
                    if field == "symbol":
                        expression = "COALESCE(json_extract(d.payload_json, '$.symbol'), json_extract(d.payload_json, '$.candidate.symbol'))"
                    elif field == "status":
                        expression = _STATUS_SQL
                    predicates.append(expression + " = ?")
                    bindings.append(val)
            clock = "COALESCE(json_extract(d.payload_json, '$.timestamp'), json_extract(d.payload_json, '$.candidate.timestamp'), d.created_at_utc)"
            for boundary, operator in ((date_from, ">="), (date_to, "<=")):
                if boundary is not None:
                    if boundary.tzinfo is None:
                        raise ValueError("Filter time must be aware")
                    predicates.append(f"julianday({clock}) {operator} julianday(?)")
                    bindings.append(boundary.isoformat())
            linked = "SELECT o.{column} FROM outcomes o WHERE o.decision_id=d.id ORDER BY o.rowid DESC LIMIT 1"
            outcome = (
                "(" + linked.format(column="payload_json") + ")" if "outcomes" in tables else "NULL"
            )
            outcome_id = "(" + linked.format(column="id") + ")" if "outcomes" in tables else "NULL"
            rows = connection.execute(
                f"SELECT d.rowid, d.id, d.created_at_utc, d.payload_json, {outcome} AS outcome_json, {outcome_id} AS outcome_id "
                f"FROM decisions d WHERE {' AND '.join(predicates)} ORDER BY d.rowid DESC LIMIT ?",
                [*bindings, limit + 1],
            ).fetchall()
            views: list[DecisionView] = []
            issues: list[str] = []
            if connection.execute(
                "SELECT 1 FROM decisions WHERE NOT json_valid(payload_json) LIMIT 1"
            ).fetchone():
                issues.append("Malformed decision rows omitted")
            for row in rows[:limit]:
                try:
                    if mode is not None and _object(row["payload_json"]).get("mode") not in (
                        mode,
                        "simulated" if mode == "synthetic" else mode,
                    ):
                        raise ValueError("Evidence mode mismatch")
                    views.append(_decision(row))
                except (ValueError, TypeError, AttributeError, InvalidOperation):
                    issues.append("Malformed decision omitted")
            if "outcomes" not in tables:
                issues.append("Outcomes table unavailable")
            return DecisionPage(
                rows=tuple(views),
                next_cursor=rows[limit - 1]["rowid"] if len(rows) > limit else None,
                issues=tuple(dict.fromkeys(issues)),
            )
    except (sqlite3.Error, OSError, EvidenceUnavailable):
        return DecisionPage(issues=("Journal unavailable or schema incomplete",))


def ledger_totals(path: Path, mode: str | None = None) -> LedgerTotals:
    """Stream every outcome in small batches; invalid evidence suppresses ratios."""

    try:
        with readonly_connection(path) as connection:
            if "outcomes" not in _tables(connection):
                return LedgerTotals()
            count = wins = invalid = 0
            pnl = fees = profit = loss = Decimal("0")
            cursor = connection.execute("SELECT payload_json FROM outcomes ORDER BY rowid")
            while batch := cursor.fetchmany(500):
                for row in batch:
                    try:
                        item = _object(row[0])
                        if mode is not None and item.get("mode") not in (
                            mode,
                            "simulated" if mode == "synthetic" else mode,
                        ):
                            raise ValueError("Evidence mode mismatch")
                        value = _decimal(item.get("pnl"))
                        cost = _decimal(item.get("fees"))
                        if value is None or cost is None or cost < 0:
                            raise ValueError("Incomplete outcome")
                        count += 1
                        wins += int(value > 0)
                        pnl += value
                        fees += cost
                        profit += max(value, Decimal("0"))
                        loss += max(-value, Decimal("0"))
                    except (ValueError, TypeError, InvalidOperation):
                        invalid += 1
            return LedgerTotals(
                trade_count=count,
                wins=wins,
                pnl=pnl,
                fees=fees,
                gross_profit=profit,
                gross_loss=loss,
                invalid_rows=invalid,
                available=True,
            )
    except (sqlite3.Error, OSError, EvidenceUnavailable):
        return LedgerTotals()


def decision_counts(path: Path) -> dict[str, int]:
    """Count complete journal statuses with a SQL reduction, independent of pagination."""

    try:
        with readonly_connection(path) as connection:
            result = connection.execute(
                f"SELECT {_STATUS_SQL} AS status, COUNT(*) FROM decisions d "
                "WHERE json_valid(d.payload_json) GROUP BY status"
            )
            return {safe_text(row[0]): int(row[1]) for row in result}
    except (sqlite3.Error, OSError, EvidenceUnavailable):
        return {}


def journal_versions(path: Path) -> list[dict[str, str]]:
    """Read bounded version identifiers only, without provider prompts or secret fields."""

    try:
        with readonly_connection(path) as connection:
            rows = connection.execute(
                "SELECT DISTINCT model_version, prompt_version, features_version FROM decisions LIMIT 20"
            )
            return [
                dict(Model=safe_text(row[0]), Prompt=safe_text(row[1]), Features=safe_text(row[2]))
                for row in rows
            ]
    except (sqlite3.Error, OSError, EvidenceUnavailable):
        return []


def parquet_rows(folder: Path, name: str, mode: str, *, limit: int = 2000) -> list[dict[str, Any]]:
    """Project only manifested report exports; refuse real locked periods before scanning."""

    if name not in ("prices", "equity") or not 1 <= limit <= 2000:
        raise ValueError("Invalid chart bounds")
    path = safe_path(folder, name + ".parquet", ".parquet")
    manifest = read_json(path.with_suffix(".manifest.json"))
    try:
        end = _timestamp(manifest["time_end"])
        if manifest.get("mode") != mode or not all(
            k in manifest for k in ("source", "checksum", "row_count", "code_version")
        ):
            raise EvidenceUnavailable("Chart manifest incomplete or mode mismatch")
        if mode != "synthetic" and (end is None or end >= FINAL_TEST_START):
            raise EvidenceUnavailable("Reserved historical observations are locked")
        columns = (
            ["timestamp", "price"]
            if name == "prices"
            else ["timestamp", "equity", "cash", "holdings"]
        )
        scan = pl.scan_parquet(path).select(columns)
        if mode != "synthetic":
            scan = scan.filter(pl.col("timestamp") < FINAL_TEST_START)
        frame = scan.limit(limit).collect(engine="streaming")
        rows = frame.to_dicts()
        if mode != "synthetic" and len(rows) < min(limit, int(manifest["row_count"])):
            raise EvidenceUnavailable("Chart coverage conflicts with the reserved-period boundary")
        for row in rows:
            row["timestamp"] = _timestamp(row["timestamp"])
            for column in columns[1:]:
                if _decimal(row[column]) is None:
                    raise ValueError("Missing numeric observation")
        return rows
    except (KeyError, ValueError, OSError, pl.exceptions.PolarsError) as exc:
        raise EvidenceUnavailable("Chart unavailable or refused by its evidence boundary") from exc


def marked_drawdown(folder: Path, mode: str) -> Decimal | None:
    """Reduce marked equity with a lazy full-file scan; never infer an intratrade path."""

    try:
        parquet_rows(folder, "equity", mode, limit=1)
        path = folder / "equity.parquet"
        manifest = read_json(path.with_suffix(".manifest.json"))
        if manifest.get("series_type") != "marked":
            return None
        result = (
            pl.scan_parquet(path)
            .filter(pl.lit(True) if mode == "synthetic" else pl.col("timestamp") < FINAL_TEST_START)
            .select("timestamp", pl.col("equity").cast(pl.Float64))
            .with_columns(pl.col("equity").cum_max().alias("peak"))
            .select(
                ((pl.col("peak") - pl.col("equity")) / pl.col("peak") * 100)
                .max()
                .alias("drawdown"),
                pl.col("equity").is_finite().all().alias("finite"),
                pl.col("equity").is_null().any().alias("missing"),
                pl.col("timestamp").diff().dt.total_microseconds().min().alias("step"),
                pl.len().alias("rows"),
            )
            .collect(engine="streaming")
            .row(0, named=True)
        )
        if result["rows"] != manifest.get("row_count") or (
            not result["finite"]
            or result["missing"]
            or (result["step"] is not None and result["step"] <= 0)
        ):
            return None
        return _decimal(result["drawdown"])
    except (EvidenceUnavailable, ValueError, OSError, pl.exceptions.PolarsError):
        return None
