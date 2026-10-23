"""Offline provider boundaries, credit accounting, UTC semantics and execution refusal."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.utils import format_datetime
from pathlib import Path

import httpx
import polars as pl
import pytest
from pydantic import SecretStr

from tb.core.contracts import ReadOnlyMarketFeed
from tb.ingest.mt5.collector import classify_forward
from tb.ingest.mt5.models import FeedConfig, FeedUnavailable, Observation, StorageRefused
from tb.ingest.mt5.storage import FeedStore, record_id
from tb.ingest.twelve_data.adapter import TwelveDataFeed
from tb.ingest.twelve_data.client import (
    CreditBudget,
    EntitlementRefused,
    QuotaRefused,
    TwelveDataClient,
    TwelveDataSettings,
)
from tb.ingest.twelve_data.collect import run
from tb.ingest.twelve_data.models import ReferenceExport

NOW = datetime(2026, 10, 23, 18, 0, 5, tzinfo=UTC)
TOKEN = "offline-fixture-secret"
SCOPE = hashlib.sha256(TOKEN.encode()).hexdigest()


def usage() -> dict[str, object]:
    return {
        "timestamp": "2026-10-23 18:00:05",
        "plan_limit": 8,
        "plan_daily_limit": 800,
        "current_usage": 0,
        "daily_usage": 0,
        "plan_category": "basic",
    }


def rate(at: datetime = NOW) -> dict[str, object]:
    return {"symbol": "EUR/USD", "rate": "1.1000", "timestamp": int(at.timestamp())}


def candles(at: datetime = NOW) -> dict[str, object]:
    return {
        "status": "ok",
        "meta": {
            "symbol": "EUR/USD",
            "interval": "1min",
            "exchange_timezone": "Australia/Sydney",
            "type": "Physical Currency",
        },
        "values": [
            {
                "datetime": at.replace(second=0).strftime("%Y-%m-%d %H:%M:%S"),
                "open": "1.10",
                "high": "1.11",
                "low": "1.09",
                "close": "1.10",
            }
        ],
    }


def make_client(
    tmp_path: Path,
    payload: dict[str, object] | None = None,
    *,
    status: int = 200,
    extra_headers: dict[str, str] | None = None,
) -> tuple[TwelveDataClient, CreditBudget, list[httpx.Request]]:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        value = usage() if request.url.path == "/api_usage" else payload or rate()
        return httpx.Response(
            status if request.url.path != "/api_usage" else 200,
            json=value,
            headers={"Date": format_datetime(NOW, usegmt=True), **(extra_headers or {})},
        )

    budget = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    client = TwelveDataClient(
        TwelveDataSettings(api_key=SecretStr(TOKEN)),
        budget,
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )
    client.get("api_usage")
    return client, budget, requests


def test_read_only_contract_and_secret_safe_requests(tmp_path: Path) -> None:
    client, budget, requests = make_client(tmp_path)
    feed: ReadOnlyMarketFeed = TwelveDataFeed(client)
    for method in (feed.contract, feed.quotes):
        with pytest.raises(FeedUnavailable):
            method("EURUSD")
    with pytest.raises(FeedUnavailable):
        TwelveDataFeed(client).quote("EURUSD")
    assert len(requests) == 1  # No order, account or bid/ask request was made.
    assert TOKEN not in str(requests[0].url)
    assert requests[0].headers["authorization"] == "apikey " + TOKEN
    assert TOKEN not in repr(TwelveDataSettings(api_key=SecretStr(TOKEN)))
    budget.close()


@pytest.mark.parametrize(
    "endpoint",
    [
        "orders",
        "accounts",
        "price",
        "quote",
        "../orders",
        "time_series?apikey=bad",
        "https://evil.invalid",
    ],
)
def test_default_deny_network_paths(tmp_path: Path, endpoint: str) -> None:
    client, _, requests = make_client(tmp_path)
    with pytest.raises(FeedUnavailable, match="allowlist"):
        client.get(endpoint, "EURUSD")
    assert len(requests) == 1


@pytest.mark.parametrize("symbol", ["EUR/USD", "EURUSD,SPY", "XAUTUSDT", "EURUSD?symbol=XAUUSD"])
def test_exact_symbol_guard(tmp_path: Path, symbol: str) -> None:
    client, _, requests = make_client(tmp_path)
    with pytest.raises(FeedUnavailable):
        client.get("exchange_rate", symbol)
    assert len(requests) == 1


def test_missing_key_has_no_network_or_reservation(tmp_path: Path) -> None:
    budget = CreditBudget(tmp_path / "credits.sqlite", "missing")
    client = TwelveDataClient(TwelveDataSettings(api_key=SecretStr("")), budget)
    with pytest.raises(FeedUnavailable, match="missing"):
        client.get("api_usage")
    assert client.network_requests == 0
    assert budget.db.execute("SELECT COUNT(*) FROM credits").fetchone()[0] == 0


def test_valid_reference_is_midpoint_and_synthetic(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path)
    row, raw = TwelveDataFeed(client).reference("EURUSD")
    assert row.kind == "reference" and row.evidence == "synthetic"
    assert row.source_at == NOW and row.bid is None and row.ask is None
    assert row.price_type == "reference_midpoint" and raw["requested_timezone"] == "UTC"
    assert TOKEN not in json.dumps(raw)


@pytest.mark.parametrize(
    "changes",
    [
        {"rate": "NaN"},
        {"rate": "Infinity"},
        {"rate": "0"},
        {"rate": True},
        {"timestamp": "2026-10-23"},
        {"timestamp": True},
        {"symbol": "XAU/USD"},
        {"timestamp": int((NOW + timedelta(hours=3)).timestamp())},
        {"timestamp": int((NOW - timedelta(seconds=91)).timestamp())},
    ],
)
def test_invalid_reference_values_and_clocks(tmp_path: Path, changes: dict[str, object]) -> None:
    client, _, _ = make_client(tmp_path, {**rate(), **changes})
    with pytest.raises((FeedUnavailable, ValueError, ArithmeticError)):
        TwelveDataFeed(client).reference("EURUSD")


def test_minute_cadence_is_not_tick_latency(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path, rate(NOW - timedelta(seconds=59)))
    row, _ = TwelveDataFeed(client).reference("EURUSD")
    assert (row.received_at - row.source_at).total_seconds() == 59
    assert row.bid is None and row.ask is None


def test_entitlement_is_refused_without_upgrade(tmp_path: Path) -> None:
    client, _, requests = make_client(
        tmp_path, {"code": 403, "status": "error", "message": TOKEN}, status=403
    )
    with pytest.raises(EntitlementRefused) as error:
        client.get("time_series", "XAUUSD")
    assert TOKEN not in str(error.value)
    assert requests[-1].url.params["symbol"] == "XAU/USD"
    assert len(requests) == 2


@pytest.mark.parametrize("http_status", [200, 429])
def test_api_quota_error_and_persistent_retry_after(tmp_path: Path, http_status: int) -> None:
    client, budget, requests = make_client(
        tmp_path,
        {"status": "error", "code": 429, "message": "daily quota " + TOKEN},
        status=http_status,
        extra_headers={"Retry-After": "120"},
    )
    with pytest.raises(QuotaRefused) as error:
        client.get("exchange_rate", "EURUSD")
    assert TOKEN not in str(error.value)
    budget.close()
    restarted = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    with pytest.raises(QuotaRefused):
        restarted.reserve(NOW + timedelta(minutes=10))
    assert len(requests) == 2  # No automatic retry.


def test_minute_daily_budgets_and_utc_reset(tmp_path: Path) -> None:
    budget = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    budget.usage({**usage(), "daily_usage": 799}, NOW)
    budget.reserve(NOW + timedelta(seconds=1))
    with pytest.raises(QuotaRefused):
        budget.reserve(NOW + timedelta(minutes=1))
    budget.reserve(NOW.replace(day=24, hour=0, minute=0, second=0))
    other = CreditBudget(tmp_path / "other.sqlite", SCOPE)
    for _ in range(8):
        other.reserve(NOW)
    with pytest.raises(QuotaRefused):
        other.reserve(NOW)
    other.reserve(NOW + timedelta(minutes=1))


def test_cache_preserves_acquisition_time_on_restart(tmp_path: Path) -> None:
    client, budget, requests = make_client(tmp_path)
    first = client.get("exchange_rate", "EURUSD")
    budget.close()
    restarted = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    cached = restarted.cached("exchange_rate:EURUSD", NOW + timedelta(seconds=30), 45)
    assert cached and cached.cached and cached.received_at == first.received_at
    assert restarted.cached("exchange_rate:EURUSD", NOW + timedelta(seconds=46), 45) is None
    assert len(requests) == 2


@pytest.mark.parametrize(
    "header", [{"Date": format_datetime(NOW + timedelta(hours=1), usegmt=True)}, {"Age": "100"}]
)
def test_bad_http_clock_and_stale_cache_refused(tmp_path: Path, header: dict[str, str]) -> None:
    with pytest.raises(FeedUnavailable, match="clock"):
        make_client(tmp_path, extra_headers=header)


def test_complete_and_incomplete_candles_no_fabricated_volume(tmp_path: Path) -> None:
    value = candles()
    values = value["values"]
    assert isinstance(values, list)
    values.insert(0, {**values[0], "datetime": "2026-10-23 17:59:00"})
    client, _, requests = make_client(tmp_path, value)
    rows, _ = TwelveDataFeed(client).candles("EURUSD")
    assert [r.interval_complete for r in rows] == [True, False]
    assert all(r.tick_volume is None and r.real_volume is None for r in rows)
    assert requests[-1].url.params["timezone"] == "UTC"
    assert rows[0].source_metadata_timezone == "Australia/Sydney"
    incomplete = rows[-1].model_copy(update={"evidence": "historical_backfill"})
    assert (
        classify_forward(
            incomplete,
            NOW - timedelta(minutes=2),
            coverage_start=NOW - timedelta(minutes=2),
            maximum_lag=120,
        ).evidence
        == "historical_backfill"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"interval": "5min"},
        {"symbol": "XAU/USD"},
        {"type": "Common Stock"},
        {"exchange_timezone": ""},
    ],
)
def test_candle_provider_mixups(tmp_path: Path, change: dict[str, str]) -> None:
    value = candles()
    assert isinstance(value["meta"], dict)
    value["meta"].update(change)
    client, _, _ = make_client(tmp_path, value)
    with pytest.raises(FeedUnavailable):
        TwelveDataFeed(client).candles("EURUSD")


def test_genuine_forex_metadata_and_gold_type_without_exchange_timezone(tmp_path: Path) -> None:
    value = candles(NOW - timedelta(minutes=1))
    assert isinstance(value["meta"], dict)
    value["meta"].pop("exchange_timezone")
    value["meta"].update(
        symbol="XAU/USD",
        type="Precious Metal",
        currency_base="Gold Spot",
        currency_quote="US Dollar",
    )
    client, _, _ = make_client(tmp_path, value)
    rows, raw = TwelveDataFeed(client).candles("XAUUSD")
    assert rows[0].source_timezone == "UTC"
    assert rows[0].source_metadata_timezone is None
    assert raw[0]["requested_timezone"] == "UTC"


def test_old_candle_values_are_not_fresh_forward_evidence(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path, candles(NOW - timedelta(minutes=10)))
    with pytest.raises(FeedUnavailable, match="stale"):
        TwelveDataFeed(client).candles("EURUSD")


def test_missing_actual_plan_cannot_make_market_request(tmp_path: Path) -> None:
    budget = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    client = TwelveDataClient(TwelveDataSettings(api_key=SecretStr(TOKEN)), budget)
    with pytest.raises(FeedUnavailable, match="plan_check"):
        client.get("time_series", "EURUSD")
    assert client.network_requests == 0


def test_credit_scope_and_upstream_headers_fail_closed(tmp_path: Path) -> None:
    budget = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    budget.usage(usage(), NOW)
    budget.header_remaining("0", NOW)
    with pytest.raises(QuotaRefused):
        budget.reserve(NOW)
    with pytest.raises(FeedUnavailable, match="scope"):
        TwelveDataClient(TwelveDataSettings(api_key=SecretStr("different-fixture")), budget)


@pytest.mark.parametrize(
    "bad", [{"plan_category": "pro"}, {"plan_limit": 0}, {"daily_usage": "0"}, {"plan_limit": True}]
)
def test_unknown_or_invalid_actual_plan(tmp_path: Path, bad: dict[str, object]) -> None:
    budget = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    with pytest.raises(FeedUnavailable):
        budget.usage({**usage(), **bad}, NOW)


def test_success_body_cannot_echo_credential(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path, {**rate(), "unexpected": TOKEN})
    with pytest.raises(FeedUnavailable, match="echo"):
        client.get("exchange_rate", "EURUSD")


def test_receipt_clock_regression_keeps_reservation_on_restart(tmp_path: Path) -> None:
    budget = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    budget.reserve(NOW)
    budget.close()
    restarted = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    with pytest.raises(QuotaRefused, match="clock"):
        restarted.reserve(NOW - timedelta(seconds=3))


def test_forming_bar_cannot_push_completed_forward_watermark(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path, candles(NOW - timedelta(minutes=1)))
    row = TwelveDataFeed(client).candles("EURUSD")[0][0]
    store = FeedStore(
        tmp_path, FeedConfig(poll_seconds=60), code_version="fixture", provider="twelve_data"
    )
    session, started = store.session("a" * 64, NOW - timedelta(minutes=2), synthetic=False)
    forming = row.model_copy(
        update={
            "source_at": NOW.replace(second=0),
            "raw_source_time": NOW.replace(second=0).strftime("%Y-%m-%d %H:%M:%S"),
            "interval_complete": False,
            "evidence": "historical_backfill",
        }
    )
    store.commit(session, [forming], [], received_at=NOW, warnings=[])
    completed = classify_forward(
        row.model_copy(update={"evidence": "historical_backfill"}),
        started,
        coverage_start=started,
        maximum_lag=120,
    )
    result = store.commit(session, [completed], [], received_at=NOW, warnings=[])
    assert result["evidence_counts"]["forward_observed"] == 1


def test_reference_store_restart_dedup_volume_and_provider_boundaries(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path, candles(NOW - timedelta(minutes=1)))
    rows, raw = TwelveDataFeed(client).candles("EURUSD")
    config = FeedConfig(poll_seconds=60)
    store = FeedStore(tmp_path, config, code_version="fixture", provider="twelve_data")
    session, _ = store.session("a" * 64, NOW - timedelta(minutes=2), synthetic=True)
    result = store.commit(session, rows, raw, received_at=NOW, warnings=[])
    silver = next(name for name in result["files"] if name.startswith("data/silver"))
    assert pl.read_parquet(tmp_path / silver)["volume_kind"].to_list() == ["unavailable"]
    store.close()
    resumed = FeedStore(tmp_path, config, code_version="fixture", provider="twelve_data")
    assert resumed.last_commit()["rows"] == 1
    assert resumed.commit(session, rows, raw, received_at=NOW, warnings=[])["duplicates"] == 1
    other = FeedStore(tmp_path, config, code_version="fixture", provider="oanda_practice")
    other_session, _ = other.session("a" * 64, NOW, synthetic=True)
    with pytest.raises(StorageRefused, match="mismatch"):
        other.commit(other_session, rows, raw, received_at=NOW, warnings=[])


def test_legacy_record_id_unchanged_by_reference_extension() -> None:
    row = Observation(
        symbol="EURUSD",
        broker_symbol="EURUSD",
        kind="quote",
        timeframe="tick",
        source_at=NOW,
        received_at=NOW,
        evidence="synthetic",
        bid="1.1",
        ask="1.2",
    )
    payload = row.model_dump(
        mode="json",
        exclude={
            "received_at",
            "evidence",
            "coverage_started_at",
            "clock_stamp",
            "source_provider",
            "reference_price",
            "price_type",
            "source_timezone",
            "source_metadata_timezone",
            "raw_source_time",
            "interval_complete",
        },
    )
    expected = hashlib.sha256(
        ("identity" + json.dumps(payload, sort_keys=True)).encode()
    ).hexdigest()
    assert record_id(row, "identity") == expected


def test_download_before_coverage_remains_backfill(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path, candles(NOW - timedelta(minutes=1)))
    rows, _ = TwelveDataFeed(client).candles("EURUSD")
    row = rows[0].model_copy(update={"evidence": "historical_backfill"})
    assert (
        classify_forward(row, NOW, coverage_start=NOW, maximum_lag=120).evidence
        == "historical_backfill"
    )


def test_fixtures_can_never_qualify_genuine_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client, _, _ = make_client(tmp_path)
    feed = TwelveDataFeed(client)
    store = FeedStore(
        tmp_path, FeedConfig(poll_seconds=60), code_version="fixture", provider="twelve_data"
    )
    result = run(tmp_path, feed, store, polls=1, clock=lambda: NOW, utc_probe=lambda: [])
    assert result.source == "synthetic"
    assert all(v["source_data"] == "NO-GO" for v in result.readiness.values())
    assert TOKEN not in capsys.readouterr().out
    assert (tmp_path / "reports/market_feed/twelve_data_synthetic/current.json").exists()
    assert not (tmp_path / "reports/market_feed/twelve_data/current.json").exists()
    assert ReferenceExport.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("failure", ["timeout", "server", "redirect", "partial", "oversized"])
def test_network_failures_are_bounded_sanitized_and_charged(tmp_path: Path, failure: str) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout(TOKEN, request=request)
        headers = {"Date": format_datetime(NOW, usegmt=True)}
        if failure == "server":
            return httpx.Response(500, json={"message": TOKEN}, headers=headers)
        if failure == "redirect":
            return httpx.Response(
                302, json={}, headers={**headers, "Location": "https://evil.invalid"}
            )
        if failure == "partial":
            return httpx.Response(200, content=b'{"timestamp":', headers=headers)
        return httpx.Response(200, content=b" " * 131073, headers=headers)

    budget = CreditBudget(tmp_path / "credits.sqlite", SCOPE)
    client = TwelveDataClient(
        TwelveDataSettings(api_key=SecretStr(TOKEN)),
        budget,
        clock=lambda: NOW,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(FeedUnavailable) as error:
        client.get("api_usage")
    assert TOKEN not in str(error.value)
    assert len(calls) == 1
    assert budget.db.execute("SELECT SUM(cost) FROM credits").fetchone()[0] == 1


def test_genuine_reference_boundary_refuses_unchecked_order_quote_copy(tmp_path: Path) -> None:
    client, _, _ = make_client(tmp_path)
    row = TwelveDataFeed(client).reference("EURUSD")[0]
    forged = row.model_copy(update={"kind": "quote", "bid": Decimal("1.1"), "ask": Decimal("1.2")})
    store = FeedStore(tmp_path, FeedConfig(), code_version="fixture", provider="twelve_data")
    session, _ = store.session("a" * 64, NOW, synthetic=True)
    with pytest.raises(StorageRefused, match="contract"):
        store.commit(session, [forged], [], received_at=NOW, warnings=[])
