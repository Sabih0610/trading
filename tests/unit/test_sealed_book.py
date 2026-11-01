"""Owned messages exercise capture/sealing without network or genuine forward data."""

import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from tb.dashboard.data_health import collector_health
from tb.ingest.sealed_book import SealedBookWriter, SequenceGap, sealed_write

START = datetime(2024, 12, 31, 23, 59, tzinfo=UTC)


def depth(first, final):
    return json.dumps(
        {
            "stream": "xautusdt@depth@100ms",
            "data": {
                "s": "XAUTUSDT",
                "U": first,
                "u": final,
                "b": [["100", "1"]],
                "a": [["101", "1"]],
            },
        }
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows read-deny acceptance")
def test_file_is_denied_to_readers_before_data_is_written(tmp_path):
    path = tmp_path / "owned.parquet"
    sealed_write(path, b"owned fixture bytes")
    assert path.stat().st_size == len(b"owned fixture bytes")
    with pytest.raises(PermissionError):
        path.read_bytes()


def test_sequence_gap_flushes_and_resyncs_without_price_statistics(tmp_path):
    writer = SealedBookWriter(
        tmp_path, started=START, code_version="owned-fixture", clock=lambda: START
    )
    writer.accept(
        json.dumps({"lastUpdateId": 10, "bids": [["100", "1"]], "asks": [["101", "1"]]}),
        snapshot=True,
    )
    writer.accept(depth(10, 12))
    with pytest.raises(SequenceGap):
        writer.accept(depth(15, 16))
    assert writer.gaps == 1
    writer.reset()
    writer.accept(json.dumps({"lastUpdateId": 20, "bids": [], "asks": []}), snapshot=True)
    writer.accept(depth(21, 22))
    writer.flush()
    health = collector_health(tmp_path)
    assert health["sequence_gap_count"] == 1 and health["reconnects"] == 1
    assert health["file_sizes"]
    assert not {"price", "bid", "ask", "spread", "depth", "volume"} & health.keys()
    assert len(list((tmp_path / "data/bronze/forward_sealed").rglob("*.parquet"))) == 2
    assert len(list((tmp_path / "data/bronze/forward_sealed").rglob("*.manifest.json"))) == 2


def test_book_ticker_update_ids_are_not_assumed_contiguous(tmp_path):
    writer = SealedBookWriter(tmp_path, started=START, code_version="owned", clock=lambda: START)
    for sequence in (10, 1000):
        writer.accept(
            json.dumps(
                {
                    "stream": "xautusdt@bookTicker",
                    "data": {"s": "XAUTUSDT", "u": sequence, "b": "100", "a": "101"},
                }
            )
        )
    assert writer.gaps == 0
    writer.flush()


def test_hour_boundary_flushes_separate_immutable_files(tmp_path):
    now = START
    writer = SealedBookWriter(tmp_path, started=START, code_version="owned", clock=lambda: now)
    writer.accept(json.dumps({"lastUpdateId": 10}), snapshot=True)
    now += timedelta(minutes=2)
    writer.accept(depth(11, 12))
    writer.flush()
    paths = list((tmp_path / "data/bronze/forward_sealed").rglob("*.parquet"))
    assert len(paths) == 2 and paths[0].parent != paths[1].parent


def test_dashboard_projects_only_health_allowlist(tmp_path):
    path = tmp_path / "reports/data_quality/xaut-collector-health.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "heartbeat": START.isoformat(),
                "price": 999,
                "spread": 3,
                "depth": [1, 2],
                "sequence_gap_count": 0,
            }
        )
    )
    assert collector_health(tmp_path) == {"heartbeat": START.isoformat(), "sequence_gap_count": 0}


def test_every_emitted_manifest_is_marked_without_reopening_archive(tmp_path, monkeypatch):
    import tb.ingest.sealed_book as module

    emitted = []
    original = module.sealed_write

    def observe_owned_write(path, payload):
        if path.suffix == ".json":
            emitted.append(json.loads(payload))
        original(path, payload)

    monkeypatch.setattr(module, "sealed_write", observe_owned_write)
    writer = SealedBookWriter(
        tmp_path, started=START, code_version="owned-fixture", clock=lambda: START
    )
    writer.accept(json.dumps({"lastUpdateId": 10}), snapshot=True)
    writer.flush()
    assert emitted and all(item["holdout"] == "forward_sealed" for item in emitted)
    assert all(item["collector_start"] == START.isoformat() for item in emitted)
    assert all(
        item["source"] == "Binance spot WebSocket" and "Binance API Terms" in item["terms"]
        for item in emitted
    )


def test_transport_disconnect_reconnects_with_a_new_live_snapshot(tmp_path, monkeypatch):
    import httpx

    import tb.ingest.sealed_book as module

    timer = [0.0]
    attempts = []

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def recv(self, **kwargs):
            timer[0] += 6
            return depth(11, 12)

    def connect(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("owned disconnect")
        return Socket()

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            return httpx.Response(200, json={"lastUpdateId": 10}, request=httpx.Request("GET", url))

    monkeypatch.setattr(module, "register_capture", lambda *args: None)
    monkeypatch.setattr(module, "connect", connect)
    monkeypatch.setattr(module.httpx, "Client", Client)
    monkeypatch.setattr(module.time, "monotonic", lambda: timer[0])
    monkeypatch.setattr(
        module.time, "sleep", lambda seconds: timer.__setitem__(0, timer[0] + seconds)
    )
    module.collect(tmp_path, seconds=10, code_version="owned-fixture")
    assert len(attempts) == 2
    assert collector_health(tmp_path)["reconnects"] == 1
    assert collector_health(tmp_path)["file_sizes"]
