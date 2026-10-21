"""Synthetic trigger, non-trigger, and causality tests for Strategies A/B/C."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.backtest.engine import EntryOrderType
from tb.risk.guards import RiskViolation
from tb.strategies import (
    LondonSweepStrategy,
    StrategyBar,
    TrendVwapStrategy,
    XautCatchUpStrategy,
    generate_decisions,
)
from tb.strategies.base import StrategyConfigurationError, StrategyDecision

_MONDAY = datetime(2024, 1, 8, tzinfo=UTC)


def _bar(
    timestamp: datetime,
    *,
    symbol: str = "XAUTUSDT",
    open_price: str = "100",
    high: str = "101",
    low: str = "99",
    close: str = "100",
    **features: object,
) -> StrategyBar:
    values: dict[str, object] = {
        "timestamp": timestamp,
        "symbol": symbol,
        "open": Decimal(open_price),
        "high": Decimal(high),
        "low": Decimal(low),
        "close": Decimal(close),
        "atr14": Decimal("2"),
    }
    values.update(features)
    return StrategyBar.model_validate(values)


def _london_pattern() -> list[StrategyBar]:
    return [
        _bar(_MONDAY + timedelta(hours=0), high="102", low="100", close="101"),
        _bar(_MONDAY + timedelta(hours=6, minutes=55), high="103", low="99", close="100"),
        _bar(_MONDAY + timedelta(hours=7), high="101", low="98", close="100"),
        _bar(
            _MONDAY + timedelta(hours=7, minutes=5),
            high="103",
            low="100",
            close="102",
            structure_event="choch_up",
            structure_direction=1,
        ),
        _bar(
            _MONDAY + timedelta(hours=7, minutes=10),
            open_price="102",
            high="104",
            low="102",
            close="103",
            structure_direction=1,
            fvg_direction="bullish",
            fvg_lower=Decimal("101"),
            fvg_upper=Decimal("102"),
        ),
    ]


def test_london_sweep_pattern_emits_exact_limit_proposal() -> None:
    entries, exits = generate_decisions(LondonSweepStrategy(), _london_pattern())

    assert exits == ()
    assert len(entries) == 1
    signal = entries[0]
    assert signal.order_type is EntryOrderType.LIMIT
    assert signal.limit_price == Decimal("101.5")
    assert signal.stop_price == Decimal("97.50")
    assert signal.target_price == Decimal("109.50")


@pytest.mark.parametrize(
    "mutation",
    [
        {2: {"low": Decimal("99.5")}},
        {3: {"structure_event": None}},
        {4: {"fvg_direction": "bearish"}},
    ],
)
def test_london_sweep_missing_condition_does_not_trigger(
    mutation: dict[int, dict[str, object]],
) -> None:
    bars = _london_pattern()
    for index, changes in mutation.items():
        bars[index] = bars[index].model_copy(update=changes)

    entries, _ = generate_decisions(LondonSweepStrategy(), bars)

    assert entries == ()


def test_london_session_uses_dst_aware_local_clock() -> None:
    start = datetime(2024, 7, 7, 23, tzinfo=UTC)  # Monday 00:00 in London.
    bars = [
        _bar(start, high="102", low="99"),
        _bar(start + timedelta(hours=7), high="101", low="98", close="100"),
        _bar(
            start + timedelta(hours=7, minutes=5),
            high="103",
            low="100",
            close="102",
            structure_event="bos_up",
        ),
        _bar(
            start + timedelta(hours=7, minutes=10),
            open_price="102",
            high="104",
            low="102",
            close="103",
            fvg_direction="bullish",
            fvg_lower=Decimal("101"),
            fvg_upper=Decimal("102"),
        ),
    ]

    entries, _ = generate_decisions(LondonSweepStrategy(), bars)

    assert len(entries) == 1


def test_xaut_catchup_enters_on_joint_trigger_and_exits_on_normalization() -> None:
    bars = [
        _bar(
            _MONDAY,
            reference_move_zscore=Decimal("2.1"),
            basis_zscore=Decimal("-1.6"),
        ),
        _bar(
            _MONDAY + timedelta(minutes=1),
            reference_move_zscore=Decimal("0"),
            basis_zscore=Decimal("-0.2"),
        ),
    ]

    entries, exits = generate_decisions(XautCatchUpStrategy(), bars)

    assert len(entries) == 1
    assert entries[0].stop_price == Decimal("97.0")
    assert entries[0].target_price == Decimal("104.50")
    assert entries[0].max_holding_bars == 12
    assert len(exits) == 1
    assert exits[0].timestamp == bars[1].timestamp


def test_xaut_catchup_requires_both_reference_move_and_lag() -> None:
    bars = [
        _bar(_MONDAY, reference_move_zscore=Decimal("1.9"), basis_zscore=Decimal("-2")),
        _bar(
            _MONDAY + timedelta(minutes=1),
            reference_move_zscore=Decimal("2.5"),
            basis_zscore=Decimal("-1"),
        ),
    ]

    entries, exits = generate_decisions(XautCatchUpStrategy(), bars)

    assert entries == ()
    assert exits == ()


def test_trend_vwap_requires_agreement_touch_and_hold_once_per_day() -> None:
    trigger = _bar(
        _MONDAY,
        symbol="BTCUSDT",
        open_price="102",
        high="103",
        low="99.9",
        close="101",
        ema20=Decimal("101"),
        ema50=Decimal("100"),
        ema20_slope=Decimal("0.001"),
        ema50_slope=Decimal("0.0005"),
        structure_direction=1,
        htf_structure_direction=1,
        session_vwap=Decimal("100"),
    )
    second = trigger.model_copy(update={"timestamp": _MONDAY + timedelta(minutes=1)})

    entries, _ = generate_decisions(TrendVwapStrategy("BTCUSDT"), [trigger, second])

    assert len(entries) == 1
    assert entries[0].stop_price == Decimal("96.9")
    assert entries[0].target_price == Decimal("109.2")


@pytest.mark.parametrize(
    "change",
    [
        {"htf_structure_direction": -1},
        {"ema20": Decimal("99")},
        {"low": Decimal("101")},
        {"close": Decimal("99.9"), "low": Decimal("99")},
    ],
)
def test_trend_vwap_missing_condition_does_not_trigger(change: dict[str, object]) -> None:
    values: dict[str, object] = {
        "timestamp": _MONDAY,
        "symbol": "BTCUSDT",
        "open_price": "102",
        "high": "103",
        "low": "99.9",
        "close": "101",
        "ema20": Decimal("101"),
        "ema50": Decimal("100"),
        "ema20_slope": Decimal("0.001"),
        "ema50_slope": Decimal("0.0005"),
        "structure_direction": 1,
        "htf_structure_direction": 1,
        "session_vwap": Decimal("100"),
    }
    values.update(change)

    decision = TrendVwapStrategy("BTCUSDT").on_bar(_bar(**values))

    assert decision == StrategyDecision()


def test_strategy_replay_is_future_independent() -> None:
    prefix = _london_pattern()[:4]
    future = _london_pattern()[4:]

    prefix_entries, _ = generate_decisions(LondonSweepStrategy(), prefix)
    full_entries, _ = generate_decisions(LondonSweepStrategy(), [*prefix, *future])

    assert prefix_entries == tuple(
        entry for entry in full_entries if entry.timestamp <= prefix[-1].timestamp
    )


def test_strategy_policy_and_input_validation_fail_closed() -> None:
    with pytest.raises(StrategyConfigurationError, match="not allowed"):
        LondonSweepStrategy("BTCUSDT")
    with pytest.raises(RiskViolation, match="data-only"):
        TrendVwapStrategy("XAUUSD")
    with pytest.raises(ValidationError, match="bounds"):
        _bar(_MONDAY, high="90")
    with pytest.raises(ValidationError, match="gap bounds"):
        _bar(_MONDAY, fvg_lower=Decimal("100"))


def test_strategy_replay_rejects_order_and_symbol_mismatch() -> None:
    bars = [_bar(_MONDAY), _bar(_MONDAY - timedelta(minutes=1))]
    with pytest.raises(ValueError, match="strictly increasing"):
        generate_decisions(XautCatchUpStrategy(), bars)
    with pytest.raises(ValueError, match="symbol"):
        generate_decisions(TrendVwapStrategy("BTCUSDT"), [_bar(_MONDAY)])
