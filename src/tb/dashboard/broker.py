"""Read-only broker evidence projection; no credentials, collector or transport import."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import streamlit as st

from tb.dashboard.readers import EvidenceUnavailable, read_json, safe_path, safe_text
from tb.ingest.broker.models import BrokerIdentity
from tb.ingest.history.core import sha256_file
from tb.ingest.rights_review import check_review


def read_broker_snapshot(
    root: Path, *, mode: Literal["owned_fixture", "genuine"]
) -> dict[str, Any]:
    """Check genuine rights before opening any quote-bearing snapshot file."""
    now = datetime.now(UTC)
    rights = None
    if mode == "genuine":
        try:
            rights = check_review(
                root, root / "config/broker_data_rights.yaml", now, provider="ctrader_demo"
            )
            for symbol in rights.instruments:
                rights.require(
                    ("retrieval", "derived_storage"),
                    provider="ctrader_demo",
                    identity=rights.account_fingerprint or "unconfigured",
                    symbol=symbol,
                    now=now,
                )
        except (ValueError, OSError):
            raise EvidenceUnavailable(
                "Genuine broker rights remain unverified; no snapshot read"
            ) from None
    folder = root / "reports/broker_quotes" / ("fixture" if mode == "owned_fixture" else "genuine")
    try:
        pointer = read_json(folder / "current.json")
        file = safe_path(folder, pointer["file"], ".json")
        if file.stat().st_size > 262144 or sha256_file(file) != pointer["sha256"]:
            raise ValueError
        value = read_json(file)
        identity = BrokerIdentity.model_validate(value["identity"])
        if (
            value["mode"] != mode
            or identity.evidence != mode
            or value.get("schema_version") != 1
            or value.get("broker_provider") != "ctrader_demo"
            or value.get("external_orders_enabled") is not False
            or value.get("fills_created") != 0
            or value.get("positions_created") != 0
            or value.get("p11b2") != "NO-GO"
            or len(value["instruments"]) > 2
            or len(value["alignments"]) > 20
            or datetime.fromisoformat(value["generated_at"]) > now
        ):
            raise ValueError
        if rights:
            if (
                rights.digest != value["rights_digest"]
                or rights.account_fingerprint != identity.account_fingerprint
            ):
                raise ValueError
            display = rights.permissions.get("private_display")
            if not display or not display.allows(now):
                for row in value["instruments"]:
                    for field in (
                        "bid",
                        "ask",
                        "spread",
                        "minimum_notional",
                        "minimum_capital_with_known_costs",
                    ):
                        row[field] = None
        return value
    except (ValueError, OSError, KeyError, TypeError):
        raise EvidenceUnavailable("Verified broker evidence unavailable") from None


def broker_view(root: Path) -> None:
    st.subheader("Broker quote readiness")
    st.caption(
        "Reference midpoint decisions and broker bid/ask are distinct sources. Observations only; P11b.2 remains NO-GO."
    )
    selection = st.selectbox(
        "Broker evidence", ["Owned broker fixtures", "Genuine broker (permission gated)"]
    )
    mode: Literal["owned_fixture", "genuine"] = (
        "owned_fixture" if selection == "Owned broker fixtures" else "genuine"
    )
    try:
        value = read_broker_snapshot(root, mode=mode)
    except EvidenceUnavailable:
        st.info(
            "No verified broker evidence attached. Genuine demo account, view scope, clocks and data-use rights remain unverified."
        )
        return
    identity = BrokerIdentity.model_validate(value["identity"])
    if mode == "owned_fixture":
        st.warning(
            "OWNED BROKER FIXTURES · Mock protocol/account data only; no genuine account qualification or fill evidence."
        )
    st.write(
        "Reference provider:",
        safe_text(value["reference_provider"]),
        "· Broker provider: ctrader_demo",
    )
    st.caption(
        f"Demo identity {identity.account_fingerprint[:12]} · {identity.permission} · archived evidence {value['generated_at']} · connection stopped"
    )
    rows = []
    for item in value["instruments"]:
        rows.append(
            {
                "Instrument": safe_text(item["symbol"]),
                "Market data at capture": item["market_data_ready"],
                "Contract complete": item["contract_ready"],
                "Costs complete": item["costs_ready"],
                "$100 funded minimum": item["funded_minimum_affordable"],
                "Minimum units": item["minimum_units"],
                "Bid": item.get("bid"),
                "Ask": item.get("ask"),
                "Spread": item.get("spread"),
                "Source UTC": item["source_timestamp"],
                "Receipt UTC": item["receipt_utc"],
                "Age at receipt seconds": item["quote_age_at_receipt_seconds"],
                "Age now seconds": round(
                    (
                        datetime.now(UTC) - datetime.fromisoformat(item["receipt_utc"])
                    ).total_seconds()
                    + item["quote_age_at_receipt_seconds"],
                    2,
                )
                if item["receipt_utc"] is not None
                else None,
                "Raw observations": item["counts"].get("raw_observations", 0),
                "Admissible quotes": item["counts"].get("admissible_quotes", 0),
                "Aligned observations": item["counts"].get("aligned_observations", 0),
                "Display": item["display_status"],
                "P11b.2": item["p11b2"],
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.dataframe(
        [
            {"Instrument": item["symbol"], "Readiness refusals": ", ".join(item["reasons"])}
            for item in value["instruments"]
        ],
        hide_index=True,
        width="stretch",
    )
    if value["alignments"]:
        st.write("Reference-to-broker observation alignment")
        st.dataframe(
            value["alignments"],
            hide_index=True,
            width="stretch",
            column_order=[
                "symbol",
                "status",
                "reason",
                "decision_at",
                "quote_received_at",
                "delay_seconds",
            ],
        )
    st.info(
        "Indicative dealing prices do not guarantee eventual fills. Legal/Shariah eligibility and all-in simulation risk remain independently unverified; no account P&L is inferred."
    )
