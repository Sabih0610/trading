"""Separate data-monitoring UI, holdout boundaries and genuinely read-only file access."""

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from tb.core.config import repo_root
from tb.dashboard.feed import FeedExport, read_feed_export
from tb.dashboard.readers import EvidenceUnavailable
from tb.ingest.mt5.adapter import MT5Feed
from tb.ingest.mt5.collector import Collector
from tb.ingest.mt5.fake import FakeReader
from tb.ingest.mt5.models import FeedConfig
from tb.ingest.mt5.storage import FeedStore


@pytest.fixture
def exported(tmp_path):
    root = tmp_path / "project with space"
    now = [datetime.now(UTC) - timedelta(minutes=5)]
    client = FakeReader(root / "terminal/terminal64.exe", lambda: now[0])
    feed = MT5Feed(
        client,
        FeedConfig(max_rows=3),
        terminal_path=client.path,
        login=str(client.login),
        server=client.server,
        clock=lambda: now[0],
    )
    store = FeedStore(root, feed.config, code_version="test")
    Collector(
        feed,
        store,
        root / "reports/market_feed/synthetic",
        clock=lambda: now[0],
        sleep=lambda seconds: None,
    ).run(max_polls=1)
    store.close()
    return root


def test_feed_snapshot_read_is_byte_preserving_and_checksums_required(exported):
    folder = exported / "reports/market_feed/synthetic"
    before = {p.name: p.read_bytes() for p in folder.glob("*.json")}
    snapshot = read_feed_export(folder)
    assert snapshot.source == "synthetic" and not snapshot.external_orders_enabled
    assert before == {p.name: p.read_bytes() for p in folder.glob("*.json")}
    pointer = json.loads((folder / "current.json").read_text())
    (folder / pointer["file"]).write_text("{}")
    with pytest.raises(EvidenceUnavailable):
        read_feed_export(folder)


def test_counterfeit_prospective_and_unfinished_candles_refused(exported):
    folder = exported / "reports/market_feed/synthetic"
    snapshot = read_feed_export(folder)
    value = snapshot.model_dump(mode="json")
    value["source"] = "mt5_demo"
    with pytest.raises(ValueError):
        FeedExport.model_validate(value)
    for row in value["quotes"]:
        row["evidence"] = "forward_observed"
    value["candles"] = []
    value["facts"] = []
    value["session_started"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    FeedExport.model_validate(value)
    value["session_started"] = datetime.now(UTC).isoformat()
    with pytest.raises(ValueError):
        FeedExport.model_validate(value)
    value = snapshot.model_dump(mode="json")
    value["candles"][0]["source_at"] = value["candles"][0]["received_at"]
    with pytest.raises(ValueError):
        FeedExport.model_validate(value)


def test_market_feed_ui_separate_from_account_and_no_env_reads(exported, monkeypatch):
    from tb.core import config as module

    monkeypatch.setattr(module, "repo_root", lambda: exported)
    app_file = repo_root() / "src/tb/dashboard/app.py"
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        assert path.name != ".env"
        return original(path, *args, **kwargs)

    with patch.object(Path, "read_text", guarded):
        app = AppTest.from_file(str(app_file), default_timeout=20).run()
        app.sidebar.radio[0].set_value("Market Feed").run()
        assert not app.exception
        assert any("unavailable" in i.value for i in app.info)
        next(radio for radio in app.radio if radio.label == "Market evidence").set_value(
            "Synthetic feed fixture"
        ).run()
        assert not app.exception
        assert any("SYNTHETIC" in w.value for w in app.warning)
        assert len(app.metric) == 0
        assert len(app.button) == 0


def test_forward_namespace_not_consumed_by_existing_historical_pipeline(exported):
    from tb.silver.pipeline import _market_inputs

    assert _market_inputs(exported / "data/bronze") == []


def test_native_adapter_has_no_sender_or_sdk_escape():
    root = repo_root() / "src/tb/ingest/mt5"
    forbidden = {
        "order_send",
        "order_check",
        "login",
        "symbol_select",
        "eval",
        "exec",
        "Popen",
        "run",
    }
    # Entry point run() is local data polling; no native generic SDK client is exported.
    for name in ("adapter.py", "mcp.py", "mcp_proxy.py"):
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                assert call not in forbidden
