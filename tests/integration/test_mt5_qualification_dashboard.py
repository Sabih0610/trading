"""Diagnostic empty-price views show safety/validity separately without credential access."""

from datetime import UTC, datetime, timedelta

import pytest
from streamlit.testing.v1 import AppTest

from tb.core.config import repo_root
from tb.dashboard.feed import FeedExport, read_feed_export
from tb.ingest.mt5.adapter import MT5Feed
from tb.ingest.mt5.diagnostics import publish_diagnostic
from tb.ingest.mt5.fake import FakeReader
from tb.ingest.mt5.models import FeedConfig


def test_failed_clock_snapshot_has_explanation_and_no_price_table(tmp_path, monkeypatch):
    from tb.core import config

    now = datetime.now(UTC) - timedelta(seconds=10)
    client = FakeReader(tmp_path / "terminal/terminal64.exe", lambda: now)
    feed = MT5Feed(
        client,
        FeedConfig(),
        terminal_path=client.path,
        login=str(client.login),
        server=client.server,
        clock=lambda: now,
    )
    identity = feed.connect()
    report = {
        "ended_at": now.isoformat(),
        "started_at": now.isoformat(),
        "session_started": now.isoformat(),
        "identity": identity.model_dump(mode="json"),
        "readiness": {},
        "counts": {
            "XAUUSD": {"received": 3, "rejected": 3, "rejected_by_reason": {"future_timestamp": 3}},
            "EURUSD": {"missing": 3, "rejected": 3},
        },
        "admission": {
            "checked_at": now.isoformat(),
            "identity_fingerprint": identity.fingerprint,
            "security_passed": True,
            "clock_passed": False,
            "native_trading_allowed": False,
            "dangerous_shell_tool_available": False,
            "reasons": ["future_timestamp"],
        },
    }
    publish_diagnostic(tmp_path, report)
    app_file = repo_root() / "src/tb/dashboard/app.py"
    monkeypatch.setattr(config, "repo_root", lambda: tmp_path)
    app = AppTest.from_file(str(app_file), default_timeout=20).run()
    app.sidebar.radio[0].set_value("Market Feed").run()
    assert not app.exception
    assert any("No validated quotes" in w.value for w in app.warning)
    assert any("metadata is unavailable" in i.value for i in app.info)
    assert any("Native MCP safety: PASS" in m.value for m in app.markdown)
    assert len(app.dataframe) == 1  # counts only; no empty quote or metadata tables
    assert len(app.metric) == len(app.button) == 0
    snapshot = read_feed_export(tmp_path / "reports/market_feed/genuine")
    assert snapshot.quotes == snapshot.candles == []
    assert snapshot.health[1].state.value == "INSTRUMENT_UNAVAILABLE"
    value = snapshot.model_dump(mode="json")
    value["collection_ended_at"] = (now + timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError, match="interval"):
        FeedExport.model_validate(value)
