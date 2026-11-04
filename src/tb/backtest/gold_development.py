"""Registered one-shot gold development batch; immutable checkpoints and no validation claims."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import psutil

from tb.backtest.stage3_metrics import (
    FoldEvidence,
    NetTrade,
    Summary,
    TrainingCell,
    daily_sharpe,
    select_cell,
    summarize,
    weekly_bootstrap,
)
from tb.ingest.history.core import sha256_file
from tb.research.gold_development_data import GoldPrepared, GoldSource, PrivateStore
from tb.research.gold_proxy import PROXY_LABEL, START, STOP, GoldResearchEvaluation
from tb.research.models import ResearchRefused, digest
from tb.strategies.gold_stage3 import (
    GOLD_TRIAL_COUNT,
    GoldTrial,
    GoldVerdict,
    gold_ambiguity_verdict,
    gold_development_verdict,
    gold_frozen_payload,
    gold_null_benchmark,
    gold_strategy,
    gold_trials,
)

REGISTRATION_SHA = "806c2db7bf100f9d5c59d867b652d0a1b33d8b41fb527621d6a24e4cd7e6ab98"
RUN_ID = "registered-gold-54-v1"
YEARS = (2022, 2023)
STRATEGIES = ("london_sweep_mss_fvg", "trend_vwap_pullback", "session_orb")
COSTS = ("1", "1.5", "2")
INITIAL_CASH = Decimal("10000")


def implementation_identity(repo: Path) -> str:
    """Bind registration, all source/config and pinned dependencies before any input access."""
    registration = repo / "reports/stage3/P11g-preregistration.md"
    if sha256_file(registration) != REGISTRATION_SHA:
        raise ResearchRefused("gold_registration_changed")
    paths = [
        *sorted((repo / "src").rglob("*.py")),
        *sorted((repo / "config").rglob("*.yaml")),
        repo / "pyproject.toml",
        repo / "uv.lock",
        registration,
    ]
    return digest([(p.relative_to(repo).as_posix(), sha256_file(p)) for p in paths])


def training_record(index: int, trial: GoldTrial, evidence: FoldEvidence) -> TrainingCell:
    """The registered training ranking, independent of later performance or execution paths."""
    summary = summarize([evidence])
    parameters = {
        "london_sweep_mss_fvg": ("reclaim_bars", "stop_buffer_atr"),
        "trend_vwap_pullback": ("touch_tolerance_atr", "stop_atr"),
        "session_orb": ("entry_window_minutes", "breakout_buffer_atr"),
    }[trial.strategy]
    config = trial.config.model_dump()
    return TrainingCell(
        trial_index=index,
        trade_count=summary.trade_count,
        expectancy_r=summary.expectancy_r,
        daily_sharpe=daily_sharpe(evidence.daily_returns),
        timeframe_seconds=int(trial.timeframe.total_seconds()),
        parameters=tuple(float(config[p]) for p in parameters),
    )


def public_metrics(summary: Summary) -> dict[str, int | float | None]:
    """Only the six owner-permitted aggregate metrics cross the public report boundary."""
    return {
        "profit_factor": summary.profit_factor,
        "expectancy_r": summary.expectancy_r,
        "max_dd_pct": summary.max_dd_pct,
        "trade_count": summary.trade_count,
        "sharpe": summary.sharpe,
        "dsr": summary.dsr,
    }


def flat_evidence(year: int, start: datetime, stop: datetime) -> FoldEvidence:
    """Genuinely absent input/selection is flat calendar evidence, never invented trades."""
    days = ((stop - timedelta(microseconds=1)).date() - start.date()).days + 1
    return FoldEvidence(year=year, daily_returns=(0.0,) * days, max_dd=0, path_max=1, path_min=1)


def evaluation_evidence(
    evaluation: GoldResearchEvaluation,
    *,
    year: int,
    calendar_start: datetime,
    stop: datetime,
) -> FoldEvidence:
    """Use F's original all-in entry risk and complete daily/intrabar equity observations."""
    result, audit = evaluation.result, evaluation.audit
    daily = {point.timestamp.date(): point.equity for point in result.equity}
    day, last_day = calendar_start.date(), (stop - timedelta(microseconds=1)).date()
    previous = INITIAL_CASH
    returns = []
    while day <= last_day:
        current = daily.get(day, previous)
        returns.append(float(current / previous - 1))
        previous = current
        day += timedelta(days=1)
    peak = maximum = minimum = INITIAL_CASH
    max_dd = Decimal("0")
    for _, equity in audit.equity_bounds:
        peak, maximum, minimum = max(peak, equity), max(maximum, equity), min(minimum, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    trades = []
    for trade in result.trades:
        risk = audit.initial_risk.get(trade.entry_time)
        if risk is None or risk <= 0:
            raise ResearchRefused("gold_original_planned_risk_missing")
        trades.append(
            NetTrade(
                entry_day=trade.entry_time.date(),
                pnl=float(trade.pnl),
                net_r=float(trade.pnl / risk),
            )
        )
    return FoldEvidence(
        year=year,
        trades=tuple(trades),
        daily_returns=tuple(returns),
        max_dd=float(max_dd),
        path_max=float(maximum / INITIAL_CASH),
        path_min=float(minimum / INITIAL_CASH),
        circuit_trips=int(audit.peak_trip_at is not None),
        halted_days=(last_day - audit.peak_trip_at.date()).days + 1 if audit.peak_trip_at else 0,
        ambiguous_bars=audit.ambiguous_bars,
    )


def sensitivity_paths(strategy: str) -> tuple[str, ...]:
    """A alone adds the approved strict fill path; no sensitivity can select another cell."""
    if strategy not in STRATEGIES:
        raise ResearchRefused("gold_unregistered_strategy")
    fills = ("touch", "through") if strategy == "london_sweep_mss_fvg" else ("touch",)
    return tuple(
        f"{fill}/{ordering}/{cost}"
        for fill in fills
        for ordering in ("stop", "target")
        for cost in COSTS
    )


def development_checklist(
    years: tuple[Summary, Summary],
    aggregate: Summary,
    stressed: tuple[Summary, Summary],
    *,
    beats_random: bool,
    missing: bool,
) -> tuple[GoldVerdict, dict[str, bool]]:
    """Disclose every registered check; known reject criteria survive missing evidence."""
    verdict = gold_development_verdict(years, aggregate, stressed, beats_random=beats_random)
    if missing and verdict != "reject":
        verdict = "insufficient evidence"
    return verdict, {
        "both_training_choices": not missing,
        "positive_2022": years[0].expectancy_r is not None and years[0].expectancy_r > 0,
        "positive_2023": years[1].expectancy_r is not None and years[1].expectancy_r > 0,
        "positive_stress_2022": stressed[0].expectancy_r is not None
        and stressed[0].expectancy_r > 0,
        "positive_stress_2023": stressed[1].expectancy_r is not None
        and stressed[1].expectancy_r > 0,
        "aggregate_pf_1_3": aggregate.profit_factor is not None and aggregate.profit_factor >= 1.3,
        "max_dd_15pct": aggregate.max_dd_pct <= 15,
        "at_least_60_trades": aggregate.trade_count >= 60,
        "beats_cash": aggregate.net_return > 0,
        "beats_random_95": beats_random,
    }


class GoldBatch:
    """One registered development run with identical-identity technical resumes only."""

    def __init__(self, repo: Path, source: GoldSource) -> None:
        # Registration verification intentionally precedes constructing even the private store.
        self.implementation_sha256 = implementation_identity(repo)
        self.repo, self.source = repo, source
        self.store = PrivateStore(source, RUN_ID)
        self.trials = gold_trials()
        self.started = time.perf_counter()
        self.peak_rss = psutil.Process().memory_info().rss
        self._prepared_key: tuple[str, timedelta, datetime] | None = None
        self._prepared_value: GoldPrepared | None = None

    def prepared(self, trial: GoldTrial, stop: datetime) -> GoldPrepared:
        """Retain one bounded prefix; config variants share source features and coverage."""
        key = (trial.strategy, trial.timeframe, stop)
        if key != self._prepared_key or self._prepared_value is None:
            self._prepared_value = None
            self._prepared_value = self.source.load(trial, stop)
            self._prepared_key = key
        return replace(self._prepared_value, trial=trial)

    def status(self, stage: str, completed: int) -> None:
        """Mutable health metadata only; immutable outcomes remain separate checkpoints."""
        self.peak_rss = max(self.peak_rss, psutil.Process().memory_info().rss)
        self.store.status(
            {
                "stage": stage,
                "completed": completed,
                "runtime_seconds": time.perf_counter() - self.started,
                "peak_rss_bytes": self.peak_rss,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

    def evidence(
        self,
        name: str,
        *,
        trial_index: int,
        start: datetime,
        stop: datetime,
        year: int,
        calendar_start: datetime | None = None,
        path: str = "touch/stop/1",
        comparison: str | None = None,
        seed: int = 20261102,
    ) -> FoldEvidence:
        """Replay/checkpoint one closed sub-job; any recorded defect stops the batch."""
        if comparison is not None and comparison not in {"cash", "random", "buy_hold"}:
            raise ResearchRefused("gold_unregistered_comparison")
        old = self.store.read(name)
        if old is not None:
            return FoldEvidence.model_validate(old)
        if self.store.read(name + ".refusal.json") is not None:
            raise ResearchRefused("gold_recorded_refusal_stop_for_review")
        trial = self.trials[trial_index]
        if path not in sensitivity_paths(trial.strategy):
            raise ResearchRefused("gold_unregistered_sensitivity_path")
        anchor = calendar_start or start
        try:
            data = self.prepared(trial, stop)
            if not data.has_scored_bars(start, stop):
                result = flat_evidence(year, anchor, stop)
            elif comparison is not None:
                if comparison not in {"cash", "random", "buy_hold"}:
                    raise ResearchRefused("gold_unregistered_comparison")
                # Literal construction keeps the closed comparison API strict under mypy.
                mode: Literal["cash", "random", "buy_hold"] = (
                    "cash"
                    if comparison == "cash"
                    else "random"
                    if comparison == "random"
                    else "buy_hold"
                )
                result = data.batch.comparison_evidence(
                    mode,
                    start=start,
                    stop=stop,
                    year=year,
                    calendar_start=anchor,
                    seed=seed,
                )
            else:
                fill, ordering, stress = path.split("/")
                evaluated = data.batch.evaluate(
                    gold_strategy(trial),
                    purpose="historical_research",
                    start=start,
                    stop=stop,
                    stress_multiplier=Decimal(stress),
                    target_first=ordering == "target",
                    trade_through_limit=fill == "through",
                )
                result = evaluation_evidence(evaluated, year=year, calendar_start=anchor, stop=stop)
        except Exception as exc:
            self.store.write(
                name + ".refusal.json",
                {
                    "error_type": type(exc).__name__,
                    "trial_index": trial_index,
                    "year": year,
                    "state": "STOP_FOR_REVIEW",
                },
            )
            raise ResearchRefused("gold_replay_refused_stop_for_review") from None
        self.store.write(name, result.model_dump(mode="json"))
        return result

    def _training(self, label: str, stop: datetime) -> tuple[dict[str, int | None], float | None]:
        cells = []
        for index, trial in enumerate(self.trials):
            evidence = self.evidence(
                f"training/{label}/{index}.json",
                trial_index=index,
                start=START,
                stop=stop,
                year=stop.year,
            )
            cells.append(training_record(index, trial, evidence))
            self.status(f"training-{label}", index + 1)
        selected = {}
        for strategy in STRATEGIES:
            chosen = select_cell(
                [c for c in cells if self.trials[c.trial_index].strategy == strategy]
            )
            selected[strategy] = chosen.trial_index if chosen is not None else None
        benchmark = gold_null_benchmark(cells)
        self.store.write(
            f"training/{label}/selection.json",
            {
                "cells": [c.model_dump(mode="json") for c in cells],
                "selected": selected,
                "benchmark": benchmark,
            },
        )
        return selected, benchmark

    def _quality(self, year: int, index: int, start: datetime, stop: datetime) -> dict[str, Any]:
        name = f"quality/{year}/{index}.json"
        old = self.store.read(name)
        if old is not None:
            return old
        trial = self.trials[index]
        data = self.prepared(trial, stop)
        decisions = data.batch.replay(gold_strategy(trial), purpose="historical_research")
        counts = data.quality_counts(start, stop, decisions)
        self.store.write(name, counts)
        return counts

    def run(self) -> dict[str, Any]:
        """Freeze both OOS selectors, score once, then freeze final development parameters."""
        identity = {
            "registration_sha256": REGISTRATION_SHA,
            "implementation_sha256": self.implementation_sha256,
            "data_manifest_sha256": self.source.identity(),
            "n_trials": GOLD_TRIAL_COUNT,
        }
        previous = self.store.read("identity.json")
        if previous is not None and previous != identity:
            raise ResearchRefused("gold_resume_identity_changed_stop_for_review")
        self.store.write("identity.json", identity)
        finished = self.store.read("results.json")
        if finished is not None:
            return finished
        selections, benchmarks = {}, {}
        # Both training stages finish before the first evaluation or comparison job.
        for year in YEARS:
            selections[year], benchmarks[year] = self._training(
                str(year), datetime(year, 1, 1, tzinfo=UTC) - timedelta(days=1)
            )
        benchmark = (
            max(b for b in benchmarks.values() if b is not None)
            if all(b is not None for b in benchmarks.values())
            else None
        )
        rows: list[dict[str, Any]] = []
        private_details: list[dict[str, Any]] = []
        final_verdicts: dict[str, GoldVerdict] = {}
        for strategy in STRATEGIES:
            paths: dict[str, list[FoldEvidence]] = {p: [] for p in sensitivity_paths(strategy)}
            comparisons: dict[str, list[FoldEvidence]] = {name: [] for name in ("cash", "buy_hold")}
            randoms: dict[int, list[FoldEvidence]] = {
                seed: [] for seed in range(20261102, 20261202)
            }
            missing, quality, choices = [], [], []
            for year in YEARS:
                selected = selections[year][strategy]
                anchor = datetime(year, 1, 1, tzinfo=UTC)
                start = anchor + timedelta(days=1)
                stop = min(datetime(year + 1, 1, 1, tzinfo=UTC), STOP - timedelta(microseconds=1))
                choices.append({"year": year, "trial_index": selected})
                if selected is None:
                    missing.append(year)
                    flat = flat_evidence(year, anchor, stop)
                    for evidence_list in paths.values():
                        evidence_list.append(flat)
                    # Coverage remains reportable even when C cannot form volume-backed entries.
                    representatives: dict[timedelta, int] = {}
                    for index, trial in enumerate(self.trials):
                        if trial.strategy == strategy:
                            representatives.setdefault(trial.timeframe, index)
                    quality.append(
                        {
                            "year": year,
                            "status": "no eligible training cell",
                            "timeframes": [
                                {
                                    "timeframe_seconds": int(period.total_seconds()),
                                    "diagnostic_trial_index": index,
                                    "selection_status": "not selected; first registered cell for coverage",
                                    "counts": self._quality(year, index, start, stop),
                                }
                                for period, index in sorted(representatives.items())
                            ],
                        }
                    )
                    continue
                prefix = f"evaluation/{year}/{strategy}"
                for path in paths:
                    paths[path].append(
                        self.evidence(
                            prefix + "/" + path + ".json",
                            trial_index=selected,
                            start=start,
                            stop=stop,
                            year=year,
                            calendar_start=anchor,
                            path=path,
                        )
                    )
                    self.status(f"{year}-{strategy}-{path}", len(paths[path]))
                quality.append(
                    {
                        "year": year,
                        "timeframe_seconds": int(self.trials[selected].timeframe.total_seconds()),
                        "counts": self._quality(year, selected, start, stop),
                    }
                )
                for name in comparisons:
                    comparisons[name].append(
                        self.evidence(
                            prefix + "/" + name + ".json",
                            trial_index=selected,
                            start=start,
                            stop=stop,
                            year=year,
                            calendar_start=anchor,
                            comparison=name,
                        )
                    )
                for seed in randoms:
                    randoms[seed].append(
                        self.evidence(
                            prefix + f"/random-{seed}.json",
                            trial_index=selected,
                            start=start,
                            stop=stop,
                            year=year,
                            calendar_start=anchor,
                            comparison="random",
                            seed=seed,
                        )
                    )
                    self.status(f"{year}-{strategy}-random", seed - 20261101)
            random_95 = (
                sorted(summarize(f).net_return for f in randoms.values())[94]
                if not missing
                else None
            )
            metrics = {
                path: {
                    "aggregate": public_metrics(summarize(folds, benchmark)),
                    "folds": [
                        {
                            "year": fold.year,
                            "status": "insufficient evidence"
                            if fold.year in missing
                            else "evaluated",
                            "metrics": public_metrics(summarize([fold], benchmarks[fold.year])),
                            "circuit_trips": fold.circuit_trips,
                            "halted_days": fold.halted_days,
                            "ambiguous_bars": fold.ambiguous_bars,
                        }
                        for fold in folds
                    ],
                }
                for path, folds in paths.items()
            }
            verdicts: dict[str, GoldVerdict] = {}
            checks = {}
            fills = ("touch", "through") if strategy == "london_sweep_mss_fvg" else ("touch",)
            for fill in fills:
                for ordering in ("stop", "target"):
                    base = paths[f"{fill}/{ordering}/1"]
                    stressed = paths[f"{fill}/{ordering}/1.5"]
                    aggregate = summarize(base, benchmark)
                    key = fill + "/" + ordering
                    verdicts[key], checks[key] = development_checklist(
                        (summarize([base[0]]), summarize([base[1]])),
                        aggregate,
                        (summarize([stressed[0]]), summarize([stressed[1]])),
                        beats_random=random_95 is not None and aggregate.net_return > random_95,
                        missing=bool(missing),
                    )
            final: GoldVerdict = "promising"
            for verdict in verdicts.values():
                final = gold_ambiguity_verdict(final, verdict)
            final_verdicts[strategy] = final
            row: dict[str, Any] = {
                "strategy": strategy,
                "symbol": "XAUTUSDT",
                "proxy": PROXY_LABEL,
                "status": "development only: not validated",
                "verdict": final,
                "missing_training_folds": missing,
                "selections": choices,
                "metrics": metrics,
                "ambiguity_verdicts": verdicts,
                "checklists": checks,
                "quality_gate": quality,
            }
            rows.append(row)
            private_details.append(
                {
                    "strategy": strategy,
                    "random_95": random_95,
                    "comparisons": {
                        name: summarize(folds).model_dump(mode="json")
                        for name, folds in comparisons.items()
                    },
                    "weekly_bootstrap": {
                        path: weekly_bootstrap(folds) for path, folds in paths.items()
                    },
                }
            )
        # No final full-development choice is allowed to influence either OOS selector.
        final_selected, _ = self._training("final-2021-2023", STOP - timedelta(days=1))
        for row in rows:
            strategy = row["strategy"]
            row["preliminary_development_verdict"] = row["verdict"]
            row["final_training_ineligible"] = final_selected[strategy] is None
            if final_selected[strategy] is None and final_verdicts[strategy] != "reject":
                final_verdicts[strategy] = "insufficient evidence"
                row["verdict"] = "insufficient evidence"
            self.store.write(f"summary/{strategy}.json", row)
        frozen = gold_frozen_payload(
            {
                name: self.trials[index] if index is not None else None
                for name, index in final_selected.items()
            },
            verdicts=final_verdicts,
            registration_sha256=REGISTRATION_SHA,
            implementation_sha256=self.implementation_sha256,
        )
        self.store.write("frozen-parameters.json", frozen)
        results = {
            "identity": identity,
            "verdicts": rows,
            "frozen_parameters": frozen,
            "private_comparisons": private_details,
            "runtime_seconds": time.perf_counter() - self.started,
            "peak_rss_bytes": self.peak_rss,
        }
        self.store.write("results.json", results)
        self.status("complete", len(rows))
        return results
