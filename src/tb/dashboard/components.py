"""Reusable read-only metric, chart and decision-table presentation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

import streamlit as st

from tb.dashboard.models import AccountMetrics, DecisionView, display_time


def amount(value: Decimal | int | None, *, suffix: str = "") -> str:
    """Format values with explicit missingness and a separate currency/percent suffix."""

    return "Unavailable" if value is None else f"{value:,.2f}{suffix}"


def _domain(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    padding = max((high - low) * 0.1, abs(low) * 0.0001, 0.000001)
    return [low - padding, high + padding]


def metric_grid(metrics: AccountMetrics, currency: str) -> None:
    """Render account metrics without combining accounts or currencies."""

    values: list[tuple[str, Decimal | None, str]] = [
        ("Account equity", metrics.equity, ""),
        ("Available capital", metrics.cash, ""),
        ("Realized P&L", metrics.realized_pnl, ""),
        ("Unrealized P&L", metrics.unrealized_pnl, ""),
        ("Net return", metrics.return_pct, "%"),
        ("Win rate", metrics.win_rate_pct, "%"),
        ("Profit factor", metrics.profit_factor, ""),
        ("Maximum drawdown", metrics.max_drawdown_pct, "%"),
    ]
    for offset in (0, 4):
        for column, (label, value, suffix) in zip(
            st.columns(4), values[offset : offset + 4], strict=True
        ):
            column.metric(label, amount(value, suffix=suffix))
    st.caption(
        f"Account currency: {currency} · Closed trades: {metrics.trade_count if metrics.trade_count is not None else 'unavailable'}"
    )
    if metrics.issue:
        st.warning(metrics.issue)
    if metrics.profit_factor is None:
        st.caption("Profit factor is unavailable when losses or complete outcomes are absent.")


def price_chart(
    prices: list[dict[str, Any]],
    decisions: tuple[DecisionView, ...],
    zone: Literal["UTC", "Asia/Karachi"],
) -> None:
    """Show stored prices and separately timed strategy/fill/outcome markers."""

    if not prices:
        st.info("Price observations unavailable for this instrument.")
        return
    values: list[dict[str, Any]] = [
        {"time": display_time(r["timestamp"], zone), "value": float(r["price"]), "kind": "Price"}
        for r in prices
    ]
    for row in decisions:
        for instant, value, kind in (
            (row.timestamp, row.entry, "Signal"),
            (row.fill_time, row.fill, "Entry"),
            (row.exit_time, row.exit, "Exit"),
        ):
            if instant is not None and value is not None:
                values.append(dict(time=display_time(instant, zone), value=float(value), kind=kind))
    st.vega_lite_chart(
        values,
        dict(
            height=300,
            encoding=dict(
                x=dict(
                    field="time",
                    type="ordinal",
                    sort="ascending",
                    title=f"Time · {zone}",
                    axis=dict(labelAngle=-30, labelOverlap=True),
                ),
                y=dict(
                    field="value",
                    type="quantitative",
                    title="Stored price",
                    scale=dict(zero=False, domain=_domain([r["value"] for r in values])),
                ),
            ),
            layer=[
                dict(
                    transform=[dict(filter="datum.kind === 'Price'")],
                    mark=dict(type="line", color="#176B60", strokeWidth=2),
                ),
                dict(
                    transform=[dict(filter="datum.kind !== 'Price'")],
                    mark=dict(type="point", filled=True, size=100),
                    encoding=dict(
                        color=dict(
                            field="kind",
                            type="nominal",
                            scale=dict(
                                domain=["Signal", "Entry", "Exit"],
                                range=["#52657A", "#23835A", "#B65339"],
                            ),
                        ),
                        tooltip=[dict(field="kind"), dict(field="time"), dict(field="value")],
                    ),
                ),
            ],
        ),
        width="stretch",
    )


def equity_chart(rows: list[dict[str, Any]], zone: Literal["UTC", "Asia/Karachi"]) -> None:
    """Draw only stored marked equity; no invented intermediate account path."""

    if not rows:
        st.info(
            "Marked equity history unavailable. Ending balances do not establish intratrade drawdown."
        )
        return
    st.vega_lite_chart(
        [dict(time=display_time(r["timestamp"], zone), equity=float(r["equity"])) for r in rows],
        dict(
            height=260,
            mark=dict(type="line", color="#176B60", point=True),
            encoding=dict(
                x=dict(
                    field="time",
                    type="ordinal",
                    sort="ascending",
                    title=f"Time · {zone}",
                    axis=dict(labelOverlap=True, labelAngle=-30),
                ),
                y=dict(
                    field="equity",
                    type="quantitative",
                    scale=dict(zero=False, domain=_domain([float(r["equity"]) for r in rows])),
                    title="Marked account equity",
                ),
                tooltip=[dict(field="time"), dict(field="equity")],
            ),
        ),
        width="stretch",
    )


def decisions_table(rows: tuple[DecisionView, ...], zone: Literal["UTC", "Asia/Karachi"]) -> None:
    """Display a fixed, masked projection including links between decisions and outcomes."""

    if not rows:
        st.info("No matching decisions in this dataset.")
        return
    records = []
    for row in rows:
        record = row.model_dump(exclude={"rowid", "timestamp", "fill_time", "exit_time"})
        record.update(
            timestamp=display_time(row.timestamp, zone),
            fill_time=display_time(row.fill_time, zone),
            exit_time=display_time(row.exit_time, zone),
        )
        records.append(
            {
                name: str(value) if isinstance(value, Decimal) else value
                for name, value in record.items()
            }
        )
    st.dataframe(records, hide_index=True, width="stretch")
