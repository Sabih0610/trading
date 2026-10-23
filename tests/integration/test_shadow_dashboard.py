"""Read-only fixture/genuine separation and no reference P&L or raw price disclosure."""

from datetime import timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tb.core.config import repo_root
from tb.dashboard.shadow import read_shadow_snapshot
from tb.ingest.history.core import sha256_file
from tb.risk.config import load_asset_registry
from tb.shadow.fixtures import FIXTURE_START, fixture_events, fixture_pin, fixture_rights
from tb.shadow.journal import ShadowJournal
from tb.shadow.models import ShadowConfig
from tb.shadow.reporting import publish
from tb.shadow.runtime import ShadowRuntime


def test_shadow_view_is_price_free_and_does_not_read_env_or_write(monkeypatch, tmp_path):
    config = ShadowConfig()
    pin = fixture_pin(config, "fixture")
    folder = tmp_path / "reports/shadow/fixture/runtime"
    journal = ShadowJournal(folder, pin, config, create=True)
    runtime = ShadowRuntime(
        journal, fixture_rights(), load_asset_registry(), started_at=FIXTURE_START
    )
    for event in fixture_events(pin, 2):
        runtime.process(event, event.observation.received_at + timedelta(milliseconds=1))
    value = publish(journal, fixture_rights())
    journal.close()
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        assert path.name != ".env"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    from tb.core import config as core_config

    app_path = repo_root() / "src/tb/dashboard/app.py"
    monkeypatch.setattr(core_config, "repo_root", lambda: tmp_path)
    before = {str(p): sha256_file(p) for p in folder.rglob("*") if p.is_file()}
    app = AppTest.from_file(str(app_path), default_timeout=25).run()
    app.sidebar.radio[0].set_value("Shadow Research").run()
    assert not app.exception
    assert any("OWNED SYNTHETIC" in w.value for w in app.warning)
    assert not app.metric and not app.button
    rendered = " ".join(v.value.to_json() for v in app.dataframe)
    assert "features" not in rendered and "entry_price" not in rendered
    assert "WAIT" in rendered and "blocked" in rendered
    assert before == {str(p): sha256_file(p) for p in folder.rglob("*") if p.is_file()}
    next(s for s in app.selectbox if s.label == "Shadow evidence").set_value(
        "Genuine shadow (permission gated)"
    ).run()
    assert not app.exception
    assert any("blocked" in v.value for v in app.info)
    assert not value.fills_created and not value.positions_created
    with pytest.raises(ValueError):
        read_shadow_snapshot(folder / "snapshots", mode="genuine_shadow")
