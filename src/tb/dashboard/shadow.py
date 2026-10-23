"""Read-only price-free shadow status; no runtime, account or network client import."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from tb.dashboard.readers import EvidenceUnavailable, read_json, safe_path, safe_text
from tb.ingest.history.core import sha256_file
from tb.ingest.rights import load_rights
from tb.shadow.models import ShadowSnapshot


def read_shadow_snapshot(folder: Path, *, mode: str) -> ShadowSnapshot:
    try:
        pointer = read_json(folder / "current.json")
        path = safe_path(folder, pointer["file"], ".json")
        if path.stat().st_size > 1048576 or sha256_file(path) != pointer["sha256"]:
            raise EvidenceUnavailable("Shadow snapshot integrity failed")
        value = ShadowSnapshot.model_validate(read_json(path))
        if value.mode != mode or value.generated_at > datetime.now(UTC):
            raise EvidenceUnavailable("Shadow provenance/clock failed")
        return value
    except (ValueError, KeyError, OSError, TypeError):
        raise EvidenceUnavailable("Verified shadow snapshot unavailable") from None


def shadow_view(root: Path) -> None:
    st.subheader("Shadow Research")
    st.caption("Reference research signals only · No orders, fills, positions or account P&L")
    selection = st.selectbox(
        "Shadow evidence", ["Owned fixture replay", "Genuine shadow (permission gated)"]
    )
    mode = "fixture_replay" if selection == "Owned fixture replay" else "genuine_shadow"
    try:
        genuine_rights = (
            load_rights(root / "config/data_rights.yaml")
            if (root / "config/data_rights.yaml").exists()
            else None
        )
    except (OSError, ValueError):
        st.error("Data permission policy invalid; genuine research remains blocked.")
        return
    if genuine_rights:
        st.write("Twelve Data permission state")
        st.dataframe(
            [
                {
                    "Usage": u,
                    "State": p.state_at(datetime.now(UTC)),
                    "Approved": p.approved,
                    "Expires": p.expires_at.isoformat() if p.expires_at else "unverified",
                }
                for u, p in genuine_rights.permissions.items()
            ],
            hide_index=True,
            width="stretch",
        )
    folder = (
        root
        / "reports/shadow"
        / ("fixture" if mode == "fixture_replay" else "genuine")
        / "runtime/snapshots"
    )
    try:
        value = read_shadow_snapshot(folder, mode=mode)
    except EvidenceUnavailable:
        st.info(
            "No verified shadow run attached. Genuine collection/trial remains blocked pending explicit data rights and approval."
        )
        return
    if mode == "fixture_replay":
        st.warning(
            "OWNED SYNTHETIC FIXTURE REPLAY · Software mechanics only; no genuine strategy performance"
        )
    st.write(
        "Provider:",
        value.provider,
        "· Consumer:",
        value.consumer_state,
        "· Collector:",
        value.collector_state,
    )
    if (
        value.consumer_state == "running"
        and (datetime.now(UTC) - value.generated_at).total_seconds() > 60
    ):
        st.warning(
            "Consumer heartbeat is stale; current availability unverified. No healthy operation inferred."
        )
    st.dataframe(value.instruments, hide_index=True, width="stretch")
    st.write("Research decision counts", value.counts)
    st.dataframe(value.latest_decisions, hide_index=True, width="stretch")
    st.caption(
        "BUY/SELL, when eligible in a future reviewed strategy, are research directions. Current definitions are blocked or WAIT controls; no strategy was invented to force an entry."
    )
    st.write("Collection budget / usage", value.quota)
    st.write("Runtime and observation lag", value.latency)
    st.write("Versions", value.versions)
    st.write(
        "Outcome metrics: unavailable; no eligible directional strategy or genuine evaluation sample."
    )
    st.write("Trade P&L: unavailable. No executable quotes, costs or fills exist in this view.")
    st.caption(safe_text(value.evidence_completeness))
    if value.failures:
        st.dataframe(value.failures, hide_index=True, width="stretch")
