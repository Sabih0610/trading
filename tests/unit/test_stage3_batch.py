"""Owned in-memory batch verifies purge/embargo, selection isolation and restart refusal."""

import copy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from tb.backtest.stage3_metrics import FoldEvidence, NetTrade
from tb.backtest.stage3_runner import Batch
from tb.research.models import ResearchRefused


class MemoryStore:
    base = "work/owned-stage3"

    def __init__(self):
        self.objects = {}

    def read(self, name):
        return copy.deepcopy(self.objects.get(name))

    def write(self, name, value):
        assert name not in self.objects or self.objects[name] == value
        self.objects[name] = copy.deepcopy(value)


class OwnedSource:
    def __init__(self, root):
        self.root = root

    def identity(self):
        return "owned-fixture-input-v1"


def test_all_training_selectors_freeze_before_evaluation_and_resume_reuses_result(
    tmp_path, monkeypatch
):
    source = OwnedSource(tmp_path)
    batch = Batch(Path(__file__).resolve().parents[2], source)
    batch.store = MemoryStore()
    # Three owned cells exercise the production selector, never genuine inputs.
    batch.trials = batch.trials[:3]
    calls = []

    def evidence(name, *, trial_index, start, stop, year, comparison=None, **kwargs):
        calls.append((name, trial_index, start, stop, year))
        training = name.startswith("training/")
        if training:
            assert stop == datetime(year, 1, 1, tzinfo=UTC) - timedelta(days=1)
            assert start == datetime(2020, 10, 1, tzinfo=UTC)
            count, expectancy = [(19, 100), (20, 0.1), (21, -1)][trial_index]
            entry_day = date(year - 1, 10, 1)
        else:
            assert start == datetime(year, 1, 2, tzinfo=UTC)
            assert stop == datetime(year + 1, 1, 1, tzinfo=UTC)
            assert trial_index == 1  # 19 lucky trades never wins; evaluation cannot select
            count, expectancy, entry_day = 1, -1, date(year, 1, 2)
        trades = tuple(
            NetTrade(entry_day=entry_day + timedelta(days=i), pnl=10 * expectancy, net_r=expectancy)
            for i in range(count)
        )
        return FoldEvidence(
            year=year,
            trades=trades,
            daily_returns=(0.01, -0.02, 0),
            max_dd=0.02,
            path_max=1.01,
            path_min=0.98,
        )

    monkeypatch.setattr(batch, "evidence", evidence)
    monkeypatch.setattr(batch, "status", lambda *args: None)
    result = batch.run()
    first_eval = next(i for i, c in enumerate(calls) if c[0].startswith("evaluation/"))
    assert first_eval == 12
    assert len(result["verdicts"]) == 1
    assert result["identity"]["n_trials"] == 162
    assert result["verdicts"][0]["verdict"] == "insufficient evidence"
    for year in (2021, 2022, 2023, 2024):
        assert batch.store.objects[f"training/{year}/selection.json"]["selected"] == {
            "trend_vwap_pullback/BTCUSDT": 1
        }
    original_calls = len(calls)
    assert batch.run() == result
    assert len(calls) == original_calls
    monkeypatch.setattr(source, "identity", lambda: "changed-input")
    with pytest.raises(ResearchRefused, match="identity_changed"):
        batch.run()


def test_no_eligible_training_cell_records_each_fold_insufficient(tmp_path, monkeypatch):
    batch = Batch(Path(__file__).resolve().parents[2], OwnedSource(tmp_path))
    batch.store = MemoryStore()
    batch.trials = batch.trials[:1]

    def evidence(name, **kwargs):
        assert name.startswith("training/"), "evaluation ran without an eligible training cell"
        return FoldEvidence(
            year=kwargs["year"], daily_returns=(0, 0), max_dd=0, path_max=1, path_min=1
        )

    monkeypatch.setattr(batch, "evidence", evidence)
    monkeypatch.setattr(batch, "status", lambda *args: None)
    result = batch.run()["verdicts"][0]
    assert result["missing_training_folds"] == [2021, 2022, 2023, 2024]
    assert result["verdict"] == "insufficient evidence"
    assert all(f["status"] == "insufficient evidence" for f in result["folds"])
