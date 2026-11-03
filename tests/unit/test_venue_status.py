"""Owned status-control fixtures only; no provider requests, prices, keys or orders."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.utils import format_datetime

import httpx
import pytest

from tb.dashboard.venue_status import venue_health_rows
from tb.ingest.history.core import atomic_write_json
from tb.ingest.venue_status import (
    ENDPOINT,
    SYMBOLS,
    VenueBook,
    VenueMonitor,
    VenueRefused,
    VenueStore,
    parse_status,
    retry_after,
)
from tb.risk.config import load_policy_bundle
from tb.risk.manager import EntryRequest, RiskManager, RiskState
from tb.risk.venue import evaluate_entry_with_venue

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def payload(status="TRADING", server_time=0):
    return json.dumps(
        {
            "serverTime": server_time,
            "symbols": [
                {"symbol": s, "status": status, "ignored_price_like_field": "not persisted"}
                for s in SYMBOLS
            ],
        }
    ).encode()


def observed(status="TRADING", at=NOW):
    return parse_status(payload(status), at, evidence="owned_fixture")


def test_status_changes_only_duplicate_polls_no_extra_rows_and_heartbeat_refreshes(tmp_path):
    store = VenueStore(
        tmp_path / "space in path" / "status.sqlite", evidence="owned_fixture", create=True
    )
    try:
        assert store.accept(observed()) == 4
        assert store.accept(observed(at=NOW + timedelta(minutes=9))) == 0
        assert store.db.execute("SELECT COUNT(*) FROM status_changes").fetchone()[0] == 4
        assert store.db.execute("SELECT COUNT(*) FROM current_status").fetchone()[0] == 4
        assert not store.book().venue_veto("BTCUSDT", NOW + timedelta(minutes=18)).veto
        assert store.book().venue_veto("BTCUSDT", NOW + timedelta(minutes=19, seconds=1)).veto
        assert store.accept(observed("BREAK", NOW + timedelta(minutes=20))) == 4
        assert store.db.execute(
            "SELECT old_status,new_status,raw_status FROM status_changes WHERE symbol=? ORDER BY seq DESC LIMIT 1",
            ("BTCUSDT",),
        ).fetchone() == ("TRADING", "BREAK", "BREAK")
        assert (
            store.health(NOW + timedelta(minutes=20))["symbols"][1]["last_change"]
            == (NOW + timedelta(minutes=20)).isoformat()
        )
    finally:
        store.close()


@pytest.mark.parametrize(
    "status", ["BREAK", "HALT", "PRE_TRADING", "UNKNOWN", "NEW_PROVIDER_STATUS"]
)
def test_nontrading_and_unknown_status_veto_only(status):
    decision = VenueBook(observations=observed(status)).venue_veto("BTCUSDT", NOW)
    assert decision.veto and decision.reason == "venue_not_trading"
    assert not hasattr(decision, "quantity") and not hasattr(decision, "side")


def test_stale_unknown_and_future_facts_fail_closed_at_query_clock():
    book = VenueBook(
        observations=observed("HALT") + observed("TRADING", NOW + timedelta(minutes=1))
    )
    assert book.venue_veto("BTCUSDT", NOW).veto
    assert not book.venue_veto("BTCUSDT", NOW + timedelta(minutes=11)).veto
    assert (
        book.venue_veto("BTCUSDT", NOW + timedelta(minutes=11, seconds=1)).reason == "venue_stale"
    )
    assert VenueBook().venue_veto("BTCUSDT", NOW).reason == "venue_unknown"
    assert book.venue_veto("XAUUSD", NOW).veto
    with pytest.raises(VenueRefused):
        book.venue_veto("BTCUSDT", NOW.replace(tzinfo=None))


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not JSON",
        b'{"symbols":[]}',
        b'{"symbols":null}',
        b'{"serverTime":NaN,"symbols":[]}',
        b'{"symbols":[],"symbols":[]}',
        json.dumps({"symbols": [{"symbol": "BTCUSDT", "status": "TRADING"}] * 4}).encode(),
        json.dumps({"symbols": [{"symbol": s, "status": None} for s in SYMBOLS]}).encode(),
        json.dumps(
            {"symbols": [{"symbol": s, "status": "bad status\n"} for s in SYMBOLS]}
        ).encode(),
        b"x" * (2 * 1024**2 + 1),
    ],
    ids=[
        "empty",
        "not-json",
        "empty-symbols",
        "null-symbols",
        "nan",
        "duplicate-key",
        "duplicate-symbol",
        "null-status",
        "malformed-status",
        "oversized",
    ],
)
def test_malformed_payloads_refused(body):
    with pytest.raises(VenueRefused):
        parse_status(body, NOW)


@pytest.mark.parametrize("server_time", [0, -10000000000000, 999999999999999999])
def test_server_clock_never_controls_known_at(server_time):
    assert {o.known_at for o in parse_status(payload(server_time=server_time), NOW)} == {NOW}


def test_store_append_only_and_atomic_clock_or_provenance_refusal(tmp_path):
    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    try:
        store.accept(observed())
        with pytest.raises(VenueRefused, match="regressed"):
            store.accept(observed(at=NOW - timedelta(seconds=1)))
        with pytest.raises(VenueRefused, match="conflicting"):
            store.accept(observed("HALT"))
        with pytest.raises(VenueRefused, match="identity"):
            store.accept(parse_status(payload(), NOW))
        assert store.db.execute("SELECT COUNT(*) FROM status_changes").fetchone()[0] == 4
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            store.db.execute("DELETE FROM status_changes")
        store.db.rollback()
    finally:
        store.close()


def test_polite_cadence_survives_restart_and_records_local_receive_time(tmp_path):
    calls = []
    clock = [NOW]

    def respond(request):
        calls.append(request)
        clock[0] += timedelta(seconds=2)
        return httpx.Response(200, content=payload(server_time=99999999999999999))

    path = tmp_path / "status.sqlite"
    store = VenueStore(path, evidence="owned_fixture", create=True)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monitor = VenueMonitor(store, client, clock=lambda: clock[0])
        assert monitor.poll_once().changes == 4
        assert not monitor.poll_once().attempted
        assert store.book().venue_veto("BTCUSDT", clock[0]).known_at == NOW + timedelta(seconds=2)
        store.close()
        store = VenueStore(path, evidence="owned_fixture")
        monitor = VenueMonitor(store, client, clock=lambda: clock[0])
        assert not monitor.poll_once().attempted
        clock[0] = NOW + timedelta(seconds=60)
        assert monitor.poll_once().changes == 0
        assert len(calls) == 2 and str(calls[0].url).startswith(ENDPOINT + "?symbols=")
        assert json.loads(calls[0].url.params["symbols"]) == list(SYMBOLS)
        assert calls[0].method == "GET" and "X-MBX-APIKEY" not in calls[0].headers
    store.close()


@pytest.mark.parametrize("code,delay", [(429, 180), (418, 3600)])
def test_429_418_retry_after_is_honored_without_retry_loop(tmp_path, code, delay):
    calls = []
    clock = [NOW]

    def respond(request):
        calls.append(request)
        return httpx.Response(code, headers={"Retry-After": str(delay)})

    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    try:
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            monitor = VenueMonitor(store, client, clock=lambda: clock[0])
            assert monitor.poll_once().category == "rate_limited"
            clock[0] = NOW + timedelta(seconds=delay - 1)
            assert not monitor.poll_once().attempted
            assert len(calls) == 1
            clock[0] = NOW + timedelta(seconds=delay)
            assert monitor.poll_once().attempted
            assert len(calls) == 2
    finally:
        store.close()


def test_retry_after_http_date_and_three_failure_cooldown(tmp_path):
    assert retry_after(format_datetime(NOW + timedelta(minutes=30)), NOW) == 1800
    assert retry_after("bad", NOW) == 60
    assert retry_after("nan", NOW) == 60
    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    try:
        for offset in (0, 60, 180):
            now = NOW + timedelta(seconds=offset)
            assert store.reserve_poll(now, 60)
            store.back_off(now, "request_or_response_refused", 60)
        assert not store.reserve_poll(NOW + timedelta(seconds=779), 60)
        assert store.reserve_poll(NOW + timedelta(seconds=780), 60)
        assert store.db.execute("SELECT failures FROM polling").fetchone()[0] == 0
    finally:
        store.close()


@pytest.mark.parametrize("failure", ["timeout", "server", "malformed", "redirect"])
def test_failed_requests_are_bounded_and_never_refresh_status(tmp_path, failure):
    calls = []

    def respond(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("owned timeout", request=request)
        return httpx.Response(
            503 if failure == "server" else 302 if failure == "redirect" else 200,
            content=b"not JSON",
            headers={"Location": "https://example.invalid/"},
        )

    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    try:
        store.accept(observed())
        with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True) as client:
            monitor = VenueMonitor(store, client, clock=lambda: NOW + timedelta(minutes=1))
            assert monitor.poll_once().category == "request_or_response_refused"
            assert len(calls) == 1 and not monitor.poll_once().attempted
            assert (
                store.book().venue_veto("BTCUSDT", NOW + timedelta(minutes=11)).reason
                == "venue_stale"
            )
            assert store.db.execute("SELECT COUNT(*) FROM status_changes").fetchone()[0] == 4
    finally:
        store.close()


def test_stream_has_an_elapsed_deadline_and_oversized_retry_never_retries_early(tmp_path):
    class SlowBody(httpx.SyncByteStream):
        def __iter__(self):
            yield b"{}"

    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    times = iter((0.0, 21.0))
    try:
        with httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=SlowBody()))
        ) as client:
            monitor = VenueMonitor(store, client, clock=lambda: NOW, elapsed=lambda: next(times))
            assert monitor.poll_once().category == "request_or_response_refused"
        store.back_off(NOW, "rate_limited", 1e300)
        assert not store.reserve_poll(NOW + timedelta(days=365), 60)
    finally:
        store.close()


def test_changed_store_schema_is_refused_without_repair(tmp_path):
    path = tmp_path / "status.sqlite"
    store = VenueStore(path, evidence="owned_fixture", create=True)
    store.close()
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER changes_no_delete")
        before = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall()
    with pytest.raises(VenueRefused, match="schema"):
        VenueStore(path, evidence="owned_fixture")
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall() == before
        )


@pytest.mark.parametrize("interval", [0, 59.9, float("nan"), float("inf")])
def test_poll_interval_below_minimum_or_nonfinite_refused(tmp_path, interval):
    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    try:
        with httpx.Client(
            transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request"))
        ) as client:
            with pytest.raises(VenueRefused):
                VenueMonitor(store, client, interval=interval)
    finally:
        store.close()


def test_risk_precheck_trading_cannot_enlarge_and_disabled_history_unchanged():
    manager = RiskManager(load_policy_bundle())
    request = EntryRequest(
        symbol="BTCUSDT", timestamp=NOW, entry_price=Decimal("100"), stop_price=Decimal("95")
    )
    state = RiskState(
        equity=Decimal("10000"),
        cash=Decimal("10000"),
        current_exposure=Decimal("0"),
        current_holdings=Decimal("0"),
        realized_pnl_day=Decimal("0"),
        start_of_day_equity=Decimal("10000"),
        completed_trades_today=0,
    )
    expected = manager.evaluate_entry(request, state)
    assert evaluate_entry_with_venue(manager, request, state) == expected
    assert (
        evaluate_entry_with_venue(manager, request, state, venue=VenueBook(observations=observed()))
        == expected
    )
    veto = evaluate_entry_with_venue(
        manager, request, state, venue=VenueBook(observations=observed("HALT"))
    )
    assert not veto.approved and veto.quantity == 0 and veto.risk_amount == 0
    with pytest.raises(VenueRefused, match="historical"):
        evaluate_entry_with_venue(manager, request, state, venue=VenueBook(), historical=True)
    assert evaluate_entry_with_venue(manager, request, state, historical=True) == expected


def test_data_health_is_read_only_and_recomputes_staleness(tmp_path):
    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    store.accept(observed())
    health = store.health(NOW)
    store.close()
    path = tmp_path / "reports/data_quality/venue-status-health.json"
    atomic_write_json(path, health)
    original = path.read_bytes()
    rows = venue_health_rows(tmp_path, NOW + timedelta(minutes=11))
    assert len(rows) == 4 and all(r["veto"] and r["reason"] == "venue_stale" for r in rows)
    assert path.read_bytes() == original
    assert all(r["last_change"] == NOW.isoformat() for r in rows)
    assert all(r["veto"] for r in venue_health_rows(tmp_path, NOW - timedelta(seconds=1)))
    path.write_text("{}")
    assert all(r["reason"] == "venue_unknown" for r in venue_health_rows(tmp_path, NOW))


def test_authenticated_clients_are_refused_before_any_request(tmp_path):
    store = VenueStore(tmp_path / "status.sqlite", evidence="owned_fixture", create=True)
    try:
        with httpx.Client(
            transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request")),
            headers={"X-MBX-APIKEY": "FICTIONAL-OWNED-TEST-ONLY"},
        ) as client:
            with pytest.raises(VenueRefused, match="without_credentials"):
                VenueMonitor(store, client)
    finally:
        store.close()
