"""Local dashboard reads immutable status, with no network, credentials or price display."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from streamlit.testing.v1 import AppTest

from tb.core.config import repo_root
from tb.dashboard.readers import EvidenceUnavailable
from tb.dashboard.reference_feed import read_reference_export
from tb.ingest.history.core import sha256_file
from tb.ingest.mt5.models import InstrumentCounts, Observation
from tb.ingest.retention import lifetime
from tb.ingest.rights import load_rights
from tb.ingest.twelve_data.collect import publish
from tb.ingest.twelve_data.models import ReferenceExport, ReferenceIdentity
from tb.shadow.fixtures import fixture_rights


@pytest.fixture
def exported(tmp_path: Path) -> Path:
    now = datetime.now(UTC)
    opening = (now - timedelta(minutes=1)).replace(second=0, microsecond=0)
    row = Observation(
        symbol="EURUSD",
        broker_symbol="EUR/USD",
        kind="candle",
        timeframe="M1",
        source_at=opening,
        received_at=now,
        evidence="forward_observed",
        open="1.23456789",
        high="1.23456789",
        low="1.23456789",
        close="1.23456789",
        source_provider="twelve_data",
        price_type="reference_midpoint",
        source_timezone="UTC",
        raw_source_time=opening.strftime("%Y-%m-%d %H:%M:%S"),
        interval_complete=True,
        coverage_started_at=opening - timedelta(minutes=1),
    )
    artifact = tmp_path / "work/rights/fictional.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("OWNED TEST DOCUMENT ONLY; no genuine provider permission")
    data = fixture_rights().model_dump(mode="json")
    data.update(
        provider="twelve_data",
        account_fingerprint="a" * 64,
        reviewed_at=(opening - timedelta(minutes=3)).isoformat(),
    )
    data["permissions"]["private_display"] = dict(data["permissions"]["derived_storage"])
    for permission in data["permissions"].values():
        permission.update(
            evidence_kind="provider_confirmation",
            evidence_artifact="work/rights/fictional.txt",
            evidence_sha256=sha256_file(artifact),
            permitted_retention_seconds=3600,
        )
    proposal = tmp_path / "config/data_rights.yaml"
    proposal.parent.mkdir()
    proposal.write_text(yaml.safe_dump(data))
    rights = load_rights(proposal)
    value = ReferenceExport(
        authorization={
            "provider": "twelve_data",
            "identity": rights.account_fingerprint,
            "rights_digest": rights.digest,
            "instruments": list(rights.instruments),
            "retention": lifetime(rights, now).model_dump(mode="json"),
        },
        source="twelve_data",
        identity=ReferenceIdentity(fingerprint="a" * 64),
        session_id="fixture-projection",
        session_started=opening - timedelta(minutes=2),
        collection_started_at=opening - timedelta(minutes=1),
        generated_at=now,
        collector_running=False,
        counts={s: InstrumentCounts() for s in ("EURUSD", "XAUUSD")},
        candles=[row],
        readiness={"EURUSD": {"source_data": "NO-GO"}, "XAUUSD": {"source_data": "NO-GO"}},
    )
    publish(tmp_path, value)
    return tmp_path


def test_status_ui_hides_prices_and_reads_no_credentials(
    exported: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tb.core import config as module

    app_file = repo_root() / "src/tb/dashboard/app.py"
    monkeypatch.setattr(module, "repo_root", lambda: exported)
    original = Path.read_text

    def guarded(path: Path, *args, **kwargs):
        assert path.name != ".env"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    before = {
        str(p): p.read_bytes()
        for p in (exported / "reports/market_feed/twelve_data").glob("*.json")
    }
    app = AppTest.from_file(str(app_file), default_timeout=20).run()
    app.sidebar.radio[0].set_value("Market Feed").run()
    next(v for v in app.selectbox if v.label == "Configured market provider").set_value(
        "Twelve Data Basic (reference)"
    ).run()
    assert not app.exception
    assert not app.button and not app.metric
    rendered = " ".join(v.value.to_json() for v in app.dataframe)
    assert "1.23456789" not in rendered
    assert "midpoint" in rendered and "withheld" in rendered and "XAUUSD" in rendered
    assert before == {
        str(p): p.read_bytes()
        for p in (exported / "reports/market_feed/twelve_data").glob("*.json")
    }


def test_reference_projection_provider_checksum_and_retrospective_refusals(exported: Path) -> None:
    folder = exported / "reports/market_feed/twelve_data"
    value = read_reference_export(folder, root=exported)
    assert value.candles[0].source_metadata_timezone is None
    payload = value.model_dump(mode="json")
    payload["source"] = "mt5_demo"
    with pytest.raises(ValueError):
        ReferenceExport.model_validate(payload)
    payload = value.model_dump(mode="json")
    payload["candles"][0]["evidence"] = "historical_backfill"
    with pytest.raises(ValueError):
        ReferenceExport.model_validate(payload)
    payload = value.model_dump(mode="json")
    payload["readiness"]["EURUSD"].update(
        source_data="QUALIFIED_BOUNDED_M1_REFERENCE",
        executable_bid_ask=False,
        realistic_paper_fills=False,
    )
    with pytest.raises(ValueError, match="qualification"):
        ReferenceExport.model_validate(payload)
    path = next(folder.glob("snapshot*.json"))
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(EvidenceUnavailable):
        read_reference_export(folder, root=exported)
