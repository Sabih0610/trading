"""Owned cTrader protocol tests: scope, identity, clocks, sides and contract arithmetic."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.ingest.broker.book import QuoteBook, integer
from tb.ingest.broker.ctrader import CTraderQuoteSource, CTraderSettings
from tb.ingest.broker.evaluation import CostEvidence, align_reference, qualify
from tb.ingest.broker.fixtures import (
    START,
    fixture_decision,
    fixture_rights,
    fixture_settings,
    fixture_source,
    responder,
    spot,
)
from tb.ingest.broker.models import BrokerContract, BrokerRefused
from tb.ingest.broker.transport import FATAL_EVENTS, READ_FIELDS, validate_request
from tb.risk.config import load_policy_bundle


def one_quote(tmp_path, symbol="EURUSD"):
    prices = (110000, 110002) if symbol == "EURUSD" else (240000000, 240020000)
    source, clock, channel = fixture_source(
        tmp_path, [spot(symbol, 1000, bid=prices[0], ask=prices[1])]
    )
    identity = source.connect()
    contract = source.metadata(symbol)
    quote = source.read()
    assert quote is not None
    return source, clock, channel, identity, contract, quote


@pytest.mark.parametrize("scope", [None, 1, "SCOPE_TRADE", "unknown", False, True, "0", -1])
def test_scope_must_be_independently_returned_view(tmp_path, scope):
    source, _clock, channel = fixture_source(tmp_path)

    def changed(kind, payload):
        row = responder(kind, payload)
        if kind == 2149:
            row["permissionScope"] = scope
        return row

    channel.responder = changed
    with pytest.raises(BrokerRefused):
        source.connect()
    assert channel.closed and channel.calls == [2100, 2149]


def test_token_grant_must_not_include_other_or_live_accounts(tmp_path):
    source, _clock, channel = fixture_source(tmp_path)

    def changed(kind, payload):
        row = responder(kind, payload)
        if kind == 2149:
            row["ctidTraderAccount"].append({"ctidTraderAccountId": 888, "isLive": True})
        return row

    channel.responder = changed
    with pytest.raises(BrokerRefused):
        source.connect()
    assert channel.calls == [2100, 2149] and channel.closed


@pytest.mark.parametrize("scope", [0, "SCOPE_VIEW"])
def test_numeric_zero_is_view_not_missing(tmp_path, scope):
    source, _clock, channel = fixture_source(tmp_path)

    def changed(kind, payload):
        value = responder(kind, payload)
        if kind == 2149:
            value["permissionScope"] = scope
        return value

    channel.responder = changed
    assert source.connect().permission == "SCOPE_VIEW"
    assert set(channel.calls) <= set(READ_FIELDS)
    source.close()


@pytest.mark.parametrize("change", ["live", "broker", "account", "missing_live", "token"])
def test_exact_demo_identity_and_token_binding(tmp_path, change):
    source, _clock, channel = fixture_source(tmp_path)

    def changed(kind, payload):
        row = responder(kind, payload)
        if kind == 2149:
            account = row["ctidTraderAccount"][0]
            if change == "live":
                account["isLive"] = True
            if change == "missing_live":
                account.pop("isLive")
            if change == "broker":
                account["brokerTitleShort"] = "different"
            if change == "account":
                account["ctidTraderAccountId"] = 888
            if change == "token":
                row["accessToken"] = "unexpected-token"
        return row

    channel.responder = changed
    with pytest.raises(BrokerRefused):
        source.connect()
    assert channel.closed


def test_missing_credentials_and_real_rights_fail_before_network(monkeypatch, tmp_path):
    def forbidden():
        raise AssertionError("Network constructor reached")

    monkeypatch.setattr("tb.ingest.broker.ctrader.DemoJsonChannel", forbidden)
    source = CTraderQuoteSource(CTraderSettings(), fixture_rights(), root=tmp_path)
    with pytest.raises(BrokerRefused):
        source.connect()
    source = CTraderQuoteSource(fixture_settings(), fixture_rights(), root=tmp_path)
    with pytest.raises(BrokerRefused):
        source.connect()
    with pytest.raises(ValidationError):
        CTraderSettings(requested_scope="trading")


def test_permission_escalation_on_reverification_disconnects(tmp_path):
    source, clock, channel, _identity, _contract, _quote = one_quote(tmp_path)
    clock.now += timedelta(seconds=20)

    def changed(kind, payload):
        result = responder(kind, payload)
        if kind == 2149:
            result["permissionScope"] = 1
        return result

    channel.responder = changed
    with pytest.raises(BrokerRefused):
        source.read()
    assert channel.closed and source._book.sides == {}


@pytest.mark.parametrize("kind", sorted(FATAL_EVENTS | {9999}))
def test_revocation_symbol_change_and_unexpected_events_stop(tmp_path, kind):
    source, _clock, channel = fixture_source(tmp_path, [{"payloadType": kind, "payload": {}}])
    source.connect()
    with pytest.raises(BrokerRefused):
        source.read()
    assert channel.closed


def test_source_rights_revocation_and_expired_tokens(tmp_path):
    source, clock, channel = fixture_source(tmp_path)
    source.connect()
    source.rights = source.rights.model_copy(update={"version": "changed"})
    with pytest.raises(BrokerRefused):
        source.read()
    assert channel.closed
    source, clock, channel = fixture_source(tmp_path)
    clock.now = fixture_settings().access_expires_at
    with pytest.raises(BrokerRefused):
        source.connect()
    assert not channel.calls


def test_partial_updates_keep_original_counterpart_times_and_values(tmp_path):
    events = [
        spot("EURUSD", 0, bid=110000),
        spot("EURUSD", 1000, ask=110002),
        spot("EURUSD", 2000, bid=110001),
        spot("EURUSD", 3000, ask=110003),
    ]
    source, _clock, _channel = fixture_source(tmp_path, events)
    source.connect()
    assert source.read() is None
    first = source.read()
    second = source.read()
    third = source.read()
    assert first.bid_source_at == START and first.ask_source_at == START + timedelta(seconds=1)
    assert second.ask_source_at == first.ask_source_at
    assert third.bid_source_at == second.bid_source_at
    assert third.spread == Decimal("0.00002")
    assert third.raw_event == {
        "symbolId": 101,
        "timestamp": int((START + timedelta(seconds=3)).timestamp() * 1000),
        "ask": 110003,
    }
    assert third.source_sequence is None
    source.close()


def test_gaps_clear_sides_and_duplicate_updates_do_not_renew_them(tmp_path):
    e = spot("EURUSD", 0, bid=110000)
    events = [e, deepcopy(e), spot("EURUSD", 6000, ask=110002), spot("EURUSD", 7000, bid=110000)]
    source, _clock, _channel = fixture_source(tmp_path, events)
    source.connect()
    assert source.read() is None
    assert source.read() is None and source.reason == "duplicate_raw_update"
    assert source.read() is None  # Initial bid expired across the gap.
    quote = source.read()
    assert quote.bid_source_at == START + timedelta(seconds=7)
    source.close()


@pytest.mark.parametrize(
    "case",
    [
        "crossed",
        "zero",
        "future",
        "stale",
        "seconds",
        "missing_time",
        "wrong_account",
        "wrong_symbol",
        "precision",
        "float",
    ],
)
def test_invalid_quotes_fail_closed_and_clear_book(tmp_path, case):
    event = spot("EURUSD", 1000, bid=110000, ask=110002)
    p = event["payload"]
    if case == "crossed":
        p["bid"] = 110003
    if case == "zero":
        p["bid"] = 0
    if case == "future":
        event["_received_at"] = START
    if case == "stale":
        event["_received_at"] += timedelta(seconds=6)
    if case == "seconds":
        p["timestamp"] //= 1000
    if case == "missing_time":
        p.pop("timestamp")
    if case == "wrong_account":
        p["ctidTraderAccountId"] = 888
    if case == "wrong_symbol":
        p["symbolId"] = 999
    if case == "precision":
        p.update(symbolId=202, bid=240000001, ask=240020000)
    if case == "float":
        p["bid"] = 110000.0
    source, _clock, channel = fixture_source(tmp_path, [event])
    source.connect()
    with pytest.raises(BrokerRefused):
        source.read()
    assert channel.closed and source._book.sides == {}


def test_out_of_order_update_is_not_relabelled_forward(tmp_path):
    source, _clock, _channel = fixture_source(
        tmp_path,
        [
            spot("EURUSD", 2000, bid=110000, ask=110002),
            spot("EURUSD", 1000, bid=110000, ask=110002),
        ],
    )
    source.connect()
    assert source.read()
    with pytest.raises(BrokerRefused):
        source.read()


def test_market_closed_and_unknown_holidays_are_not_guessed(tmp_path):
    source, clock, _channel, identity, contract, quote = one_quote(tmp_path)
    for change in [
        {"schedule": ((172800, 259200),)},
        {"holidays": None},
        {"holidays": ({"name": "owned closure"},)},
    ]:
        c = BrokerContract.model_validate({**contract.model_dump(), **change})
        with pytest.raises(BrokerRefused):
            QuoteBook().accept(quote.raw_event, c, identity, clock(), source.rights.digest)
    source.close()


@pytest.mark.parametrize(
    "symbol,units,capital",
    [("EURUSD", Decimal(1000), Decimal("1100.02000")), ("XAUUSD", Decimal(1), Decimal("2400.2"))],
)
def test_protocol_cents_and_independent_100_funded_rejection(tmp_path, symbol, units, capital):
    source, clock, _channel, _identity, contract, quote = one_quote(tmp_path, symbol)
    assert contract.min_units == units
    result = qualify(contract, quote, now=clock(), bundle=load_policy_bundle())
    assert result.minimum_notional == capital and result.funded_minimum_affordable is False
    assert result.market_data_ready and not result.costs_ready and not result.contract_ready
    assert (
        not result.local_simulation_ready and not result.legal_eligible and result.p11b2 == "NO-GO"
    )
    source.close()


def test_tick_arithmetic_and_cost_currency_contradictions(tmp_path):
    source, clock, _channel, _identity, contract, quote = one_quote(tmp_path)
    data = contract.model_dump()
    data.update(
        tick_value_currency="USD", reported_tick_size="0.00001", reported_tick_value_per_lot="2"
    )
    with pytest.raises(ValidationError):
        BrokerContract.model_validate(data)
    data["reported_tick_value_per_lot"] = "1"
    valid = BrokerContract.model_validate(data)
    assert valid.lot_units * valid.tick_size == 1
    costs = CostEvidence(
        account_fingerprint=contract.account_fingerprint,
        contract_digest=contract.digest,
        account_currency="EUR",
        round_trip_reserve=0,
        basis="OWNED explicit zero reserve",
        evidence_reference="owned-only",
        evidence="owned_fixture",
        verified=True,
        observed_at=START,
        expires_at=START + timedelta(days=1),
    )
    assert not qualify(
        contract, quote, now=clock(), bundle=load_policy_bundle(), costs=costs
    ).costs_ready
    source.close()


def test_alignment_is_causal_separates_sources_and_never_uses_midpoints(tmp_path):
    source, clock, _channel, _identity, _contract, quote = one_quote(tmp_path)
    decision = fixture_decision("EURUSD")
    result = align_reference(
        decision, quote, now=clock(), reference_rights=fixture_rights(reference=True)
    )
    assert result.status == "observed" and not result.creates_execution
    assert result.decision_at == decision.decision_at and result.broker_provider != "twelve_data"
    assert result.spread == quote.ask - quote.bid
    # Move only decision availability forward; no quote backdating or midpoint substitution.
    later = decision.model_copy(update={"decision_at": clock()})
    result = align_reference(
        later, quote, now=clock(), reference_rights=fixture_rights(reference=True)
    )
    assert result.status == "unavailable" and result.quote_id is None
    other = align_reference(
        fixture_decision("XAUUSD"),
        quote,
        now=clock(),
        reference_rights=fixture_rights(reference=True),
    )
    assert other.reason == "reference_broker_instrument_mismatch"
    source.close()


@pytest.mark.parametrize("value", [True, False, 1.0, "1e3", "nan", "-1", None])
def test_integer_fields_are_not_lossily_coerced(value):
    with pytest.raises(BrokerRefused):
        integer(value)


def test_every_non_read_message_type_and_extra_field_is_refused():
    for kind in range(2100, 2200):
        if kind not in READ_FIELDS:
            with pytest.raises(BrokerRefused):
                validate_request(kind, {})
    with pytest.raises(BrokerRefused):
        validate_request(2121, {"ctidTraderAccountId": 777, "volume": 100})
    with pytest.raises(BrokerRefused):
        validate_request(
            2127, {"ctidTraderAccountId": 777, "symbolId": [101], "subscribeToSpotTimestamp": False}
        )
    for name in ["submit_order", "amend_order", "order_send", "execute", "trade"]:
        assert not hasattr(CTraderQuoteSource, name)


def test_midpoint_disagreement_never_changes_broker_sides(tmp_path):
    source, clock, _channel, _identity, _contract, quote = one_quote(tmp_path)
    decision = fixture_decision("EURUSD").model_copy(
        update={"features": {"reference_midpoint": 9.99}}
    )
    before = quote.model_dump_json()
    link = align_reference(
        decision, quote, now=clock(), reference_rights=fixture_rights(reference=True)
    )
    assert link.quote_id == quote.event_id and link.spread == Decimal("0.00002")
    assert quote.model_dump_json() == before
    assert not any(
        k in link.model_dump() for k in ["fill", "commission", "pnl", "position", "quantity"]
    )
    source.close()


def test_later_alignment_and_missing_costs_do_not_become_ready(tmp_path):
    source, clock, _channel, _identity, contract, quote = one_quote(tmp_path)
    clock.now += timedelta(seconds=6)
    result = qualify(contract, quote, now=clock(), bundle=load_policy_bundle())
    assert not result.market_data_ready and result.minimum_notional is None
    link = align_reference(
        fixture_decision("EURUSD"),
        quote,
        now=clock(),
        reference_rights=fixture_rights(reference=True),
    )
    assert link.status == "unavailable"
    source.close()
