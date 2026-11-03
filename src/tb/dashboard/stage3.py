"""Read-only Backtest Lab for admitted private Stage 3 result JSON."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tb.backtest.stage3_data import PrivateStore, VisionGold
from tb.backtest.stage3_runner import REGISTRATION_SHA, RUN_ID
from tb.research.models import ResearchRefused


def lab_result(root: Path) -> dict[str, Any] | None:
    """Recheck current rights, private-display permission, lifetime and result integrity."""
    value = PrivateStore(VisionGold(root), RUN_ID).read("results.json", display=True)
    if value is not None:
        if value.get("identity", {}).get("registration_sha256") != REGISTRATION_SHA:
            raise ResearchRefused("stage3_lab_registration_refused")
        for row in value.get("verdicts", []):
            if any(f.get("year") not in (2021, 2022, 2023, 2024) for f in row["folds"]):
                raise ResearchRefused("stage3_lab_scope_refused")
    return value


def stage3_view() -> None:
    """Display stored evidence only; this view has no run, tune, acquire or order action."""
    import streamlit as st

    st.subheader("Backtest Lab — Stage 3 crypto")
    configured = os.environ.get("TB_STAGE3_DATA_ROOT")
    if not configured:
        st.info("Private Stage 3 results are not configured.")
        return
    try:
        value = lab_result(Path(configured))
    except (OSError, ValueError, KeyError):
        st.info("Private results unavailable or refused by current rights, retention or integrity.")
        return
    if value is None:
        st.info("No completed registered batch is stored.")
        return
    st.caption("Private historical research · no execution · 162 fixed trials · 2024 validation")
    rows = value["verdicts"]
    label = st.selectbox("Strategy and symbol", [r["strategy"] + " / " + r["symbol"] for r in rows])
    selected = next(r for r in rows if r["strategy"] + " / " + r["symbol"] == label)
    st.write("Verdict: " + selected["verdict"])
    st.dataframe(
        [
            {
                "year": f["year"],
                "status": f["status"],
                **(f["metrics"] or {}),
                "5% circuit trips": f["circuit_trips"],
                "halted days": f["halted_days"],
                "ambiguous bars": f["ambiguous_bars"],
            }
            for f in selected["folds"]
        ],
        hide_index=True,
    )
    for ordering in ("stop", "target"):
        st.write(ordering + " first checklist")
        st.dataframe(
            [
                {"check": name, "passes": passes}
                for name, passes in selected["checklists"][ordering].items()
            ],
            hide_index=True,
        )
    st.write("Nominal 2R break-even win rate: 1/(1+2) = 33.33%")
    st.caption(
        "Compare with actual after-cost win_rate below; early exits and fees change payoffs."
    )
    st.dataframe(
        [
            {"path": path, "scope": scope, **metrics}
            for path, scopes in selected["metrics"].items()
            for scope, metrics in scopes.items()
        ],
        hide_index=True,
    )
