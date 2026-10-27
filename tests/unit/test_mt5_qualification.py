"""Clock disagreement, native safety admission and normalized commit evidence regressions."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx
import pytest

from tb.dashboard.feed import read_feed_export
from tb.ingest.mt5.adapter import MT5Feed
from tb.ingest.mt5.collector import Collector
from tb.ingest.mt5.fake import FakeReader
from tb.ingest.mt5.mcp import ReadOnlyMCP
from tb.ingest.mt5.models import AdmissionCheck, FeedConfig, FeedUnavailable
from tb.ingest.mt5.qualification import AdmissionMonitor, clock_reference_passes, independent_utc
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.mt5.timestamps import parse_explicit_utc, parse_tick_epoch


@pytest.fixture
def setup(tmp_path):
    now = [datetime(2024, 6, 3, 10, 0, 5, tzinfo=UTC)]
    reader = FakeReader(tmp_path / "terminal with space/terminal64.exe", lambda: now[0])
    feed = MT5Feed(
        reader,
        FeedConfig(max_rows=4, max_polls=3),
        terminal_path=reader.path,
        login=str(reader.login),
        server=reader.server,
        clock=lambda: now[0],
    )
    feed.connect()
    return feed, now


def test_integer_epoch_millis_and_timezone_independence():
    at = parse_tick_epoch({"time": 1717408805, "time_msc": 1717408805123})
    assert at == datetime(2024, 6, 3, 10, 0, 5, 123000, UTC)
    assert at.astimezone(ZoneInfo("Asia/Karachi")).hour == 15
    assert parse_explicit_utc("2024-06-03T15:00:05.123+05:00") == at


@pytest.mark.parametrize(
    "raw",
    [
        {"time": True},
        {"time": "1717408805"},
        {"time": -1},
        {"time": 1717408805, "time_msc": 1717408806123},
        {"time": 1717408805, "time_msc": -1},
        {"time": 10**100},
    ],
)
def test_invalid_or_disagreeing_epochs(raw):
    with pytest.raises(FeedUnavailable):
        parse_tick_epoch(raw)


@pytest.mark.parametrize("text", ["2024-06-03T13:00:05", "bad", None])
def test_naive_server_text_never_assumed_utc(text):
    with pytest.raises(FeedUnavailable):
        parse_explicit_utc(text)


def test_three_hour_future_both_fields_never_corrected(setup):
    feed, now = setup
    future = now[0] + timedelta(hours=3)
    feed.client.quote_overrides.update(
        time=int(future.timestamp()), time_msc=int(future.timestamp()) * 1000
    )
    with pytest.raises(FeedUnavailable, match="future"):
        feed.quote("EURUSD")
    assert feed.latest_raw["time_msc"] == int(future.timestamp()) * 1000


def test_hidden_gold_requires_owner_no_selection_call(setup):
    feed, _ = setup
    feed.client.info_overrides.update(visible=False, select=False)
    with pytest.raises(FeedUnavailable, match="hidden"):
        feed.quote("XAUUSD")
    assert "symbol_select" not in feed.client.calls


def test_receipt_clock_step_refused(setup):
    feed, now = setup
    original = feed.client.read

    def step(name, *args, **kwargs):
        value = original(name, *args, **kwargs)
        if name == "symbol_info_tick":
            now[0] += timedelta(hours=3)
        return value

    with patch.object(feed.client, "read", side_effect=step):
        with pytest.raises(FeedUnavailable, match="receipt_clock_changed"):
            feed.quote("EURUSD")


def reference(now):
    return [{"accepted": True, "received_utc": now.isoformat(), "reference_utc": now.isoformat()}]


def test_missing_unsynced_stale_or_disagreeing_host_reference(setup):
    _, now = setup
    assert clock_reference_passes(reference(now[0]), now[0])
    assert not clock_reference_passes([], now[0])
    assert not clock_reference_passes(reference(now[0]), now[0] + timedelta(seconds=61))
    assert not clock_reference_passes(reference(now[0]), now[0] - timedelta(seconds=1))
    assert not clock_reference_passes(
        [*reference(now[0]), {"accepted": False, "reference_utc": "2024-01-01T00:00:00Z"}], now[0]
    )


def test_independent_reference_disagrees_with_broken_host_without_time_edit():
    now = datetime(2024, 6, 3, 13, 0, 5, tzinfo=UTC)

    def handler(request):
        if request.url.host == "www.cloudflare.com":
            return httpx.Response(200, text="ip=DO_NOT_PERSIST\nts=1717408805\n")
        return httpx.Response(302, headers={"Date": "Mon, 03 Jun 2024 10:00:05 GMT"})

    refs = independent_utc(
        transport=httpx.MockTransport(handler), clock=lambda: now, monotonic=lambda: 1
    )
    assert not clock_reference_passes(refs, now)
    assert all(r["reference_minus_receipt_seconds"] == -10800 for r in refs)
    assert "DO_NOT_PERSIST" not in json.dumps(refs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_trading_allowed", True),
        ("native_trading_allowed", None),
        ("dangerous_shell_tool_available", True),
        ("dangerous_shell_tool_available", None),
        ("security_passed", False),
        ("clock_passed", False),
        ("identity_fingerprint", "wrong"),
        ("reasons", ("unverified",)),
    ],
)
def test_admission_fails_closed(setup, field, value):
    feed, now = setup
    check = AdmissionCheck(
        checked_at=now[0],
        identity_fingerprint=feed.verify().fingerprint,
        security_passed=True,
        clock_passed=True,
        native_trading_allowed=False,
        dangerous_shell_tool_available=False,
    )
    assert check.allows(now[0], feed.verify().fingerprint)
    assert not check.model_copy(update={field: value}).allows(now[0], feed.verify().fingerprint)
    assert not check.allows(now[0] + timedelta(seconds=61), feed.verify().fingerprint)


def test_real_collector_cannot_run_without_security_gate(setup, tmp_path):
    feed, now = setup
    feed.client.synthetic = False
    store = FeedStore(tmp_path, feed.config, code_version="test")
    try:
        with pytest.raises(FeedUnavailable, match="admission"):
            Collector(
                feed, store, tmp_path / "reports/market_feed/genuine", clock=lambda: now[0]
            ).run(max_polls=1)
        assert "symbol_info_tick" not in feed.client.calls
        assert store.last_commit() is None
    finally:
        store.close()


def test_collector_replay_counts_unique_commits(setup, tmp_path):
    feed, now = setup
    store = FeedStore(tmp_path, feed.config, code_version="test")
    folder = tmp_path / "reports/market_feed/synthetic"
    try:
        result = Collector(feed, store, folder, clock=lambda: now[0], sleep=lambda _: None).run(
            max_polls=2
        )
        for count in result["counts"].values():
            assert count["received"] == count["valid"] == 2
            assert count["duplicates"] == count["quote_updates"] == 1
            assert count["qualified_forward"] == 0
        assert len(read_feed_export(folder).quotes) == 2
    finally:
        store.close()


def test_commit_receipt_contains_downgraded_rows_not_original_labels(setup, tmp_path):
    feed, now = setup
    store = FeedStore(tmp_path, feed.config, code_version="test")
    session, _ = store.session(
        feed.verify().fingerprint, now[0] - timedelta(minutes=1), synthetic=False
    )
    try:
        row, raw = feed.quote("EURUSD")
        row = row.model_copy(update={"evidence": "forward_observed"})
        store.commit(session, [row], [raw], received_at=now[0], warnings=[])
        older = row.model_copy(update={"source_at": now[0] - timedelta(seconds=5)})
        receipt = store.commit(session, [older], [raw], received_at=now[0], warnings=[])
        assert receipt["_accepted_rows"][0].evidence == "historical_backfill"
        assert receipt["evidence_counts"]["forward_observed"] == 0
        assert "_accepted_rows" not in store.last_commit()
    finally:
        store.close()


@pytest.mark.parametrize(
    "native_result", [[], None, {"result": []}, {"result": {"content": [None, 123]}}]
)
def test_invalid_native_response_is_sanitized(native_result):
    client = ReadOnlyMCP(
        "FAKE",
        login="123",
        server="Offline-Demo",
        symbols={"EURUSD": "EURUSD"},
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=native_result)),
    )
    try:
        with pytest.raises(FeedUnavailable):
            client.call("get_time_information", {})
    finally:
        client.close()


def test_monitor_permission_and_source_admission_with_mocked_clients(setup):
    feed, now = setup
    feed.client.info_overrides.update(visible=True, select=True)
    from types import SimpleNamespace

    native = SimpleNamespace(dangerous_shell_tool_available=False, discover=lambda: [])
    permission = [False]

    def call(name, arguments):
        if name == "terminal_get_info":
            return {"native_mcp_trading_permission": permission[0]}
        if name == "get_trading_account_info":
            return {"fingerprint": feed.verify().fingerprint}
        return {"utc_time": now[0].isoformat()}

    native.call = call
    monitor = AdmissionMonitor(feed, native)
    with patch("tb.ingest.mt5.qualification.independent_utc", return_value=reference(now[0])):
        assert monitor().allows(now[0], feed.verify().fingerprint)
        permission[0] = True
        assert not monitor().security_passed
        permission[0] = False
        feed.client.quote_overrides.update(
            time=int(now[0].timestamp()) + 10800, time_msc=(int(now[0].timestamp()) + 10800) * 1000
        )
        assert not monitor().clock_passed


@pytest.mark.parametrize(
    "shape",
    [
        {"account": None},
        {"account": []},
        {"account": {"type": "demo", "login": 123, "server": "changed"}},
    ],
)
def test_invalid_native_account_shapes_and_server_change(shape):
    client = ReadOnlyMCP(
        "FAKE",
        login="123",
        server="Offline-Demo",
        symbols={"EURUSD": "EURUSD"},
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"result": {"structuredContent": shape}})
        ),
    )
    try:
        with pytest.raises(FeedUnavailable):
            client.call("get_time_information", {})
    finally:
        client.close()


def test_revoked_admission_stops_before_next_market_poll(setup, tmp_path):
    feed, now = setup
    feed.client.synthetic = False
    calls = [0]

    def admission():
        calls[0] += 1
        return AdmissionCheck(
            checked_at=now[0],
            identity_fingerprint=feed.verify().fingerprint,
            security_passed=calls[0] <= 2,
            clock_passed=True,
            native_trading_allowed=calls[0] > 2,
            dangerous_shell_tool_available=False,
        )

    store = FeedStore(tmp_path, feed.config, code_version="test")
    folder = tmp_path / "reports/market_feed/genuine"
    try:
        collector = Collector(
            feed, store, folder, clock=lambda: now[0], sleep=lambda _: None, admission=admission
        )
        with pytest.raises(FeedUnavailable, match="admission"):
            collector.run(max_polls=2)
        assert feed.client.calls.count("symbol_info_tick") == 2
        snapshot = read_feed_export(folder)
        assert not snapshot.collector_running
        assert not snapshot.admission.security_passed
    finally:
        store.close()


def test_collection_gap_resets_coverage_and_records_source_gap(setup, tmp_path):
    feed, now = setup
    store = FeedStore(tmp_path, feed.config, code_version="test")

    def gap(_):
        now[0] += timedelta(seconds=20)

    try:
        collector = Collector(
            feed, store, tmp_path / "reports/market_feed/synthetic", clock=lambda: now[0], sleep=gap
        )
        result = collector.run(max_polls=2)
        assert "collection_gap_coverage_reset" in result["warnings"]
        assert all(at == now[0] for at in collector.coverage.values())
        assert "source_time_gap_detected" in store.last_commit()["warnings"]
        assert "complete_tick_coverage_unverified" in result["coverage_kind"]
    finally:
        store.close()


def test_duration_bound_is_enforced_before_connection(setup, tmp_path):
    feed, _ = setup
    store = FeedStore(tmp_path, feed.config, code_version="test")
    try:
        for duration in (0, 2701, -1):
            with pytest.raises(FeedUnavailable, match="duration"):
                Collector(feed, store, tmp_path / "export").run(duration_seconds=duration)
        assert store.last_commit() is None
    finally:
        store.close()
