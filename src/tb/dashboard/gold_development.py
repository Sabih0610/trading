"""Read-only aggregate gold development evidence; no acquisition or strategy controls."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tb.backtest.gold_development import REGISTRATION_SHA, RUN_ID
from tb.research.gold_development_data import GoldSource, PrivateStore
from tb.research.gold_proxy import PROXY_LABEL
from tb.research.models import ResearchRefused

METRICS = frozenset(("profit_factor", "expectancy_r", "max_dd_pct", "trade_count", "sharpe", "dsr"))
STRATEGIES = frozenset(("london_sweep_mss_fvg", "trend_vwap_pullback", "session_orb"))


def gold_lab_result(root: Path) -> list[dict[str, Any]] | None:
    """Current original rights, retention, display permission and checksum precede reads."""
    value = PrivateStore(GoldSource(root), RUN_ID).read("results.json", display=True)
    if value is None:
        return None
    if value.get("identity", {}).get("registration_sha256") != REGISTRATION_SHA:
        raise ResearchRefused("gold_lab_registration_refused")
    result = []
    for row in value.get("verdicts", []):
        if (
            row.get("strategy") not in STRATEGIES
            or row.get("symbol") != "XAUTUSDT"
            or row.get("proxy") != PROXY_LABEL
            or row.get("status") != "development only: not validated"
            or row.get("verdict") not in {"reject", "promising", "insufficient evidence"}
        ):
            raise ResearchRefused("gold_lab_scope_refused")
        for path in row["metrics"].values():
            if set(path["aggregate"]) != METRICS:
                raise ResearchRefused("gold_lab_metric_scope_refused")
            for fold in path["folds"]:
                if fold["year"] not in (2022, 2023) or set(fold["metrics"]) != METRICS:
                    raise ResearchRefused("gold_lab_fold_scope_refused")
        result.append(
            {
                key: row[key]
                for key in (
                    "strategy",
                    "symbol",
                    "proxy",
                    "status",
                    "verdict",
                    "metrics",
                    "ambiguity_verdicts",
                    "quality_gate",
                    "missing_training_folds",
                )
            }
        )
    if len(result) != 3 or {row["strategy"] for row in result} != STRATEGIES:
        raise ResearchRefused("gold_lab_incomplete_batch_refused")
    return result


def gold_view() -> None:
    """Display permitted aggregates and diagnostics without accessing input prices."""
    import streamlit as st

    st.subheader("Backtest Lab — gold development")
    st.warning("development only: not validated")
    st.caption(PROXY_LABEL + " · 54 fixed trials · no execution")
    configured = os.environ.get("TB_GOLD_STAGE3_DATA_ROOT")
    if not configured:
        st.info("Private gold development results are not configured.")
        return
    try:
        rows = gold_lab_result(Path(configured))
    except (OSError, ValueError, KeyError, TypeError):
        st.info("Private gold results unavailable or refused by rights, retention or integrity.")
        return
    if rows is None:
        st.info("No completed registered gold batch is stored.")
        return
    name = st.selectbox("Gold strategy", [row["strategy"] for row in rows])
    selected = next(row for row in rows if row["strategy"] == name)
    st.write("Development verdict: " + selected["verdict"])
    st.dataframe(
        [{"path": path, **scope["aggregate"]} for path, scope in selected["metrics"].items()],
        hide_index=True,
    )
    st.dataframe(
        [
            {
                "path": path,
                "year": fold["year"],
                "status": fold["status"],
                **fold["metrics"],
                "5% circuit trips": fold["circuit_trips"],
                "halted days": fold["halted_days"],
                "ambiguous bars": fold["ambiguous_bars"],
            }
            for path, scope in selected["metrics"].items()
            for fold in scope["folds"]
        ],
        hide_index=True,
    )
    st.write("Quality gate counts")
    st.json(selected["quality_gate"])
    st.write("Ordering and trade-through verdicts")
    st.json(selected["ambiguity_verdicts"])
