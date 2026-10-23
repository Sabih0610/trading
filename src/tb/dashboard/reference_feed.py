"""Read-only status projection; Basic market prices are withheld by usage policy."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import streamlit as st

from tb.dashboard.models import display_time
from tb.dashboard.readers import EvidenceUnavailable, read_json, safe_path, safe_text
from tb.ingest.history.core import sha256_file
from tb.ingest.twelve_data.models import ReferenceExport


def read_reference_export(folder: Path) -> ReferenceExport:
    """Read only a bounded hash-indexed snapshot; never credentials, caches or raw files."""
    try:
        pointer = read_json(folder / "current.json")
        path = safe_path(folder, pointer["file"], ".json")
        if path.stat().st_size > 1_000_000 or sha256_file(path) != pointer["sha256"]:
            raise EvidenceUnavailable("Reference export integrity refused")
        value = ReferenceExport.model_validate(read_json(path))
        if value.source != "twelve_data" or value.generated_at > datetime.now(UTC):
            raise EvidenceUnavailable("Reference source/clock refused")
        return value
    except (OSError, ValueError, TypeError, KeyError):
        raise EvidenceUnavailable("Verified Twelve Data snapshot unavailable") from None


def reference_feed_view(folder: Path, zone: Literal["UTC", "Asia/Karachi"]) -> None:
    """Provider data readiness is independent of costs, broker access or trading permission."""
    st.subheader("Twelve Data · Basic · reference midpoint observations")
    st.caption("Read-only · No executable bid/ask · External orders disabled · P11b unstarted")
    try:
        value = read_reference_export(folder)
    except EvidenceUnavailable:
        st.info("Verified Twelve Data observations unavailable.")
        return
    st.info(
        "Permitted usage: personal noncommercial internal development, non-display. "
        "Basic display rights remain unconfirmed; market prices are withheld. "
        "Long-term archive, redistribution and realistic paper fills are not authorized."
    )
    st.write(
        "Collector:",
        "last reported running; liveness unverified" if value.collector_running else "stopped",
    )
    st.caption(
        f"Collected {display_time(value.collection_started_at, zone)} · Last receipt snapshot {display_time(value.generated_at, zone)}"
    )
    now = datetime.now(UTC)
    rows = []
    for symbol, count in value.counts.items():
        observation = next((r for r in value.references if r.symbol == symbol), None)
        if observation is None:
            observation = max(
                (r for r in value.candles if r.symbol == symbol),
                key=lambda r: r.source_at,
                default=None,
            )
        age = (now - observation.source_at).total_seconds() if observation else None
        cadence_limit = 180 if observation and observation.kind == "candle" else 90
        rows.append(
            {
                "Provider": "Twelve Data Basic",
                "Instrument": symbol,
                "Last price": "withheld: display rights unconfirmed",
                "Data type": "completed M1 reference midpoint OHLC"
                if observation and observation.kind == "candle"
                else "aggregated reference midpoint",
                "Source timestamp (UTC)": display_time(observation.source_at, "UTC")
                if observation
                else "unavailable",
                "Receipt time (UTC)": display_time(observation.received_at, "UTC")
                if observation
                else "unavailable",
                "Freshness": "unavailable"
                if age is None
                else ("fresh within minute cadence" if 0 <= age <= cadence_limit else "STALE"),
                "Received": count.received,
                "Accepted": count.valid,
                "Rejected": count.rejected,
                "Duplicates": count.duplicates,
                "Qualified forward": count.qualified_forward,
                "Recorded qualification": safe_text(
                    value.readiness[symbol].get("source_data", "NO-GO")
                ),
                "Completed forward M1": value.readiness[symbol].get("completed_forward_M1", 0),
                "Executable bid/ask": "unavailable",
                "Realistic paper trading": "NO-GO",
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        "Recorded bounded qualification remains distinct from current freshness and continuous reliability. HTTP/UTC validation uses the documented timestamp contract; original broker profiles are unchanged."
    )
    for symbol, readiness in value.readiness.items():
        st.write(safe_text(symbol), "—", safe_text(readiness.get("reason", "unavailable")))
    st.write("Incomplete intervals in last response:", value.incomplete_intervals)
    st.caption(
        "Only elapsed completed M1 intervals can qualify. Initial history stays backfill; provider finality and complete tick coverage remain unverified."
    )
    st.write("Actual plan and conservative usage:", value.plan_usage)
    for warning in value.warnings:
        st.warning(safe_text(warning))
