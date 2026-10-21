from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from tb.backtest.engine import BacktestEngine, Bar, EntrySignal
from tb.backtest.validation import (
    FINAL_TEST_START,
    EvaluationWindow,
    FinalTestLockedError,
    WalkForwardRunner,
    authorize_evaluation,
    default_walk_forward_windows,
)


def _window(year: int) -> EvaluationWindow:
    return EvaluationWindow(
        name=str(year),
        train_start=datetime(year - 1, 1, 1, tzinfo=UTC),
        train_end=datetime(year - 1, 12, 31, tzinfo=UTC),
        evaluate_start=datetime(year, 1, 1, tzinfo=UTC),
        evaluate_end=datetime(year, 12, 31, tzinfo=UTC),
    )


def _bar(timestamp: datetime) -> Bar:
    return Bar(timestamp=timestamp, open=100, high=110, low=90, close=100, volume=100)


def test_default_windows_expand_without_touching_final_period() -> None:
    windows = default_walk_forward_windows()

    assert [item.evaluate_start.year for item in windows] == [2021, 2022, 2023, 2024]
    assert all(item.train_start.year == 2020 for item in windows)
    assert windows[-1].evaluate_end < FINAL_TEST_START


@pytest.mark.parametrize(
    "changes",
    [
        {"train_start": datetime(2024, 1, 1)},
        {"train_end": datetime(2024, 1, 2, tzinfo=UTC)},
        {"evaluate_end": datetime(2023, 1, 1, tzinfo=UTC)},
    ],
)
def test_invalid_window_fails_closed(changes: dict[str, datetime]) -> None:
    values: dict[str, object] = {
        "name": "bad",
        "train_start": datetime(2023, 1, 1, tzinfo=UTC),
        "train_end": datetime(2023, 12, 31, tzinfo=UTC),
        "evaluate_start": datetime(2024, 1, 1, tzinfo=UTC),
        "evaluate_end": datetime(2024, 12, 31, tzinfo=UTC),
    }
    values.update(changes)

    with pytest.raises(ValidationError):
        EvaluationWindow.model_validate(values)


def test_locked_period_refuses_before_creating_log(tmp_path: Path) -> None:
    log = tmp_path / "final.md"

    with pytest.raises(FinalTestLockedError, match="--final-test"):
        authorize_evaluation(_window(2025), final_test=False, log_path=log, run_id="refused")

    assert not log.exists()


def test_explicit_final_authorization_appends_audit_entry(tmp_path: Path) -> None:
    log = tmp_path / "final.md"
    authorized = datetime(2026, 10, 21, 2, 30, tzinfo=UTC)

    authorize_evaluation(
        _window(2025),
        final_test=True,
        log_path=log,
        run_id="approved-run",
        authorized_at=authorized,
    )
    authorize_evaluation(
        _window(2025),
        final_test=True,
        log_path=log,
        run_id="second-run",
        authorized_at=authorized + timedelta(minutes=1),
    )

    content = log.read_text(encoding="utf-8")
    assert content.count("# Final test access log") == 1
    assert "approved-run" in content
    assert "second-run" in content


@pytest.mark.parametrize("run_id", ["", "bad|id", "bad\nid"])
def test_unsafe_final_run_id_is_rejected(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        authorize_evaluation(
            _window(2025), final_test=True, log_path=tmp_path / "log.md", run_id=run_id
        )


def test_walk_forward_builder_receives_past_and_evaluation_separately() -> None:
    window = _window(2024)
    training_time = datetime(2023, 6, 1, tzinfo=UTC)
    evaluation_time = datetime(2024, 6, 1, tzinfo=UTC)
    seen: list[tuple[tuple[Bar, ...], tuple[Bar, ...]]] = []

    def build(training: tuple[Bar, ...], evaluation: tuple[Bar, ...]) -> list[EntrySignal]:
        seen.append((training, evaluation))
        return []

    runner = WalkForwardRunner(lambda: BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")))
    results = runner.run(
        [_bar(training_time), _bar(evaluation_time)],
        build,
        windows=[window],
        run_id="walk-forward",
    )

    assert len(results) == 1
    assert seen[0][0][0].timestamp == training_time
    assert seen[0][1][0].timestamp == evaluation_time


def test_walk_forward_rejects_signal_outside_evaluation() -> None:
    window = _window(2024)
    bars = [_bar(datetime(2023, 6, 1, tzinfo=UTC)), _bar(datetime(2024, 6, 1, tzinfo=UTC))]

    def build(training: tuple[Bar, ...], evaluation: tuple[Bar, ...]) -> list[EntrySignal]:
        del evaluation
        return [
            EntrySignal(
                timestamp=training[0].timestamp,
                symbol="BTCUSDT",
                stop_price=90,
                target_price=110,
            )
        ]

    runner = WalkForwardRunner(lambda: BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")))
    with pytest.raises(ValueError, match="pre-evaluation"):
        runner.run(bars, build, windows=[window], run_id="leak")


def test_walk_forward_purge_removes_near_boundary_training_rows() -> None:
    window = EvaluationWindow(
        name="purged",
        train_start=datetime(2023, 1, 1, tzinfo=UTC),
        train_end=datetime(2023, 12, 31, 23, 59, tzinfo=UTC),
        evaluate_start=datetime(2024, 1, 1, tzinfo=UTC),
        evaluate_end=datetime(2024, 12, 31, tzinfo=UTC),
    )
    old = _bar(datetime(2023, 12, 20, tzinfo=UTC))
    near = _bar(datetime(2023, 12, 31, tzinfo=UTC))
    evaluation = _bar(datetime(2024, 1, 1, tzinfo=UTC))
    seen: list[tuple[Bar, ...]] = []

    def build(training: tuple[Bar, ...], _: tuple[Bar, ...]) -> list[EntrySignal]:
        seen.append(training)
        return []

    runner = WalkForwardRunner(lambda: BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")))
    runner.run(
        [old, near, evaluation],
        build,
        windows=[window],
        run_id="purged",
        purge=timedelta(days=2),
    )

    assert seen == [(old,)]
    with pytest.raises(ValueError, match="purge"):
        runner.run(
            [old, evaluation],
            build,
            windows=[window],
            run_id="bad-purge",
            purge=timedelta(seconds=-1),
        )
