"""Unit tests for atomic, resumable historical-ingestion primitives."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from tb.ingest.history.core import (
    BronzeManifest,
    DiskSpaceError,
    DownloadError,
    IntegrityError,
    RemoteNotFound,
    RetryPolicy,
    atomic_write_bytes,
    atomic_write_json,
    download_bytes,
    estimate_required_bytes,
    manifest_is_complete,
    parse_checksum,
    partition_directory,
    require_disk_space,
    sha256_bytes,
    verify_sha256,
)


def _manifest(data: bytes) -> BronzeManifest:
    instant = datetime(2026, 1, 2, tzinfo=UTC)
    digest = sha256_bytes(data)
    return BronzeManifest(
        source="binance_spot",
        symbol="BTCUSDT",
        timeframe="1m",
        source_url="https://data.example/BTCUSDT.zip",
        requested_from=instant,
        requested_to=instant,
        actual_from=instant,
        actual_to=instant,
        rows=1,
        byte_count=len(data),
        source_sha256=digest,
        parquet_sha256=digest,
        downloaded_at=instant,
        code_version="test",
    )


def test_atomic_write_handles_paths_with_spaces(tmp_path: Path) -> None:
    target = tmp_path / "path with spaces" / "partition.parquet"

    atomic_write_bytes(target, b"complete")

    assert target.read_bytes() == b"complete"
    assert list(target.parent.glob("*.tmp")) == []


def test_failed_replace_preserves_old_target_and_removes_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "partition.parquet"
    target.write_bytes(b"old")

    def fail_replace(source: Path, destination: Path) -> None:
        raise PermissionError(f"locked: {source.name} -> {destination.name}")

    monkeypatch.setattr("tb.ingest.history.core.os.replace", fail_replace)

    with pytest.raises(PermissionError, match="locked"):
        atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"old"
    assert [path for path in tmp_path.iterdir() if path != target] == []


def test_checksum_parser_accepts_crlf_and_rejects_wrong_file() -> None:
    payload = b"archive"
    digest = sha256_bytes(payload)

    assert parse_checksum(f"{digest}  file.zip\r\n", "file.zip") == digest
    assert verify_sha256(payload, digest) == digest
    with pytest.raises(IntegrityError, match="does not match expected"):
        parse_checksum(f"{digest}  other.zip\n", "file.zip")
    with pytest.raises(IntegrityError, match="mismatch"):
        verify_sha256(payload + b"corrupt", digest)


def test_429_honors_retry_after_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, request=request)
        return httpx.Response(200, content=b"ok", request=request)

    delays: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = download_bytes(client, "https://data.example/file", sleep=delays.append)

    assert result == b"ok"
    assert delays == [2.0]


def test_network_drop_retries_then_reports_attempt_count() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("drop", request=request)

    policy = RetryPolicy(attempts=3, base_delay_seconds=1, jitter_seconds=0)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DownloadError, match="after 3 attempts"):
            download_bytes(client, "https://data.example/file", policy=policy, sleep=lambda _: None)
    assert calls == 3


def test_permanent_and_missing_responses_do_not_retry() -> None:
    for status, error in ((404, RemoteNotFound), (403, DownloadError)):
        calls = 0

        def handler(request: httpx.Request, response_status: int = status) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(response_status, request=request)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(error):
                download_bytes(client, "https://data.example/file", sleep=lambda _: None)
        assert calls == 1


def test_partition_path_is_hive_style_and_traversal_safe(tmp_path: Path) -> None:
    instant = datetime(2026, 7, 1, tzinfo=UTC)

    result = partition_directory(tmp_path, "binance_spot", "BTCUSDT", "1m", instant)

    assert result == tmp_path / "binance_spot" / "BTCUSDT" / "1m" / "year=2026" / "month=07"
    with pytest.raises(ValueError, match="Unsafe source"):
        partition_directory(tmp_path, "../escape", "BTCUSDT", "1m", instant)
    with pytest.raises(ValueError, match="timezone-aware"):
        partition_directory(tmp_path, "source", "BTCUSDT", "1m", datetime(2026, 7, 1))


def test_disk_space_fails_before_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    usage = shutil_disk_usage(total=100, used=90, free=10)
    monkeypatch.setattr("tb.ingest.history.core.shutil.disk_usage", lambda _: usage)

    with pytest.raises(DiskSpaceError, match="Need 11 bytes"):
        require_disk_space(tmp_path / "not-created", 11)
    assert require_disk_space(tmp_path, 10) == 10


def test_manifest_detects_complete_duplicate_run_and_corruption(tmp_path: Path) -> None:
    data_path = tmp_path / "part.parquet"
    manifest_path = tmp_path / "_manifest.json"
    data = b"parquet fixture"
    atomic_write_bytes(data_path, data)
    atomic_write_json(manifest_path, _manifest(data))

    assert manifest_is_complete(data_path, manifest_path)
    data_path.write_bytes(data + b"changed")
    assert not manifest_is_complete(data_path, manifest_path)


def test_size_estimate_is_conservative_and_rejects_invalid_values() -> None:
    assert estimate_required_bytes(10, 100) == 1250
    assert estimate_required_bytes(0, 100) == 0
    with pytest.raises(ValueError, match="cannot be negative"):
        estimate_required_bytes(-1, 100)


class shutil_disk_usage:
    """Small named-field stand-in for shutil.disk_usage output."""

    def __init__(self, *, total: int, used: int, free: int) -> None:
        self.total = total
        self.used = used
        self.free = free
