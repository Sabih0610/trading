"""Owned-only carry, fresh metadata, recovery and holding-deadline fixtures."""

from datetime import timedelta
from decimal import Decimal as D

import pytest

from tb.core.instruments import MarketQuote
from tb.paper.metadata import OwnedSpecRefresh, apply_owned_spec_refresh, spec_digest
from tb.paper.offline.fixtures import START, package, tick
from tb.paper.offline.models import VERSION, PaperContractRefresh, PaperInput, PaperRefused, digest
from tb.paper.offline.store import PaperStore
from tb.paper.simulation import LocalPaperSimulator, SimulatedCandidate
from tb.risk.config import load_policy_bundle
from tb.risk.guards import RiskViolation
from tb.shadow.models import ResearchDecision

T = START + timedelta(minutes=8)


def buy(p, at=T, *, flat=False, days=None, lots=D(".01")):
    features = {"reference_close": 1.1}
    decision = ResearchDecision(
        id=digest(["owned-multi-day", at]),
        event_id=digest(["owned-event", at]),
        evidence_id=digest("owned-multi-day"),
        mode="fixture_replay",
        provider="owned_fixture",
        symbol="EURUSD",
        strategy=p.strategy,
        strategy_version=p.reference_strategy_version,
        feature_version=p.reference_feature_version,
        source_open_at=at - timedelta(minutes=7),
        source_close_at=at - timedelta(minutes=2),
        received_at=at - timedelta(milliseconds=1),
        information_available_at=at - timedelta(milliseconds=1),
        decision_at=at,
        signal="BUY",
        status="candidate",
        reasons=("controlled_owned_holding_case",),
        features=features,
        features_sha256=digest(features),
        rights_digest=p.reference_rights_digest,
        source_version=VERSION,
        consumer_version=VERSION,
        runtime_milliseconds=0,
    )
    return PaperInput(
        kind="decision",
        symbol="EURUSD",
        received_at=at,
        decision=decision,
        stop=D("1.09"),
        target=D("1.2"),
        requested_lots=lots,
        flat_by_end_of_day=flat,
        max_holding_days=days,
    )


def opened(folder, *, flat=False, days=None):
    p = package()
    store = PaperStore(folder, p, load_policy_bundle(), create=True)
    store.process(tick(p, T, D("1.1")))
    store.process(buy(p, T + timedelta(milliseconds=1), flat=flat, days=days))
    store.process(tick(p, T + timedelta(seconds=1), D("1.1")))
    assert store.state.accounts["ENG10000"].position is not None
    return p, store


def refresh_event(previous, at, *, observation_id=None):
    # These are explicitly supplied fictional independent source observations.
    observed = at - timedelta(milliseconds=1)
    current = previous.model_copy(
        update={
            "spec": previous.spec.model_copy(update={"observed_at": observed}),
            "metadata": previous.metadata.model_copy(update={"observed_at": observed}),
            "conversion": previous.conversion.model_copy(update={"observed_at": observed}),
        }
    )
    refresh = PaperContractRefresh(
        observation_id=observation_id or digest(["owned-observation", at]),
        previous_digest=digest(previous.model_dump(mode="json")),
        known_at=at,
        contract=current,
    )
    return PaperInput(kind="metadata", symbol="EURUSD", received_at=at, metadata_refresh=refresh)


@pytest.mark.parametrize("holding_days", [1, 3, 10])
def test_offline_ten_day_deadline_with_explicit_fresh_observations_and_restart(
    tmp_path, holding_days
):
    p, store = opened(tmp_path, days=holding_days)
    entered = T + timedelta(seconds=1)
    previous = p.contracts["EURUSD"]
    try:
        for day in range(1, holding_days + 1):
            quote_at = entered + timedelta(days=day)
            refresh = refresh_event(previous, quote_at - timedelta(milliseconds=1))
            assert store.process(refresh) == "committed"
            previous = refresh.metadata_refresh.contract
            store.close()
            store = PaperStore(tmp_path, p, load_policy_bundle())
            assert store.state.metadata_overrides["EURUSD"] == previous
            assert store.process(refresh) == "duplicate"
            store.process(tick(p, quote_at, D("1.1")))
            account = store.state.accounts["ENG10000"]
            if day < holding_days:
                assert account.position is not None
                assert account.position.entered_at == entered
            else:
                assert account.position is None and account.completed_trades == 1
        closed = [
            e
            for e in store.effects()
            if e.get("account") == "ENG10000" and e["kind"] == "position_closed"
        ]
        assert len(closed) == 1 and closed[0]["reason"] == "max_holding_days"
        assert len(store.state.metadata_observations) == holding_days
        before = store.state.model_dump_json()
        store.close()
        store = PaperStore(tmp_path, p, load_policy_bundle())
        assert store.state.model_dump_json() == before
    finally:
        store.close()


@pytest.mark.parametrize(
    "stage", ["after_reduce", "after_ledger", "after_checkpoint", "after_commit"]
)
def test_refresh_checkpoint_crash_recovery_is_atomic_before_next_quote(tmp_path, stage):
    p, store = opened(tmp_path)
    at = T + timedelta(days=1)
    refresh = refresh_event(p.contracts["EURUSD"], at)

    def crash(point):
        if point == stage:
            raise RuntimeError("owned simulated crash")

    with pytest.raises(RuntimeError, match="owned simulated crash"):
        store.process(refresh, fault=crash)
    store.close()
    store = PaperStore(tmp_path, p, load_policy_bundle())
    try:
        assert store.process(refresh) in {"duplicate", "committed"}
        store.process(tick(p, at + timedelta(milliseconds=1), D("1.1")))
        assert store.state.accounts["ENG10000"].position is not None
        assert len(store.state.metadata_observations) == 1
    finally:
        store.close()


@pytest.mark.parametrize(
    "damage",
    [
        "future_known",
        "future_spec",
        "stale_spec",
        "wrong_digest",
        "wrong_units",
        "wrong_account",
        "wrong_cost",
        "wrong_session",
        "wrong_currency",
    ],
)
def test_offline_refresh_refuses_clock_provenance_or_fact_changes(tmp_path, damage):
    p, store = opened(tmp_path)
    at = T + timedelta(hours=23)
    good = refresh_event(p.contracts["EURUSD"], at)
    refresh = good.metadata_refresh
    contract = refresh.contract
    if damage == "future_known":
        refresh = refresh.model_copy(update={"known_at": at + timedelta(seconds=1)})
    if damage == "future_spec":
        contract = contract.model_copy(
            update={
                "spec": contract.spec.model_copy(update={"observed_at": at + timedelta(seconds=1)})
            }
        )
    if damage == "stale_spec":
        contract = contract.model_copy(
            update={"spec": contract.spec.model_copy(update={"observed_at": START})}
        )
    if damage == "wrong_digest":
        refresh = refresh.model_copy(update={"previous_digest": "0" * 64})
    if damage == "wrong_units":
        contract = contract.model_copy(
            update={"spec": contract.spec.model_copy(update={"contract_size": D(10)})}
        )
    if damage == "wrong_account":
        contract = contract.model_copy(
            update={
                "metadata": contract.metadata.model_copy(update={"account_fingerprint": "0" * 64})
            }
        )
    if damage == "wrong_cost":
        contract = contract.model_copy(
            update={"spec": contract.spec.model_copy(update={"fee_bps": D(2)})}
        )
    if damage == "wrong_session":
        contract = contract.model_copy(
            update={"metadata": contract.metadata.model_copy(update={"schedule": ((0, 1),)})}
        )
    if damage == "wrong_currency":
        contract = contract.model_copy(
            update={"conversion": contract.conversion.model_copy(update={"quote_currency": "EUR"})}
        )
    refresh = refresh.model_copy(update={"contract": contract})
    event = good.model_copy(update={"metadata_refresh": refresh})
    original = store.state.model_dump_json()
    with pytest.raises((PaperRefused, RiskViolation, ValueError)):
        store.process(event)
    store.close()
    store = PaperStore(tmp_path, p, load_policy_bundle())
    assert store.state.model_dump_json() == original
    store.close()


def test_reused_observation_id_cannot_extend_freshness(tmp_path):
    p, store = opened(tmp_path)
    at = T + timedelta(hours=23)
    first = refresh_event(p.contracts["EURUSD"], at)
    store.process(first)
    previous = first.metadata_refresh.contract
    second = refresh_event(
        previous, at + timedelta(hours=1), observation_id=first.metadata_refresh.observation_id
    )
    try:
        with pytest.raises(PaperRefused, match="owned_metadata"):
            store.process(second)
    finally:
        store.close()


def test_missing_refresh_does_not_waive_24_hour_metadata_guard(tmp_path):
    p, store = opened(tmp_path)
    try:
        store.process(tick(p, T + timedelta(days=2), D("1.1")))
        assert store.state.accounts["ENG10000"].position is not None
        assert store.state.accounts["ENG10000"].equity is None
        assert any(
            e["reason"] == "quote_clock_price_session_or_metadata_refused" for e in store.effects()
        )
    finally:
        store.close()


@pytest.mark.parametrize("flat", [False, True])
def test_local_simulator_ten_day_deadline_requires_explicit_fresh_metadata(tmp_path, flat):
    p = package()
    spec = p.contracts["EURUSD"].spec
    entered = T + timedelta(seconds=1)
    times = [T, entered] + [entered + timedelta(days=d) for d in range(1, 11)]
    quotes = [
        MarketQuote(symbol="EURUSD", timestamp=t, bid=D("1.1"), ask=D("1.10002")) for t in times
    ]
    conversions = [
        p.contracts["EURUSD"].conversion.model_copy(update={"observed_at": t}) for t in times
    ]
    candidate = SimulatedCandidate(
        symbol="EURUSD",
        timestamp=T,
        stop=D("1.09"),
        target=D("1.2"),
        requested_lots=D(".01"),
        flat_by_end_of_day=flat,
    )
    observations = []
    previous = spec
    for at in times[2:]:
        current = previous.model_copy(update={"observed_at": at})
        observations.append(
            OwnedSpecRefresh(
                observation_id=digest(["owned-spec-observation", at]),
                previous_digest=spec_digest(previous),
                known_at=at,
                spec=current,
            )
        )
        previous = current
    result = LocalPaperSimulator(
        "EURUSD", spec, initial_cash=D(10000), ledger_path=tmp_path / "owned.sqlite"
    ).run(quotes, [candidate], conversions, metadata_refreshes=observations)
    assert len(result.trades) == 1
    assert result.trades[0].entry_time == entered
    assert result.trades[0].exit_reason == ("end_of_day" if flat else "max_holding_days")
    assert result.trades[0].exit_time == (entered if flat else entered + timedelta(days=10))


def test_local_missing_metadata_refresh_refuses_instead_of_restamping(tmp_path):
    p = package()
    spec = p.contracts["EURUSD"].spec
    times = [T, T + timedelta(seconds=1), T + timedelta(days=1)]
    quotes = [
        MarketQuote(symbol="EURUSD", timestamp=t, bid=D("1.1"), ask=D("1.10002")) for t in times
    ]
    conversions = [
        p.contracts["EURUSD"].conversion.model_copy(update={"observed_at": t}) for t in times
    ]
    candidate = SimulatedCandidate(
        symbol="EURUSD",
        timestamp=T,
        stop=D("1.09"),
        target=D("1.2"),
        requested_lots=D(".01"),
        flat_by_end_of_day=False,
    )
    with pytest.raises(RiskViolation, match="stale"):
        LocalPaperSimulator(
            "EURUSD", spec, initial_cash=D(10000), ledger_path=tmp_path / "owned.sqlite"
        ).run(quotes, [candidate], conversions)


def test_spec_refresh_refuses_genuine_provenance_and_future_observation():
    spec = package().contracts["EURUSD"].spec
    at = T + timedelta(hours=1)
    good = OwnedSpecRefresh(
        observation_id=digest("owned-refresh"),
        previous_digest=spec_digest(spec),
        known_at=at,
        spec=spec.model_copy(update={"observed_at": at}),
    )
    assert apply_owned_spec_refresh(spec, good, at).observed_at == at
    with pytest.raises(RiskViolation):
        apply_owned_spec_refresh(spec, good, at - timedelta(seconds=1))
    with pytest.raises(RiskViolation):
        apply_owned_spec_refresh(spec.model_copy(update={"synthetic": False}), good, at)


@pytest.mark.parametrize("gap,reason", [(D(".8"), "daily_loss"), (D(".4"), "peak_drawdown")])
def test_offline_overnight_gap_uses_previous_liquidation_anchor(tmp_path, gap, reason):
    p, store = opened(tmp_path)
    previous = store.state.accounts["ENG10000"].equity
    at = START + timedelta(hours=23)
    try:
        store.process(tick(p, at, gap))
        account = store.state.accounts["ENG10000"]
        assert account.position is None
        assert account.safety.day_start == previous
        assert any(
            e["kind"] == "risk_shutdown"
            and e["reason"] == reason
            and e.get("account") == "ENG10000"
            for e in store.effects()
        )
        if reason == "daily_loss":
            assert account.safety.daily_halted
        else:
            assert account.safety.peak_halted
    finally:
        store.close()


@pytest.mark.parametrize("gap,reason", [(D(".8"), "daily_loss"), (D(".4"), "peak_drawdown")])
def test_local_overnight_gap_halts_and_closes_at_actual_adverse_quote(tmp_path, gap, reason):
    p = package()
    spec = p.contracts["EURUSD"].spec
    times = [T, T + timedelta(seconds=1), START + timedelta(hours=23)]
    prices = [D("1.1"), D("1.1"), gap]
    quotes = [
        MarketQuote(symbol="EURUSD", timestamp=t, bid=v, ask=v + D(".00002"))
        for t, v in zip(times, prices, strict=True)
    ]
    conversions = [
        p.contracts["EURUSD"].conversion.model_copy(update={"observed_at": t}) for t in times
    ]
    candidate = SimulatedCandidate(
        symbol="EURUSD",
        timestamp=T,
        stop=D("1.09"),
        target=D("1.2"),
        requested_lots=D(".01"),
        flat_by_end_of_day=False,
    )
    result = LocalPaperSimulator(
        "EURUSD", spec, initial_cash=D(10000), ledger_path=tmp_path / "owned.sqlite"
    ).run(quotes, [candidate], conversions)
    assert len(result.trades) == 1 and result.trades[0].exit_time == times[-1]
    assert result.trades[0].exit_reason == reason
    assert result.trades[0].exit_price == spec.exit_price(gap)
    assert reason in result.shutdowns


@pytest.mark.parametrize("flat", [False, True])
def test_eod_clock_cancels_only_globally_or_proposal_required_orders(tmp_path, flat):
    p = package()
    store = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    at = T  # An admitted EURUSD entry session; clock semantics are tested explicitly.
    try:
        store.process(tick(p, at, D("1.1")))
        store.process(buy(p, at + timedelta(milliseconds=1), flat=flat))
        pending = [
            order
            for order in store.state.accounts["ENG10000"].orders.values()
            if order.purpose == "entry" and order.status == "pending"
        ]
        assert len(pending) == 1 and pending[0].lots > 0
        store.process(
            PaperInput(
                kind="clock",
                symbol="EURUSD",
                received_at=at + timedelta(milliseconds=500),
                reason="end_of_day",
            )
        )
        store.process(tick(p, at + timedelta(seconds=1), D("1.1")))
        account = store.state.accounts["ENG10000"]
        assert (account.position is not None) is (not flat)
        assert any(o.status == "cancelled" for o in account.orders.values()) is flat
    finally:
        store.close()


def test_metadata_known_at_chain_cannot_regress_even_with_newer_source_observation(tmp_path):
    p, store = opened(tmp_path)
    at = T + timedelta(hours=23)
    first = refresh_event(p.contracts["EURUSD"], at)
    store.process(first)
    previous = first.metadata_refresh.contract
    fresh_observed = at - timedelta(microseconds=500)
    current = previous.model_copy(
        update={
            "spec": previous.spec.model_copy(update={"observed_at": fresh_observed}),
            "metadata": previous.metadata.model_copy(update={"observed_at": fresh_observed}),
            "conversion": previous.conversion.model_copy(update={"observed_at": fresh_observed}),
        }
    )
    backwards = PaperContractRefresh(
        observation_id=digest("owned-backward-known"),
        previous_digest=digest(previous.model_dump(mode="json")),
        known_at=at - timedelta(microseconds=250),
        contract=current,
    )
    event = PaperInput(
        kind="metadata",
        symbol="EURUSD",
        received_at=at + timedelta(seconds=1),
        metadata_refresh=backwards,
    )
    try:
        with pytest.raises(PaperRefused, match="owned_metadata_chain"):
            store.process(event)
    finally:
        store.close()


@pytest.mark.parametrize("flat", [False, True])
def test_late_eur_usd_fixture_remains_refused_outside_entry_sessions(tmp_path, flat):
    p = package()
    store = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    at = T.replace(hour=23, minute=59, second=59, microsecond=0)
    try:
        store.process(tick(p, at, D("1.1")))
        store.process(buy(p, at + timedelta(milliseconds=1), flat=flat))
        account = store.state.accounts["ENG10000"]
        assert account.position is None and account.fill_count == 0
        assert all(order.status == "rejected" for order in account.orders.values())
        assert any(
            effect.get("account") == "ENG10000"
            and effect["reason"] == "EURUSD is outside all configured entry sessions"
            for effect in store.effects()
        )
    finally:
        store.close()
