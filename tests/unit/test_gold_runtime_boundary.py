"""Owned-only tests of frozen admission, closed comparisons and aggregate gold display."""

import copy
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tb.backtest.gold_cli import (
    FREEZE_PATH,
    REVIEW_SHA,
    configuration_identity,
    require_frozen_approval,
)
from tb.backtest.gold_development import REGISTRATION_SHA, implementation_identity
from tb.dashboard.gold_development import METRICS, gold_lab_result
from tb.research.gold_development_data import PrivateStore
from tb.research.gold_proxy import (
    PROXY_LABEL,
    GoldProxyBatch,
    ProxyInput,
    SessionQuality,
    gold_costs,
)
from tb.research.models import ResearchRefused
from tb.strategies.base import StrategyBar


def fixture_batch(*, missing=False, empty=False):
    rows = []
    for i in range(400 if not empty else 0):
        stamp = datetime(2023, 1, 2, 8, tzinfo=UTC) + timedelta(minutes=5 * i)
        rows.append(
            ProxyInput(
                bar=StrategyBar(
                    timestamp=stamp,
                    symbol="XAUUSD",
                    open=Decimal("100"),
                    high=Decimal("101"),
                    low=Decimal("99"),
                    close=Decimal("100"),
                ),
                quality=SessionQuality(
                    known_at=stamp + timedelta(minutes=5),
                    expected_minutes=100,
                    present_minutes=0 if missing else 100,
                ),
            )
        )
    return GoldProxyBatch(tuple(rows), timedelta(minutes=5), purpose="historical_research")


def compare(batch, name, **overrides):
    kwargs = dict(
        start=datetime(2023, 1, 2, tzinfo=UTC),
        stop=datetime(2023, 12, 31, 23, 59, 59, tzinfo=UTC),
        year=2023,
        calendar_start=datetime(2023, 1, 1, tzinfo=UTC),
        seed=20261102,
    )
    kwargs.update(overrides)
    return batch.comparison_evidence(name, **kwargs)


def test_closed_comparisons_include_all_calendar_days_and_real_g2_costs():
    batch = fixture_batch()
    cash = compare(batch, "cash")
    assert cash.daily_returns == (0.0,) * 365 and not cash.trades
    hold = compare(batch, "buy_hold")
    costs = gold_costs()
    quantity = Decimal("10000") / (costs.entry_price(Decimal("100")) * (1 + Decimal(".001")))
    proceeds = quantity * costs.exit_price(Decimal("100"))
    ending = proceeds - costs.fee(proceeds)
    assert len(hold.daily_returns) == 365 and hold.max_dd > 0
    assert hold.path_min == pytest.approx(float(ending / 10000))
    random = compare(batch, "random")
    assert random == compare(batch, "random") and len(random.daily_returns) == 365
    assert random.trades
    assert not compare(fixture_batch(missing=True), "random").trades


@pytest.mark.parametrize("name", ["cash", "random", "buy_hold"])
def test_empty_comparison_remains_flat_without_inventing_evidence(name):
    evidence = compare(fixture_batch(empty=True), name)
    assert not evidence.trades and evidence.daily_returns == (0.0,) * 365


@pytest.mark.parametrize(
    "overrides",
    [
        {"stop": datetime(2024, 1, 1, tzinfo=UTC)},
        {"year": 2024},
        {"start": datetime(2020, 1, 1, tzinfo=UTC)},
        {"calendar_start": datetime(2022, 12, 31, tzinfo=UTC)},
        {"start": datetime(2023, 1, 2)},
    ],
)
def test_closed_comparison_refuses_2024_and_unregistered_clocks(overrides):
    with pytest.raises(ResearchRefused, match="scope"):
        compare(fixture_batch(empty=True), "random", **overrides)


@pytest.fixture
def frozen_repo(tmp_path):
    checkout = Path(__file__).resolve().parents[2]
    for name in ("reports/stage3/P11g-preregistration.md", "reports/reviews/P11g-prereg-review.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((checkout / name).read_bytes())
    (tmp_path / "config").mkdir()
    (tmp_path / "config/policy.yaml").write_text("owned_fixture: true\n")
    (tmp_path / "src").mkdir()
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("owned fixture\n")
    path = tmp_path / FREEZE_PATH
    path.parent.mkdir(parents=True)
    record = dict(
        kind="gold_development_pre_data_freeze",
        gate_status="passed",
        registration_sha256=REGISTRATION_SHA,
        review_sha256=REVIEW_SHA,
        implementation_sha256=implementation_identity(tmp_path),
        configuration_sha256=configuration_identity(tmp_path),
    )
    path.write_text(json.dumps(record))
    return tmp_path, record


def test_complete_freeze_must_match_approval_registration_code_config_and_gate(frozen_repo):
    repo, record = frozen_repo
    assert require_frozen_approval(repo) == record
    (repo / "config/policy.yaml").write_text("owned_fixture: changed\n")
    with pytest.raises(ResearchRefused, match="not_frozen"):
        require_frozen_approval(repo)


@pytest.mark.parametrize(
    "field,value",
    [
        ("gate_status", "failed"),
        ("review_sha256", "wrong"),
        ("implementation_sha256", "wrong"),
        ("registration_sha256", "wrong"),
    ],
)
def test_invalid_freeze_never_admits_inputs(frozen_repo, field, value):
    repo, record = frozen_repo
    record[field] = value
    (repo / FREEZE_PATH).write_text(json.dumps(record))
    with pytest.raises(ResearchRefused, match="not_frozen"):
        require_frozen_approval(repo)


def display_fixture():
    metrics = {key: 0 for key in METRICS}
    return {
        "identity": {"registration_sha256": REGISTRATION_SHA},
        "private_comparisons": {"must": "not leak"},
        "verdicts": [
            dict(
                strategy=name,
                symbol="XAUTUSDT",
                proxy=PROXY_LABEL,
                status="development only: not validated",
                verdict="insufficient evidence",
                metrics={
                    "touch/stop/1": {
                        "aggregate": metrics,
                        "folds": [{"year": 2023, "metrics": metrics}],
                    }
                },
                ambiguity_verdicts={},
                quality_gate=[],
                missing_training_folds=[2022, 2023],
                forbidden_private_series=[100, 101],
            )
            for name in ("london_sweep_mss_fvg", "trend_vwap_pullback", "session_orb")
        ],
    }


def test_gold_lab_rechecks_display_and_exports_aggregate_projection_only(monkeypatch, tmp_path):
    value = display_fixture()

    def read(self, name, *, display=False):
        assert display and name == "results.json"
        return value

    monkeypatch.setattr(PrivateStore, "read", read)
    rows = gold_lab_result(tmp_path)
    assert len(rows) == 3
    assert "private" not in json.dumps(rows)
    assert all(row["status"] == "development only: not validated" for row in rows)


@pytest.mark.parametrize("case", ["registration", "year", "metric", "validated", "missing"])
def test_gold_lab_refuses_invalid_scope_or_unpermitted_metric(monkeypatch, tmp_path, case):
    value = copy.deepcopy(display_fixture())
    row = value["verdicts"][0]
    if case == "registration":
        value["identity"]["registration_sha256"] = "wrong"
    elif case == "year":
        row["metrics"]["touch/stop/1"]["folds"][0]["year"] = 2024
    elif case == "metric":
        row["metrics"]["touch/stop/1"]["aggregate"]["net_return"] = 0.1
    elif case == "validated":
        row["verdict"] = "validated"
    else:
        value["verdicts"].pop()
    monkeypatch.setattr(PrivateStore, "read", lambda *a, **k: value)
    with pytest.raises(ResearchRefused):
        gold_lab_result(tmp_path)


def test_gold_view_empty_state_has_development_and_proxy_labels(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("TB_GOLD_STAGE3_DATA_ROOT", raising=False)
    app = AppTest.from_string(
        "from tb.dashboard.gold_development import gold_view\ngold_view()", default_timeout=25
    ).run()
    assert not app.exception
    assert any("development only: not validated" in value.value for value in app.warning)
    assert any(PROXY_LABEL in value.value for value in app.caption)
    assert not app.button
