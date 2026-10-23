"""Read-only prospective feed projection, isolated from account P&L and historical readers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import streamlit as st
from pydantic import AwareDatetime, Field, model_validator

from tb.dashboard.models import display_time
from tb.dashboard.readers import EvidenceUnavailable, read_json, safe_path, safe_text
from tb.ingest.history.core import sha256_file
from tb.ingest.mt5.models import (
    TIMEFRAMES,
    AdmissionCheck,
    DemoIdentity,
    FeedConfig,
    FeedState,
    Health,
    InstrumentCounts,
    InstrumentFacts,
    Observation,
    quote_health,
)
from tb.risk.config import PolicyModel


class FeedExport(PolicyModel):
    schema_version: Literal[1]
    source: Literal["mt5_demo", "synthetic"]
    session_id: str
    session_started: AwareDatetime
    generated_at: AwareDatetime
    identity: DemoIdentity | dict[str, Any]
    facts: list[InstrumentFacts] = Field(max_length=2)
    health: list[Health] = Field(max_length=2)
    quotes: list[Observation] = Field(max_length=2)
    candles: list[Observation] = Field(max_length=100)
    warnings: list[str] = Field(max_length=50)
    historical_backfill_displayed: Literal[False]
    external_orders_enabled: Literal[False]
    poll_seconds: float = Field(ge=5, le=300)
    collector_running: bool
    collection_started_at: AwareDatetime | None = None
    collection_ended_at: AwareDatetime | None = None
    counts: dict[str, InstrumentCounts] = Field(default_factory=dict)
    admission: AdmissionCheck | None = None
    connection_status: str = "unverified"
    coverage_kind: str = "coverage_unverified"

    @model_validator(mode="after")
    def prospective_only(self) -> FeedExport:
        from datetime import timedelta

        if self.collection_started_at and self.collection_started_at > self.generated_at:
            raise ValueError("Future collection start refused")
        if self.collection_ended_at and (
            self.collection_ended_at > self.generated_at
            or (
                self.collection_started_at and self.collection_ended_at < self.collection_started_at
            )
        ):
            raise ValueError("Collection interval refused")
        if self.identity or self.quotes or self.candles:
            DemoIdentity.model_validate(self.identity)
        if any(r.kind != "quote" for r in self.quotes) or any(
            r.kind != "candle" for r in self.candles
        ):
            raise ValueError("Feed projection record kind mismatch")
        if any(f.source != self.source for f in self.facts):
            raise ValueError("Feed metadata provenance mismatch")
        for row in [*self.quotes, *self.candles]:
            if self.source == "synthetic":
                if row.evidence != "synthetic":
                    raise ValueError("Synthetic provenance mismatch")
            elif (
                row.evidence != "forward_observed"
                or row.source_at < self.session_started
                or row.received_at < row.source_at
                or row.received_at > self.generated_at
            ):
                raise ValueError("Historical evidence refused by prospective reader")
            if (
                row.kind == "candle"
                and row.source_at + timedelta(seconds=TIMEFRAMES[row.timeframe]) > row.received_at
            ):
                raise ValueError("Unfinished candle refused")
            if self.source == "mt5_demo" and row.kind == "candle":
                end = row.source_at + timedelta(seconds=TIMEFRAMES[row.timeframe])
                if (
                    row.coverage_started_at is None
                    or row.coverage_started_at > row.source_at
                    or (row.received_at - end).total_seconds() > self.poll_seconds * 3
                ):
                    raise ValueError("Prospective candle coverage or receipt lag refused")
        return self


def read_feed_export(folder: Path) -> FeedExport:
    """Verify a small, explicitly indexed snapshot; never scan raw or reserved market files."""
    try:
        pointer = read_json(folder / "current.json")
        path = safe_path(folder, pointer["file"], ".json")
        if path.stat().st_size > 1_000_000 or sha256_file(path) != pointer["sha256"]:
            raise EvidenceUnavailable("Feed export integrity failed")
        export = FeedExport.model_validate(read_json(path))
        now = datetime.now(UTC)
        if export.generated_at > now or export.session_started > export.generated_at:
            raise EvidenceUnavailable("Feed export clock or session refused")
        return export
    except (OSError, ValueError, KeyError, TypeError):
        raise EvidenceUnavailable("Verified market-feed snapshot unavailable") from None


def market_feed_view(root: Path, zone: Literal["UTC", "Asia/Karachi"]) -> None:
    """Show monitoring separately; no quote is combined with synthetic account returns."""
    st.subheader("Market Feed")
    collection = st.radio(
        "Market evidence",
        ["Genuine MT5 demo observations", "Synthetic feed fixture"],
        horizontal=True,
    )
    synthetic = collection == "Synthetic feed fixture"
    folder = root / "reports/market_feed" / ("synthetic" if synthetic else "genuine")
    st.caption(
        "Data acquisition only · External orders disabled · Independent eligibility unchanged"
    )
    try:
        export = read_feed_export(folder)
        if (export.source == "synthetic") != synthetic:
            raise EvidenceUnavailable("Collection provenance mismatch")
    except EvidenceUnavailable:
        st.info("Market feed unavailable. No verified collection snapshot is attached.")
        return
    if synthetic:
        st.warning("SYNTHETIC feed fixture. These prices are generated for software testing.")
    else:
        st.info("Source: MT5 demo market observations. This is a data feed; trading is disabled.")
    st.write(
        "Collector:",
        "last reported running; liveness unverified" if export.collector_running else "stopped",
    )
    connection_labels = {
        "pinned_demo_connected_at_diagnostic; current_liveness_unverified": "Demo terminal connected at the diagnostic; current connection unverified",
        "pinned_demo_connected": "Pinned demo terminal connected at the last poll",
        "not_currently_observed": "Current connection unverified",
    }
    st.write(
        "Connection observation:", connection_labels.get(export.connection_status, "Unverified")
    )
    st.caption("Connection and collection state do not establish price validity.")
    if export.collection_started_at:
        st.caption(
            f"Collection start: {display_time(export.collection_started_at, zone)} · End: "
            + (
                display_time(export.collection_ended_at, zone)
                if export.collection_ended_at
                else "not reported"
            )
        )
    if export.admission:
        st.write(
            "Native MCP safety:",
            "PASS" if export.admission.security_passed else "FAILED / unverified",
            "· Trading permission:",
            export.admission.native_trading_allowed,
            "· Shell tool available:",
            export.admission.dangerous_shell_tool_available,
        )
        st.caption(
            f"Safety observation: {display_time(export.admission.checked_at, zone)}; current settings require fresh verification."
        )
    else:
        st.info("Native MCP safety state has not been verified in this snapshot.")
    if export.counts:
        st.dataframe(
            [
                {
                    "Market": s,
                    "Received": c.received,
                    "Valid": c.valid,
                    "Rejected": c.rejected,
                    "Duplicates": c.duplicates,
                    "Qualified": c.qualified_forward,
                    "Source updates": c.quote_updates,
                    "Missing": c.missing,
                }
                for s, c in export.counts.items()
            ],
            hide_index=True,
            width="stretch",
        )
        for symbol_name, count in export.counts.items():
            if count.rejected_by_reason:
                for reason, number in count.rejected_by_reason.items():
                    st.write(
                        safe_text(symbol_name),
                        "rejected:",
                        safe_text(reason.replace("_", " ")),
                        "—",
                        number,
                    )
    st.caption(
        "Bounded diagnostic samples"
        if export.coverage_kind.startswith("bounded_diagnostic")
        else "Sampled polling observations"
    )
    st.caption("Complete market tick coverage has not been verified.")
    st.caption(
        f"Session {safe_text(export.session_id)} · Started {display_time(export.session_started, zone)}"
    )
    identity = DemoIdentity.model_validate(export.identity) if export.identity else None
    if identity:
        st.write("Broker:", safe_text(identity.broker), "· Server:", safe_text(identity.server))
        st.caption(
            f"Demo identity fingerprint: {identity.fingerprint[:12]}… · Terminal build {identity.terminal_build}"
        )
    now = datetime.now(UTC)
    for health in export.health:
        current = quote_health(
            health.symbol,
            health.source_at,
            health.received_at,
            now,
            FeedConfig(),
            connected=export.collector_running
            and health.state not in {FeedState.DISCONNECTED, FeedState.INSTRUMENT_UNAVAILABLE},
        )
        if health.state in {FeedState.INSTRUMENT_UNAVAILABLE, FeedState.UNKNOWN}:
            current = health
        st.write(safe_text(health.symbol), "—", current.state.value, "—", safe_text(current.reason))
    rows = []
    for row in export.quotes:
        age = (now - row.source_at).total_seconds()
        rows.append(
            {
                "Market": row.symbol,
                "Broker symbol": row.broker_symbol,
                "Bid": str(row.bid),
                "Ask": str(row.ask),
                "Spread": str(row.ask - row.bid)
                if row.ask is not None and row.bid is not None
                else "unavailable",
                "Reported spread (points)": row.spread_points,
                "Source time": display_time(row.source_at, zone),
                "Receipt time": display_time(row.received_at, zone),
                "Age (seconds)": round(age, 1),
                "Evidence": row.evidence,
            }
        )
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.warning(
            "No validated quotes are available. Check source UTC against receipt UTC, exact symbol visibility, demo connection and native safety permissions. No invalid bid/ask is displayed."
        )
    st.caption(
        f"Stored quote sample: {len(rows)} latest observations; this is not a return or strategy sample."
    )
    if not export.facts:
        st.info(
            "Instrument metadata is unavailable. Verify exact XAUUSD and EURUSD mappings; do not substitute a similarly named stock."
        )
    else:
        instrument_facts_table(export)
    st.subheader("Recent completed prospective candles")
    if export.candles:
        symbol = st.selectbox("Feed candle market", sorted({r.symbol for r in export.candles}))
        timeframe = st.selectbox(
            "Feed candle timeframe",
            sorted({r.timeframe for r in export.candles if r.symbol == symbol}),
        )
        candles = sorted(
            [r for r in export.candles if r.symbol == symbol and r.timeframe == timeframe],
            key=lambda r: r.source_at,
        )
        candle_rows: list[dict[str, Any]] = [
            {
                "Time": display_time(r.source_at, zone),
                "Open": str(r.open),
                "High": str(r.high),
                "Low": str(r.low),
                "Close": str(r.close),
                "Broker tick count": str(r.tick_volume),
                "Evidence": r.evidence,
            }
            for r in candles
        ]
        st.dataframe(candle_rows, hide_index=True, width="stretch")
        st.caption(
            f"{len(candles)} completed {timeframe} observations. Tick counts are broker activity, not global FX volume."
        )
    else:
        st.info(
            "No completed candles qualify for prospective display yet. Historical backfill stays quarantined."
        )
    for warning in export.warnings:
        st.warning(safe_text(warning.replace("_", " ")))


def instrument_facts_table(export: FeedExport) -> None:
    """Render only an available, validated instrument metadata projection."""
    st.dataframe(
        [
            {
                "Market": f.symbol,
                "Broker symbol": f.broker_symbol,
                "Base": f.base_currency,
                "Quote": f.quote_currency,
                "Tick size": str(f.tick_size),
                "Contract size": str(f.contract_size),
                "Sizing usable": False,
                "Session schedule": f.session_schedule,
            }
            for f in export.facts
        ],
        hide_index=True,
        width="stretch",
    )
