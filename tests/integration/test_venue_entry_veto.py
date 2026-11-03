"""Optional fixture-only entry veto cannot alter owned inventory exit processing."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.ingest.venue_status import VenueBook, VenueRefused, VetoDecision
from tb.paper.offline.engine import PaperReducer
from tb.paper.offline.fixtures import package, tick
from tb.paper.offline.models import PaperInput
from tb.paper.simulation import LocalPaperSimulator, size_candidate
from tb.paper.smoke import fixture_market
from tb.risk.config import load_policy_bundle

from .test_offline_paper import T, decision


def block(symbol, at, *, evidence="owned_fixture"):
    return VetoDecision(
        symbol=symbol,
        at=at,
        veto=True,
        reason="venue_not_trading",
        known_at=at,
        raw_status="HALT",
        evidence=evidence,
    )


def test_optional_shared_sizing_hook_only_reduces_risk_permission():
    spec, quotes, conversions, candidates = fixture_market("EURUSD")
    quote, conversion, candidate = quotes[1], conversions[1], candidates[0]
    args = dict(
        now=quote.timestamp,
        equity=Decimal("10000"),
        cash=Decimal("10000"),
        day_start=Decimal("10000"),
        peak=Decimal("10000"),
        bundle=load_policy_bundle(),
    )
    ordinary = size_candidate(candidate, spec, quote, conversion, **args)
    vetoed = size_candidate(
        candidate,
        spec,
        quote,
        conversion,
        **args,
        venue_veto=block(candidate.symbol, quote.timestamp),
    )
    assert ordinary.approved
    assert not vetoed.approved and vetoed.lots == 0 and vetoed.planned_loss == 0
    allowed = VetoDecision(
        symbol=candidate.symbol,
        at=quote.timestamp,
        veto=False,
        reason="venue_trading",
        known_at=quote.timestamp,
        raw_status="TRADING",
        evidence="owned_fixture",
    )
    assert (
        size_candidate(candidate, spec, quote, conversion, **args, venue_veto=allowed) == ordinary
    )


def test_persistent_owned_lab_veto_blocks_proposal_and_next_event_fill():
    p = package()
    bundle = load_policy_bundle()
    reducer = PaperReducer(p, bundle)
    reducer.apply(tick(p, T, Decimal("1.1")))
    proposed = decision(p, T + timedelta(milliseconds=1))
    proposed = proposed.model_copy(
        update={"venue_veto": block(proposed.symbol, proposed.received_at)}
    )
    state, effects = reducer.apply(proposed)
    assert state.accounts["ENG10000"].reserved == 0
    assert any(e.get("reason") == "venue_not_trading" for e in effects)
    assert state.accounts["ENG10000"].fill_count == 0
    reducer = PaperReducer(p, bundle)
    reducer.apply(tick(p, T, Decimal("1.1")))
    reducer.apply(decision(p, T + timedelta(milliseconds=1)))
    incoming = tick(p, T + timedelta(seconds=1), Decimal("1.1"))
    incoming = incoming.model_copy(
        update={"venue_veto": block(incoming.symbol, incoming.received_at)}
    )
    state, effects = reducer.apply(incoming)
    assert state.accounts["ENG10000"].position is None
    assert state.accounts["ENG10000"].fill_count == 0
    assert any(e.get("reason") == "venue_not_trading" for e in effects)


@pytest.mark.parametrize("exit_kind", ["stop", "signal"])
def test_veto_never_prevents_owned_long_exit_or_forces_a_sale(exit_kind):
    p = package()
    reducer = PaperReducer(p, load_policy_bundle())
    reducer.apply(tick(p, T, Decimal("1.1")))
    reducer.apply(decision(p, T + timedelta(milliseconds=1)))
    reducer.apply(tick(p, T + timedelta(seconds=1), Decimal("1.1")))
    assert reducer.state.accounts["ENG10000"].position is not None
    hold = tick(p, T + timedelta(seconds=2), Decimal("1.1"))
    hold = hold.model_copy(update={"venue_veto": block(hold.symbol, hold.received_at)})
    state, _ = reducer.apply(hold)
    assert state.accounts["ENG10000"].position is not None  # HALT never forces a sale
    if exit_kind == "signal":
        sell = decision(p, T + timedelta(seconds=3), "SELL")
        sell = sell.model_copy(update={"venue_veto": block(sell.symbol, sell.received_at)})
        reducer.apply(sell)
        exit_quote = tick(p, T + timedelta(seconds=4), Decimal("1.101"))
    else:
        exit_quote = tick(p, T + timedelta(seconds=3), Decimal("1.09"))
    exit_quote = exit_quote.model_copy(
        update={"venue_veto": block(exit_quote.symbol, exit_quote.received_at)}
    )
    state, _ = reducer.apply(exit_quote)
    account = state.accounts["ENG10000"]
    assert account.position is None and account.completed_trades == 1 and account.fill_count == 2


def test_owned_lab_cannot_admit_live_provider_status_facts():
    with pytest.raises(ValidationError, match="provenance"):
        PaperInput(
            kind="clock",
            symbol="EURUSD",
            received_at=T,
            venue_veto=block("EURUSD", T, evidence="public_api"),
        )


def test_historical_contract_replay_refuses_current_venue_book_before_ledger(tmp_path):
    spec, _, _, _ = fixture_market("EURUSD")
    genuine = spec.model_copy(update={"synthetic": False})
    with pytest.raises(VenueRefused, match="historical"):
        LocalPaperSimulator(
            "EURUSD",
            genuine,
            initial_cash=Decimal("10000"),
            ledger_path=tmp_path / "should-not-exist.sqlite",
            venue=VenueBook(),
        )
    assert not (tmp_path / "should-not-exist.sqlite").exists()
