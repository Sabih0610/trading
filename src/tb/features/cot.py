"""COT Index (positioning stochastic) for COMEX gold; causal by construction (P12e).

Method credited to tradermonty/claude-trading-skills `cot-contrarian-detector` (MIT, commit
84fa61270e75a6d99d6eba1f2ccee12bc876e30e): index = (net - window min) / (window max - window min) * 100
over the last N weekly reports including the current one; undefined (None) with short history or a
flat window. Reimplemented here on free CFTC files; no code copied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import polars as pl

from tb.research.models import ResearchRefused

VERSION = "cot-index-1.0.0"
Category = Literal["noncommercial", "managed_money", "nonreportable"]
NET: dict[Category, tuple[str, str]] = {
    "noncommercial": ("noncomm_long", "noncomm_short"),
    "managed_money": ("mm_long", "mm_short"),
    "nonreportable": ("nonrept_long", "nonrept_short"),
}


def cot_index(values: list[int], lookback: int) -> float | None:
    """Index of the LAST value against the last ``lookback`` values (inclusive)."""
    if lookback < 2:
        raise ResearchRefused("cot_lookback_too_short")
    if len(values) < lookback:
        return None
    window = values[-lookback:]
    low, high = min(window), max(window)
    if high == low:
        return None
    return (window[-1] - low) / (high - low) * 100.0


@dataclass(frozen=True)
class CotReading:
    report_date: date
    known_at: datetime
    index: float | None
    net: int
    open_interest: int


def readings(silver: pl.DataFrame, category: Category, lookback: int) -> list[CotReading]:
    """One reading per weekly report, each computed only from that report and earlier ones."""
    long_col, short_col = NET[category]
    frame = silver.sort("report_date")
    if frame["report_date"].n_unique() != frame.height:
        raise ResearchRefused("cot_duplicate_report_date")
    nets: list[int] = []
    out: list[CotReading] = []
    for row in frame.iter_rows(named=True):
        nets.append(int(row[long_col]) - int(row[short_col]))
        out.append(
            CotReading(
                row["report_date"],
                row["known_at"],
                cot_index(nets, lookback),
                nets[-1],
                int(row["open_interest"]),
            )
        )
    return out


def reading_at(series: list[CotReading], t: datetime) -> CotReading | None:
    """Latest reading already public at ``t``; never a later report."""
    if t.tzinfo is None:
        raise ResearchRefused("cot_naive_clock_refused")
    known = [r for r in series if r.known_at <= t]
    return known[-1] if known else None
