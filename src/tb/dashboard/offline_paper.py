"""Read-only owned Paper Lab; SQLite opens in read-only mode and secrets are never read."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from typing import Any

import streamlit as st

from tb.dashboard.readers import EvidenceUnavailable, read_json, safe_path
from tb.ingest.history.core import sha256_file
from tb.paper.offline.models import VERSION, PaperInput, PaperState, digest
from tb.paper.offline.store import VERSIONS


def read_offline_paper(root: Path) -> dict[str, Any]:
    """Reconcile immutable snapshot, local checkpoint chain and independent journal cash flows."""
    folder = root / "reports/offline_paper"
    try:
        pointer = read_json(folder / "current.json")
        path = safe_path(folder, pointer["file"], ".json")
        if path.stat().st_size > 8388608 or sha256_file(path) != pointer["sha256"]:
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        if (
            value["schema_version"] != 1
            or value["version"] != VERSION
            or value["mode"] != "owned_offline_paper"
            or value["label"] != "SYNTHETIC — SOFTWARE TEST ONLY"
            or value["external_orders_enabled"] is not False
            or value["genuine_sources_enabled"] is not False
            or value["genuine_performance_claim"] is not False
            or value["partial_fills_supported"] is not False
            or not 1 <= len(value["studies"]) <= 20
        ):
            raise ValueError
        for study in value["studies"]:
            state = PaperState.model_validate(study["state"])
            if digest(state.model_dump(mode="json")) != study["state_sha256"]:
                raise ValueError
            journal = safe_path(
                root / "work/offline_paper",
                str(Path(study["journal"]).relative_to("work/offline_paper")),
                ".sqlite",
            )
            manifest = read_json(journal.parent / "paper.manifest.json")
            if (
                manifest["provider"] != "owned_fixture"
                or manifest["code_sha256"] != value["code_sha256"]
                or manifest["package"] != study["package"]
                or manifest["package_sha256"] != digest(study["package"])
            ):
                raise ValueError
            with sqlite3.connect(f"{journal.as_uri()}?mode=ro", uri=True) as db:
                rows = db.execute(
                    "SELECT id,input_json,payload_sha,effects_json,state_json,state_sha,chain_sha FROM paper_events ORDER BY seq LIMIT 5001"
                ).fetchall()
                if not rows or len(rows) > 5000 or len(rows) != study["checkpoint_events"]:
                    raise ValueError
                chain = "0" * 64
                effects = []
                ledger_count = 0
                for (
                    event_id,
                    input_json,
                    payload_sha,
                    effects_json,
                    state_json,
                    state_sha,
                    recorded,
                ) in rows:
                    current_effects = json.loads(effects_json)
                    if (
                        digest(json.loads(input_json)) != payload_sha
                        or digest(json.loads(state_json)) != state_sha
                    ):
                        raise ValueError
                    chain = digest(
                        [chain, event_id, payload_sha, state_sha, digest(current_effects)]
                    )
                    if chain != recorded:
                        raise ValueError
                    event = PaperInput.model_validate_json(input_json)
                    for i, effect in enumerate(current_effects):
                        identifier = digest(["paper-ledger", event.id, i])
                        payload = {"mode": "owned_offline_paper", "input_id": event.id, **effect}
                        row = db.execute(
                            "SELECT payload_json,content_sha256 FROM decisions WHERE id=?",
                            (identifier,),
                        ).fetchone()
                        expected = {
                            "id": identifier,
                            "created_at_utc": event.received_at.astimezone(UTC)
                            .isoformat()
                            .replace("+00:00", "Z"),
                            "decision_id": None,
                            "payload": payload,
                            **VERSIONS.model_dump(),
                        }
                        if (
                            row is None
                            or json.loads(row[0]) != payload
                            or row[1] != digest(expected)
                        ):
                            raise ValueError
                        ledger_count += 1
                    effects.extend(current_effects)
                if db.execute("SELECT count(*) FROM decisions").fetchone()[0] != ledger_count:
                    raise ValueError
                if chain != study["chain_sha256"] or json.loads(rows[-1][4]) != study["state"]:
                    raise ValueError
            fills = [e for e in effects if e["kind"] == "hypothetical_fill"]
            if fills != study["fills"] or effects[-250:] != study["journal_tail"]:
                raise ValueError
            for key, account in state.accounts.items():
                account_fills = [f for f in fills if f["account"] == key]
                if account.cash != account.initial_cash + sum(
                    (Decimal(f["cash_delta"]) for f in account_fills), Decimal(0)
                ):
                    raise ValueError
                if account.fees != sum(
                    (Decimal(f["fee"]) for f in account_fills), Decimal(0)
                ) or account.fill_count != len(account_fills):
                    raise ValueError
        return value
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
        raise EvidenceUnavailable("Owned paper evidence missing or failed reconciliation") from None


def offline_paper_view(root: Path) -> None:
    """Inspect owned lifecycle reasons and accounting; this view has no action controls."""
    st.subheader("Offline Paper Lab")
    st.warning("SYNTHETIC — SOFTWARE TEST ONLY")
    st.caption(
        "Owned inputs and hypothetical all-or-none fills. No genuine broker performance, liquidity depth, queue position or market-impact evidence. Partial fills are unsupported."
    )
    try:
        value = read_offline_paper(root)
    except EvidenceUnavailable as exc:
        st.info(str(exc))
        st.code("python -m tb.paper.offline.cli demo", language="powershell")
        return
    study_name = st.selectbox("Owned scenario", [s["name"] for s in value["studies"]])
    study = next(s for s in value["studies"] if s["name"] == study_name)
    account_id = st.selectbox("Virtual account", ["USD100", "ENG10000"])
    a = study["state"]["accounts"][account_id]
    metrics = [
        ("Starting USD", a["initial_cash"]),
        ("Cash USD", a["cash"]),
        ("Reserved USD", a["reserved"]),
        ("Net liquidation equity USD", a["equity"]),
        ("Realized P&L USD", a["realized_pnl"]),
        ("Unrealized P&L USD", a["unrealized_pnl"]),
        ("Fees USD", a["fees"]),
        ("Adverse slippage USD", a["slippage"]),
        ("Maximum drawdown %", a["maximum_drawdown_pct"]),
    ]
    cols = st.columns(3)
    for i, (label, data) in enumerate(metrics):
        cols[i % 3].metric(label, "Unavailable" if data is None else f"{Decimal(str(data)):,.6f}")
    st.info(
        f"Risk state: daily halt={a['safety']['daily_halted']}; peak halt={a['safety']['peak_halted']}. {a['completed_trades']} closed hypothetical trades; {a['fill_count']} hypothetical fills."
    )
    st.caption(
        f"Checkpoint {study['checkpoint_events']} inputs; recovered {study['recovered_events']}; evidence {study['integrity']}. Account cash independently reconciles to committed fill cash flows."
    )
    st.write("Owned position")
    st.json(a["position"] or {"state": "flat"})
    st.write("Paper intention lifecycle and refusal reasons")
    st.dataframe(list(a["orders"].values()), hide_index=True, width="stretch")
    st.write("Hypothetical fill journal")
    st.dataframe(
        [f for f in study["fills"] if f["account"] == account_id], hide_index=True, width="stretch"
    )
    with st.expander("Management, closing and accounting reasons"):
        st.json([e for e in study["journal_tail"] if e.get("account") == account_id][-40:])
    with st.expander("Source, contract and strategy versions"):
        st.json(
            {
                "version": value["version"],
                "code_sha256": value["code_sha256"],
                "package": study["package"],
                "chain_sha256": study["chain_sha256"],
                "quoted_spread_at_fills_usd": a["quoted_spread_cost"],
            }
        )
    st.caption(
        "Spread and slippage are already reflected in fill prices; the displayed diagnostics are not deducted again. Missing marks remain unavailable. Legal and independent Shariah eligibility are not established by this software test."
    )
