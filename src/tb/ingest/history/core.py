"""Shared, offline-testable safety primitives for historical downloads."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal, Self
from uuid import uuid4

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_PATH_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class HistoryError(RuntimeError):
    """Base error for a fail-closed historical-data operation."""


class DownloadError(HistoryError):
    """Raised after a public download cannot be completed safely."""


class RemoteNotFound(DownloadError):
    """Raised for a missing remote object so adapters can classify expected gaps."""


class IntegrityError(HistoryError):
    """Raised when source or local integrity validation fails."""


class DiskSpaceError(HistoryError):
    """Raised before a download whose estimated footprint does not fit."""


class RetryPolicy(BaseModel):
    """Deterministic bounds for transient public HTTP failures."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    attempts: int = Field(default=5, ge=1, le=10)
    base_delay_seconds: float = Field(default=1.0, gt=0, le=60)
    max_delay_seconds: float = Field(default=30.0, gt=0, le=300)
    jitter_seconds: float = Field(default=0.5, ge=0, le=10)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    @model_validator(mode="after")
    def delay_bounds_are_ordered(self) -> Self:
        """Ensure exponential delay starts at or below its cap."""

        if self.base_delay_seconds > self.max_delay_seconds:
            raise ValueError("base_delay_seconds cannot exceed max_delay_seconds")
        return self


class BronzeManifest(BaseModel):
    """Versioned integrity record written only after a Bronze partition succeeds."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal[1] = 1
    source: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    symbol: str = Field(pattern=r"^[A-Z0-9]{2,20}$")
    timeframe: str = Field(pattern=r"^[A-Za-z0-9]{1,12}$")
    source_url: str = Field(min_length=8)
    requested_from: AwareDatetime
    requested_to: AwareDatetime
    actual_from: AwareDatetime | None
    actual_to: AwareDatetime | None
    rows: int = Field(ge=0)
    byte_count: int = Field(ge=0)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parquet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    downloaded_at: AwareDatetime
    code_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def ranges_are_ordered(self) -> Self:
        """Reject inverted requested or actual ranges."""

        if self.requested_to < self.requested_from:
            raise ValueError("requested_to cannot precede requested_from")
        if (self.actual_from is None) != (self.actual_to is None):
            raise ValueError("actual_from and actual_to must both be set or both be null")
        if self.actual_from is not None and self.actual_to is not None:
            if self.actual_to < self.actual_from:
                raise ValueError("actual_to cannot precede actual_from")
        return self


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase SHA-256 digest for a source payload."""

    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file in bounded chunks."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksum(text: str, expected_filename: str) -> str:
    """Parse a conventional SHA-256 sidecar and bind it to the expected filename."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise IntegrityError("Checksum sidecar must contain exactly one non-empty line")
    fields = lines[0].split()
    if len(fields) != 2:
        raise IntegrityError("Checksum sidecar must contain a digest and filename")
    digest, filename = fields
    filename = filename.removeprefix("*")
    if not _SHA256_PATTERN.fullmatch(digest.casefold()):
        raise IntegrityError("Checksum sidecar does not contain a valid SHA-256 digest")
    if filename != expected_filename:
        raise IntegrityError(
            f"Checksum filename {filename!r} does not match expected {expected_filename!r}"
        )
    return digest.casefold()


def verify_sha256(payload: bytes, expected: str) -> str:
    """Return the actual digest when it matches, otherwise fail loudly."""

    normalized = expected.casefold()
    if not _SHA256_PATTERN.fullmatch(normalized):
        raise IntegrityError("Expected checksum is not a valid SHA-256 digest")
    actual = sha256_bytes(payload)
    if actual != normalized:
        raise IntegrityError(f"SHA-256 mismatch: expected {normalized}, got {actual}")
    return actual


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write bytes through a sibling temporary file and atomically replace the target."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: BaseModel | dict[str, object]) -> None:
    """Serialize JSON deterministically, then write it atomically."""

    raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    payload = (json.dumps(raw, indent=2, sort_keys=True) + "\n").encode()
    atomic_write_bytes(path, payload)


def _retry_delay(
    response: httpx.Response | None,
    attempt_index: int,
    policy: RetryPolicy,
    random_value: float,
) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                parsed = float(retry_after)
            except ValueError:
                parsed = -1
            if 0 <= parsed <= policy.max_delay_seconds:
                return parsed
    exponential = min(
        float(policy.base_delay_seconds) * (2**attempt_index),
        float(policy.max_delay_seconds),
    )
    return float(exponential + random_value * float(policy.jitter_seconds))


def download_bytes(
    client: httpx.Client,
    url: str,
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
    random_fn: Callable[[], float] = random.random,
) -> bytes:
    """Download public bytes with bounded retries for timeouts, 429, and 5xx responses."""

    active_policy = RetryPolicy() if policy is None else policy
    last_problem = "unknown transient failure"
    for attempt_index in range(active_policy.attempts):
        response: httpx.Response | None = None
        try:
            response = client.get(url, timeout=active_policy.timeout_seconds)
        except httpx.TransportError as exc:
            last_problem = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code == 200:
                return response.content
            if response.status_code == 404:
                raise RemoteNotFound(f"Remote object not found: {url}")
            if response.status_code != 429 and response.status_code < 500:
                raise DownloadError(f"HTTP {response.status_code} for {url}")
            last_problem = f"HTTP {response.status_code}"

        if attempt_index + 1 < active_policy.attempts:
            sleep(_retry_delay(response, attempt_index, active_policy, random_fn()))
    raise DownloadError(
        f"Download failed after {active_policy.attempts} attempts for {url}: {last_problem}"
    )


def _safe_segment(value: str, label: str) -> str:
    if not _PATH_SEGMENT_PATTERN.fullmatch(value):
        raise ValueError(f"Unsafe {label} path segment: {value!r}")
    return value


def partition_directory(
    bronze_root: Path,
    source: str,
    symbol: str,
    timeframe: str,
    timestamp: datetime,
) -> Path:
    """Build a traversal-safe monthly Bronze partition directory."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Partition timestamp must be timezone-aware")
    safe_source = _safe_segment(source, "source")
    safe_symbol = _safe_segment(symbol, "symbol")
    safe_timeframe = _safe_segment(timeframe, "timeframe")
    return (
        bronze_root
        / safe_source
        / safe_symbol
        / safe_timeframe
        / f"year={timestamp.year:04d}"
        / f"month={timestamp.month:02d}"
    )


def estimate_required_bytes(
    partition_count: int,
    average_partition_bytes: int,
    *,
    safety_factor: float = 1.25,
) -> int:
    """Estimate required disk bytes using a conservative safety factor."""

    if partition_count < 0 or average_partition_bytes < 0:
        raise ValueError("Size estimate inputs cannot be negative")
    if safety_factor < 1 or safety_factor > 10:
        raise ValueError("safety_factor must be within [1, 10]")
    return int(partition_count * average_partition_bytes * safety_factor)


def require_disk_space(target: Path, required_bytes: int) -> int:
    """Return free bytes or fail before a write that cannot fit."""

    if required_bytes < 0:
        raise ValueError("required_bytes cannot be negative")
    probe = target.resolve()
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < required_bytes:
        raise DiskSpaceError(f"Need {required_bytes} bytes but only {free} bytes are free")
    return free


def manifest_is_complete(data_path: Path, manifest_path: Path) -> bool:
    """Return true only when data bytes and their validated manifest agree."""

    if not data_path.is_file() or not manifest_path.is_file():
        return False
    try:
        manifest = BronzeManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    return (
        manifest.byte_count == data_path.stat().st_size
        and manifest.parquet_sha256 == sha256_file(data_path)
    )
