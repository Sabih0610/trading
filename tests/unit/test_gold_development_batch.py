"""Owned fixtures for one-shot gold selection isolation, fill paths and immutable resumes."""

import copy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from tb.backtest import gold_development as module
from tb.backtest.engine import BacktestResult, EquityPoint, ExitReason, ReplayAudit, TradeRecord
from tb.backtest.gold_development import (
    GoldBatch,
    development_checklist,
    evaluation_evidence,
    flat_evidence,
    implementation_identity,
    public_metrics,
    sensitivity_paths,
    training_record,
)
from tb.backtest.stage3_metrics import FoldEvidence, NetTrade, Summary
from tb.research.gold_proxy import PROXY_LABEL, START, STOP, GoldResearchEvaluation
from tb.research.models import ResearchRefused
from tb.strategies.gold_stage3 import gold_trials

REPO = Path(__file__).resolve().parents[2]
METRIC_KEYS = {"profit_factor", "expectancy_r", "max_dd_pct", "trade_count", "sharpe", "dsr"}


class MemoryStore:
    def __init__(self, *args):
        self.objects = {}
        self.health = None

    def read(self, name):
        return copy.deepcopy(self.objects.get(name))

    def write(self, name, value):
        assert name not in self.objects or self.objects[name] == value
        self.objects[name] = copy.deepcopy(value)

    def status(self, value):
        self.health = copy.deepcopy(value)


class OwnedSource:
    def identity(self):
        return "owned-gold-fixture-v1"

    def load(self, *args):
        raise AssertionError("Fixture unexpectedly attempted source input")


@pytest.fixture
def owned_batch(monkeypatch):
    monkeypatch.setattr(module, "PrivateStore", MemoryStore)
    batch = GoldBatch(REPO, OwnedSource())
    monkeypatch.setattr(batch, "status", lambda *args: None)
    monkeypatch.setattr(batch, "_quality", lambda *args: {"candidate_calendar_sessions": 260})
    monkeypatch.setattr(module, "weekly_bootstrap", lambda *args: None)
    return batch


def evidence(year, count=60, expectancy=0.5, *, circuit=False):
    return FoldEvidence(
        year=year,
        trades=tuple(
            NetTrade(
                entry_day=date(year, 1, 2) + timedelta(days=i),
                pnl=20 if i % 4 else -10,
                net_r=expectancy,
            )
            for i in range(count)
        ),
        daily_returns=(0.001, -0.0002, 0.0005),
        max_dd=0.01,
        path_max=1.01,
        path_min=0.99,
        circuit_trips=int(circuit),
        halted_days=17 if circuit else 0,
        ambiguous_bars=3 if circuit else 0,
    )


def test_both_selectors_precede_oos_final_selector_follows_and_strict_fill_can_reject(
    owned_batch, monkeypatch
):
    calls = []

    def replay(name, *, trial_index, start, stop, year, comparison=None, path="touch/stop/1", **kw):
        calls.append((name, trial_index, start, stop, year, path))
        trial = owned_batch.trials[trial_index]
        if name.startswith("training/"):
            assert start == START
            if "final-2021-2023" in name:
                assert stop == STOP - timedelta(days=1)
                assert any(c[0].startswith("evaluation/") for c in calls)
            else:
                fold = int(name.split("/")[1])
                assert stop == datetime(fold, 1, 1, tzinfo=UTC) - timedelta(days=1)
                assert not any(c[0].startswith("evaluation/") for c in calls)
            offset = [
                i for i, t in enumerate(owned_batch.trials) if t.strategy == trial.strategy
            ].index(trial_index)
            # A lucky 19-trade candidate cannot displace the eligible 20-trade runner-up.
            return evidence(
                year,
                19 if offset == 0 else 20,
                100 if offset == 0 else (0.5 if offset == 1 else 0.1),
            )
        assert len([c for c in calls if c[0].startswith("training/")]) == 108
        assert start == datetime(year, 1, 2, tzinfo=UTC)
        assert stop == min(datetime(year + 1, 1, 1, tzinfo=UTC), STOP - timedelta(microseconds=1))
        assert kw["calendar_start"] == datetime(year, 1, 1, tzinfo=UTC)
        selected = {"london_sweep_mss_fvg": 1, "session_orb": 10, "trend_vwap_pullback": 37}
        assert trial_index == selected[trial.strategy]
        if comparison:
            return evidence(year, expectancy=-0.2).model_copy(
                update={"daily_returns": (-0.001, 0.0)}
            )
        return evidence(
            year,
            expectancy=-0.2 if path.startswith("through/") else 0.5,
            circuit=path == "through/stop/1",
        )

    monkeypatch.setattr(owned_batch, "evidence", replay)
    result = owned_batch.run()
    assert result["identity"]["n_trials"] == 54
    assert result["frozen_parameters"]["n_trials"] == 54
    rows = {row["strategy"]: row for row in result["verdicts"]}
    assert rows["london_sweep_mss_fvg"]["verdict"] == "reject"
    assert rows["london_sweep_mss_fvg"]["ambiguity_verdicts"]["touch/stop"] == "promising"
    assert rows["london_sweep_mss_fvg"]["ambiguity_verdicts"]["through/stop"] == "reject"
    assert rows["session_orb"]["verdict"] == "promising"
    assert len(rows["london_sweep_mss_fvg"]["metrics"]) == 12
    assert len(rows["session_orb"]["metrics"]) == 6
    trips = rows["london_sweep_mss_fvg"]["metrics"]["through/stop/1"]["folds"]
    assert all(
        f["circuit_trips"] == 1 and f["halted_days"] == 17 and f["ambiguous_bars"] == 3
        for f in trips
    )
    for row in rows.values():
        for path in row["metrics"].values():
            assert set(path["aggregate"]) == METRIC_KEYS
            assert all(set(f["metrics"]) == METRIC_KEYS for f in path["folds"])
    final_position = next(i for i, c in enumerate(calls) if "final-2021-2023" in c[0])
    assert all(c[0].startswith("training/final-2021-2023/") for c in calls[final_position:])
    before = len(calls)
    assert owned_batch.run() == result
    assert len(calls) == before
    monkeypatch.setattr(owned_batch.source, "identity", lambda: "changed-fixture")
    with pytest.raises(ResearchRefused, match="identity_changed"):
        owned_batch.run()


def test_no_eligible_training_cell_keeps_trials_and_quality_but_never_scores_oos(
    owned_batch, monkeypatch
):
    quality_calls = []

    def replay(name, **kwargs):
        assert name.startswith("training/"), "OOS replay ran without an eligible training choice"
        return evidence(kwargs["year"], count=19, expectancy=99)

    def quality(year, index, start, stop):
        quality_calls.append((year, index))
        return {"candidate_calendar_sessions": 260, "sessions_with_no_eligible_bars": 260}

    monkeypatch.setattr(owned_batch, "evidence", replay)
    monkeypatch.setattr(owned_batch, "_quality", quality)
    result = owned_batch.run()
    assert result["identity"]["n_trials"] == 54
    assert len(quality_calls) == 12  # 3 strategies * 2 timeframes * 2 years
    for row in result["verdicts"]:
        assert row["verdict"] == "insufficient evidence"
        assert row["missing_training_folds"] == [2022, 2023]
        assert all(len(q["timeframes"]) == 2 for q in row["quality_gate"])
        assert all(v["config"] is None for v in result["frozen_parameters"]["strategies"].values())
        assert all(
            f["metrics"]["trade_count"] == 0 for p in row["metrics"].values() for f in p["folds"]
        )


def test_recorded_replay_defect_cannot_be_retried_or_silently_fixed(owned_batch, monkeypatch):
    def fail(*args):
        raise RuntimeError("owned fault")

    monkeypatch.setattr(owned_batch, "prepared", fail)
    kwargs = {
        "trial_index": 0,
        "start": START,
        "stop": datetime(2021, 12, 31, tzinfo=UTC),
        "year": 2021,
    }
    with pytest.raises(ResearchRefused, match="replay_refused"):
        owned_batch.evidence("training/test.json", **kwargs)
    assert owned_batch.store.objects["training/test.json.refusal.json"] == {
        "error_type": "RuntimeError",
        "trial_index": 0,
        "year": 2021,
        "state": "STOP_FOR_REVIEW",
    }
    monkeypatch.setattr(
        owned_batch, "prepared", lambda *args: pytest.fail("Recorded defect retried")
    )
    with pytest.raises(ResearchRefused, match="recorded_refusal"):
        owned_batch.evidence("training/test.json", **kwargs)


def test_empty_window_emits_flat_evidence_and_checkpoint_without_unscoped_replay(
    owned_batch, monkeypatch
):
    monkeypatch.setattr(
        owned_batch, "prepared", lambda *args: SimpleNamespace(has_scored_bars=lambda *args: False)
    )
    result = owned_batch.evidence(
        "training/empty.json",
        trial_index=0,
        start=START,
        stop=datetime(2021, 12, 31, tzinfo=UTC),
        year=2021,
    )
    assert len(result.trades) == 0
    assert len(result.daily_returns) == 364
    assert not any(result.daily_returns)
    assert "training/empty.json" in owned_batch.store.objects
    with pytest.raises(ResearchRefused, match="unregistered_comparison"):
        owned_batch.evidence(
            "bad.json",
            trial_index=0,
            start=START,
            stop=datetime(2021, 12, 31, tzinfo=UTC),
            year=2021,
            comparison="future",
        )


def test_calendar_and_initial_risk_survive_conversion():
    stamp = datetime(2023, 12, 20, tzinfo=UTC)
    result = BacktestResult(
        trades=(
            TradeRecord(
                symbol="XAUTUSDT",
                entry_time=stamp,
                exit_time=stamp + timedelta(minutes=5),
                quantity=1,
                entry_price=100,
                exit_price=90,
                entry_fee=1,
                exit_fee=1,
                pnl=-12,
                exit_reason=ExitReason.STOP,
            ),
        ),
        rejections=(),
        equity=(
            EquityPoint(timestamp=stamp, cash=9988, holdings=0, close=90, equity=9988, exposure=0),
        ),
    )
    audit = ReplayAudit(
        initial_risk={stamp: Decimal("24")},
        equity_bounds=[(stamp, Decimal("9500"))],
        peak_trip_at=stamp,
        ambiguous_bars=2,
    )
    converted = evaluation_evidence(
        GoldResearchEvaluation(PROXY_LABEL, "owned", result, audit),
        year=2023,
        calendar_start=datetime(2023, 1, 1, tzinfo=UTC),
        stop=STOP - timedelta(microseconds=1),
    )
    assert len(converted.daily_returns) == 365
    assert converted.trades[0].net_r == -0.5  # original risk24, never realized loss12
    assert converted.max_dd == 0.05
    assert converted.circuit_trips == 1 and converted.halted_days == 12
    assert converted.ambiguous_bars == 2
    audit.initial_risk.clear()
    with pytest.raises(ResearchRefused, match="planned_risk_missing"):
        evaluation_evidence(
            GoldResearchEvaluation(PROXY_LABEL, "owned", result, audit),
            year=2023,
            calendar_start=stamp,
            stop=STOP - timedelta(microseconds=1),
        )


def test_training_record_preserves_numeric_grid_order():
    for i, trial in enumerate(gold_trials()):
        cell = training_record(i, trial, evidence(2021, count=20))
        assert cell.trial_index == i and cell.trade_count == 20
        assert cell.timeframe_seconds == trial.timeframe.total_seconds()
        assert len(cell.parameters) == 2


@pytest.mark.parametrize(
    "strategy,count", [("london_sweep_mss_fvg", 12), ("trend_vwap_pullback", 6), ("session_orb", 6)]
)
def test_registered_paths_are_closed_and_do_not_increase_trial_count(strategy, count):
    paths = sensitivity_paths(strategy)
    assert len(paths) == len(set(paths)) == count
    assert {p.split("/")[2] for p in paths} == {"1", "1.5", "2"}


def test_defined_failure_has_priority_over_missing_year_and_stress_is_a_gate():
    good = Summary(
        trade_count=60,
        expectancy_r=0.2,
        profit_factor=1.5,
        max_dd_pct=5,
        net_return=0.1,
        sharpe=1,
        dsr=None,
        win_rate=0.5,
    )
    bad = good.model_copy(update={"expectancy_r": -0.01})
    absent = good.model_copy(update={"expectancy_r": None, "profit_factor": None, "trade_count": 0})
    assert (
        development_checklist((bad, absent), good, (good, absent), beats_random=True, missing=True)[
            0
        ]
        == "reject"
    )
    assert (
        development_checklist((good, good), good, (bad, good), beats_random=True, missing=False)[0]
        == "reject"
    )
    assert (
        development_checklist((good, good), good, (good, good), beats_random=True, missing=False)[0]
        == "promising"
    )
    assert (
        development_checklist((good, good), good, (good, good), beats_random=True, missing=True)[0]
        == "insufficient evidence"
    )
    assert set(public_metrics(good)) == METRIC_KEYS


def test_registration_hash_is_checked_before_source_or_store(monkeypatch):
    monkeypatch.setattr(module, "sha256_file", lambda path: "0" * 64)
    monkeypatch.setattr(
        module,
        "PrivateStore",
        lambda *args: pytest.fail("Store constructed before registration check"),
    )
    with pytest.raises(ResearchRefused, match="registration_changed"):
        GoldBatch(REPO, OwnedSource())
    with pytest.raises(ResearchRefused, match="registration_changed"):
        implementation_identity(REPO)


def test_final_calendar_keeps_december31_without_reading_2024():
    flat = flat_evidence(2023, datetime(2023, 1, 1, tzinfo=UTC), STOP - timedelta(microseconds=1))
    assert len(flat.daily_returns) == 365


def test_null_final_selector_cannot_promote_but_preserves_oos_verdicts(owned_batch, monkeypatch):
    def replay(name, *, year, comparison=None, **kwargs):
        if "final-2021-2023" in name:
            return evidence(year, count=19)
        if name.startswith("training/"):
            return evidence(year, count=20)
        if comparison:
            return evidence(year).model_copy(update={"daily_returns": (-0.001, 0.0)})
        return evidence(year)

    monkeypatch.setattr(owned_batch, "evidence", replay)
    result = owned_batch.run()
    for row in result["verdicts"]:
        assert row["preliminary_development_verdict"] == "promising"
        assert row["final_training_ineligible"]
        assert row["verdict"] == "insufficient evidence"
        assert set(row["ambiguity_verdicts"].values()) == {"promising"}
        frozen = result["frozen_parameters"]["strategies"][row["strategy"]]
        assert frozen["config"] is None
        assert frozen["development_verdict"] == "insufficient evidence"


def test_implementation_identity_binds_source_config_and_dependencies(tmp_path):
    (tmp_path / "reports/stage3").mkdir(parents=True)
    (tmp_path / "src/tb").mkdir(parents=True)
    (tmp_path / "config").mkdir()
    registration = REPO / "reports/stage3/P11g-preregistration.md"
    (tmp_path / "reports/stage3/P11g-preregistration.md").write_bytes(registration.read_bytes())
    source = tmp_path / "src/tb/owned.py"
    config = tmp_path / "config/owned.yaml"
    source.write_text("owned = 1\n")
    config.write_text("owned: 1\n")
    (tmp_path / "pyproject.toml").write_text("# owned\n")
    (tmp_path / "uv.lock").write_text("# owned pinned\n")
    previous = implementation_identity(tmp_path)
    for path in (source, config, tmp_path / "uv.lock"):
        path.write_text(path.read_text() + "# changed\n")
        current = implementation_identity(tmp_path)
        assert current != previous
        previous = current


def test_unregistered_strategy_has_no_sensitivity_catalogue():
    with pytest.raises(ResearchRefused, match="unregistered_strategy"):
        sensitivity_paths("unregistered")
