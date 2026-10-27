"""Real Streamlit AppTest startup, views, risk display and unchanged stored evidence."""

import ast
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tb.core.config import repo_root
from tb.dashboard.fixtures import create_dashboard_fixtures
from tb.dashboard.models import account_metrics
from tb.dashboard.readers import account_record, catalog, ledger_totals
from tb.ingest.history.core import sha256_file
from tb.risk.config import load_policy_bundle

APP = repo_root() / "src/tb/dashboard/app.py"


@pytest.fixture(scope="module")
def report_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("P10 path with spaces")
    create_dashboard_fixtures(root / "P10-demo")
    return root


def _app(root: Path, monkeypatch: pytest.MonkeyPatch, *, demo: bool = False) -> AppTest:
    monkeypatch.setenv("TB_DASHBOARD_REPORT_ROOT", str(root))
    result = AppTest.from_file(str(APP), default_timeout=25).run()
    if demo:
        result.sidebar.selectbox[0].set_value("Synthetic demo").run()
    assert not result.exception
    return result


@pytest.mark.parametrize(
    "view",
    [
        "Overview",
        "Markets & Strategies",
        "Trades & Decisions",
        "Risk & System Health",
        "AI & Model Research",
    ],
)
def test_startup_and_every_empty_view_work_without_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, view: str
) -> None:
    app = _app(tmp_path, monkeypatch)
    app.sidebar.radio[0].set_value(view).run()
    assert not app.exception
    if view == "Overview":
        assert all(item.value == "Unavailable" for item in app.metric)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "view",
    [
        "Overview",
        "Markets & Strategies",
        "Trades & Decisions",
        "Risk & System Health",
        "AI & Model Research",
    ],
)
def test_demo_views_are_labelled_and_do_not_change_ledger(
    report_root: Path, monkeypatch: pytest.MonkeyPatch, view: str
) -> None:
    path = report_root / "P10-demo/btc-profit/journal.sqlite"
    before = sha256_file(path)
    app = _app(report_root, monkeypatch, demo=True)
    app.sidebar.radio[0].set_value(view).run()
    assert not app.exception
    assert any("SYNTHETIC FIXTURE" in item.value for item in app.warning)
    assert sha256_file(path) == before
    assert all(button.label in ("Newest decisions", "Older decisions") for button in app.button)
    if view == "Risk & System Health":
        policy = load_policy_bundle().risk.limits
        shown = app.dataframe[0].value
        assert shown["Planned_risk_pct"].iloc[0] == str(policy.risk_per_trade_pct)
        assert shown["Daily_equity_loss_pct"].iloc[0] == str(policy.daily_loss_limit_pct)
        assert shown["Peak_drawdown_pct"].iloc[0] == str(policy.max_peak_drawdown_pct)
    if view == "AI & Model Research":
        assert [metric.value for metric in app.metric] == ["0", "0"]


def test_exported_trade_rejection_veto_and_shutdown_evidence(report_root: Path) -> None:
    sources = catalog(report_root / "P10-demo")
    counts = {}
    for source in sources:
        folder = report_root / "P10-demo" / source.path
        totals = ledger_totals(folder / "journal.sqlite", source.mode)
        metrics = account_metrics(account_record(folder, source), totals)
        counts[source.id] = metrics.trade_count
        if source.id in ("btc-profit", "eur-profit"):
            assert metrics.realized_pnl > 0
        if source.id == "gold-gap":
            assert metrics.realized_pnl < 0
        if source.id in ("gold-small", "eur-small", "ai-veto", "empty"):
            assert metrics.trade_count == 0
    assert len(counts) == 7


def test_read_only_ui_has_no_writer_or_execution_imports() -> None:
    for path in APP.parent.glob("*.py"):
        if path.name == "fixtures.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(
                    token in (node.module or "")
                    for token in ("execution", "paper.simulation", "ledger.store")
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in (
                    "data_editor",
                    "append_decision",
                    "append_outcome",
                    "submit",
                    "write_parquet",
                )


def test_veto_filter_and_empty_account(report_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(report_root, monkeypatch, demo=True)
    app.sidebar.selectbox[1].set_value("ai-veto").run()
    app.sidebar.radio[0].set_value("Trades & Decisions").run()
    next(w for w in app.selectbox if w.label == "Decision status").set_value("vetoed").run()
    assert not app.exception
    assert app.dataframe[0].value["status"].iloc[0] == "vetoed"
    app.sidebar.selectbox[1].set_value("empty").run()
    assert not app.exception
    assert any("No matching decisions" in item.value for item in app.info)


def test_ui_masks_unknown_secret_fields_and_does_not_read_env(
    report_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree(report_root / "P10-demo", tmp_path / "P10-demo")
    path = tmp_path / "P10-demo/btc-profit/journal.sqlite"
    # Append a synthetic row; the dashboard itself has no writer.
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT * FROM decisions LIMIT 1").fetchone()
        columns = [v[1] for v in conn.execute("PRAGMA table_info(decisions)")]
        values = dict(zip(columns, row, strict=True))
        values["id"] = "privacy-fixture"
        payload = json.loads(values["payload_json"])
        payload.update(reason="api_key=PRIVATE_SENTINEL", api_key="HIDDEN_UNKNOWN_FIELD")
        values["payload_json"] = json.dumps(payload)
        conn.execute(
            "INSERT INTO decisions ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")",
            list(values.values()),
        )
    original_read = Path.read_text

    def guarded_read(path: Path, *args, **kwargs):
        if path.name == ".env":
            pytest.fail("Dashboard inspected credentials")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    app = _app(tmp_path, monkeypatch, demo=True)
    app.sidebar.radio[0].set_value("Trades & Decisions").run()
    assert not app.exception
    rendered = " ".join(frame.value.to_json() for frame in app.dataframe)
    assert "PRIVATE_SENTINEL" not in rendered and "HIDDEN_UNKNOWN_FIELD" not in rendered
