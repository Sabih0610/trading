"""Practice adapter contract tests: all responses fictional; no accounts or service calls."""

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from tb.dashboard.feed import read_feed_export
from tb.ingest.mt5.collector import Collector
from tb.ingest.mt5.models import FeedUnavailable, StorageRefused
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.oanda import OandaPracticeFeed, OandaSettings, PracticeAccess


@pytest.fixture
def practice(clock_profile_factory):
    now = [datetime(2024, 6, 3, 10, 0, 5, tzinfo=UTC)]
    calls = []
    state = {
        "wrong_instrument": False,
        "status": "tradeable",
        "offset": 0,
        "bad_candle": False,
        "http_status": 200,
    }

    def handler(request):
        calls.append(request)
        assert request.method == "GET" and request.url.host == "api-fxpractice.oanda.com"
        if request.url.path.endswith("summary"):
            value = {
                "account": {
                    "id": "123-456",
                    "currency": "USD",
                    "balance": "PRIVATE",
                    "name": "PRIVATE",
                }
            }
        elif request.url.path.endswith("instruments"):
            value = {
                "instruments": [
                    {
                        "name": request.url.params["instruments"],
                        "minimumTradeSize": "1",
                        "maximumOrderUnits": "100000",
                        "displayPrecision": 5,
                    }
                ]
            }
        elif request.url.path.endswith("pricing"):
            value = {
                "prices": [
                    {
                        "instrument": "GBP_USD"
                        if state["wrong_instrument"]
                        else request.url.params["instruments"],
                        "status": state["status"],
                        "time": (now[0] + timedelta(seconds=state["offset"]))
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "bids": [{"price": "1.10000"}],
                        "asks": [{"price": "1.10002"}],
                    }
                ]
            }
        else:
            alias = request.url.path.split("/")[-2]
            value = {
                "instrument": alias,
                "granularity": request.url.params["granularity"],
                "candles": [
                    {
                        "complete": not state["bad_candle"],
                        "time": (now[0] - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                        "bid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.11"},
                        "volume": 20,
                    }
                ],
            }
        return httpx.Response(state["http_status"], json=value)

    profile = clock_profile_factory(
        provider="oanda_practice",
        broker="OANDA Practice",
        server="api-fxpractice.oanda.com",
        environment="practice",
        semantics="rfc3339_utc",
    )
    feed = OandaPracticeFeed(
        OandaSettings(token=SecretStr("FAKE"), account_id=SecretStr("123-456")),
        profile=profile,
        transport=httpx.MockTransport(handler),
        fixture=True,
        clock=lambda: now[0],
    )
    yield feed, now, calls, state
    feed.close()


def test_no_credentials_or_region_permissions_means_no_transport():
    for settings in (
        OandaSettings(),
        OandaSettings(token=SecretStr("FAKE"), account_id=SecretStr("123-456")),
    ):
        with pytest.raises(FeedUnavailable):
            OandaPracticeFeed(settings, profile=None)
    assert not PracticeAccess().permits(datetime.now(UTC))


def test_quote_identity_z_timestamp_and_no_sizing(practice):
    feed, now, calls, _ = practice
    assert feed.connect().environment == "practice"
    row, _raw = feed.quote("EURUSD")
    assert row.source_at == now[0] and row.clock_stamp.raw_representation.endswith("Z")
    assert row.evidence == "synthetic" and row.bid < row.ask
    assert "PRIVATE" not in json.dumps(feed.verify().model_dump(mode="json"))
    assert len(list(feed.quotes("EURUSD"))) == 1
    with pytest.raises(FeedUnavailable, match="sizing"):
        feed.contract("EURUSD")
    with pytest.raises(FeedUnavailable):
        feed.ticks("EURUSD")
    assert all(c.method == "GET" for c in calls)


@pytest.mark.parametrize(
    "operation", ["orders", "positions", "account_switch", "write", "shell", "https://example.com"]
)
def test_mutation_or_arbitrary_operation_denied_before_transport(practice, operation):
    feed, _, calls, _ = practice
    with pytest.raises(FeedUnavailable):
        feed._get(operation)
    assert calls == []


@pytest.mark.parametrize(
    "key,value",
    [
        ("wrong_instrument", True),
        ("status", "non-tradeable"),
        ("offset", 10800),
        ("http_status", 401),
        ("http_status", 429),
    ],
)
def test_bad_native_price_permission_and_source_clock_refused(practice, key, value):
    feed, _, _, state = practice
    state[key] = value
    with pytest.raises(FeedUnavailable):
        feed.quote("EURUSD")


def test_completed_candles_backfill_and_incomplete_excluded(practice):
    feed, _, _, state = practice
    rows, raw = feed.candles("EURUSD", "M1")
    assert len(rows) == 1 and rows[0].evidence == "synthetic" and raw[0]["complete"]
    state["bad_candle"] = True
    assert feed.candles("EURUSD", "M1")[0] == []


def test_same_pipeline_provider_namespace_dedup_restart_corruption_and_quota(practice, tmp_path):
    feed, now, _, _ = practice
    store = FeedStore(tmp_path, feed.config, provider="oanda_practice", code_version="fixture")
    folder = tmp_path / "reports/market_feed/oanda-synthetic"
    try:
        result = Collector(feed, store, folder, clock=lambda: now[0], sleep=lambda _: None).run(
            max_polls=2
        )
        assert result["source"] == "synthetic"
        assert all(
            v["duplicates"] == 1 and v["qualified_forward"] == 0 for v in result["counts"].values()
        )
        assert len(read_feed_export(folder).quotes) == 2
        assert "data/bronze/oanda_practice" in next(iter(store.last_commit()["files"]))
        store.close()
        store = FeedStore(tmp_path, feed.config, provider="oanda_practice", code_version="fixture")
        assert store.last_commit() is not None
        file = next(iter(store.last_commit()["files"]))
        (tmp_path / file).write_bytes(b"corrupt")
        with pytest.raises(StorageRefused):
            store.last_commit()
    finally:
        store.close()


def test_read_only_adapter_source_has_no_mutation_transport():
    tree = ast.parse(Path("src/tb/ingest/oanda.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "post",
                "put",
                "patch",
                "delete",
                "order_send",
                "order_check",
                "login",
                "symbol_select",
            }


def test_mock_profile_cannot_enable_genuine_client(practice):
    feed, now, _, _ = practice
    access = PracticeAccess(
        pakistan_demo_access_verified=True,
        practice_api_verified=True,
        no_funding_required_verified=True,
        storage_rights_reviewed=True,
        evidence_references=("https://example.invalid/offline",),
        expires_at=now[0] + timedelta(days=1),
    )
    with pytest.raises(FeedUnavailable, match="genuine clock"):
        OandaPracticeFeed(
            OandaSettings(token=SecretStr("FAKE"), account_id=SecretStr("123-456")),
            profile=feed.clock_profile,
            access=access,
            clock=lambda: now[0],
        )
