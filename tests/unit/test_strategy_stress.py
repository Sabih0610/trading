from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tb.backtest.engine import EntrySignal
from tb.strategies.stress import (
    delay_entries,
    monte_carlo_trade_order,
    parameter_perturbations,
    remove_best_fraction,
)

_START = datetime(2024, 1, 1, tzinfo=UTC)


def _signal(timestamp: datetime) -> EntrySignal:
    return EntrySignal(
        timestamp=timestamp,
        symbol="BTCUSDT",
        stop_price=Decimal("95"),
        target_price=Decimal("110"),
    )


def test_parameter_perturbations_are_one_at_a_time_and_reproducible() -> None:
    defaults = {"stop": Decimal("2"), "target": Decimal("3")}

    trials = parameter_perturbations(defaults)

    assert [trial.label for trial in trials] == [
        "base",
        "stop_minus",
        "stop_plus",
        "target_minus",
        "target_plus",
    ]
    assert trials[1].values["stop"] == Decimal("1.6")
    assert trials[2].values["stop"] == Decimal("2.4")
    assert all(trial.values["target"] == Decimal("3") for trial in trials[1:3])


def test_entry_delay_uses_observed_bars_and_drops_end_overflow() -> None:
    times = [_START + timedelta(minutes=index) for index in range(3)]

    delayed = delay_entries([_signal(times[0]), _signal(times[2])], times, extra_bars=1)

    assert [signal.timestamp for signal in delayed] == [times[1]]
    with pytest.raises(ValueError, match="align"):
        delay_entries([_signal(_START + timedelta(seconds=30))], times, extra_bars=1)
    with pytest.raises(ValueError, match="duplicates"):
        delay_entries([], [times[0], times[0]], extra_bars=1)
    with pytest.raises(ValueError, match="negative"):
        delay_entries([], times, extra_bars=-1)


def test_best_five_percent_removal_is_adverse_and_stable() -> None:
    pnl = [Decimal(value) for value in (10, -2, 5, -1, 3)]

    stressed = remove_best_fraction(pnl)

    assert stressed == (Decimal("-2"), Decimal("5"), Decimal("-1"), Decimal("3"))
    assert remove_best_fraction([]) == ()


def test_seeded_monte_carlo_preserves_pnl_and_reports_path_risk() -> None:
    pnl = [Decimal(value) for value in (10, -30, 20, -5, 15)]

    first = monte_carlo_trade_order(pnl, initial_equity=Decimal("100"), simulations=100, seed=7)
    second = monte_carlo_trade_order(pnl, initial_equity=Decimal("100"), simulations=100, seed=7)

    assert first == second
    assert first.worst_drawdown_pct >= first.percentile_95_drawdown_pct
    assert first.percentile_95_drawdown_pct >= first.median_drawdown_pct


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: parameter_perturbations({}, factor=Decimal("0.2")), "defaults"),
        (
            lambda: parameter_perturbations({"x": Decimal("1")}, factor=Decimal("1")),
            "factor",
        ),
        (lambda: remove_best_fraction([Decimal("1")], fraction=Decimal("0")), "fraction"),
        (
            lambda: monte_carlo_trade_order([], initial_equity=Decimal("1")),
            "At least one",
        ),
        (
            lambda: monte_carlo_trade_order([Decimal("1")], initial_equity=Decimal("0")),
            "initial_equity",
        ),
        (
            lambda: monte_carlo_trade_order(
                [Decimal("1")], initial_equity=Decimal("1"), simulations=0
            ),
            "simulations",
        ),
    ],
)
def test_stress_arguments_fail_closed(call: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()
