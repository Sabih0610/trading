"""P11p owned-fixture tests: catalogue, causality, exits, rotation, safety, rerun refusal."""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tb.backtest.costs import CostAssumptions
from tb.backtest.stage3_metrics import FoldEvidence, NetTrade, TrainingCell
from tb.backtest.swing_portfolio import AssetInputs, simulate
from tb.backtest.swing_stage3 import DSR_TRIALS, TRIAL_COUNT, benchmark_sharpe, bootstrap_ci, run
from tb.research.models import ResearchRefused
from tb.research.swing_data import SwingSeries
from tb.risk.config import load_policy_bundle
from tb.risk.manager import RiskManager
from tb.strategies.signals import CompletedBar
from tb.strategies.swing_rotation import (
    DaySignals,
    SwingTrial,
    build_signal_table,
    preregistered_trials,
)

START = datetime(2021, 1, 4, tzinfo=UTC)  # a Monday


def _series(label: str, closes: list[float], start: datetime = START) -> SwingSeries:
    daily = []
    for i, c in enumerate(closes):
        o = Decimal(str(closes[i - 1] if i else c))
        cl = Decimal(str(c))
        t = start + timedelta(days=i)
        daily.append(
            CompletedBar(
                label,
                "1d",
                t,
                t + timedelta(days=1),
                o,
                max(o, cl) * Decimal("1.01"),
                min(o, cl) * Decimal("0.99"),
                cl,
            )
        )
    weekly = []
    for w in range(len(closes) // 7):
        chunk = daily[w * 7 : (w + 1) * 7]
        t = chunk[0].opened_at
        weekly.append(
            CompletedBar(
                label,
                "1w",
                t,
                t + timedelta(days=7),
                chunk[0].open,
                max(b.high for b in chunk),
                min(b.low for b in chunk),
                chunk[-1].close,
            )
        )
    atr = {b.opened_at: b.close * Decimal("0.04") for b in daily}
    return SwingSeries(label, tuple(daily), tuple(weekly), atr, ())


def _risk() -> RiskManager:
    return RiskManager(load_policy_bundle())


def _inputs(
    series: SwingSeries, signals: dict | None = None, stress: Decimal = Decimal(1)
) -> AssetInputs:
    asset = load_policy_bundle().registry.asset(series.label)
    return AssetInputs(
        {b.opened_at: b for b in series.daily},
        signals if signals is not None else build_signal_table(series),
        series.swing_lows,
        CostAssumptions.from_asset(asset, stress_multiplier=stress),
    )


def test_catalogue_is_exactly_27_and_dsr_counts_prior_trials() -> None:
    trials = preregistered_trials()
    assert len(trials) == TRIAL_COUNT == 27
    assert DSR_TRIALS == 27 + 216
    assert len({(t.trigger, t.param, t.stop_k) for t in trials}) == 27
    assert [t.index for t in trials] == list(range(27))


def test_signal_table_is_causal() -> None:
    closes = [100 + i * 0.5 for i in range(400)]
    base = build_signal_table(_series("BTCUSDT", closes))
    future = closes[:300] + [c * 3 for c in closes[300:]]  # change only the future
    changed = build_signal_table(_series("BTCUSDT", future))
    cutoff = START + timedelta(days=300)
    for key, value in base.items():
        if key <= cutoff:
            assert changed[key] == value


def _forced(series: SwingSeries, entry_close: datetime, trend_days: int = 400) -> dict:
    """Hand-made signal table: one breakout(20) at ``entry_close``, trend always on."""
    table = {}
    for b in series.daily:
        fires = frozenset({("breakout", "20")}) if b.closed_at == entry_close else frozenset()
        table[b.closed_at] = DaySignals(
            True, Decimal("0.1"), fires, b.close, b.close * Decimal("0.04")
        )
    return table


def test_entry_fills_next_open_and_one_position_at_a_time() -> None:
    s = _series("BTCUSDT", [100.0] * 60)
    signal_close = START + timedelta(days=20)
    table = _forced(s, signal_close)
    trial = SwingTrial(0, "breakout", "20", Decimal("2"))
    res = simulate(
        trial,
        {"BTCUSDT": _inputs(s, table)},
        _risk(),
        start=START,
        stop=START + timedelta(days=60),
        embargo=False,
    )
    assert len(res.evidence.trades) == 1
    assert res.evidence.trades[0].entry_day == signal_close.date()  # filled at the next day's open


def test_max_holding_forces_exit_within_10_days() -> None:
    s = _series("BTCUSDT", [100.0] * 60)
    table = _forced(s, START + timedelta(days=5))
    res = simulate(
        SwingTrial(0, "breakout", "20", Decimal("2")),
        {"BTCUSDT": _inputs(s, table)},
        _risk(),
        start=START,
        stop=START + timedelta(days=60),
        embargo=False,
    )
    assert res.holding_days and max(res.holding_days) <= 10


def test_gap_below_stop_exits_at_open() -> None:
    closes = [100.0] * 30 + [50.0] * 30
    s = _series("BTCUSDT", closes)
    gap = s.daily[30]  # make day 30 OPEN below the stop (a true overnight gap)
    gapped = CompletedBar(
        gap.symbol,
        "1d",
        gap.opened_at,
        gap.closed_at,
        Decimal("50"),
        Decimal("51"),
        Decimal("49"),
        Decimal("50"),
    )
    s = replace(s, daily=(*s.daily[:30], gapped, *s.daily[31:]))
    table = _forced(s, START + timedelta(days=25))
    res = simulate(
        SwingTrial(0, "breakout", "20", Decimal("2")),
        {"BTCUSDT": _inputs(s, table)},
        _risk(),
        start=START,
        stop=START + timedelta(days=60),
        embargo=False,
    )
    assert res.gap_stop_exits == 1
    assert res.evidence.trades[0].net_r < -1  # a gap loss exceeds the planned risk


def test_gold_never_enters_on_a_weekend() -> None:
    s = _series("XAUTUSDT", [2000.0] * 40)
    # signal on Friday close -> next open is Saturday -> must be refused
    friday_close = START + timedelta(days=5)  # START is Monday; +4 = Fri open, +5 = Sat 00:00
    table = _forced(s, friday_close)
    res = simulate(
        SwingTrial(0, "breakout", "20", Decimal("2")),
        {"XAUTUSDT": _inputs(s, table)},
        _risk(),
        start=START,
        stop=START + timedelta(days=40),
        embargo=False,
    )
    assert res.evidence.trades == ()


def test_cost_filter_blocks_small_moves() -> None:
    s = _series("BTCUSDT", [100.0] * 40)
    table = {
        k: replace(v, atr14=v.close * Decimal("0.0001"))
        for k, v in _forced(s, START + timedelta(days=10)).items()
    }
    res = simulate(
        SwingTrial(0, "breakout", "20", Decimal("2")),
        {"BTCUSDT": _inputs(s, table)},
        _risk(),
        start=START,
        stop=START + timedelta(days=40),
        embargo=False,
    )
    assert res.evidence.trades == ()


def test_embargo_blocks_entries_in_first_ten_days() -> None:
    s = _series("BTCUSDT", [100.0] * 40)
    table = _forced(s, START + timedelta(days=3))
    res = simulate(
        SwingTrial(0, "breakout", "20", Decimal("2")),
        {"BTCUSDT": _inputs(s, table)},
        _risk(),
        start=START,
        stop=START + timedelta(days=40),
        embargo=True,
    )
    assert res.evidence.trades == ()


def test_random_benchmark_is_seeded_and_reproducible() -> None:
    s = _series("BTCUSDT", [100 + i * 0.2 for i in range(120)])
    inp = {"BTCUSDT": _inputs(s)}
    a = simulate(
        None,
        inp,
        _risk(),
        start=START,
        stop=START + timedelta(days=120),
        stop_k=Decimal("2"),
        rng=random.Random(7),
        p_random=0.2,
    )
    b = simulate(
        None,
        inp,
        _risk(),
        start=START,
        stop=START + timedelta(days=120),
        stop_k=Decimal("2"),
        rng=random.Random(7),
        p_random=0.2,
    )
    assert a.evidence == b.evidence


def test_benchmark_and_bootstrap_are_deterministic() -> None:
    cells = [
        TrainingCell(
            trial_index=i,
            trade_count=30,
            expectancy_r=0.1,
            daily_sharpe=0.01 * i,
            timeframe_seconds=86400,
            parameters=(0.0, 0.0, float(i)),
        )
        for i in range(27)
    ]
    assert benchmark_sharpe(cells) == benchmark_sharpe(cells) and benchmark_sharpe(cells) > 0
    fold = FoldEvidence(
        year=2022,
        trades=tuple(
            NetTrade(entry_day=(START + timedelta(days=400 + i)).date(), pnl=1.0, net_r=0.5)
            for i in range(30)
        ),
        daily_returns=(0.0,),
        max_dd=0.0,
        path_max=1.0,
        path_min=1.0,
    )
    from datetime import date

    assert bootstrap_ci([fold], date(2022, 1, 1), date(2023, 12, 31)) == bootstrap_ci(
        [fold], date(2022, 1, 1), date(2023, 12, 31)
    )


def test_runner_refuses_rerun(tmp_path: Path) -> None:
    (tmp_path / "results.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ResearchRefused):
        run(tmp_path, tmp_path)


def test_swing_low_above_price_cancels_entry_instead_of_crashing() -> None:
    from tb.strategies.signals import ConfirmedSwingLow

    s = _series("BTCUSDT", [100.0] * 40)
    high_low = ConfirmedSwingLow("BTCUSDT", Decimal("500"), START, START + timedelta(days=2))
    s = replace(s, swing_lows=(high_low,))
    table = _forced(s, START + timedelta(days=10))
    res = simulate(
        SwingTrial(0, "breakout", "20", Decimal("1.5")),
        {"BTCUSDT": _inputs(s, table)},
        _risk(),
        start=START,
        stop=START + timedelta(days=40),
        embargo=False,
    )
    assert res.evidence.trades == ()
