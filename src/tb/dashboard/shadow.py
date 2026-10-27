"""Read-only price-free shadow status; no runtime, account or network client import."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from tb.dashboard.readers import EvidenceUnavailable, read_json, safe_path, safe_text
from tb.ingest.history.core import sha256_file
from tb.ingest.retention import require_projection
from tb.ingest.rights import load_rights
from tb.ingest.rights_review import check_review
from tb.shadow.fixtures import SCENARIOS
from tb.shadow.models import ShadowSnapshot


def read_shadow_snapshot(folder: Path, *, mode: str, root: Path | None = None) -> ShadowSnapshot:
    try:
        if mode not in {"fixture_replay", "genuine_shadow"}:
            raise EvidenceUnavailable("Unknown shadow mode")
        now = datetime.now(UTC)
        rights = None
        if mode == "genuine_shadow":
            if root is None:
                raise EvidenceUnavailable("Current documentary rights required; no snapshot read")
            rights = check_review(root, root / "config/data_rights.yaml", now)
            for symbol in rights.instruments:
                rights.require(
                    ("derived_storage", "private_display"),
                    provider="twelve_data",
                    identity=rights.account_fingerprint or "unconfigured",
                    symbol=symbol,
                    now=now,
                )
        pointer = read_json(folder / "current.json")
        if rights:
            require_projection(rights, pointer.get("authorization", {}), now)
        path = safe_path(folder, pointer["file"], ".json")
        if path.stat().st_size > 1048576 or sha256_file(path) != pointer["sha256"]:
            raise EvidenceUnavailable("Shadow snapshot integrity failed")
        value = ShadowSnapshot.model_validate(read_json(path))
        if rights and (
            value.authorization != pointer.get("authorization")
            or value.rights_digest != rights.digest
            or value.source_identity != rights.account_fingerprint
            or value.provider != rights.provider
            or {row.get("instrument") for row in value.instruments} != set(rights.instruments)
        ):
            raise EvidenceUnavailable("Current shadow source/rights mismatch")
        if rights:
            retained = require_projection(rights, pointer["authorization"], now)
            for row in value.latest_decisions:
                if (
                    row.get("received_at")
                    and datetime.fromisoformat(row["received_at"].replace("Z", "+00:00"))
                    < retained.acquired_at
                ):
                    raise EvidenceUnavailable("Shadow acquisition clock changed")
        if value.mode != mode or value.generated_at > datetime.now(UTC):
            raise EvidenceUnavailable("Shadow provenance/clock failed")
        return value
    except (ValueError, KeyError, OSError, TypeError):
        raise EvidenceUnavailable("Verified shadow snapshot unavailable") from None


def shadow_view(root: Path) -> None:
    st.subheader("Shadow Research")
    st.caption("Reference research signals only · No orders, fills, positions or account P&L")
    selection = st.selectbox(
        "Shadow evidence",
        ["Owned fixture replay", "Owned price-only scenarios", "Genuine shadow (permission gated)"],
    )
    mode = (
        "genuine_shadow" if selection == "Genuine shadow (permission gated)" else "fixture_replay"
    )
    try:
        genuine_rights = (
            load_rights(root / "config/data_rights.yaml")
            if mode == "genuine_shadow" and (root / "config/data_rights.yaml").exists()
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
    if selection == "Owned price-only scenarios":
        scenario = st.selectbox("Owned market scenario", SCENARIOS)
        folder = root / "reports/shadow/price_only" / scenario / "runtime/snapshots"
    try:
        value = read_shadow_snapshot(folder, mode=mode, root=root)
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
    if value.strategy_states:
        st.write("Strategy readiness and warm-up")
        st.dataframe(
            value.strategy_states,
            hide_index=True,
            width="stretch",
            column_order=[
                "symbol",
                "strategy",
                "signal",
                "status",
                "contiguous_bars",
                "warmup_required",
                "reasons",
                "decision_at",
                "strategy_version",
                "evidence_mode",
            ],
        )
    st.dataframe(
        value.latest_decisions,
        hide_index=True,
        width="stretch",
        column_order=[
            "symbol",
            "strategy",
            "signal",
            "status",
            "decision_at",
            "reasons",
            "received_at",
            "source_close_at",
            "strategy_version",
            "feature_version",
            "id",
            "strategy_config_sha256",
        ],
    )
    st.caption(
        "BUY/SELL are directional research hypotheses only. SELL denotes a downward hypothesis only and grants no execution permission. Old execution-dependent strategies retain their compatibility blocks."
    )
    st.write("Collection budget / usage", value.quota)
    st.write("Runtime and observation lag", value.latency)
    st.write("Versions", value.versions)
    if value.evaluation:
        st.write("Frozen future-reference evaluation", value.evaluation_protocol)
        st.dataframe(
            value.evaluation,
            hide_index=True,
            width="stretch",
            column_order=[
                "symbol",
                "strategy",
                "horizon_m5",
                "available",
                "correct_direction",
                "incorrect_or_flat",
                "nonoverlapping",
                "overlapping",
                "missing_outcomes",
                "not_yet_available",
                "status",
                "directional_accuracy",
                "always_up_correct",
                "previous_move_scored",
                "previous_move_correct",
                "always_WAIT_scored",
                "directional_decisions",
                "nonoverlapping_correct",
            ],
        )
        st.caption(
            "Directional accuracy is not a trade win rate. Synthetic outcomes verify mechanics only. Overlapping windows, horizons and instruments are not independent evidence; WAIT is excluded and missing outcomes are not losses."
        )
        if value.recent_labels:
            st.write("Available future-reference labels")
            st.dataframe(
                value.recent_labels,
                hide_index=True,
                width="stretch",
                column_order=[
                    "symbol",
                    "strategy",
                    "signal",
                    "horizon_m5",
                    "label",
                    "correct",
                    "nonoverlapping",
                    "available_at",
                    "evaluation_start",
                    "evaluation_end",
                    "decision_id",
                ],
            )
    else:
        st.write(
            "Outcome metrics: unavailable; no eligible directional strategy or genuine evaluation sample."
        )
    st.write("Trade P&L: unavailable. No executable quotes, costs or fills exist in this view.")
    st.caption(safe_text(value.evidence_completeness))
    if value.failures:
        st.dataframe(value.failures, hide_index=True, width="stretch")
