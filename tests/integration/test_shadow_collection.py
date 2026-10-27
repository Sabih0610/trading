"""Offline M5 transport, persistent scheduling/budgets and immutable Silver source bridge."""

import hashlib
import json
from datetime import timedelta
from email.utils import format_datetime

import httpx
import pytest
from pydantic import SecretStr

from tb.ingest.mt5.models import FeedConfig, FeedUnavailable
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.twelve_data.adapter import TwelveDataFeed
from tb.ingest.twelve_data.client import (
    CreditBudget,
    QuotaRefused,
    TwelveDataClient,
    TwelveDataSettings,
)
from tb.shadow.collection import collect_m5_once, latest_due_close
from tb.shadow.fixtures import FIXTURE_START, fixture_pin, fixture_rights
from tb.shadow.models import ShadowConfig
from tb.shadow.source import read_committed


def client(tmp_path, *, credit_weight="1"):
    now = FIXTURE_START + timedelta(minutes=7)
    key = "owned-offline-M5-fixture"
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/api_usage":
            payload = {
                "plan_limit": 8,
                "plan_daily_limit": 800,
                "current_usage": 0,
                "daily_usage": 0,
                "plan_category": "basic",
            }
        else:
            symbol = request.url.params["symbol"]
            payload = {
                "meta": {
                    "symbol": symbol,
                    "interval": request.url.params["interval"],
                    "type": "Physical Currency" if symbol == "EUR/USD" else "Precious Metal",
                },
                "status": "ok",
                "values": [
                    {
                        "datetime": FIXTURE_START.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": "1.1",
                        "high": "1.2",
                        "low": "1.0",
                        "close": "1.15",
                    }
                ],
            }
        headers = {"Date": format_datetime(now, usegmt=True)}
        if credit_weight is not None:
            headers["api-credits-used"] = credit_weight
        return httpx.Response(
            200,
            json=payload,
            headers=headers,
        )

    budget = CreditBudget(
        tmp_path / "credits.sqlite", hashlib.sha256(key.encode()).hexdigest(), daily_ceiling=600
    )
    result = TwelveDataClient(
        TwelveDataSettings(api_key=SecretStr(key)),
        budget,
        fixture_transport=httpx.MockTransport(handler),
        clock=lambda: now,
    )
    result.get("api_usage")
    return result, calls, now


def test_M5_parameters_slot_dedup_restart_and_source_manifest(tmp_path):
    c, calls, now = client(tmp_path)
    store = FeedStore(
        tmp_path,
        FeedConfig(max_rows=10, poll_seconds=300),
        code_version="test-source",
        provider="twelve_data",
    )
    feed = TwelveDataFeed(c)
    assert latest_due_close(now) == FIXTURE_START + timedelta(minutes=5)
    assert collect_m5_once(feed, store, fixture_rights(), started_at=FIXTURE_START, now=now) == 2
    assert collect_m5_once(feed, store, fixture_rights(), started_at=FIXTURE_START, now=now) == 0
    assert len(calls) == 3
    assert all(r.method == "GET" for r in calls)
    assert calls[-1].url.params["interval"] == "5min" and calls[-1].url.params["timezone"] == "UTC"
    manifest_name = store.db.execute(
        "SELECT manifest FROM batches ORDER BY seq DESC LIMIT 1"
    ).fetchone()[0]
    path = tmp_path / manifest_name
    pin = fixture_pin(ShadowConfig(), "test-consumer").model_copy(
        update={"identity": c.source_identity, "source_version": "test-source"}
    )
    events = list(read_committed(tmp_path, path, pin))
    assert len(events) == 1 and events[0].observation.timeframe == "M5"
    assert events[0].observation.coverage_started_at == FIXTURE_START
    c.budget.close()
    restarted = CreditBudget(tmp_path / "credits.sqlite", c.credential_scope, daily_ceiling=600)
    assert not restarted.claim_m5(FIXTURE_START + timedelta(minutes=5), "XAUUSD", now)
    value = json.loads(path.read_text())
    silver = next(tmp_path / name for name in value["files"] if "silver" in name)
    silver.write_bytes(b"corrupt owned fixture")
    with pytest.raises(FeedUnavailable):
        list(read_committed(tmp_path, path, pin))


@pytest.mark.parametrize("offset", [0, 18, 119, 181, 600])
def test_no_poll_before_publication_or_replay_of_missed_slots(tmp_path, offset):
    c, _, _ = client(tmp_path)
    close = FIXTURE_START + timedelta(minutes=5)
    assert not c.budget.claim_m5(close, "EURUSD", close + timedelta(seconds=offset))


def test_weekend_composites_do_not_schedule_market_poll(tmp_path):
    c, _, _ = client(tmp_path)
    close = FIXTURE_START + timedelta(days=5, minutes=5)
    assert not c.budget.claim_m5(close, "EURUSD", close + timedelta(seconds=120))


def test_application_budget_headroom_and_actual_usage_block_HTTP(tmp_path):
    c, calls, now = client(tmp_path)
    c.budget.usage(
        {
            "plan_limit": 8,
            "plan_daily_limit": 800,
            "current_usage": 0,
            "daily_usage": 600,
            "plan_category": "basic",
        },
        now,
    )
    with pytest.raises(QuotaRefused):
        c.get("time_series", "EURUSD", timeframe="M5")
    assert len(calls) == 1


def test_genuine_client_requires_rights_even_for_cached_success(tmp_path):
    c, _, _ = client(tmp_path)
    c.get("time_series", "EURUSD", timeframe="M5")
    c.close()
    # No custom transport: genuine construction must refuse before cache/network.
    settings = TwelveDataSettings(api_key=SecretStr("owned-offline-M5-fixture"))
    genuine = TwelveDataClient(
        settings, c.budget, clock=lambda: FIXTURE_START + timedelta(minutes=7)
    )
    genuine.plan_confirmed = True
    with pytest.raises(FeedUnavailable, match="rights"):
        genuine.get("time_series", "EURUSD", timeframe="M5")
    assert genuine.network_requests == 0


@pytest.mark.parametrize("weight", [None, "2", "1"])
def test_genuine_M5_credit_weight_is_verified_before_cache(tmp_path, monkeypatch, weight):
    # Exercise the genuine guard with an owned key and an entirely mocked HTTP transport.
    c, calls, now = client(tmp_path, credit_weight=weight)
    c.rights = fixture_rights().model_copy(
        update={"provider": "twelve_data", "account_fingerprint": c.source_identity}
    )
    c.rights = c.rights.model_copy(
        update={
            "permissions": {
                key: value.model_copy(update={"permitted_retention_seconds": 3600})
                for key, value in c.rights.permissions.items()
            }
        }
    )
    c._synthetic = False
    c.rights_root = tmp_path
    # This case isolates credit weights; documentary policy denial has separate regressions.
    monkeypatch.setattr("tb.ingest.twelve_data.client.check_review", lambda *a, **k: c.rights)
    try:
        if weight == "1":
            reply = c.get("time_series", "EURUSD", timeframe="M5")
            assert not reply.cached and c.plan_confirmed
            assert c.budget.cached("time_series:EURUSD:M5", now, 45) is not None
        else:
            with pytest.raises(FeedUnavailable, match="credit_weight_unverified"):
                c.get("time_series", "EURUSD", timeframe="M5")
            assert not c.plan_confirmed
            assert c.budget.cached("time_series:EURUSD:M5", now, 45) is None
            with pytest.raises(QuotaRefused, match="retry_after_active"):
                c.budget.reserve(now)
        assert len(calls) == 2
    finally:
        c.close()
        c.budget.close()


def test_provider_mixups_never_enter_source_bridge(tmp_path):
    c, _, now = client(tmp_path)
    store = FeedStore(
        tmp_path, FeedConfig(max_rows=10), code_version="test-source", provider="twelve_data"
    )
    collect_m5_once(TwelveDataFeed(c), store, fixture_rights(), started_at=FIXTURE_START, now=now)
    name = store.db.execute("SELECT manifest FROM batches LIMIT 1").fetchone()[0]
    pin = fixture_pin(ShadowConfig(), "test").model_copy(
        update={"identity": "f" * 64, "source_version": "test-source"}
    )
    with pytest.raises(FeedUnavailable):
        list(read_committed(tmp_path, tmp_path / name, pin))


def test_no_price_history_is_read_when_genuine_rights_are_unverified(monkeypatch, tmp_path):
    from tb.shadow import cli

    monkeypatch.setattr(
        "sys.argv", ["shadow", "watch", "--seconds", "1", "--output", str(tmp_path / "genuine")]
    )
    with pytest.raises(FeedUnavailable, match="rights"):
        cli.main()
    assert not (tmp_path / "genuine").exists()
