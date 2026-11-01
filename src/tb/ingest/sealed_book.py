"""Capture-only XAUT public book archive. No read or unseal implementation exists here."""

from __future__ import annotations

import argparse
import atexit
import ctypes
import hashlib
import io
import json
import math
import os
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import polars as pl
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from tb.core.config import repo_root
from tb.core.leases import writer_lease
from tb.core.logging import configure_cli_logging
from tb.ingest.history.core import atomic_write_json, require_disk_space
from tb.research.registry import immutable_json

STREAM_URL = (
    "wss://data-stream.binance.vision/stream?streams=xautusdt@depth@100ms/xautusdt@bookTicker"
)
SNAPSHOT_URL = "https://data-api.binance.vision/api/v3/depth?symbol=XAUTUSDT&limit=1000"
TERMS = "Binance API Terms (accessed 2026-11-01; provider version string unverified)"
TERMS_URL = "https://www.binance.com/en/terms"
HOLDOUT = "forward_sealed"
MAX_BUFFER_ROWS = 200_000


class SequenceGap(ValueError):
    """The public depth stream requires a fresh connection and current snapshot."""


def _integer(value: Any) -> int:
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError("invalid public update identity")
    return value


@lru_cache(maxsize=1)
def _native_acl() -> tuple[Any, Any]:
    """Build one protected DACL; reuse native APIs rather than spawning per-file shells."""
    from tb.ingest.broker.onboarding.private import owner_sid

    sid = owner_sid()
    sddl = f"D:P(D;;0x1;;;{sid})(A;;FA;;;SY)(A;;FA;;;{sid})"
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    descriptor = pointer()
    convert = api.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(pointer), pointer]
    convert.restype = ctypes.c_int
    if not convert(sddl, 1, ctypes.byref(descriptor), None):
        raise RuntimeError("sealed_archive_descriptor_failed")
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    atexit.register(kernel.LocalFree, descriptor)
    present, defaulted, dacl = ctypes.c_int(), ctypes.c_int(), pointer()
    get_dacl = api.GetSecurityDescriptorDacl
    get_dacl.argtypes = [
        pointer,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(pointer),
        ctypes.POINTER(ctypes.c_int),
    ]
    get_dacl.restype = ctypes.c_int
    if (
        not get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted))
        or not present.value
        or not dacl.value
    ):
        raise RuntimeError("sealed_archive_dacl_failed")
    install = api.SetNamedSecurityInfoW
    install.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.c_uint32,
        pointer,
        pointer,
        pointer,
        pointer,
    ]
    install.restype = ctypes.c_uint32
    return install, dacl


def deny_data_reads(path: Path) -> None:
    """Protect an empty new file before writing, without reopening any archived bytes."""
    if os.name != "nt":
        path.chmod(0o200)
        return
    install, dacl = _native_acl()
    # SE_FILE_OBJECT; protected DACL with ReadData deny (0x1), no inherited grants.
    if install(str(path), 1, 0x80000004, None, None, dacl, None) != 0:
        raise RuntimeError("sealed_archive_acl_failed")


def sealed_write(path: Path, payload: bytes) -> None:
    """Write new bytes exclusively under a preinstalled read deny, then fsync; no reread."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink() or path.parent.is_junction():
        raise ValueError("sealed archive link refused")
    with path.open("xb") as handle:
        deny_data_reads(path)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def register_capture(root: Path, started: datetime) -> None:
    """Record explicit owner capture-only authority, without manufacturing dataset admission."""
    decision = root / "prompts/P11d-audit-fixes-and-real-data.md"
    text = decision.read_text(encoding="utf-8")
    if "## Sealed forward collection (owner decision, 2026-11-01)" not in text:
        raise ValueError("sealed capture owner decision missing")
    immutable_json(
        root / "work/research/registry/sealed-collection/xaut-forward.json",
        {
            "kind": "owner_authorized_sealed_capture",
            "holdout": HOLDOUT,
            "source": "Binance spot WebSocket",
            "source_url": STREAM_URL,
            "terms": TERMS,
            "terms_url": TERMS_URL,
            "owner_decision": "P11d sealed forward collection, 2026-11-01",
            "decision_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "admitted_for_research": False,
            "reviewer_approval": None,
            "retention": "sealed until P14; no automatic unseal, renewal, deletion or analytical use",
            "read_authorization": "one P14 final forward test, separate logged owner authorization required",
        },
    )


class SealedBookWriter:
    """Bounded raw-message buffers; only explicit allowed operational health leaves the writer."""

    def __init__(
        self,
        root: Path,
        *,
        started: datetime,
        code_version: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        flush_interval: float = 900,
    ) -> None:
        if not math.isfinite(flush_interval) or flush_interval <= 0:
            raise ValueError("sealed capture flush interval must be positive and finite")
        self.root, self.started, self.code_version, self.clock = (
            root.resolve(),
            started,
            code_version,
            clock,
        )
        self.rows: list[dict[str, Any]] = []
        self.flush_interval = flush_interval
        self.buffer_started: datetime | None = None
        self.hour: datetime | None = None
        self.last_depth: int | None = None
        self.gaps = 0
        self.reconnects = 0
        self.file_sizes: deque[int] = deque(maxlen=48)
        self.files_by_utc_hour: dict[str, int] = {}
        self.connected = False
        self.last_error = "none"
        self.last_heartbeat = float("-inf")

    def heartbeat(self, *, force: bool = False) -> None:
        """Metadata only: never prices, spreads, depth, volumes, or inferred market statistics."""
        monotonic = time.monotonic()
        if not force and monotonic - self.last_heartbeat < 5:
            return
        now = self.clock()
        atomic_write_json(
            self.root / "reports/data_quality/xaut-collector-health.json",
            {
                "schema_version": 1,
                "collector": "sealed_xaut_book",
                "symbol": "XAUTUSDT",
                "sealed": True,
                "collector_start": self.started.isoformat(),
                "heartbeat": now.isoformat(),
                "uptime_seconds": max(0.0, (now - self.started).total_seconds()),
                "sequence_gap_count": self.gaps,
                "reconnects": self.reconnects,
                "file_sizes": list(self.file_sizes),
                "files_by_utc_hour": dict(self.files_by_utc_hour),
                "flush_interval_seconds": self.flush_interval,
                "connected": self.connected,
                "last_error_category": self.last_error,
            },
        )
        self.last_heartbeat = monotonic

    def reset(self) -> None:
        self.last_depth = None
        self.connected = False
        self.reconnects += 1
        self.heartbeat(force=True)

    def flush_if_due(self) -> None:
        """Flush an elapsed buffer or UTC hour boundary, including on receive timeouts."""
        if self.buffer_started is None:
            return
        now = self.clock()
        if (
            now.replace(minute=0, second=0, microsecond=0) != self.hour
            or (now - self.buffer_started).total_seconds() >= self.flush_interval
        ):
            self.flush()

    def accept(self, payload: str, *, snapshot: bool = False) -> None:
        """Inspect transport identity/sequence only; seal the exact original JSON payload."""
        now = self.clock()
        if now < self.started or now.utcoffset() != UTC.utcoffset(now) or len(payload) > 1_048_576:
            raise ValueError("sealed capture clock or message bound refused")
        value = json.loads(payload)
        data = value if snapshot else value.get("data", {})
        stream = "snapshot" if snapshot else value.get("stream")
        if not snapshot and (
            data.get("s") != "XAUTUSDT"
            or stream not in {"xautusdt@depth@100ms", "xautusdt@bookTicker"}
        ):
            raise ValueError("sealed capture stream identity refused")
        gap = False
        if snapshot:
            self.last_depth = _integer(data.get("lastUpdateId"))
        elif stream == "xautusdt@depth@100ms":
            first, final = _integer(data.get("U")), _integer(data.get("u"))
            if first > final:
                raise ValueError("invalid depth update range")
            if self.last_depth is None:
                gap = True
            elif final > self.last_depth:
                gap = first > self.last_depth + 1
                if not gap:
                    self.last_depth = final
        else:
            _integer(data.get("u"))  # bookTicker IDs need not be contiguous.
        hour = now.replace(minute=0, second=0, microsecond=0)
        self.flush_if_due()
        self.hour = hour
        if not self.rows:
            self.buffer_started = now
        self.rows.append(
            {
                "received_at": now,
                "stream": stream,
                "raw_json": payload,
                "holdout": HOLDOUT,
                "sequence_gap": gap,
            }
        )
        if gap:
            self.gaps += 1
            self.flush()
            self.heartbeat()
            raise SequenceGap("public_depth_sequence_gap")
        if len(self.rows) >= MAX_BUFFER_ROWS:
            self.flush()
        self.heartbeat()

    def flush(self) -> None:
        """Seal raw Parquet and its marked manifest immediately; never reopen either file."""
        if not self.rows or self.hour is None:
            return
        require_disk_space(self.root, 128 * 1024**2)
        folder = (
            self.root / "data/bronze/forward_sealed/XAUTUSDT" / self.hour.strftime("%Y/%m/%d/%H")
        )
        # Resolve/verify the final absolute namespace before creating any artifact.
        if not folder.resolve().is_relative_to(
            (self.root / "data/bronze/forward_sealed").resolve()
        ):
            raise ValueError("sealed capture namespace escape")
        name = uuid4().hex
        path = folder / (name + ".parquet")
        buffer = io.BytesIO()
        pl.DataFrame(self.rows).with_columns(
            pl.col("received_at").cast(pl.Datetime("ns", "UTC"))
        ).write_parquet(
            buffer,
            compression="zstd",
            compression_level=6,
            statistics=False,
            row_group_size=131_072,
            metadata={"holdout": HOLDOUT},
        )
        payload = buffer.getvalue()
        checksum = hashlib.sha256(payload).hexdigest()  # In-memory writer bytes; no archive read.
        sealed_write(path, payload)
        manifest = {
            "schema_version": 1,
            "holdout": HOLDOUT,
            "source": "Binance spot WebSocket",
            "source_url": STREAM_URL,
            "snapshot_url": SNAPSHOT_URL,
            "terms": TERMS,
            "terms_url": TERMS_URL,
            "collector_start": self.started.isoformat(),
            "code_version": self.code_version,
            "hour_utc": self.hour.isoformat(),
            "rows": len(self.rows),
            "byte_count": len(payload),
            "sha256": checksum,
            "sealed_until": "P14 single final forward evaluation; logged owner authorization required",
        }
        sealed_write(
            path.with_suffix(".manifest.json"),
            (json.dumps(manifest, sort_keys=True) + "\n").encode(),
        )
        self.file_sizes.append(len(payload))
        hour_key = self.hour.isoformat()
        self.files_by_utc_hour[hour_key] = self.files_by_utc_hour.get(hour_key, 0) + 1
        while len(self.files_by_utc_hour) > 48:
            del self.files_by_utc_hour[next(iter(self.files_by_utc_hour))]
        self.rows.clear()
        self.buffer_started = None
        self.heartbeat(force=True)


def collect(
    root: Path, *, seconds: int = 3600, code_version: str, flush_interval: float = 900
) -> None:
    """Forward-only sockets with current snapshots, bounded buffering and reconnect/resync."""
    started = datetime.now(UTC)
    register_capture(root, started)
    writer = SealedBookWriter(
        root, started=started, code_version=code_version, flush_interval=flush_interval
    )
    deadline = time.monotonic() + seconds
    with writer_lease(root / "work/sealed-xaut/collector.lock"):
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=20) as client:
            try:
                while time.monotonic() < deadline:
                    try:
                        writer.heartbeat()
                        with connect(
                            STREAM_URL,
                            proxy=None,
                            open_timeout=20,
                            close_timeout=5,
                            max_size=1_048_576,
                            max_queue=64,
                        ) as socket:
                            # Snapshot is current live state, not a historical/back-fill request.
                            response = client.get(SNAPSHOT_URL)
                            response.raise_for_status()
                            writer.accept(response.text, snapshot=True)
                            writer.connected = True
                            while time.monotonic() < deadline:
                                try:
                                    message = socket.recv(timeout=10)
                                except TimeoutError:
                                    writer.flush_if_due()
                                    writer.heartbeat()
                                    continue
                                writer.accept(
                                    message.decode() if isinstance(message, bytes) else message
                                )
                    except (ConnectionClosed, OSError, ValueError, httpx.HTTPError, TimeoutError):
                        writer.last_error = "transport_or_sequence_refused"
                        writer.flush_if_due()
                        writer.reset()
                        time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))
            finally:
                writer.flush()
                writer.connected = False
                writer.heartbeat(force=True)


def main() -> None:
    """Owner-authorized capture only. No archive read, preview, evaluation or unseal command."""
    configure_cli_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root())
    parser.add_argument("--seconds", type=int, default=86400)
    parser.add_argument("--flush-interval", type=float, default=900)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if not args.capture or not 1 <= args.seconds <= 86400:
        raise SystemExit("Pass --capture for the owner-authorized sealed forward writer")
    if (args.root / ".env").exists():
        raise SystemExit("Use the credential-free task checkout for sealed collection")
    from tb.ingest.history.cli import _code_version

    collect(
        args.root.resolve(),
        seconds=args.seconds,
        code_version=_code_version(),
        flush_interval=args.flush_interval,
    )


if __name__ == "__main__":
    main()
