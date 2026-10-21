"""Immutable raw payload and normalized snapshot storage for calendar/news metadata."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

import polars as pl

from tb.core.timeutil import utc_now
from tb.ingest.calendar.models import CalendarEvent
from tb.ingest.history.core import (
    BronzeManifest,
    atomic_write_bytes,
    atomic_write_json,
    manifest_is_complete,
    partition_directory,
    sha256_bytes,
    sha256_file,
)
from tb.ingest.news.models import NewsItem

_SOURCE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


class SnapshotStatus(StrEnum):
    """Normalized snapshot outcome."""

    WRITTEN = "written"
    SKIPPED = "skipped"


def _source_symbol(source: str) -> str:
    symbol = "".join(character for character in source.upper() if character.isalnum())
    if len(symbol) < 2 or len(symbol) > 20:
        raise ValueError(f"Source name cannot form a safe manifest symbol: {source!r}")
    return symbol


def store_raw_payload(
    bronze_root: Path,
    *,
    dataset: str,
    source: str,
    payload: bytes,
    fetched_at: datetime,
    extension: str,
) -> Path:
    """Store exact fetched bytes once under a content-addressed immutable raw path."""

    if dataset not in {"calendar", "news"}:
        raise ValueError(f"Unsupported content dataset: {dataset}")
    if not _SOURCE.fullmatch(source):
        raise ValueError(f"Unsafe content source: {source!r}")
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise ValueError("Raw payload fetch time must be timezone-aware")
    if not extension.isalnum() or len(extension) > 8:
        raise ValueError(f"Unsafe raw extension: {extension!r}")
    instant = fetched_at.astimezone(UTC)
    digest = sha256_bytes(payload)
    path = (
        bronze_root
        / "_raw"
        / dataset
        / source
        / f"year={instant.year:04d}"
        / f"month={instant.month:02d}"
        / f"{instant:%Y%m%dT%H%M%S}-{digest[:16]}.{extension}"
    )
    if path.is_file():
        if sha256_file(path) != digest:
            raise ValueError(f"Content-addressed raw file is corrupt: {path}")
        return path
    atomic_write_bytes(path, payload)
    return path


def _commit_snapshot(
    bronze_root: Path,
    *,
    dataset: str,
    source: str,
    timeframe: str,
    source_url: str,
    source_payload: bytes,
    records: list[dict[str, object]],
    time_column: str,
    id_column: str,
    code_version: str,
    resume: bool,
) -> SnapshotStatus:
    if not records:
        raise ValueError("Cannot commit an empty normalized snapshot")
    frame = pl.DataFrame(records, infer_schema_length=None).sort([time_column, id_column])
    if frame[id_column].is_duplicated().any():
        raise ValueError(f"Normalized {dataset} snapshot contains duplicate {id_column} values")
    first_value = frame[time_column].min()
    last_value = frame[time_column].max()
    if not isinstance(first_value, datetime) or not isinstance(last_value, datetime):
        raise ValueError(f"Normalized {dataset} snapshot has invalid time values")
    digest = sha256_bytes(source_payload)
    normalized_payload = json.dumps(records, sort_keys=True, default=str).encode()
    normalized_digest = sha256_bytes(normalized_payload)
    partition = partition_directory(
        bronze_root,
        dataset,
        _source_symbol(source),
        timeframe,
        first_value,
    )
    data_path = partition / f"{source}-{digest[:8]}-{normalized_digest[:8]}.parquet"
    manifest_path = partition / f"{data_path.stem}_manifest.json"
    if resume and manifest_is_complete(data_path, manifest_path):
        return SnapshotStatus.SKIPPED

    partition.mkdir(parents=True, exist_ok=True)
    temporary = data_path.with_name(f".{data_path.name}.{uuid4().hex}.tmp")
    try:
        frame.write_parquet(temporary, compression="zstd", statistics=True)
        os.replace(temporary, data_path)
    finally:
        temporary.unlink(missing_ok=True)
    downloaded_at = utc_now()
    manifest = BronzeManifest(
        source=dataset,
        symbol=_source_symbol(source),
        timeframe=timeframe,
        source_url=source_url,
        requested_from=first_value,
        requested_to=last_value,
        actual_from=first_value,
        actual_to=last_value,
        rows=frame.height,
        byte_count=data_path.stat().st_size,
        source_sha256=digest,
        parquet_sha256=sha256_file(data_path),
        downloaded_at=downloaded_at,
        code_version=code_version,
    )
    atomic_write_json(manifest_path, manifest)
    return SnapshotStatus.WRITTEN


def commit_calendar_snapshot(
    bronze_root: Path,
    *,
    source: str,
    source_url: str,
    source_payload: bytes,
    events: list[CalendarEvent],
    code_version: str,
    resume: bool,
) -> SnapshotStatus:
    """Commit one deduplicated normalized calendar snapshot with its manifest."""

    records = [event.model_dump(mode="python") for event in events]
    return _commit_snapshot(
        bronze_root,
        dataset="calendar",
        source=source,
        timeframe="event",
        source_url=source_url,
        source_payload=source_payload,
        records=records,
        time_column="scheduled_utc",
        id_column="event_id",
        code_version=code_version,
        resume=resume,
    )


def commit_news_snapshot(
    bronze_root: Path,
    *,
    source: str,
    source_url: str,
    source_payload: bytes,
    items: list[NewsItem],
    code_version: str,
    resume: bool,
) -> SnapshotStatus:
    """Commit one deduplicated normalized headline snapshot with its manifest."""

    records = [item.model_dump(mode="python") for item in items]
    return _commit_snapshot(
        bronze_root,
        dataset="news",
        source=source,
        timeframe="headline",
        source_url=source_url,
        source_payload=source_payload,
        records=records,
        time_column="published_utc",
        id_column="id",
        code_version=code_version,
        resume=resume,
    )
