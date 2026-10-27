"""Local read-only Streamlit evidence dashboard; no provider or execution capabilities."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import streamlit as st

from tb.agents.budget import load_ai_budget
from tb.backtest.research import assess_research, load_research_policies
from tb.core.config import ConfigLoadError, repo_root
from tb.core.contracts import DashboardSnapshot
from tb.dashboard.broker import broker_view
from tb.dashboard.components import decisions_table, equity_chart, metric_grid, price_chart
from tb.dashboard.feed import market_feed_view
from tb.dashboard.models import (
    DecisionPage,
    EvidenceSource,
    LedgerTotals,
    RiskObservation,
    account_metrics,
    display_time,
    freshness,
)
from tb.dashboard.readers import (
    EvidenceUnavailable,
    account_record,
    catalog,
    decision_counts,
    decision_page,
    file_stamp,
    journal_versions,
    ledger_totals,
    marked_drawdown,
    parquet_rows,
    read_json,
    safe_path,
    safe_text,
)
from tb.risk.config import PolicyBundle, effective_risk_limits, load_policy_bundle

VIEWS = (
    "Overview",
    "Markets & Strategies",
    "Trades & Decisions",
    "Risk & System Health",
    "AI & Model Research",
    "Market Feed",
    "Shadow Research",
    "Offline Paper Lab",
)


@st.cache_data(ttl=15, max_entries=32, show_spinner=False)
def cached_page(
    path: str, stamp: tuple[int, ...], mode: str, filters: dict[str, Any]
) -> DecisionPage:
    """Cache bounded projections, never database handles or secret-bearing raw rows."""

    return decision_page(Path(path), mode=mode, **filters)


@st.cache_data(ttl=30, max_entries=16, show_spinner=False)
def cached_totals(path: str, stamp: tuple[int, ...], mode: str) -> LedgerTotals:
    """Cache complete streaming aggregates independently from visible pages."""

    return ledger_totals(Path(path), mode)


@st.cache_data(ttl=30, max_entries=32, show_spinner=False)
def cached_chart(folder: str, name: str, mode: str, stamp: tuple[int, ...]) -> list[dict[str, Any]]:
    """Bound chart memory and invalidate on data/manifest changes."""

    return parquet_rows(Path(folder), name, mode)


@st.cache_data(ttl=30, max_entries=16, show_spinner=False)
def cached_drawdown(folder: str, mode: str, stamp: tuple[int, ...]) -> Decimal | None:
    """Scan complete marked exports without confusing a chart page with full performance."""

    return marked_drawdown(Path(folder), mode)


def _chart(folder: Path | None, name: str, source: EvidenceSource | None) -> list[dict[str, Any]]:
    if folder is None or source is None:
        return []
    try:
        path = safe_path(folder, name + ".parquet", ".parquet")
        return cached_chart(str(folder), name, source.mode, file_stamp(path))
    except EvidenceUnavailable:
        st.info(f"{name.title()} chart unavailable or refused by its provenance/holdout boundary.")
        return []


def _evidence(root: Path) -> tuple[int | None, int | None]:
    """Read explicit existing evaluation counters; absence never becomes a successful trial."""

    try:
        trials = read_json(root / "reports/safety/P09.5/P09.5.json").get("empirical_trials")
        trials = trials if isinstance(trials, int) and trials >= 0 else None
    except EvidenceUnavailable:
        trials = None
    try:
        path = root / "reports/ml/P08.md"
        text = path.read_text(encoding="utf-8") if path.stat().st_size <= 1_000_000 else ""
        models = (
            0
            if re.search(r"Training / calibration / validation trials\s*\|\s*0 / 0 / 0", text)
            else None
        )
    except OSError:
        models = None
    return trials, models


def _markets(
    bundle: PolicyBundle | None,
    source: EvidenceSource | None,
    folder: Path | None,
    page: DecisionPage,
    zone: Literal["UTC", "Asia/Karachi"],
) -> None:
    st.subheader("Markets & Strategies")
    if bundle is None:
        st.info("Instrument policy unavailable.")
        return
    assets = [
        a
        for a in bundle.registry.assets
        if a.symbol in ("XAUUSD", "EURUSD", "XAUTUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")
    ]
    rows = []
    try:
        policies = load_research_policies()
    except (ConfigLoadError, ValueError):
        policies = None
    for asset in assets:
        rows.append(
            dict(
                Instrument=asset.symbol,
                Type=asset.instrument_type,
                Research=asset.eligibility.historical_research,
                Local_simulation=asset.eligibility.local_simulation,
                Broker_demo=asset.eligibility.broker_demo,
                Live=asset.eligibility.live,
                Policy_status=asset.shariah_status.value,
                Independent_approval=safe_text(
                    asset.eligibility.independent_shariah_source or "Unavailable"
                ),
                Strategies=", ".join(asset.allowed_strategies)
                or "Separate contract research; no empirical strategy",
                Coverage=assess_research(policies.policy(asset.symbol), None).status
                if policies
                else "Policy unavailable",
            )
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        "Policy status is a project research label. Independent live eligibility has not been established."
    )
    selected = st.selectbox(
        "Price instrument",
        [a.symbol for a in assets],
        index=next((i for i, a in enumerate(assets) if source and a.symbol == source.symbol), 0),
    )
    if source is None or source.symbol != selected:
        st.info("No stored price export selected for this instrument.")
    else:
        price_chart(_chart(folder, "prices", source), page.rows, zone)
        if folder is not None:
            try:
                manifest = read_json(safe_path(folder, "prices.manifest.json", ".json"))
                st.caption("Source: " + safe_text(manifest.get("source", "Unavailable")))
                st.caption(
                    "Recorded coverage: "
                    + safe_text(manifest.get("time_start", "Unavailable"))
                    + " → "
                    + safe_text(manifest.get("time_end", "Unavailable"))
                )
                st.caption(
                    "Declared checksum: "
                    + safe_text(manifest.get("checksum", "Unavailable"))
                    + " · Not rehashed by the UI"
                )
            except EvidenceUnavailable:
                st.info("Price provenance unavailable.")
        st.caption(
            "Up to 2,000 stored price observations; markers are from the displayed journal page."
        )
    st.info(
        "Binance XAUT has insufficient history before the locked holdout. Reference XAUUSD never substitutes for Binance XAUT performance."
    )


def _risk(bundle: PolicyBundle | None, folder: Path | None, source: EvidenceSource | None) -> None:
    st.subheader("Risk & System Health")
    if bundle is not None:
        limits = bundle.risk.limits
        st.dataframe(
            [
                dict(
                    Planned_risk_pct=str(limits.risk_per_trade_pct),
                    Daily_equity_loss_pct=str(limits.daily_loss_limit_pct),
                    Peak_drawdown_pct=str(limits.max_peak_drawdown_pct),
                    Maximum_positions=limits.max_open_positions,
                    Gross_exposure_multiple=str(limits.max_total_exposure_multiple),
                    End_of_day_flat=limits.flat_by_end_of_day,
                )
            ],
            hide_index=True,
            width="stretch",
        )
        overrides = [
            dict(
                Instrument=a.symbol,
                Risk_pct=str(effective_risk_limits(a, limits).risk_per_trade_pct),
                Daily_entries=effective_risk_limits(a, limits).max_trades_per_day_per_asset,
            )
            for a in bundle.registry.assets
            if a.eligibility.local_simulation
        ]
        st.dataframe(overrides, hide_index=True, width="stretch")
    else:
        st.warning("Risk configuration unavailable; no safety status inferred.")
    if folder is not None and source is not None:
        counts = decision_counts(safe_path(folder, "journal.sqlite", ".sqlite"))
        st.write("Recorded decision counts" if counts else "Decision counts unavailable")
        if counts:
            st.dataframe(
                [dict(Status=k, Count=v) for k, v in counts.items()],
                hide_index=True,
                width="stretch",
            )
        try:
            record = RiskObservation.model_validate(
                read_json(safe_path(folder, "risk-state.json", ".json"))
            )
            if record.mode != source.mode:
                raise EvidenceUnavailable("Mode mismatch")
            instant = record.observed_at
            st.write("Recorded circuit observation: " + freshness(instant))
            st.dataframe(
                [
                    dict(
                        Daily_halted=record.daily_halted,
                        Peak_halted=record.peak_halted,
                        Observed_UTC=instant.isoformat(),
                    )
                ],
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Recorded evidence only. Current running-account latch and feed receipt health are unavailable."
            )
        except (EvidenceUnavailable, KeyError, ValueError, TypeError):
            st.info("Risk-latch observation unavailable.")
    st.info(
        "Live feed lag, runtime errors, broker reconciliation and active monitoring: unavailable. External orders are disabled."
    )


def _ai(
    root: Path, page: DecisionPage, trials: int | None, models: int | None, folder: Path | None
) -> None:
    st.subheader("AI & Model Research")
    left, right = st.columns(2)
    left.metric("Qualified empirical trials", "Unavailable" if trials is None else str(trials))
    right.metric(
        "Empirically trained market models", "Unavailable" if models is None else str(models)
    )
    st.info(
        "Trading accuracy, live calibration, model drift and after-cost AI value are not established. Mock or synthetic decisions are mechanics evidence."
    )
    st.caption(
        "Counters: stored P09.5 evidence summary and P08 evaluation report. No model/provider request is made."
    )
    try:
        budget = load_ai_budget(config_dir=root / "config")
        st.dataframe(
            [
                dict(
                    Provider=safe_text(name),
                    Policy="Enabled in config; runtime unverified"
                    if policy.enabled
                    else "Policy disabled",
                    Daily_cap_USD=policy.daily_usd,
                    Monthly_cap_USD=policy.monthly_usd,
                )
                for name, policy in budget.providers.items()
            ],
            hide_index=True,
            width="stretch",
        )
    except (ConfigLoadError, OSError, ValueError):
        st.info("Provider policy unavailable.")
    st.caption(
        "No credentials are inspected. Provider availability and calibration summaries are unavailable without recorded evidence."
    )
    decisions_table(tuple(r for r in page.rows if r.status in ("vetoed", "skipped")), "UTC")
    if folder:
        versions = journal_versions(safe_path(folder, "journal.sqlite", ".sqlite"))
        if versions:
            st.subheader("Recorded versions")
            st.dataframe(versions, hide_index=True, width="stretch")
            st.caption(
                "Software and fixture provenance; these identifiers do not establish a market-trained model."
            )
    try:
        arena = read_json(root / "reports/arena/P09.json")
        st.caption(
            "Arena evidence: "
            + safe_text(arena.get("mode", "Unavailable"))
            + " · "
            + safe_text(arena.get("independent_answers", "Unavailable"))
            + " recorded independent answers · "
            + safe_text(arena.get("paid_calls", "Unavailable"))
            + " paid calls"
        )
    except EvidenceUnavailable:
        st.info("Arena summary unavailable.")


def _implementation_status(root: Path) -> None:
    try:
        state = read_json(root / "docs/state/progress.json")
        phases = state.get("phases", {})
        st.subheader("Implementation status")
        st.dataframe(
            [
                dict(
                    Phase=key,
                    Component=safe_text(value.get("title", "Unavailable")),
                    Status=safe_text(value.get("status", "Unavailable")),
                )
                for key, value in phases.items()
                if key
                in ("P02", "P05", "P06", "P08", "P09", "P09.5", "P10", "P11", "P12", "P13", "P14")
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Phase documentation shows implemented software. Running-account health and empirical value are separate evidence."
        )
    except (EvidenceUnavailable, AttributeError, TypeError):
        st.info("Implementation status unavailable.")


def main() -> None:
    """Render read-only evidence views with explicit empty and incomplete states."""

    st.set_page_config(
        page_title="Trading Research | Evidence Review", page_icon="◈", layout="wide"
    )
    root = repo_root()
    report_root = Path(
        os.environ.get("TB_DASHBOARD_REPORT_ROOT", str(root / "reports/dashboard"))
    ).resolve()
    st.title("Trading Research")
    st.caption("EVIDENCE REVIEW  /  READ-ONLY  /  EXTERNAL ORDERS DISABLED")
    st.sidebar.title("Research workspace")
    collection = st.sidebar.selectbox(
        "Evidence collection", ["Workspace records", "Synthetic demo"]
    )
    collection_root = report_root / "P10-demo" if collection == "Synthetic demo" else report_root
    try:
        sources = catalog(collection_root)
    except EvidenceUnavailable:
        sources = ()
        st.warning("Evidence catalog unavailable or invalid.")
    ids = [s.id for s in sources]
    selected_id = st.sidebar.selectbox(
        "Account dataset",
        ids or ["No dataset"],
        format_func=lambda value: next(
            (safe_text(s.title) for s in sources if s.id == value), value
        ),
        disabled=not sources,
    )
    source = next((s for s in sources if s.id == selected_id), None)
    zone: Literal["UTC", "Asia/Karachi"] = st.sidebar.selectbox(
        "Display timezone", ["UTC", "Asia/Karachi"]
    )
    view = st.sidebar.radio("View", VIEWS)
    st.sidebar.caption(
        "Filters change this view only. No account actions or policy edits are available."
    )
    if view == "Market Feed":
        market_feed_view(root, zone)
        broker_view(root)
        return
    if view == "Offline Paper Lab":
        from tb.dashboard.offline_paper import offline_paper_view

        offline_paper_view(root)
        return
    if view == "Shadow Research":
        from tb.dashboard.shadow import shadow_view

        shadow_view(root)
        broker_view(root)
        return
    if source is not None:
        st.warning(
            "SYNTHETIC FIXTURE · No genuine performance or AI accuracy"
            if source.mode == "synthetic"
            else f"Evidence mode: {source.mode}"
        )
        st.caption(safe_text(source.title))
    else:
        st.info(
            "No account dataset selected. Metrics remain unavailable. Synthetic demo records are a separate collection."
        )
    try:
        bundle: PolicyBundle | None = load_policy_bundle()
    except (ConfigLoadError, ValueError):
        bundle = None
    folder = (
        safe_path(collection_root, source.path + "/account.json", ".json").parent
        if source
        else None
    )
    account = account_record(folder, source) if folder is not None and source else None
    page = DecisionPage()
    trials, models = _evidence(root)
    if folder is not None and source is not None:
        path = safe_path(folder, "journal.sqlite", ".sqlite")
        filters: dict[str, Any] = {}
        if view == "Trades & Decisions":
            st.subheader("Trades & Decisions")
            a, b, c = st.columns(3)
            market = a.selectbox("Market", ["All", source.symbol])
            strategy = b.selectbox("Strategy", ["All", source.strategy])
            status = c.selectbox(
                "Decision status", ["All", "accepted", "rejected", "vetoed", "skipped"]
            )
            date_start = a.date_input("From date", value=None)
            date_end = b.date_input("Through date", value=None)
            filters = dict(
                symbol=None if market == "All" else market,
                strategy=None if strategy == "All" else strategy,
                status=None if status == "All" else status,
                date_from=datetime.combine(date_start, time.min, tzinfo=ZoneInfo(zone)).astimezone(
                    UTC
                )
                if date_start
                else None,
                date_to=datetime.combine(date_end, time.max, tzinfo=ZoneInfo(zone)).astimezone(UTC)
                if date_end
                else None,
            )
            signature = str((source.id, filters))
            if st.session_state.get("filter_signature") != signature:
                st.session_state.update(filter_signature=signature, cursor=None)
            filters["before"] = st.session_state.get("cursor")
        page = cached_page(str(path), file_stamp(path), source.mode, filters)
        for issue in page.issues:
            st.info(issue)
    if view == "Overview":
        st.subheader("Account overview")
        totals = (
            cached_totals(
                str(folder / "journal.sqlite"), file_stamp(folder / "journal.sqlite"), source.mode
            )
            if folder and source
            else LedgerTotals()
        )
        dd = (
            cached_drawdown(str(folder), source.mode, file_stamp(folder / "equity.parquet"))
            if folder and source
            else None
        )
        metrics = account_metrics(account, totals, dd)
        metric_grid(metrics, source.currency if source else "unavailable")
        if account:
            st.caption(
                "Snapshot as of "
                + display_time(account.as_of, zone)
                + " · Archived evidence; current account state unverified"
            )
        equity_chart(_chart(folder, "equity", source), zone)
        st.caption(
            "Drawdown uses the complete stored marked-equity export. Charts display at most 2,000 observations."
        )
        if source and account and trials is not None and models is not None:
            snapshot = DashboardSnapshot(
                mode=source.mode,
                generated_at=account.as_of,
                symbols=(source.symbol,),
                coverage_status="Synthetic fixture"
                if source.mode == "synthetic"
                else "Stored report export",
                empirical_strategy_trials=trials,
                trained_market_models=models,
                arena_status="offline_mock / unproven",
                news_status="runtime unavailable",
                net_equity=account.equity,
            )
            st.caption(
                f"Source mode: {snapshot.mode} · External routing: disabled · News: {snapshot.news_status}"
            )
        _implementation_status(root)
    elif view == "Markets & Strategies":
        _markets(bundle, source, folder, page, zone)
    elif view == "Trades & Decisions":
        decisions_table(page.rows, zone)
        left, right = st.columns(2)
        if left.button("Newest decisions"):
            st.session_state.cursor = None
            st.rerun()
        if right.button("Older decisions", disabled=page.next_cursor is None):
            st.session_state.cursor = page.next_cursor
            st.rerun()
        st.caption(
            "50 decisions per page. Decision/outcome IDs link the original journal evidence; account totals are independent of this page."
        )
    elif view == "Risk & System Health":
        _risk(bundle, folder, source)
    else:
        _ai(root, page, trials, models, folder)


if __name__ == "__main__":
    main()
