"""One frozen Stage 3 batch, immutable sub-job checkpoints and training-only selection."""

from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psutil

from tb.backtest.stage3_data import DATASET_ID, PrivateStore, VisionGold
from tb.backtest.stage3_metrics import (
    FoldEvidence,
    TrainingCell,
    ambiguity_verdict,
    checklist,
    daily_sharpe,
    select_cell,
    summarize,
    training_benchmark,
)
from tb.backtest.stage3_replay import PreparedBars, buy_hold, replay
from tb.backtest.validation import TRAIN_START, default_walk_forward_windows
from tb.core.leases import writer_lease
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.research.models import ResearchRefused, digest
from tb.research.registry import declare_artifact, load_vision_plan, safe
from tb.strategies.stage3 import StrategyTrial, preregistered_trials

REGISTRATION_SHA = "f7109e15baf3cecbc0f21d28df3e671d886be424947fed5e9f9c1ec801ddf396"
RUN_ID = "registered-162-v1"
PATHS = ("stop-1", "stop-1.5", "stop-2", "target-1", "target-1.5", "target-2")


def implementation_identity(repo: Path) -> str:
    """Source, config, dependency and registration bytes bind every resume."""
    registration = repo / "reports/stage3/P11f-preregistration.md"
    if sha256_file(registration) != REGISTRATION_SHA:
        raise ResearchRefused("stage3_registration_changed")
    paths = [
        *sorted((repo / "src").rglob("*.py")),
        *sorted((repo / "config").rglob("*.yaml")),
        repo / "pyproject.toml",
        repo / "uv.lock",
        registration,
    ]
    return digest([(p.relative_to(repo).as_posix(), sha256_file(p)) for p in paths])


def training_record(index: int, trial: StrategyTrial, evidence: FoldEvidence) -> TrainingCell:
    summary = summarize([evidence])
    config = trial.config.model_dump()
    parameters = {
        "trend_vwap_pullback": ("touch_tolerance_atr", "stop_atr"),
        "volatility_breakout": ("history_bars", "compression_bars"),
        "ts_momentum": ("return_bars", "stop_atr"),
    }[trial.strategy]
    return TrainingCell(
        trial_index=index,
        trade_count=summary.trade_count,
        expectancy_r=summary.expectancy_r,
        daily_sharpe=daily_sharpe(evidence.daily_returns),
        timeframe_seconds=int(trial.timeframe.total_seconds()),
        parameters=tuple(float(config[p]) for p in parameters),
    )


class Batch:
    """Resume identical completed work; never select from evaluation-year outcomes."""

    def __init__(self, repo: Path, source: VisionGold) -> None:
        self.repo, self.source, self.store = repo, source, PrivateStore(source, RUN_ID)
        self.trials = preregistered_trials()
        self.started = time.perf_counter()
        self.peak_rss = psutil.Process().memory_info().rss
        self.status_path = safe(source.root, self.store.base + "/status.json")
        self._prepared_key: tuple[str, int, datetime] | None = None
        self._prepared_value: PreparedBars | None = None

    def prepared(self, symbol: str, seconds: int, stop: datetime) -> PreparedBars:
        name = {900: "15m", 3600: "1h", 14400: "4h"}[seconds]
        key = (symbol, seconds, stop)
        if self._prepared_key != key or self._prepared_value is None:
            self._prepared_value = None
            self._prepared_value = self.source.load(symbol, name, stop)
            self._prepared_key = key
        return self._prepared_value

    def status(self, stage: str, completed: int) -> None:
        plan = load_vision_plan(self.source.root, DATASET_ID, self.source.clock())
        declare_artifact(self.source.root, plan, self.status_path, ["reports"], [plan.digest])
        atomic_write_json(
            self.status_path,
            {
                "stage": stage,
                "completed": completed,
                "runtime_seconds": time.perf_counter() - self.started,
                "peak_rss_bytes": self.peak_rss,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

    def evidence(
        self,
        name: str,
        *,
        trial_index: int,
        start: datetime,
        stop: datetime,
        year: int,
        comparison: str | None = None,
        seed: int = 20261102,
        path: str = "stop-1",
    ) -> FoldEvidence:
        old = self.store.read(name)
        if old is not None:
            return FoldEvidence.model_validate(old)
        if self.store.read(name + ".refusal.json") is not None:
            raise ResearchRefused("stage3_recorded_refusal_stop_for_review")
        trial = self.trials[trial_index]
        calendar_start = start - timedelta(days=1) if name.startswith("evaluation/") else start
        try:
            data = self.prepared(trial.symbol, int(trial.timeframe.total_seconds()), stop)
            if comparison == "buy_hold":
                result = buy_hold(data, start, stop, calendar_start=calendar_start)
            else:
                from decimal import Decimal

                ordering, stress = path.split("-")
                result = replay(
                    data,
                    start=start,
                    stop=stop,
                    year=year,
                    trial=trial if comparison is None else None,
                    comparison=comparison,
                    seed=seed,
                    stress=Decimal(stress),
                    target_first=ordering == "target",
                    calendar_start=calendar_start,
                )
        except Exception as exc:
            self.store.write(
                name + ".refusal.json",
                {
                    "error_type": type(exc).__name__,
                    "trial_index": trial_index,
                    "year": year,
                    "state": "STOP_FOR_HUMAN_REVIEW",
                },
            )
            raise ResearchRefused("stage3_replay_refused_stop_for_review") from None
        self.store.write(name, result.model_dump(mode="json"))
        return result

    def run(self) -> dict[str, Any]:
        identity = {
            "registration_sha256": REGISTRATION_SHA,
            "implementation_sha256": implementation_identity(self.repo),
            "data_manifest_sha256": self.source.identity(),
            "n_trials": 162,
        }
        previous = self.store.read("identity.json")
        if previous is not None and previous != identity:
            raise ResearchRefused("stage3_resume_identity_changed_stop_for_review")
        self.store.write("identity.json", identity)
        finished = self.store.read("results.json")
        if finished is not None:
            return finished
        selections: dict[int, dict[str, int | None]] = {}
        benchmarks = {}
        groups = sorted({(t.strategy, t.symbol) for t in self.trials})
        # Freeze all four training selectors before any evaluation, including 2024.
        for window in default_walk_forward_windows():
            year = window.evaluate_start.year
            stop = window.evaluate_start - timedelta(days=1)
            cells = []
            for index, trial in enumerate(self.trials):
                evidence = self.evidence(
                    f"training/{year}/{index}.json",
                    trial_index=index,
                    start=TRAIN_START,
                    stop=stop,
                    year=year,
                )
                cells.append(training_record(index, trial, evidence))
                self.status(f"training-{year}", index + 1)
            selected = {}
            for strategy, symbol in groups:
                chosen = select_cell(
                    [
                        cell
                        for cell in cells
                        if (
                            self.trials[cell.trial_index].strategy,
                            self.trials[cell.trial_index].symbol,
                        )
                        == (strategy, symbol)
                    ]
                )
                selected[strategy + "/" + symbol] = chosen.trial_index if chosen else None
            benchmark = training_benchmark(cells)
            self.store.write(
                f"training/{year}/selection.json",
                {
                    "cells": [c.model_dump(mode="json") for c in cells],
                    "selected": selected,
                    "benchmark": benchmark,
                },
            )
            selections[year], benchmarks[year] = selected, benchmark
        summaries = []
        private_details = []
        for strategy, symbol in groups:
            key = strategy + "/" + symbol
            paths: dict[str, list[FoldEvidence]] = {p: [] for p in PATHS}
            buy_holds: list[FoldEvidence] = []
            randoms: dict[int, list[FoldEvidence]] = {
                seed: [] for seed in range(20261102, 20261202)
            }
            other_comparisons: dict[str, list[FoldEvidence]] = {
                name: [] for name in ("cash", "yesterday", "ema", "channel")
            }
            missing: list[int] = []
            for window in default_walk_forward_windows():
                year = window.evaluate_start.year
                selected_index = selections[year][key]
                if selected_index is None:
                    missing.append(year)
                    days = (
                        datetime(year + 1, 1, 1, tzinfo=UTC) - datetime(year, 1, 1, tzinfo=UTC)
                    ).days
                    flat = FoldEvidence(
                        year=year, daily_returns=(0.0,) * days, max_dd=0, path_max=1, path_min=1
                    )
                    for path in PATHS:
                        paths[path].append(flat)
                    continue
                start, stop = (
                    window.evaluate_start + timedelta(days=1),
                    window.evaluate_end + timedelta(microseconds=1),
                )
                prefix = f"evaluation/{year}/{key}"
                for path in PATHS:
                    paths[path].append(
                        self.evidence(
                            prefix + "/" + path + ".json",
                            trial_index=selected_index,
                            start=start,
                            stop=stop,
                            year=year,
                            path=path,
                        )
                    )
                    self.status(f"{year}-{key}-{path}", len(paths[path]))
                buy_holds.append(
                    self.evidence(
                        prefix + "/buy_hold.json",
                        trial_index=selected_index,
                        start=start,
                        stop=stop,
                        year=year,
                        comparison="buy_hold",
                    )
                )
                for name in other_comparisons:
                    other_comparisons[name].append(
                        self.evidence(
                            prefix + "/" + name + ".json",
                            trial_index=selected_index,
                            start=start,
                            stop=stop,
                            year=year,
                            comparison=name,
                        )
                    )
                for seed in randoms:
                    randoms[seed].append(
                        self.evidence(
                            prefix + f"/random-{seed}.json",
                            trial_index=selected_index,
                            start=start,
                            stop=stop,
                            year=year,
                            comparison="random",
                            seed=seed,
                        )
                    )
                    self.status(f"{year}-{key}-random", seed - 20261101)
            finite_dev = [benchmarks[y] for y in (2021, 2022, 2023)]
            dev_benchmark = (
                max(b for b in finite_dev if b is not None)
                if all(b is not None for b in finite_dev)
                else None
            )

            def scoped(evidence: list[FoldEvidence], validation: bool) -> list[FoldEvidence]:
                return [f for f in evidence if (f.year == 2024) == validation]

            def comparator_values(
                validation: bool,
                missing: list[int] = missing,
                randoms: dict[int, list[FoldEvidence]] = randoms,
                buy_holds: list[FoldEvidence] = buy_holds,
            ) -> tuple[float | None, tuple[float, float] | None]:
                expected = {2024} if validation else {2021, 2022, 2023}
                if any(y in missing for y in expected):
                    return None, None
                random_returns = sorted(
                    summarize(scoped(r, validation)).net_return for r in randoms.values()
                )
                benchmark = summarize(scoped(buy_holds, validation))
                return random_returns[94], (benchmark.net_return, benchmark.max_dd_pct / 100)

            random_dev, bh_dev = comparator_values(False)
            random_val, bh_val = comparator_values(True)
            verdicts, checklists = {}, {}
            for ordering in ("stop", "target"):
                dev = scoped(paths[ordering + "-1"], False)
                val = scoped(paths[ordering + "-1"], True)
                verdict, checks = checklist(
                    dev,
                    val,
                    dev_benchmark=dev_benchmark,
                    validation_benchmark=benchmarks[2024],
                    random_dev_95=random_dev,
                    random_validation_95=random_val,
                    buy_hold_dev=bh_dev,
                    buy_hold_validation=bh_val,
                    stressed_dev=summarize(scoped(paths[ordering + "-1.5"], False)),
                    stressed_validation=summarize(scoped(paths[ordering + "-1.5"], True)),
                )
                if 2024 in missing:
                    verdict = "insufficient evidence"
                verdicts[ordering], checklists[ordering] = verdict, checks
            final_verdict = ambiguity_verdict(verdicts["stop"], verdicts["target"])
            metrics = {}
            for path in PATHS:
                metrics[path] = {
                    "development": summarize(scoped(paths[path], False), dev_benchmark).model_dump(
                        mode="json"
                    ),
                    "validation": summarize(scoped(paths[path], True), benchmarks[2024]).model_dump(
                        mode="json"
                    ),
                }
            folds = []
            for year in (2021, 2022, 2023, 2024):
                fold_evidence = next((f for f in paths["stop-1"] if f.year == year), None)
                folds.append(
                    {
                        "year": year,
                        "status": "insufficient evidence" if year in missing else "evaluated",
                        "metrics": summarize([fold_evidence], benchmarks[year]).model_dump(
                            mode="json"
                        )
                        if fold_evidence
                        else None,
                        "circuit_trips": fold_evidence.circuit_trips if fold_evidence else 0,
                        "halted_days": fold_evidence.halted_days if fold_evidence else 0,
                        "ambiguous_bars": fold_evidence.ambiguous_bars if fold_evidence else 0,
                    }
                )
            row = {
                "strategy": strategy,
                "symbol": symbol,
                "verdict": final_verdict,
                "missing_training_folds": missing,
                "metrics": metrics,
                "checklists": checklists,
                "ambiguity_verdicts": verdicts,
                "folds": folds,
            }
            summaries.append(row)
            private_details.append(
                {
                    "strategy": strategy,
                    "symbol": symbol,
                    "buy_hold": {
                        "development": summarize(scoped(buy_holds, False)).model_dump(mode="json"),
                        "validation": summarize(scoped(buy_holds, True)).model_dump(mode="json"),
                    },
                    "random_dev_95": random_dev,
                    "random_validation_95": random_val,
                    "comparisons": {
                        name: {
                            "development": summarize(scoped(e, False)).model_dump(mode="json"),
                            "validation": summarize(scoped(e, True)).model_dump(mode="json"),
                        }
                        for name, e in other_comparisons.items()
                    },
                }
            )
            self.store.write(f"summary/{key}.json", row)
        results = {
            "identity": identity,
            "verdicts": summaries,
            "private_comparisons": private_details,
            "nominal_break_even_win_rate": 1 / 3,
            "runtime_seconds": time.perf_counter() - self.started,
            "peak_rss_bytes": self.peak_rss,
        }
        self.store.write("results.json", results)
        self.status("complete", len(summaries))
        return results


def main() -> None:
    """Run approved closed Part B locally; resume requires byte-identical identities."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    if (repo / ".env").exists() or (args.data_root / ".env").exists():
        raise ResearchRefused("stage3_credential_free_checkouts_required")
    implementation_identity(repo)  # registration check precedes even registry metadata
    batch = Batch(repo, VisionGold(args.data_root))
    done = threading.Event()

    def sample_memory() -> None:
        process = psutil.Process()
        while not done.wait(0.2):
            batch.peak_rss = max(batch.peak_rss, process.memory_info().rss)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        with writer_lease(safe(args.data_root, batch.store.base + "/run.lock")):
            result = batch.run()
        print(
            json.dumps(
                {
                    "complete": True,
                    "experiments": len(result["verdicts"]),
                    "registration_sha256": REGISTRATION_SHA,
                }
            )
        )
    finally:
        done.set()
        sampler.join()


if __name__ == "__main__":
    main()
