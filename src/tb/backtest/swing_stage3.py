"""P11p Stage 3b runner: walk-forward, selection, sensitivities, benchmarks, verdict.

Development (2022, 2023) is completed and its 2024 parameter choice frozen to disk
**before** any 2024 bar is loaded. Only aggregates are ever written publicly.
"""

from __future__ import annotations

import json
import math
import random
import statistics as stats
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import NormalDist
from typing import Any

from tb.backtest.costs import CostAssumptions
from tb.backtest.stage3_metrics import (
    FoldEvidence,
    Summary,
    TrainingCell,
    daily_sharpe,
    ratio,
    select_cell,
    summarize,
)
from tb.backtest.swing_portfolio import INITIAL_CASH, AssetInputs, simulate
from tb.research.models import HOLDOUT, ResearchRefused
from tb.research.swing_data import SwingSeries, load_swing_series
from tb.risk.config import load_policy_bundle
from tb.risk.manager import RiskManager
from tb.silver.swing_source import CRYPTO_DATASET, GOLD_DATASET, PAXG_DATASET
from tb.strategies.swing_rotation import build_signal_table, preregistered_trials

PRIOR_TRIALS = 216  # P11f (162) + P11g (54)
TRIAL_COUNT = 27
DSR_TRIALS = TRIAL_COUNT + PRIOR_TRIALS  # 243
PURGE_DAYS = 10
RANDOM_SEEDS = range(20261106, 20261206)  # 100 seeds
BOOTSTRAP_SEED = 20261106
DATA_START = datetime(2020, 10, 1, tzinfo=UTC)


def utc(y: int, m: int = 1, d: int = 1) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


def benchmark_sharpe(cells: list[TrainingCell], n: int = DSR_TRIALS) -> float | None:
    """Expected null maximum Sharpe over n trials, dispersion from finite training cells."""
    values = [c.daily_sharpe for c in cells if c.daily_sharpe is not None]
    if len(values) < 2 or stats.pstdev(values) <= 0:
        return None
    gamma, normal = 0.5772156649015329, NormalDist()
    z = (1 - gamma) * normal.inv_cdf(1 - 1 / n) + gamma * normal.inv_cdf(1 - 1 / (n * math.e))
    return max(0.0, stats.pstdev(values) * z)


def bootstrap_ci(folds: list[FoldEvidence], first: date, last: date) -> tuple[float, float] | None:
    """10,000 fixed-seed whole-week draws over every calendar week, empty weeks included."""
    monday = first - timedelta(days=first.weekday())
    weeks: dict[date, list[float]] = {}
    while monday <= last:
        weeks[monday] = []
        monday += timedelta(days=7)
    for fold in folds:
        for t in fold.trades:
            key = t.entry_day - timedelta(days=t.entry_day.weekday())
            if key in weeks:
                weeks[key].append(t.net_r)
    blocks = [(sum(v), len(v)) for v in weeks.values()]
    rng, draws = random.Random(BOOTSTRAP_SEED), []
    for _ in range(10000):
        total, count = 0.0, 0
        for _ in blocks:
            a, s = rng.choice(blocks)
            total, count = total + a, count + s
        if not count:
            return None
        draws.append(total / count)
    draws.sort()
    return draws[249], draws[9749]


@dataclass
class Universe:
    """Assets keyed by strategy label; built from admitted series only."""

    series: dict[str, SwingSeries]

    def inputs(self, stress: Decimal = Decimal(1)) -> dict[str, AssetInputs]:
        bundle = load_policy_bundle()
        out = {}
        for label, s in self.series.items():
            asset = bundle.registry.asset(label)
            if asset is None:
                raise ResearchRefused("swing_asset_not_registered")
            out[label] = AssetInputs(
                bars={b.opened_at: b for b in s.daily},
                signals=build_signal_table(s),
                swing_lows=s.swing_lows,
                costs=CostAssumptions.from_asset(asset, stress_multiplier=stress),
            )
        return out


def _with_costs(inputs: dict[str, AssetInputs], stress: Decimal) -> dict[str, AssetInputs]:
    bundle = load_policy_bundle()
    assets = {k: bundle.registry.asset(k) for k in inputs}
    if any(a is None for a in assets.values()):
        raise ResearchRefused("swing_asset_not_registered")
    return {
        k: AssetInputs(
            v.bars,
            v.signals,
            v.swing_lows,
            CostAssumptions.from_asset(assets[k], stress_multiplier=stress),  # type: ignore[arg-type]
        )
        for k, v in inputs.items()
    }


def training_cells(
    inputs: dict[str, AssetInputs], risk: RiskManager, end: datetime
) -> list[TrainingCell]:
    cells = []
    for trial in preregistered_trials():
        ev = simulate(
            trial,
            inputs,
            risk,
            start=DATA_START,
            stop=end - timedelta(days=PURGE_DAYS),
            embargo=False,
        ).evidence
        rs = [t.net_r for t in ev.trades]
        cells.append(
            TrainingCell(
                trial_index=trial.index,
                trade_count=len(rs),
                expectancy_r=stats.fmean(rs) if rs else None,
                daily_sharpe=daily_sharpe(ev.daily_returns),
                timeframe_seconds=86400,
                parameters=trial.parameters,
            )
        )
    return cells


def buy_and_hold(
    inputs: dict[str, AssetInputs], start: datetime, stop: datetime
) -> tuple[float, float]:
    """BTC fully funded from the first open to the last close, both-side costs; (return, maxDD)."""
    a = inputs["BTCUSDT"]
    days = sorted(d for d in a.bars if start <= d < stop)
    if not days:
        return 0.0, 0.0
    c = a.costs
    first = a.bars[days[0]]
    fill = c.entry_price(first.open)
    qty = INITIAL_CASH / (fill * (1 + c.stressed_fee_bps / 10000))
    peak, dd, value = float(INITIAL_CASH), 0.0, float(INITIAL_CASH)
    for d in days:
        v = qty * c.exit_price(a.bars[d].close)
        value = float(v - c.fee(v))
        peak = max(peak, value)
        dd = max(dd, (peak - value) / peak)
    return value / float(INITIAL_CASH) - 1, dd


def random_p95(
    inputs: dict[str, AssetInputs],
    risk: RiskManager,
    start: datetime,
    stop: datetime,
    k: Decimal,
    trades: int,
) -> float:
    days = max(1, (stop - start).days - 10)
    p = min(1.0, trades / days) if trades else 0.0
    results = sorted(
        summarize(
            [
                simulate(
                    None,
                    inputs,
                    risk,
                    start=start,
                    stop=stop,
                    stop_k=k,
                    rng=random.Random(seed),
                    p_random=p,
                ).evidence
            ]
        ).net_return
        for seed in RANDOM_SEEDS
    )
    return results[94]


def _summary(folds: list[FoldEvidence], bench: float | None) -> Summary:
    return summarize(folds, bench)


def run(root: Path, out_dir: Path, *, years_dev: tuple[int, int] = (2022, 2023)) -> dict[str, Any]:
    """Execute the registered batch once. Refuses to overwrite an existing result."""
    if (out_dir / "results.json").exists():
        raise ResearchRefused("p11p_result_exists_refuse_rerun")
    out_dir.mkdir(parents=True, exist_ok=True)
    risk = RiskManager(load_policy_bundle())
    trials = {t.index: t for t in preregistered_trials()}
    if len(trials) != TRIAL_COUNT:
        raise ResearchRefused("p11p_trial_count_changed")

    # ---------- development: data up to 2023-12-31 only ----------
    dev = Universe(
        {
            "BTCUSDT": load_swing_series(root, CRYPTO_DATASET, "BTCUSDT", (2020, 2021, 2022, 2023)),
            "ETHUSDT": load_swing_series(root, CRYPTO_DATASET, "ETHUSDT", (2020, 2021, 2022, 2023)),
            "SOLUSDT": load_swing_series(root, CRYPTO_DATASET, "SOLUSDT", (2020, 2021, 2022, 2023)),
            "XAUTUSDT": load_swing_series(
                root, GOLD_DATASET, "XAUUSD", (2021, 2022, 2023), label="XAUTUSDT"
            ),
        }
    )
    dev_inputs = dev.inputs()
    folds: dict[int, dict[str, Any]] = {}
    for year in years_dev:
        cells = training_cells(dev_inputs, risk, utc(year))
        chosen = select_cell(cells)
        bench = benchmark_sharpe(cells)
        entry: dict[str, Any] = {
            "cells": [c.model_dump() for c in cells],
            "benchmark": bench,
            "selected": None if chosen is None else chosen.trial_index,
        }
        if chosen is not None:
            t = trials[chosen.trial_index]
            base = simulate(t, dev_inputs, risk, start=utc(year), stop=utc(year + 1))
            s15 = simulate(
                t,
                _with_costs(dev_inputs, Decimal("1.5")),
                risk,
                start=utc(year),
                stop=utc(year + 1),
            )
            s20 = simulate(
                t, _with_costs(dev_inputs, Decimal("2")), risk, start=utc(year), stop=utc(year + 1)
            )
            entry.update(
                base=base,
                s15=s15,
                s20=s20,
                buy_hold=buy_and_hold(dev_inputs, utc(year), utc(year + 1)),
                random_p95=random_p95(
                    dev_inputs, risk, utc(year), utc(year + 1), t.stop_k, len(base.evidence.trades)
                ),
            )
        folds[year] = entry
    final_cells = training_cells(dev_inputs, risk, utc(2024))
    final_choice = select_cell(final_cells)
    final_bench = benchmark_sharpe(final_cells)
    frozen = {
        "selected_trial": None if final_choice is None else final_choice.trial_index,
        "frozen_at": datetime.now(UTC).isoformat(),
        "trials": TRIAL_COUNT,
        "dsr_trials": DSR_TRIALS,
    }
    (out_dir / "frozen-2024-selection.json").write_text(
        json.dumps(frozen, indent=2), encoding="utf-8"
    )

    # ---------- validation: 2024 loaded only now, after the freeze ----------
    val: dict[str, Any] = {"selected": frozen["selected_trial"], "benchmark": final_bench}
    if final_choice is not None:
        full = Universe(
            {
                "BTCUSDT": load_swing_series(
                    root, CRYPTO_DATASET, "BTCUSDT", (2020, 2021, 2022, 2023, 2024)
                ),
                "ETHUSDT": load_swing_series(
                    root, CRYPTO_DATASET, "ETHUSDT", (2020, 2021, 2022, 2023, 2024)
                ),
                "SOLUSDT": load_swing_series(
                    root, CRYPTO_DATASET, "SOLUSDT", (2020, 2021, 2022, 2023, 2024)
                ),
                "XAUTUSDT": load_swing_series(
                    root.parent / "trading-p11k",
                    PAXG_DATASET,
                    "PAXGUSDT",
                    (2023, 2024),
                    label="XAUTUSDT",
                ),
            }
        )
        vi = full.inputs()
        t = trials[final_choice.trial_index]
        stop = min(utc(2025), HOLDOUT)
        base = simulate(t, vi, risk, start=utc(2024), stop=stop)
        val.update(
            base=base,
            s15=simulate(t, _with_costs(vi, Decimal("1.5")), risk, start=utc(2024), stop=stop),
            s20=simulate(t, _with_costs(vi, Decimal("2")), risk, start=utc(2024), stop=stop),
            buy_hold=buy_and_hold(vi, utc(2024), stop),
            random_p95=random_p95(vi, risk, utc(2024), stop, t.stop_k, len(base.evidence.trades)),
        )
    return verdict(folds, val, out_dir)


def _exp(ev: FoldEvidence) -> float | None:
    rs = [t.net_r for t in ev.trades]
    return stats.fmean(rs) if rs else None


def verdict(folds: dict[int, dict[str, Any]], val: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    dev_ok = all("base" in f for f in folds.values())
    checks: dict[str, bool] = {}
    public: dict[str, Any] = {"phase": "P11p", "trials": TRIAL_COUNT, "dsr_trials": DSR_TRIALS}
    if not dev_ok or "base" not in val:
        public["verdict"] = "insufficient evidence"
        public["reason"] = (
            "no eligible training cell (>=20 trades) in a fold"
            if not dev_ok
            else "no frozen 2024 cell"
        )
    else:
        dev_folds = [f["base"].evidence for f in folds.values()]
        dev15 = [f["s15"].evidence for f in folds.values()]
        bench = max((f["benchmark"] or 0.0) for f in folds.values())
        dsum, vsum = _summary(dev_folds, bench), _summary([val["base"].evidence], val["benchmark"])
        d15, v15 = _summary(dev15, None), _summary([val["s15"].evidence], None)
        ci = bootstrap_ci(dev_folds, date(2022, 1, 1), date(2023, 12, 31))
        dev_bh = [f["buy_hold"] for f in folds.values()]
        dev_bh_ret = math.prod(1 + r for r, _ in dev_bh) - 1
        dev_bh_dd = max(dd for _, dd in dev_bh)
        checks = {
            "positive_2022": (_exp(folds[2022]["base"].evidence) or 0) > 0,
            "positive_2023": (_exp(folds[2023]["base"].evidence) or 0) > 0,
            "positive_2024": (vsum.expectancy_r or 0) > 0,
            "pf_dev": (dsum.profit_factor or 0) >= 1.3,
            "pf_2024": (vsum.profit_factor or 0) >= 1.3,
            "max_dd": dsum.max_dd_pct <= 15 and vsum.max_dd_pct <= 15,
            "dev_trades_60": dsum.trade_count >= 60,
            "trades_2024_20": vsum.trade_count >= 20,
            "beats_cash": dsum.net_return > 0 and vsum.net_return > 0,
            "beats_random_95": all(
                f["base"] and summarize([f["base"].evidence]).net_return > f["random_p95"]
                for f in folds.values()
            )
            and vsum.net_return > val["random_p95"],
            "beats_btc_ratio": ratio(dsum.net_return, dsum.max_dd_pct / 100)
            > ratio(dev_bh_ret, dev_bh_dd)
            and ratio(vsum.net_return, vsum.max_dd_pct / 100) > ratio(*val["buy_hold"]),
            "positive_1_5x": (d15.expectancy_r or 0) > 0 and (v15.expectancy_r or 0) > 0,
            "dsr_95": (dsum.dsr or 0) >= 0.95 and (vsum.dsr or 0) >= 0.95,
            "bootstrap_ci_above_0": ci is not None and ci[0] > 0,
        }
        insufficient = not (checks["dev_trades_60"] and checks["trades_2024_20"])
        public["verdict"] = (
            "pass"
            if all(checks.values())
            else ("insufficient evidence" if insufficient else "fail")
        )
        months = 36
        public["metrics"] = {
            "development": dsum.model_dump(),
            "validation_2024": vsum.model_dump(),
            "development_1_5x_expectancy_r": d15.expectancy_r,
            "validation_1_5x_expectancy_r": v15.expectancy_r,
            "trades_per_month_dev": dsum.trade_count / 24,
            "trades_per_month_2024": vsum.trade_count / 12,
            "avg_holding_days": stats.fmean(
                h for f in folds.values() for h in f["base"].holding_days
            )
            if any(f["base"].holding_days for f in folds.values())
            else None,
            "per_asset_trades_dev": _merge([f["base"].per_asset for f in folds.values()]),
            "win_rate_dev": dsum.win_rate,
            "break_even_win_rate_dev": _break_even([t.net_r for f in dev_folds for t in f.trades]),
            "cost_share_of_gross_profit_dev": _cost_share(folds),
            "gap_stop_exits": sum(f["base"].gap_stop_exits for f in folds.values())
            + val["base"].gap_stop_exits,
            "circuit": [
                {
                    "year": y,
                    "trips": f["base"].evidence.circuit_trips,
                    "halted_days": f["base"].evidence.halted_days,
                }
                for y, f in folds.items()
            ]
            + [
                {
                    "year": 2024,
                    "trips": val["base"].evidence.circuit_trips,
                    "halted_days": val["base"].evidence.halted_days,
                }
            ],
        }
        _ = months
        public["checklist"] = checks
        public["selected_trials"] = {str(y): f["selected"] for y, f in folds.items()} | {
            "2024": val["selected"]
        }
    # private evidence (trades, returns) stays in out_dir
    private = {
        "folds": {
            str(y): {
                k: (v.evidence.model_dump(mode="json") if hasattr(v, "evidence") else v)
                for k, v in f.items()
                if k not in ("cells",)
            }
            | {"cells": f.get("cells")}
            for y, f in folds.items()
        },
        "validation": {
            k: (v.evidence.model_dump(mode="json") if hasattr(v, "evidence") else v)
            for k, v in val.items()
        },
        "public": public,
    }
    (out_dir / "results.json").write_text(
        json.dumps(private, indent=2, default=str), encoding="utf-8"
    )
    return public


def _break_even(rs: list[float]) -> float | None:
    """Win rate needed to break even given the realized average win and loss (in R)."""
    wins, losses = [r for r in rs if r > 0], [-r for r in rs if r <= 0]
    if not wins or not losses:
        return None
    avg_w, avg_l = stats.fmean(wins), stats.fmean(losses)
    return avg_l / (avg_w + avg_l)


def _cost_share(folds: dict[int, dict[str, Any]]) -> float | None:
    gross = sum(float(f["base"].gross_profit) for f in folds.values())
    paid = sum(float(f["base"].costs_paid) for f in folds.values())
    return paid / gross if gross > 0 else None


def _merge(dicts: list[dict[str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in dicts:
        for k, v in d.items():
            out[k] = out.get(k, 0) + v
    return out


def main() -> None:
    root = Path("E:/trading-p11e")
    out = root / "work" / "stage3" / "P11p" / "registered-27-v1"
    print(json.dumps(run(root, out), indent=2, default=str))


if __name__ == "__main__":
    main()
