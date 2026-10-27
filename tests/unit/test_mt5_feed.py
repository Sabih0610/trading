"""Native reader, provenance, health, bounded storage and restart safety regressions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tb.dashboard.feed import FeedExport, read_feed_export
from tb.ingest.mt5.adapter import MT5Feed, PythonReader, UnavailableFeed
from tb.ingest.mt5.collector import Collector, classify_forward
from tb.ingest.mt5.fake import FakeReader
from tb.ingest.mt5.models import (
    FeedConfig,
    FeedState,
    FeedUnavailable,
    IdentityRefused,
    Observation,
    StorageRefused,
    quote_health,
)
from tb.ingest.mt5.storage import FeedStore


@pytest.fixture
def clock():
    return [datetime(2024, 6, 3, 10, 0, 5, tzinfo=UTC)]


@pytest.fixture
def feed(tmp_path, clock):
    client = FakeReader(tmp_path / "terminal with space/terminal64.exe", lambda: clock[0])
    config = FeedConfig(max_rows=4, max_polls=3)
    result = MT5Feed(
        client,
        config,
        terminal_path=client.path,
        login=str(client.login),
        server=client.server,
        clock=lambda: clock[0],
    )
    result.connect()
    return result


def test_optional_package_and_explicit_unavailable():
    with patch("tb.ingest.mt5.adapter.importlib.import_module", side_effect=ImportError):
        with pytest.raises(FeedUnavailable, match="Optional MT5"):
            PythonReader()
    with pytest.raises(FeedUnavailable):
        list(UnavailableFeed().quotes("XAUUSD"))


def test_python_attachment_cannot_launch_or_switch_account(tmp_path):
    from types import SimpleNamespace

    from tb.ingest.mt5 import adapter
    from tb.ingest.mt5.adapter import PYTHON_READS

    calls = []
    module = SimpleNamespace(
        **{name: lambda *args, **kwargs: calls.append("native") for name in PYTHON_READS}
    )
    with (
        patch.object(adapter.psutil, "process_iter", return_value=[]),
        patch.object(adapter.importlib, "import_module", return_value=module),
    ):
        reader = PythonReader()
        with pytest.raises(FeedUnavailable):
            reader.read("initialize", str(tmp_path / "terminal64.exe"), login=123)
        with pytest.raises(FeedUnavailable):
            reader.read("initialize", str(tmp_path / "terminal64.exe"), timeout=5000)
        assert calls == []


@pytest.mark.parametrize("mode", [1, 2, None, "demo"])
def test_non_demo_identity_refused(feed, mode):
    feed.client.trade_mode = mode
    with pytest.raises(IdentityRefused):
        feed.verify()


@pytest.mark.parametrize(
    "field,value", [("login", 123), ("server", "Other-Demo"), ("connected", False)]
)
def test_switches_and_disconnect_refused(feed, field, value):
    setattr(feed.client, field, value)
    with pytest.raises(FeedUnavailable):
        feed.quote("EURUSD")


def test_terminal_path_pin(feed, tmp_path):
    feed.client.path = tmp_path / "different/terminal64.exe"
    with pytest.raises(IdentityRefused):
        feed.verify()


def test_exact_alias_and_metadata_validation(feed):
    feed.client.aliases = {"XAUUSD": "XAUUSDm", "EURUSD": "EURUSD.a"}
    feed.config = FeedConfig(symbols=feed.client.aliases)
    facts = feed.metadata("XAUUSD")
    assert facts.broker_symbol == "XAUUSDm" and facts.base_currency == "XAU"
    assert not facts.sizing_usable and facts.session_schedule == "unavailable"
    feed.client.info_overrides["currency_base"] = "USD"  # GOLD can be a stock, not gold.
    with pytest.raises(FeedUnavailable, match="currencies"):
        feed.metadata("XAUUSD")


def test_missing_metadata_never_invents_sizing(feed):
    feed.client.info_overrides.update(trade_tick_size=None, volume_step=None, trade_tick_value=None)
    facts = feed.metadata("EURUSD")
    assert facts.tick_size is None and facts.volume_step is None and facts.tick_value is None
    assert not facts.sizing_usable
    with pytest.raises(FeedUnavailable, match="Sizing contract unavailable"):
        feed.contract("EURUSD")


def test_ambiguous_catalog_refused(feed):
    original = feed.client.read

    def duplicate(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        return result + result if name == "symbols_get" else result

    with patch.object(feed.client, "read", side_effect=duplicate):
        with pytest.raises(FeedUnavailable, match="ambiguous"):
            feed.metadata("EURUSD")


@pytest.mark.parametrize(
    "overrides",
    [{"bid": 0}, {"bid": 3, "ask": 2}, {"ask": float("nan")}, {"time_msc": -999999999999999999}],
)
def test_malformed_quotes_refused(feed, overrides):
    feed.client.quote_overrides.update(overrides)
    with pytest.raises((ValueError, OverflowError, OSError)):
        feed.quote("EURUSD")


def test_real_millisecond_mapping_and_future_refusal(feed, clock):
    observation, _ = feed.quote("EURUSD")
    assert observation.bid < observation.ask
    assert observation.source_at == datetime.fromtimestamp(
        int(clock[0].timestamp() * 1000) / 1000, UTC
    )
    assert observation.received_at == clock[0]
    feed.client.quote_overrides["time_msc"] = int(
        (clock[0] + timedelta(seconds=5)).timestamp() * 1000
    )
    with pytest.raises(FeedUnavailable, match="future"):
        feed.quote("EURUSD")


@pytest.mark.parametrize("timeframe", ["M1", "M5", "M15", "H1", "H4"])
def test_completed_candles_bounded_no_current_bar(feed, clock, timeframe):
    from tb.ingest.mt5.models import TIMEFRAMES

    rows, raw = feed.candles("EURUSD", timeframe)
    assert len(raw) <= 4 and len(rows) == 3
    assert all(r.source_at + timedelta(seconds=TIMEFRAMES[timeframe]) <= clock[0] for r in rows)
    feed.client.missing_candles = True
    with pytest.raises(FeedUnavailable):
        feed.candles("EURUSD", timeframe)


def test_backfill_never_becomes_forward_by_download_time(feed, clock):
    row, _ = feed.quote("EURUSD")
    row = row.model_copy(update={"evidence": "historical_backfill"})
    started = clock[0] - timedelta(seconds=10)
    assert (
        classify_forward(row, started, coverage_start=None, maximum_lag=30).evidence
        == "forward_observed"
    )
    old = row.model_copy(update={"source_at": started - timedelta(days=1)})
    assert (
        classify_forward(old, started, coverage_start=None, maximum_lag=30).evidence
        == "historical_backfill"
    )
    ticks, _ = feed.ticks("EURUSD")
    tick = ticks[0].model_copy(update={"evidence": "historical_backfill"})
    assert (
        classify_forward(tick, started, coverage_start=started, maximum_lag=30).evidence
        == "historical_backfill"
    )


def test_candle_forward_requires_continuous_coverage(feed, clock):
    rows, _ = feed.candles("EURUSD", "M1")
    row = rows[-1].model_copy(update={"evidence": "historical_backfill"})
    assert (
        classify_forward(row, row.source_at, coverage_start=row.source_at, maximum_lag=15).evidence
        == "forward_observed"
    )
    assert (
        classify_forward(row, row.source_at, coverage_start=clock[0], maximum_lag=15).evidence
        == "historical_backfill"
    )
    assert (
        classify_forward(row, row.source_at, coverage_start=None, maximum_lag=15).evidence
        == "historical_backfill"
    )


def test_health_stale_delayed_closed_unknown_future_and_dst(clock):
    now = clock[0]
    config = FeedConfig()
    for age, expected in [
        (0, FeedState.CONNECTED),
        (45, FeedState.DELAYED),
        (121, FeedState.STALE),
        (-10, FeedState.UNKNOWN),
    ]:
        assert (
            quote_health(
                "EURUSD", now - timedelta(seconds=age), now, now, config, connected=True
            ).state
            == expected
        )
    assert (
        quote_health("EURUSD", now, now, now, config, connected=False).state
        == FeedState.DISCONNECTED
    )
    assert (
        quote_health("EURUSD", None, None, now, config, connected=True).state == FeedState.UNKNOWN
    )
    assert (
        quote_health("EURUSD", now, now, now, config, connected=True, market_closed=True).state
        == FeedState.MARKET_CLOSED
    )
    # A weekend by itself is not a broker-specific session calendar.
    weekend = now + timedelta(days=5)
    assert (
        quote_health("EURUSD", now, now, weekend, config, connected=True).state == FeedState.STALE
    )
    ny = datetime(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    row = Observation(
        symbol="EURUSD",
        broker_symbol="EURUSD",
        kind="quote",
        timeframe="tick",
        source_at=ny,
        received_at=ny,
        evidence="synthetic",
        bid=1,
        ask=2,
    )
    assert row.source_at == datetime(2024, 11, 3, 6, 30, tzinfo=UTC)


def test_store_dedup_reopen_out_of_order_and_integrity(feed, tmp_path, clock):
    root = tmp_path / "store with space"
    store = FeedStore(root, feed.config, code_version="test")
    session, started = store.session(feed.verify().fingerprint, clock[0], synthetic=True)
    row, raw = feed.quote("EURUSD")
    assert store.commit(session, [row], [raw], received_at=clock[0], warnings=[])["rows"] == 1
    store.close()
    store = FeedStore(root, feed.config, code_version="test")
    assert store.session(feed.verify().fingerprint, clock[0], synthetic=True) == (session, started)
    assert store.last_commit()["rows"] == 1
    assert store.commit(session, [row], [raw], received_at=clock[0], warnings=[])["duplicates"] == 1
    older = row.model_copy(update={"source_at": clock[0] - timedelta(seconds=1)})
    commit = store.commit(session, [older], [raw], received_at=clock[0], warnings=[])
    assert "out_of_order_source_observation" in commit["warnings"]
    file = root / next(k for k in commit["files"] if k.endswith("source.json"))
    file.write_text("corrupt")
    with pytest.raises(StorageRefused, match="integrity"):
        store.last_commit()
    store.close()


def test_store_atomic_failure_orphans_ignored_and_retry(feed, tmp_path, clock):
    store = FeedStore(tmp_path, feed.config, code_version="test")
    session, _ = store.session(feed.verify().fingerprint, clock[0], synthetic=True)
    row, raw = feed.quote("EURUSD")
    from tb.ingest.mt5 import storage

    original = storage.atomic_write_json

    def fail_commit(path, value):
        if path.name == "commit.json":
            raise OSError("simulated interruption")
        original(path, value)

    with patch.object(storage, "atomic_write_json", side_effect=fail_commit):
        with pytest.raises(OSError):
            store.commit(session, [row], [raw], received_at=clock[0], warnings=[])
    assert store.last_commit() is None
    assert store.db.execute("SELECT COUNT(*) FROM seen").fetchone()[0] == 0
    assert store.commit(session, [row], [raw], received_at=clock[0], warnings=[])["rows"] == 1
    store.close()


def test_batch_quota_and_counterfeit_forward_refused(feed, tmp_path, clock):
    store = FeedStore(tmp_path, FeedConfig(max_rows=1, max_storage_mb=1), code_version="test")
    session, _ = store.session(feed.verify().fingerprint, clock[0], synthetic=True)
    row, raw = feed.quote("EURUSD")
    with pytest.raises(StorageRefused):
        store.commit(session, [row, row], [raw], received_at=clock[0], warnings=[])
    with pytest.raises(StorageRefused):
        store.commit(
            session,
            [row.model_copy(update={"evidence": "forward_observed"})],
            [raw],
            received_at=clock[0],
            warnings=[],
        )
    (tmp_path / "data/mt5_feed/full.bin").write_bytes(b"0" * 1024 * 1024)
    with pytest.raises(StorageRefused, match="quota"):
        store.commit(session, [row], [raw], received_at=clock[0], warnings=[])
    store.close()


def test_collector_export_isolated_read_only_and_stopped(feed, tmp_path, clock):
    def sleep(seconds):
        clock[0] += timedelta(seconds=seconds)

    store = FeedStore(tmp_path, feed.config, code_version="test")
    folder = tmp_path / "reports/market_feed/synthetic"
    collector = Collector(feed, store, folder, clock=lambda: clock[0], sleep=sleep)
    result = collector.run(max_polls=2, tick_history=True)
    assert result["source"] == "synthetic"
    export = read_feed_export(folder)
    assert len(export.quotes) == 2 and not export.collector_running
    assert all(h.state == FeedState.DISCONNECTED for h in export.health)
    assert all(r.evidence == "synthetic" for r in export.quotes)
    # M1 canonical Silver keeps receipt/evidence fields and the original session tags.
    files = list((tmp_path / "data/silver").rglob("*.parquet"))
    assert any("session_london" in pl.read_parquet(p).columns for p in files)
    assert set(feed.client.calls) <= {
        "initialize",
        "shutdown",
        "terminal_info",
        "account_info",
        "symbols_get",
        "symbol_info",
        "symbol_info_tick",
        "copy_rates_from_pos",
        "copy_ticks_from",
    }
    with pytest.raises(ValueError):
        FeedExport.model_validate({**export.model_dump(), "source": "mt5_demo"})
    store.close()


def test_reconnection_backoff_and_live_refusal_no_retry(feed, tmp_path, clock):
    store = FeedStore(tmp_path, feed.config, code_version="test")
    sleeps = []
    collector = Collector(
        feed, store, tmp_path / "report", clock=lambda: clock[0], sleep=sleeps.append
    )
    with patch.object(
        feed,
        "connect",
        side_effect=[FeedUnavailable("offline"), FeedUnavailable("offline"), feed.verify()],
    ):
        collector._connect()
    assert sleeps == [1, 2]
    with patch.object(feed, "connect", side_effect=IdentityRefused("identity")) as connect:
        with pytest.raises(IdentityRefused):
            collector._connect()
        assert connect.call_count == 1
    store.close()


def test_future_source_is_quarantined_and_not_exported_as_forward(feed, tmp_path, clock):
    store = FeedStore(tmp_path, feed.config, code_version="test")
    feed.client.quote_overrides["time_msc"] = int(
        (clock[0] + timedelta(hours=3)).timestamp() * 1000
    )
    folder = tmp_path / "reports/market_feed/synthetic"
    result = Collector(feed, store, folder, clock=lambda: clock[0], sleep=lambda seconds: None).run(
        max_polls=1
    )
    assert result["quotes"] == []
    assert all(h["state"] == "UNKNOWN" for h in result["health"])
    assert "EURUSD_future_timestamp_refused" in result["warnings"]
    assert store.last_commit()["raw_rows"] == 1 and store.last_commit()["rows"] == 0
    assert list((tmp_path / "data/bronze").rglob("source.json"))
    store.close()


def test_snapshot_pointer_never_overwrites_payload_on_clock_repeat(feed, tmp_path, clock):
    import json

    from tb.ingest.history.core import sha256_file

    store = FeedStore(tmp_path, feed.config, code_version="test")
    folder = tmp_path / "reports/market_feed/synthetic"
    collector = Collector(feed, store, folder, clock=lambda: clock[0], sleep=lambda seconds: None)
    collector.run(max_polls=1)
    first = json.loads((folder / "current.json").read_text())
    collector.run(max_polls=1)
    second = json.loads((folder / "current.json").read_text())
    assert first["file"] != second["file"]
    assert sha256_file(folder / first["file"]) == first["sha256"]
    store.close()
