"""Leak-resistant walk-forward windows and the locked final-test boundary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, model_validator

from tb.backtest.engine import BacktestEngine, BacktestResult, Bar, EntrySignal

TRAIN_START = datetime(2020, 10, 1, tzinfo=UTC)
VALIDATION_END = datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
FINAL_TEST_START = datetime(2025, 1, 1, tzinfo=UTC)


class FinalTestLockedError(ValueError):
    """Raised before final-period observations are evaluated without authorization."""


class EvaluationWindow(BaseModel):
    """One expanding-training walk-forward evaluation window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    train_start: datetime
    train_end: datetime
    evaluate_start: datetime
    evaluate_end: datetime

    @model_validator(mode="after")
    def ordered_and_aware(self) -> EvaluationWindow:
        """Reject overlap, naive timestamps, and inverted boundaries."""

        timestamps = (
            self.train_start,
            self.train_end,
            self.evaluate_start,
            self.evaluate_end,
        )
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise ValueError("Walk-forward boundaries must be timezone-aware")
        if self.train_start > self.train_end:
            raise ValueError("Training window is inverted")
        if self.evaluate_start > self.evaluate_end:
            raise ValueError("Evaluation window is inverted")
        if self.train_end >= self.evaluate_start:
            raise ValueError("Training and evaluation windows must not overlap")
        return self


class WalkForwardResult(NamedTuple):
    """Simulation result paired with the exact window that produced it."""

    window: EvaluationWindow
    result: BacktestResult


SignalBuilder = Callable[[tuple[Bar, ...], tuple[Bar, ...]], Sequence[EntrySignal]]
EngineFactory = Callable[[], BacktestEngine]


def default_walk_forward_windows() -> tuple[EvaluationWindow, ...]:
    """Return expanding annual folds ending with the reserved 2024 validation year."""

    return tuple(
        EvaluationWindow(
            name="validation-2024" if year == 2024 else f"development-{year}",
            train_start=TRAIN_START,
            train_end=datetime(year - 1, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
            evaluate_start=datetime(year, 1, 1, tzinfo=UTC),
            evaluate_end=datetime(year, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
        )
        for year in range(2021, 2025)
    )


def authorize_evaluation(
    window: EvaluationWindow,
    *,
    final_test: bool,
    log_path: Path = Path("reports/final_test_log.md"),
    run_id: str,
    authorized_at: datetime | None = None,
) -> None:
    """Refuse final-period evaluation unless the explicit flag is recorded first."""

    if window.evaluate_end < FINAL_TEST_START:
        return
    if not final_test:
        raise FinalTestLockedError(
            "The final test period begins 2025-01-01; pass --final-test to authorize evaluation"
        )
    clean_run_id = run_id.strip()
    if not clean_run_id or any(character in clean_run_id for character in "\r\n|"):
        raise ValueError("run_id must be non-empty and safe for the audit log")
    timestamp = datetime.now(UTC) if authorized_at is None else authorized_at
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("authorized_at must be timezone-aware")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not log_path.exists() or log_path.stat().st_size == 0
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        if needs_header:
            handle.write("# Final test access log\n\n")
            handle.write("| Authorized UTC | Run ID | Evaluation start | Evaluation end |\n")
            handle.write("|---|---|---|---|\n")
        handle.write(
            f"| {timestamp.astimezone(UTC):%Y-%m-%d %H:%M:%S UTC} | {clean_run_id} | "
            f"{window.evaluate_start.astimezone(UTC).isoformat()} | "
            f"{window.evaluate_end.astimezone(UTC).isoformat()} |\n"
        )


class WalkForwardRunner:
    """Build signals from past-only data and evaluate each fold on a fresh engine."""

    def __init__(self, engine_factory: EngineFactory) -> None:
        self.engine_factory = engine_factory

    def run(
        self,
        bars: Sequence[Bar],
        signal_builder: SignalBuilder,
        *,
        windows: Sequence[EvaluationWindow] | None = None,
        final_test: bool = False,
        final_test_log: Path = Path("reports/final_test_log.md"),
        run_id: str,
        purge: timedelta = timedelta(0),
    ) -> tuple[WalkForwardResult, ...]:
        """Run non-empty folds, authorizing any locked window before reading its bars."""

        if purge < timedelta(0):
            raise ValueError("purge must not be negative")
        selected_windows = default_walk_forward_windows() if windows is None else tuple(windows)
        results: list[WalkForwardResult] = []
        for window in selected_windows:
            authorize_evaluation(
                window,
                final_test=final_test,
                log_path=final_test_log,
                run_id=run_id,
            )
            training_cutoff = min(window.train_end, window.evaluate_start - purge)
            training = tuple(
                bar for bar in bars if window.train_start <= bar.timestamp <= training_cutoff
            )
            evaluation = tuple(
                bar for bar in bars if window.evaluate_start <= bar.timestamp <= window.evaluate_end
            )
            if not training or not evaluation:
                continue
            signals = list(signal_builder(training, evaluation))
            if any(signal.timestamp < window.evaluate_start for signal in signals):
                raise ValueError("Signal builder returned a pre-evaluation signal")
            if any(signal.timestamp > window.evaluate_end for signal in signals):
                raise ValueError("Signal builder returned a post-evaluation signal")
            results.append(
                WalkForwardResult(window, self.engine_factory().run(list(evaluation), signals))
            )
        return tuple(results)
