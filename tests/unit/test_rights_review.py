"""Owner documentary workflow is offline, scoped, expiring and never request-as-approval."""

from datetime import timedelta

import pytest
import yaml

from tb.ingest.history.core import sha256_file
from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.rights_review import apply_review, check_review
from tb.shadow.fixtures import FIXTURE_START, fixture_rights


@pytest.fixture
def review(tmp_path):
    root = tmp_path
    doc = root / "work/rights/provider-confirmation.txt"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "OWNED TEST DOCUMENT ONLY. No actual provider confirmation or market data.",
        encoding="utf-8",
    )
    payload = fixture_rights().model_dump(mode="json")
    payload.update(provider="twelve_data", version="2.0.0")
    for permission in payload["permissions"].values():
        permission.update(
            evidence_kind="provider_confirmation",
            evidence_artifact="work/rights/provider-confirmation.txt",
            evidence_sha256=sha256_file(doc),
            permitted_retention_seconds=3600,
        )
    proposal = root / "work/proposal.yaml"
    proposal.write_text(yaml.safe_dump(payload), encoding="utf-8")
    (root / "config").mkdir()
    baseline = fixture_rights().model_dump(mode="json")
    (root / "config/data_rights.yaml").write_text(yaml.safe_dump(baseline), encoding="utf-8")
    return root, proposal, payload


def test_proposal_check_is_readonly_and_explicit_apply_needs_new_version(review):
    root, path, _payload = review
    original = (root / "config/data_rights.yaml").read_bytes()
    assert check_review(root, path, FIXTURE_START + timedelta(seconds=1)).version == "2.0.0"
    assert (root / "config/data_rights.yaml").read_bytes() == original
    apply_review(root, path, FIXTURE_START + timedelta(seconds=1))
    with pytest.raises(FeedUnavailable, match="new_version"):
        apply_review(root, path, FIXTURE_START + timedelta(seconds=1))


@pytest.mark.parametrize(
    "change",
    [
        {"approved": False},
        {"approved_by": None},
        {"expires_at": "2024-06-03T08:00:00Z"},
        {"evidence_kind": "request_pending"},
        {"evidence_sha256": "f" * 64},
        {"permitted_retention_seconds": None},
        {"evidence_artifact": ".env"},
    ],
)
def test_incomplete_pending_expired_or_unverified_proposal_cannot_apply(review, change):
    root, path, payload = review
    payload["permissions"]["historical_storage"].update(change)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    original = (root / "config/data_rights.yaml").read_bytes()
    with pytest.raises(FeedUnavailable):
        apply_review(root, path, FIXTURE_START + timedelta(seconds=1))
    assert (root / "config/data_rights.yaml").read_bytes() == original


def test_supervised_runtime_cannot_outlive_documented_retention(review):
    from tb.ingest.rights_review import require_retention_window

    root, path, _ = review
    rights = check_review(root, path, FIXTURE_START + timedelta(seconds=1))
    require_retention_window(rights, 3000)
    with pytest.raises(FeedUnavailable, match="retention_window"):
        require_retention_window(rights, 3600)
