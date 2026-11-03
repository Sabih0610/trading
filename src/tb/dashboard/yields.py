"""Read-only Treasury coverage/quality metadata; never a price-file reader."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tb.ingest.history.core import sha256_file
from tb.ingest.treasury import DATASET_ID
from tb.research.models import ResearchRefused
from tb.research.registry import read_metadata, safe
from tb.research.treasury_registry import load_treasury_plan


def treasury_health(root: Path, now: datetime | None = None) -> dict[str, Any]:
    """Current rights/private display and exact integrity precede the quality projection."""
    now = now or datetime.now(UTC)
    base = f"data/manifests/us_treasury/{DATASET_ID}"
    try:
        plan = load_treasury_plan(root, now, display=True)
        manifest = read_metadata(root, base + "/current.json", base=base)
        if (
            manifest.get("dataset_id") != DATASET_ID
            or manifest.get("source") != "us_treasury"
            or manifest.get("policy_digest") != plan.digest
            or manifest.get("retention") != plan.retention.model_dump(mode="json")
        ):
            raise ResearchRefused("treasury_health_identity_invalid")
        expected = f"reports/data_quality/us_treasury/{DATASET_ID}/{manifest['generation']}.json"
        if manifest["quality_path"] != expected:
            raise ResearchRefused("treasury_health_namespace_invalid")
        path = safe(root, expected, base="reports/data_quality")
        if path.stat().st_size > 131072 or sha256_file(path) != manifest["quality_sha256"]:
            raise ResearchRefused("treasury_health_checksum_invalid")
        report = read_metadata(root, expected, base="reports/data_quality")
        if (
            report.get("generation") != manifest["generation"]
            or report.get("policy_digest") != plan.digest
        ):
            raise ResearchRefused("treasury_health_quality_stale")
        return {
            "dataset_id": DATASET_ID,
            "status": manifest["status"],
            "last_refresh": manifest["last_refresh"],
            "coverage": report["years"],
            "rows": report["rows"],
            "weekdays_without_publication": report["weekdays_without_publication"],
            "weekend_publications": report["weekend_publications"],
            "missing_by_tenor": report["missing_by_tenor"],
            "known_at_rule": report["known_at_rule"],
            "retention_expires_at": plan.retention.expires_at.isoformat(),
        }
    except (ValueError, OSError, KeyError):
        return {"dataset_id": DATASET_ID, "status": "unavailable_or_refused"}


def treasury_health_view(root: Path) -> None:
    """Optional private root override, without keys or any acquisition/mutation action."""
    import os

    import streamlit as st

    configured = os.environ.get("TB_TREASURY_DATA_ROOT")
    result = treasury_health(Path(configured) if configured else root)
    st.subheader("US Treasury yield context")
    st.caption("Data-only · default-off features · strictly prior publication availability")
    if result["status"] != "complete":
        st.info("Treasury coverage unavailable or refused by current rights/retention.")
        return
    st.dataframe(result["coverage"], hide_index=True, width="stretch")
    st.write({key: value for key, value in result.items() if key != "coverage"})
