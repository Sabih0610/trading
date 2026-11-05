"""Independent audit tests for trading-rule and risk enforcement (Claude full audit).

These tests deliberately do not reuse Codex fixtures beyond public constructors. Tests that
demonstrate a real defect are kept as strict xfails tagged ``FINDING R-n``.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

import tb.backtest.engine as bt_engine
from tb.agents.schemas import ArenaAction, ArenaAnswer
from tb.backtest.costs import CostAssumptions
from tb.backtest.engine import BacktestEngine, Bar, EntrySignal
from tb.paper.simulation import size_candidate
from tb.paper.smoke import fixture_market
from tb.risk.account import AccountCircuitBreaker, SafetyState
from tb.risk.config import (
    MAX_DAILY_LOSS_PCT,
    MAX_RISK_PER_TRADE_PCT,
    AssetRegistry,
    PolicyBundle,
    RiskLimits,
    RiskOverride,
    effective_risk_limits,
    load_policy_bundle,
)
from tb.risk.guards import (
    OrderIntent,
    OrderSide,
    RiskViolation,
    assert_long_only,
    check_daily_loss,
    check_exposure,
    check_trade_count,
)
from tb.risk.manager import EntryRequest, RejectionCode, RiskManager, RiskState

BUNDLE = load_policy_bundle()
WEDNESDAY_NOON = datetime(2024, 1, 3, 12, tzinfo=UTC)
SATURDAY_NOON = datetime(2024, 1, 6, 12, tzinfo=UTC)
D = Decimal
DEFAULT_EQUITY = D(10000)


def _state(equity: Decimal = DEFAULT_EQUITY, **changes: Any) -> RiskState:
    data: dict[str, Any] = dict(
        equity=equity,
        cash=equity,
        current_exposure=D(0),
        current_holdings=D(0),
        realized_pnl_day=D(0),
        start_of_day_equity=equity,
        completed_trades_today=0,
    )
    data.update(changes)
    return RiskState(**data)


def _req(symbol: str = "XAUTUSDT", ts: datetime = WEDNESDAY_NOON, **changes: Any) -> EntryRequest:
    data: dict[str, Any] = dict(
        symbol=symbol, timestamp=ts, entry_price=D(2000), stop_price=D(1990)
    )
    data.update(changes)
    return EntryRequest(**data)


def _bundle_with_asset_changes(symbol: str, **changes: Any) -> PolicyBundle:
    raw = BUNDLE.registry.model_dump(mode="python")
    for asset in raw["assets"]:
        if asset["symbol"] == symbol:
            for key, value in changes.items():
                if isinstance(value, dict) and isinstance(asset.get(key), dict):
                    asset[key] = {**asset[key], **value}
                else:
                    asset[key] = value
    return PolicyBundle(registry=AssetRegistry.model_validate(raw), risk=BUNDLE.risk)


# ---------------------------------------------------------------------------
# Config ceilings: nothing in config may widen AGENTS.md hard caps.
# ---------------------------------------------------------------------------


def test_shipped_config_enforces_tighter_research_defaults() -> None:
    limits = BUNDLE.risk.limits
    assert limits.risk_per_trade_pct == D("0.5")
    assert limits.daily_loss_limit_pct == D("2.0")
    assert limits.max_peak_drawdown_pct == D("5.0")
    assert limits.max_open_positions == 1
    assert limits.max_total_exposure_multiple == D("1.0")
    xaut = effective_risk_limits(BUNDLE.registry.asset("XAUTUSDT"), limits)  # type: ignore[arg-type]
    assert xaut.risk_per_trade_pct == D("0.25")
    assert xaut.max_trades_per_day_per_asset == 2


_BASE_LIMITS = BUNDLE.risk.limits.model_dump()


@settings(max_examples=60, deadline=None)
@given(
    field=st.sampled_from(
        [
            ("risk_per_trade_pct", MAX_RISK_PER_TRADE_PCT),
            ("max_total_exposure_multiple", D(1)),
            ("daily_loss_limit_pct", MAX_DAILY_LOSS_PCT),
            ("max_peak_drawdown_pct", D(5)),
        ]
    ),
    excess=st.decimals(min_value=D("0.0001"), max_value=D(1000), places=4),
)
def test_risk_limits_cannot_exceed_hard_ceilings(
    field: tuple[str, Decimal], excess: Decimal
) -> None:
    name, ceiling = field
    with pytest.raises(ValidationError):
        RiskLimits.model_validate({**_BASE_LIMITS, name: ceiling + excess})


@pytest.mark.parametrize(
    "changes",
    [
        {"max_trades_per_day_per_asset": 4},
        {"max_open_positions": 2},
        # test changed because the owner changed the rule (AGENTS.md 2026-11-05)
        {"max_holding_days": 11},
        {"max_holding_days": 0},
        {"max_holding_days": 1.5},
        {"max_holding_days": True},
        {"allow_xaut_weekend_entries": True},
        {"risk_per_trade_pct": "NaN"},
        {"risk_per_trade_pct": "Infinity"},
        {"risk_per_trade_pct": "-0.1"},
        {"daily_loss_limit_pct": "0"},
    ],
)
def test_risk_limits_reject_widening_or_nonfinite(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RiskLimits.model_validate({**_BASE_LIMITS, **changes})


def test_asset_override_cannot_loosen_active_global_limit() -> None:
    # 0.75 is below the 1% hard cap but looser than the active 0.5% global value.
    with pytest.raises((ValidationError, ValueError)):
        _bundle_with_asset_changes("BTCUSDT", risk_overrides={"risk_per_trade_pct": "0.75"})
    with pytest.raises(ValidationError):
        RiskOverride(risk_per_trade_pct=D("1.01"))


# ---------------------------------------------------------------------------
# Long-only / spot-only boundary.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("market", ["margin", "futures", "SPOT_margin", "perp", " ", "usdm"])
def test_non_spot_market_is_rejected(market: str) -> None:
    try:
        decision = RiskManager(BUNDLE).evaluate_entry(_req(market=market), _state())
    except ValidationError:
        return  # blank market fails closed by exception (see R-3)
    assert not decision.approved and decision.quantity == 0


def test_sell_entry_is_rejected() -> None:
    decision = RiskManager(BUNDLE).evaluate_entry(_req(side=OrderSide.SELL), _state())
    assert decision.reason_code is RejectionCode.ENTRY_SIDE_INVALID and decision.quantity == 0


@pytest.mark.parametrize("symbol", ["XAUUSD", "EURUSD", "USDT", "DOGEUSDT", "BTCUSDT_PERP"])
def test_data_only_or_unknown_symbols_never_approved(symbol: str) -> None:
    try:
        decision = RiskManager(BUNDLE).evaluate_entry(_req(symbol=symbol), _state())
    except ValidationError:
        return  # fail-closed by exception is acceptable for this check
    assert not decision.approved


@settings(max_examples=200, deadline=None)
@given(
    holdings=st.decimals(min_value=0, max_value=10**6, places=8),
    extra=st.decimals(min_value=D("0.00000001"), max_value=10**6, places=8),
)
def test_selling_more_than_owned_is_always_refused(holdings: Decimal, extra: Decimal) -> None:
    with pytest.raises(RiskViolation):
        RiskManager.validate_inventory_sale("XAUTUSDT", holdings + extra, holdings)
    if holdings > 0:
        RiskManager.validate_inventory_sale("XAUTUSDT", holdings, holdings)


def test_negative_holdings_cannot_be_represented() -> None:
    with pytest.raises(ValidationError):
        OrderIntent(
            symbol="XAUTUSDT",
            side=OrderSide.SELL,
            quantity=D(1),
            current_holdings=D(-1),
            market="spot",
        )
    with pytest.raises(ValidationError):
        _state(current_holdings=D(-1))
    order = OrderIntent(symbol="XAUTUSDT", side=OrderSide.BUY, quantity=D(5), market="spot")
    assert assert_long_only(order) is order


# ---------------------------------------------------------------------------
# Sizing properties of the deterministic manager.
# ---------------------------------------------------------------------------


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    symbol=st.sampled_from(["XAUTUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]),
    equity=st.decimals(min_value=D("1"), max_value=D("10000000"), places=2),
    cash_fraction=st.decimals(min_value=D("0"), max_value=D("1"), places=4),
    entry=st.decimals(min_value=D("0.01"), max_value=D("200000"), places=4),
    stop_fraction=st.decimals(min_value=D("0.00001"), max_value=D("0.99"), places=5),
    requested=st.none() | st.decimals(min_value=D("0.00000001"), max_value=D("1000"), places=8),
    stress=st.decimals(min_value=D(1), max_value=D(3), places=2),
    price_is_fill=st.booleans(),
)
def test_approved_entry_never_exceeds_risk_cash_or_exposure(
    symbol: str,
    equity: Decimal,
    cash_fraction: Decimal,
    entry: Decimal,
    stop_fraction: Decimal,
    requested: Decimal | None,
    stress: Decimal,
    price_is_fill: bool,
) -> None:
    stop = entry * (1 - stop_fraction)
    assume(stop > 0)
    cash = equity * cash_fraction
    asset = BUNDLE.registry.asset(symbol)
    assert asset is not None
    costs = CostAssumptions.from_asset(asset, stress_multiplier=stress)
    try:
        costs.exit_price(stop)
    except ValueError:
        assume(False)
    limits = effective_risk_limits(asset, BUNDLE.risk.limits)
    decision = RiskManager(BUNDLE).evaluate_entry(
        _req(
            symbol=symbol,
            entry_price=entry,
            stop_price=stop,
            requested_quantity=requested,
            price_is_fill=price_is_fill,
        ),
        _state(equity, cash=cash),
        costs=costs,
    )
    if not decision.approved:
        assert decision.quantity == 0
        return
    fill = entry if price_is_fill else costs.entry_price(entry)
    # Tolerance of one part in 1e20 absorbs 28-digit Decimal context rounding (see R-4).
    tol = D("1.00000000000000000001")
    assert decision.quantity > 0
    assert decision.risk_amount <= equity * limits.risk_per_trade_pct / 100 * tol
    assert decision.quantity * fill + costs.fee(decision.quantity * fill) <= cash * tol
    assert decision.quantity * fill <= equity * limits.max_total_exposure_multiple
    if requested is not None:
        assert decision.quantity <= requested


@settings(max_examples=150, deadline=None)
@given(
    step=st.sampled_from([D("0.001"), D("0.01"), D("0.1"), D("0.00001")]),
    equity=st.decimals(min_value=D("100"), max_value=D("1000000"), places=2),
    max_qty=st.decimals(min_value=D("0.0001"), max_value=D("50"), places=4),
)
def test_exchange_rounding_never_rounds_size_up(
    step: Decimal, equity: Decimal, max_qty: Decimal
) -> None:
    bundle = _bundle_with_asset_changes(
        "BTCUSDT", exchange_rules={"step_size": step, "max_qty": max_qty}
    )
    unrounded = RiskManager(BUNDLE).evaluate_entry(
        _req(symbol="BTCUSDT", entry_price=D(50000), stop_price=D(49000)), _state(equity)
    )
    rounded = RiskManager(bundle).evaluate_entry(
        _req(symbol="BTCUSDT", entry_price=D(50000), stop_price=D(49000)), _state(equity)
    )
    if rounded.approved:
        assert rounded.quantity <= unrounded.quantity
        assert rounded.quantity <= max_qty
        assert rounded.quantity % step == 0


def test_unquantized_quantity_is_rounded_down_not_half_even() -> None:
    asset = BUNDLE.registry.asset("XAUTUSDT")
    assert asset is not None
    costs = CostAssumptions.from_asset(asset, stress_multiplier=D("2.37"))
    entry = D("0.0155")
    decision = RiskManager(BUNDLE).evaluate_entry(
        _req(entry_price=entry, stop_price=entry * (1 - D("0.00123"))),
        _state(D("1.11"), cash=D("1.11") * D("0.2455")),
        costs=costs,
    )
    assert decision.approved
    assert decision.risk_amount <= D("1.11") * D("0.25") / 100


# ---------------------------------------------------------------------------
# Daily loss, peak drawdown, trade count, open positions, kill switch.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"realized_pnl_day": D(-200)}, RejectionCode.DAILY_LOSS),  # exactly 2%
        ({"equity": D(9800)}, RejectionCode.DAILY_LOSS),  # unrealized 2% equity loss
        (
            {"peak_equity": D(10600), "equity": D(10070), "start_of_day_equity": D(10070)},
            RejectionCode.PEAK_DRAWDOWN,
        ),
        ({"completed_trades_today": 2}, RejectionCode.TRADE_COUNT),  # XAUT override = 2
        ({"open_positions": 1}, RejectionCode.POSITION_LIMIT),
        ({"current_holdings": D("0.00000001")}, RejectionCode.POSITION_LIMIT),
        ({"current_exposure": D("0.01")}, RejectionCode.POSITION_LIMIT),
        ({"kill_switch": True}, RejectionCode.KILL_SWITCH),
    ],
)
def test_each_halt_condition_rejects_xaut_entry(
    changes: dict[str, Any], code: RejectionCode
) -> None:
    base: dict[str, Any] = dict(equity=D(10000), cash=D(10000), start_of_day_equity=D(10000))
    base.update(changes)
    equity = base.pop("equity")
    decision = RiskManager(BUNDLE).evaluate_entry(_req(), _state(equity, **base))
    assert decision.reason_code is code
    assert decision.quantity == 0


def test_btc_trade_count_uses_global_three() -> None:
    rm = RiskManager(BUNDLE)
    req = _req(symbol="BTCUSDT", entry_price=D(50000), stop_price=D(49000))
    assert rm.evaluate_entry(req, _state(completed_trades_today=2)).approved
    assert (
        rm.evaluate_entry(req, _state(completed_trades_today=3)).reason_code
        is RejectionCode.TRADE_COUNT
    )


def test_guard_helpers_refuse_limits_above_hard_caps() -> None:
    with pytest.raises(RiskViolation):
        check_daily_loss(D(0), D(100), D("3.01"))
    with pytest.raises(RiskViolation):
        check_trade_count(0, 4)
    with pytest.raises(RiskViolation):
        check_exposure(D(0), D(1), D(1), D("1.0001"))
    with pytest.raises(RiskViolation):
        check_exposure(D(0), D("100.01"), D(100))


@settings(max_examples=150, deadline=None)
@given(
    drops=st.lists(
        st.decimals(min_value=D("-0.03"), max_value=D("0.03"), places=4), min_size=2, max_size=40
    ),
)
def test_circuit_breaker_latches(drops: list[Decimal]) -> None:
    limits = BUNDLE.risk.limits
    start = datetime(2024, 1, 1, tzinfo=UTC)
    breaker = AccountCircuitBreaker(
        SafetyState(day=start.date(), day_start=D(1000), peak=D(1000)), limits
    )
    equity = D(1000)
    peak_latched = False
    daily_latched_day = None
    for index, drop in enumerate(drops):
        now = start + timedelta(hours=6 * index)
        equity = max(equity * (1 + drop), D("0.01"))
        result = breaker.observe(now, equity)
        if result == "peak_drawdown":
            peak_latched = True
        if peak_latched:
            assert result == "peak_drawdown"  # never unlatches, even across days
        if result == "daily_loss":
            daily_latched_day = now.date()
        elif daily_latched_day == now.date() and not peak_latched:
            pytest.fail("daily halt released before UTC rollover")


# ---------------------------------------------------------------------------
# Weekend / timezone handling.
# ---------------------------------------------------------------------------


def test_xaut_weekend_entry_rejected_in_utc_and_offsets() -> None:
    rm = RiskManager(BUNDLE)
    assert (
        rm.evaluate_entry(_req(ts=SATURDAY_NOON), _state()).reason_code
        is RejectionCode.SESSION_POLICY
    )
    # Sunday 23:59 UTC is still weekend; expressed as Monday 04:59 in UTC+5.
    sunday_late = datetime(2024, 1, 7, 23, 59, tzinfo=UTC).astimezone(timezone(timedelta(hours=5)))
    assert (
        rm.evaluate_entry(_req(ts=sunday_late), _state()).reason_code
        is RejectionCode.SESSION_POLICY
    )
    # Naive clocks fail closed.
    naive = rm.evaluate_entry(_req(ts=datetime(2024, 1, 3, 12)), _state())
    assert naive.reason_code is RejectionCode.SESSION_POLICY
    # BTC is allowed at weekends by policy.
    assert rm.evaluate_entry(
        _req(symbol="BTCUSDT", ts=SATURDAY_NOON, entry_price=D(50000), stop_price=D(49000)),
        _state(),
    ).approved


def test_xaut_weekend_rule_cannot_be_reenabled_via_asset_registry() -> None:
    try:
        bundle = _bundle_with_asset_changes("XAUTUSDT", weekend_trading=True)
    except (ValidationError, ValueError):
        return  # desired: registry refuses the widening
    decision = RiskManager(bundle).evaluate_entry(_req(ts=SATURDAY_NOON), _state())
    assert not decision.approved


def test_unnormalized_symbol_returns_decision_instead_of_raising() -> None:
    decision = RiskManager(BUNDLE).evaluate_entry(_req(symbol="xautusdt"), _state())
    # P11j owner contract now requires a rejection for noncanonical entry symbols.
    assert not decision.approved
    assert decision.reason_code is RejectionCode.ASSET_POLICY


# ---------------------------------------------------------------------------
# AI advisory can only veto or reduce.
# ---------------------------------------------------------------------------


def _xau_size(advisory: ArenaAnswer | None) -> Any:
    spec, quotes, conversions, candidates = fixture_market("XAUUSD")
    return size_candidate(
        candidates[0],
        spec,
        quotes[1],
        conversions[1],
        now=quotes[1].timestamp,
        equity=D(1_000_000),
        cash=D(1_000_000),
        day_start=D(1_000_000),
        peak=D(1_000_000),
        bundle=BUNDLE,
        advisory=advisory,
    )


@settings(max_examples=80, deadline=None)
@given(
    decision=st.sampled_from(["take", "skip"]),
    action=st.sampled_from(list(ArenaAction)),
    multiplier=st.floats(min_value=0.0, max_value=1.0),
)
def test_valid_ai_answer_never_enlarges_size(
    decision: str, action: ArenaAction, multiplier: float
) -> None:
    base = _xau_size(None)
    assert base.approved
    answer = ArenaAnswer(
        decision=decision,  # type: ignore[arg-type]
        confidence=0.9,
        reason_code="AUDIT_CASE",
        key_risk="audit",
        action=action,
        size_multiplier=multiplier,
    )
    sized = _xau_size(answer)
    assert sized.lots <= base.lots
    assert sized.planned_loss <= base.planned_loss
    if decision == "skip" or action is ArenaAction.VETO:
        assert not sized.approved


@pytest.mark.parametrize("bad", [5.0, 1.0000001, float("inf"), -1.0, float("nan")])
def test_unvalidated_ai_multiplier_still_cannot_enlarge(bad: float) -> None:
    base = _xau_size(None)
    forged = ArenaAnswer.model_construct(
        decision="take",
        confidence=1.0,
        reason_code="FORGED",
        key_risk="x",
        action=ArenaAction.REDUCE,
        size_multiplier=bad,
    )
    try:
        sized = _xau_size(forged)
    except Exception:
        return  # fail-closed
    assert not sized.approved or sized.lots <= base.lots


def test_ai_schema_rejects_out_of_range_multiplier() -> None:
    for bad in (1.5, -0.1, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            ArenaAnswer(
                decision="take",
                confidence=0.5,
                reason_code="AB",
                key_risk="x",
                action=ArenaAction.REDUCE,
                size_multiplier=bad,
            )


# ---------------------------------------------------------------------------
# Backtest engine scenario properties.
# ---------------------------------------------------------------------------


def _bars(start: datetime, moves: list[Decimal], minutes: int = 60) -> list[Bar]:
    bars: list[Bar] = []
    price = D(2000)
    for index, move in enumerate(moves):
        open_ = price
        close = max(open_ * (1 + move), D("1"))
        high = max(open_, close) * D("1.002")
        low = min(open_, close) * D("0.998")
        bars.append(
            Bar(
                timestamp=start + timedelta(minutes=minutes * index),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=D(1_000_000),
            )
        )
        price = close
    return bars


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    moves=st.lists(
        st.decimals(min_value=D("-0.02"), max_value=D("0.02"), places=4), min_size=24, max_size=110
    ),
    signal_mask=st.lists(st.booleans(), min_size=110, max_size=110),
    stop_pct=st.decimals(min_value=D("0.002"), max_value=D("0.05"), places=4),
    symbol=st.sampled_from(["XAUTUSDT", "BTCUSDT"]),
)
def test_backtest_invariants(
    moves: list[Decimal], signal_mask: list[bool], stop_pct: Decimal, symbol: str
) -> None:
    # Thursday 18:00 UTC -> runs through Friday and into the weekend.
    bars = _bars(datetime(2024, 1, 4, 18, tzinfo=UTC), moves)
    signals = [
        EntrySignal(
            timestamp=bar.timestamp,
            symbol=symbol,
            stop_price=bar.close * (1 - stop_pct),
            target_price=bar.close * (1 + 2 * stop_pct),
        )
        for bar, flag in zip(bars, signal_mask, strict=False)
        if flag
    ]
    engine = BacktestEngine(symbol, initial_cash=D(10000), risk_manager=RiskManager(BUNDLE))
    result = engine.run(bars, signals)
    asset = BUNDLE.registry.asset(symbol)
    assert asset is not None
    limits = effective_risk_limits(asset, BUNDLE.risk.limits)

    # Exposure and long-only on every marked point.
    for point in result.equity:
        assert point.holdings >= 0
        assert point.cash >= 0
        if point.holdings > 0:
            assert point.exposure <= point.equity * limits.max_total_exposure_multiple
    # Flat at the last bar of every UTC day.
    by_day: dict[Any, Any] = {}
    for point in result.equity:
        by_day[point.timestamp.date()] = point
    assert all(point.holdings == 0 for point in by_day.values())
    # Trades per UTC day per asset.
    counts = Counter(trade.entry_time.date() for trade in result.trades)
    assert all(count <= limits.max_trades_per_day_per_asset for count in counts.values())
    # No XAUT weekend entries.
    if symbol == "XAUTUSDT":
        assert all(trade.entry_time.weekday() < 5 for trade in result.trades)
    # Planned all-in stop risk at entry <= risk budget of pre-entry equity.
    index_of = {point.timestamp: i for i, point in enumerate(result.equity)}
    for trade in result.trades:
        assert trade.quantity > 0
        i = index_of[trade.entry_time]
        pre_equity = result.equity[i - 1].equity
        signal = next(s for s in signals if s.timestamp == result.equity[i - 1].timestamp)
        stop_exit = engine.costs.exit_price(signal.stop_price)
        planned = (
            trade.quantity * (trade.entry_price - stop_exit)
            + trade.entry_fee
            + engine.costs.fee(trade.quantity * stop_exit)
        )
        assert planned <= pre_equity * limits.risk_per_trade_pct / 100 * D("1.000000001")


def test_backtest_circuit_uses_effective_asset_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _bundle_with_asset_changes("XAUTUSDT", risk_overrides={"daily_loss_limit_pct": "1.0"})
    captured: list[RiskLimits] = []
    real = bt_engine.AccountCircuitBreaker

    def spy(state: SafetyState, limits: RiskLimits) -> AccountCircuitBreaker:
        captured.append(limits)
        return real(state, limits)

    monkeypatch.setattr(bt_engine, "AccountCircuitBreaker", spy)
    bars = _bars(datetime(2024, 1, 3, 1, tzinfo=UTC), [D(0)] * 3)
    BacktestEngine("XAUTUSDT", initial_cash=D(1000), risk_manager=RiskManager(bundle)).run(bars, [])
    assert captured and captured[0].daily_loss_limit_pct == D("1.0")


def test_backtest_gap_through_stop_does_not_carry_position_past_day() -> None:
    start = datetime(2024, 1, 3, 20, tzinfo=UTC)
    bars = _bars(start, [D(0), D(0), D(0), D(0), D(0), D(0)])
    signals = [
        EntrySignal(
            timestamp=bars[0].timestamp, symbol="XAUTUSDT", stop_price=D(1900), target_price=D(2500)
        ),
    ]
    result = BacktestEngine(
        "XAUTUSDT", initial_cash=D(10000), risk_manager=RiskManager(BUNDLE)
    ).run(bars, signals)
    assert result.trades and result.trades[0].exit_reason.value == "end_of_day"
    assert result.trades[0].exit_time.date() == result.trades[0].entry_time.date()
