"""Consent-gated, sequential FX archives; raw bytes retained, no holdout requests."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from tb.core.leases import writer_lease
from tb.ingest.history.core import (
    IntegrityError,
    atomic_write_bytes,
    atomic_write_json,
    require_disk_space,
    sha256_file,
)
from tb.ingest.history.dukascopy import Side, candle_url, decode_candles
from tb.research.forex_registry import load_forex_plan
from tb.research.models import HOLDOUT, ForexDatasetPlan, ResearchRefused
from tb.research.registry import declare_artifact, read_metadata, safe

MAX_ARCHIVE_BYTES = 64 * 1024**2
SIDES: tuple[Side, ...] = ("BID", "ASK")


class ProviderFailure(RuntimeError):
    """Price-free, bounded technical diagnostics for the owner and fallback planner."""

    def __init__(self, details: dict[str, Any]) -> None:
        self.details = details
        super().__init__("historical_provider_technical_failure")


def request_bytes(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    data: dict[str, str] | None = None,
    referer: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    attempts: int = 3,
) -> bytes | None:
    """At most three sequential tries with backoff; never follow unreviewed redirects."""
    if not 1 <= attempts <= 3:
        raise ValueError("historical request attempts outside bound")
    error_class, sample, status = "unknown", "request failed", None
    for attempt in range(attempts):
        sleep(1 if not attempt else min(2**attempt, 8))
        try:
            with client.stream(
                method,
                url,
                data=data,
                headers={"Referer": referer} if referer else {},
                timeout=30,
                follow_redirects=False,
            ) as response:
                status = response.status_code
                if status == 404:
                    return None
                if status != 200:
                    error_class, sample = "HTTPStatusError", f"HTTP {status}"
                    continue
                parts, size = [], 0
                for part in response.iter_bytes():
                    size += len(part)
                    if size > MAX_ARCHIVE_BYTES:
                        raise ValueError("historical response size bound exceeded")
                    parts.append(part)
                return b"".join(parts)
        except (httpx.HTTPError, OSError, ValueError) as exc:
            error_class, sample = type(exc).__name__, "transport or bounded response failure"
    raise ProviderFailure(
        {
            "endpoint": url,
            "utc": clock().isoformat(),
            "http_status": status,
            "error_class": error_class,
            "successful_requests": 0,
            "failed_requests": attempts,
            "error_sample": sample,
        }
    )


class DownloadForm(HTMLParser):
    """Only the provider's download form; no script execution or arbitrary form actions."""

    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form":
            self.active = values.get("action") == "/get.php" and not self.fields
        elif tag == "input" and self.active:
            name, value = values.get("name"), values.get("value")
            if (
                name in {"tk", "date", "datemonth", "platform", "timeframe", "fxpair"}
                and value is not None
            ):
                self.fields[str(name)] = value

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.active = False


def histdata_window(period: date) -> tuple[datetime, datetime]:
    """Nominal file bounds in UTC: EST is constant UTC-5, including DST dates."""
    start = datetime(period.year, period.month, 1, tzinfo=UTC) + timedelta(hours=5)
    stop = datetime(
        period.year + (period.month == 12), period.month % 12 + 1, 1, tzinfo=UTC
    ) + timedelta(hours=5)
    return start, stop


def validate_period(plan: ForexDatasetPlan, symbol: str, period: date) -> None:
    """Refuse unsafe whole archives before even requesting their download page."""
    if plan.provider == "histdata":
        start, stop = histdata_window(period)
    else:
        start = datetime.combine(period, datetime.min.time(), UTC)
        stop = start + timedelta(days=1)
    if (
        symbol not in plan.instruments
        or start < plan.coverage_start
        or stop > plan.coverage_end + timedelta(minutes=1)
        or stop > HOLDOUT
        or (plan.provider == "histdata" and period.day != 1)
    ):
        raise ResearchRefused("forex_archive_outside_UTC_scope_or_holdout_boundary")


def decode_histdata(payload: bytes, symbol: str, period: date) -> pl.DataFrame:
    """Generic ASCII M1, fixed +5 hours, bid-only; never infer an ask/spread."""
    if symbol not in {"EURUSD", "XAUUSD"}:
        raise ResearchRefused("forex_symbol_not_approved")
    start, stop = histdata_window(period)
    rows: list[dict[str, Any]] = []
    for fields in csv.reader(io.StringIO(payload.decode("ascii")), delimiter=";"):
        if not fields:
            continue
        if len(fields) != 6:
            raise IntegrityError("HistData M1 field count invalid")
        instant = datetime.strptime(fields[0], "%Y%m%d %H%M%S").replace(tzinfo=UTC) + timedelta(
            hours=5
        )
        if not start <= instant < min(stop, HOLDOUT) or instant.second:
            raise ResearchRefused("histdata_row_outside_UTC_scope_or_holdout")
        values = [float(v) for v in fields[1:]]
        o, h, low, c, volume = values
        if (
            not all(math.isfinite(v) for v in values)
            or min(o, h, low, c) <= 0
            or volume < 0
            or low > min(o, c)
            or h < max(o, c)
            or low > h
        ):
            raise IntegrityError("HistData OHLC or numeric value invalid")
        rows.append(
            {
                "timestamp_ns": int(instant.timestamp()) * 10**9,
                "open": o,
                "high": h,
                "low": low,
                "close": c,
                "volume": volume,
                "symbol": symbol,
                "source": "histdata",
                "price_side": "bid",
                "volume_unreliable": True,
            }
        )
    if not rows or len(rows) > 50000:
        raise IntegrityError("HistData empty or oversized monthly row count")
    return pl.DataFrame(rows).with_columns(pl.col("timestamp_ns").cast(pl.Int64))


def _folder(root: Path, plan: ForexDatasetPlan, symbol: str, period: date) -> Path:
    return safe(root, f"data/bronze/{plan.provider}/{plan.dataset_id}/{symbol}/1m/{period.year}")


def download_period(
    root: Path,
    dataset_id: str,
    client: httpx.Client,
    *,
    symbol: str,
    period: date,
    code_version: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Admit before requests/reads; resume complete original artifacts without overwriting."""
    plan = load_forex_plan(root, dataset_id, clock())
    validate_period(plan, symbol, period)
    folder = _folder(root, plan, symbol, period)
    stem = f"{symbol}-{period.isoformat()}"
    manifest_path = folder / f"{stem}.manifest.json"
    with writer_lease(safe(root, f"work/research/locks/forex-{dataset_id}-{symbol}.lock")):
        if manifest_path.exists():
            old = read_metadata(root, manifest_path.relative_to(root).as_posix())
            if old["policy_digest"] != plan.digest or old["period"] != period.isoformat():
                raise ResearchRefused("forex_existing_manifest_identity_changed")
            for item in old.get("artifacts", []):
                if (
                    sha256_file(safe(root, item["path"], base=f"data/bronze/{plan.provider}"))
                    != item["sha256"]
                ):
                    raise IntegrityError("Committed FX Bronze changed")
            return {**old, "resumed": True}
        require_disk_space(root, 512 * 1024**2)
        common: dict[str, Any] = {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "policy_digest": plan.digest,
            "source": plan.provider,
            "price_side": plan.price_side,
            "source_timezone": plan.source_timezone,
            "symbol": symbol,
            "interval": "1m",
            "period": period.isoformat(),
            "terms_version": plan.terms_version,
            "scope": plan.scope,
            "derived_report_rules": plan.derived_report_rules,
            "retention": plan.retention.model_dump(mode="json"),
            "code_version": code_version,
            "evidence": sorted(
                {(p.evidence_artifact, p.evidence_sha256) for p in plan.rights.permissions.values()}
            ),
            "downloaded_at": clock().isoformat(),
        }
        blobs: dict[str, bytes] = {}
        urls: list[str] = []
        if plan.provider == "histdata":
            page = f"{plan.source}/download-free-forex-data/?/ascii/1-minute-bar-quotes/{symbol.lower()}/{period.year}/{period.month}"
            html = request_bytes(client, "GET", page, clock=clock, sleep=sleep)
            if html is None:
                result = {
                    **common,
                    "status": "missing",
                    "reason": "HTTP_404_download_page",
                    "source_urls": [page],
                    "artifacts": [],
                }
                atomic_write_json(manifest_path, result)
                return result
            form = DownloadForm()
            form.feed(html.decode("utf-8", errors="replace"))
            fields = form.fields
            if (
                not fields.get("tk")
                or fields.get("fxpair") != symbol
                or fields.get("datemonth") != f"{period:%Y%m}"
                or fields.get("date") != str(period.year)
                or fields.get("platform") != "ASCII"
                or fields.get("timeframe") != "M1"
            ):
                raise ProviderFailure(
                    {
                        "endpoint": page,
                        "utc": clock().isoformat(),
                        "http_status": 200,
                        "error_class": "DownloadFormInvalid",
                        "successful_requests": 1,
                        "failed_requests": 1,
                        "error_sample": "Expected bounded monthly ASCII M1 form unavailable",
                    }
                )
            endpoint = plan.source + "/get.php"
            payload = request_bytes(
                client, "POST", endpoint, data=fields, referer=page, clock=clock, sleep=sleep
            )
            if payload is None:
                result = {
                    **common,
                    "status": "missing",
                    "reason": "HTTP_404_archive",
                    "source_urls": [page, endpoint],
                    "artifacts": [],
                }
                atomic_write_json(manifest_path, result)
                return result
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                expected = f"DAT_ASCII_{symbol}_M1_{period:%Y%m}.csv"
                members = [m for m in archive.infolist() if m.filename.upper() == expected.upper()]
                if len(members) != 1 or members[0].file_size > MAX_ARCHIVE_BYTES:
                    raise IntegrityError("HistData archive member identity or size invalid")
                csv_bytes = archive.read(members[0])
            frame = decode_histdata(csv_bytes, symbol, period)
            blobs = {stem + ".zip": payload, stem + ".csv": csv_bytes}
            urls = [page, endpoint]
        else:
            sides: dict[str, pl.DataFrame] = {}
            for side in SIDES:
                url = candle_url(symbol, period, side)
                payload = request_bytes(client, "GET", url, clock=clock, sleep=sleep)
                urls.append(url)
                if payload is None:
                    continue
                decoded = decode_candles(payload, symbol, period, side)
                if decoded.is_empty():
                    continue
                blobs[stem + f"-{side}.bi5"] = payload
                sides[side] = decoded.select(
                    "timestamp_ns",
                    *[
                        (pl.col(f"{k}_raw").cast(pl.Float64) / pl.col("price_scale")).alias(
                            k if side == "BID" else f"ask_{k}"
                        )
                        for k in ("open", "high", "low", "close")
                    ],
                    "volume" if side == "BID" else pl.col("volume").alias("ask_volume"),
                )
            if not sides:
                result = {
                    **common,
                    "status": "missing",
                    "reason": "empty_or_missing_UTC_day",
                    "source_urls": urls,
                    "artifacts": [],
                }
                atomic_write_json(manifest_path, result)
                return result
            if set(sides) != {"BID", "ASK"}:
                raise IntegrityError("Both Dukascopy BID and ASK series required")
            frame = sides["BID"].join(sides["ASK"], on="timestamp_ns", how="inner", validate="1:1")
            if frame.height != sides["BID"].height or frame.height != sides["ASK"].height:
                raise IntegrityError("Dukascopy sides are not aligned")
            frame = frame.with_columns(
                pl.lit(symbol).alias("symbol"),
                pl.lit(plan.provider).alias("source"),
                pl.lit("bid_ask").alias("price_side"),
                pl.lit(True).alias("volume_unreliable"),
            )
            if frame.filter(
                pl.any_horizontal(
                    [pl.col(f"ask_{k}") < pl.col(k) for k in ("open", "high", "low", "close")]
                )
            ).height:
                raise IntegrityError("Dukascopy ask below bid")
            frame = frame.with_columns(
                *[
                    ((pl.col(k) + pl.col(f"ask_{k}")) / 2).alias(f"mid_{k}")
                    for k in ("open", "high", "low", "close")
                ],
                (pl.col("ask_close") - pl.col("close")).alias("spread_close"),
            )
        load_forex_plan(root, dataset_id, clock())
        first, last = frame["timestamp_ns"].min(), frame["timestamp_ns"].max()
        if (
            not isinstance(first, int)
            or not isinstance(last, int)
            or first < int(plan.coverage_start.timestamp()) * 10**9
            or last >= int(HOLDOUT.timestamp()) * 10**9
        ):
            raise ResearchRefused("forex_decoded_timestamp_outside_scope")
        output = io.BytesIO()
        frame.write_parquet(
            output, compression="zstd", compression_level=6, row_group_size=131072, statistics=True
        )
        blobs[stem + ".parquet"] = output.getvalue()
        artifacts = []
        for name, blob in blobs.items():
            path = folder / name
            declare_artifact(root, plan, path, ["raw", "original_source"], [])
            expected_hash = hashlib.sha256(blob).hexdigest()
            if path.exists():
                if sha256_file(path) != expected_hash:
                    raise IntegrityError("FX uncommitted artifact collision")
            else:
                atomic_write_bytes(path, blob)
            artifacts.append({"path": path.relative_to(root).as_posix(), "sha256": expected_hash})
        result = {
            **common,
            "status": "complete",
            "source_urls": urls,
            "artifacts": artifacts,
            "parquet": (folder / (stem + ".parquet")).relative_to(root).as_posix(),
            "rows": frame.height,
            "first_timestamp_ns": first,
            "last_timestamp_ns": last,
        }
        load_forex_plan(root, dataset_id, clock())
        atomic_write_json(manifest_path, result)
        return result
