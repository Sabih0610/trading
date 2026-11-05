"""JSON-only coverage health for the separate daily/weekly derivations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import streamlit as st

from tb.research.registry import read_metadata, safe
from tb.silver.swing_source import swing_scope


def swing_health_rows(root: Path) -> list[dict[str, Any]]:
    """Read bounded manifests only, never source or derived market rows."""
    rows: list[dict[str, Any]] = []
    base = "data/manifests/swing-v1"
    for path in sorted(safe(root, base).glob("*/*/*.json")):
        match = re.fullmatch(r"(BTCUSDT|ETHUSDT|SOLUSDT|PAXGUSDT|XAUUSD)-(202[0-4])", path.stem)
        if match is None:
            continue
        symbol, year_text = match.groups()
        year, dataset_id, provider = int(year_text), path.parent.name, path.parent.parent.name
        try:
            scope = swing_scope(dataset_id, symbol)
            if year not in scope.years or provider != scope.provider:
                continue
            item = read_metadata(root, path.relative_to(root).as_posix(), base=base)
            if (
                item.get("version") != "swing-medallion-v1"
                or item.get("status") != "complete"
                or item.get("dataset_id") != dataset_id
                or item.get("symbol") != symbol
                or item.get("year") != year
                or item.get("source") != provider
                or item.get("price_side") != scope.price_side
                or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("generation", "")))
                or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("calendar_identity", "")))
            ):
                raise ValueError("Daily/weekly manifest identity mismatch")
            if set(item.get("outputs", {})) != {"gold/1d", "gold/1w"}:
                raise ValueError("Daily/weekly outputs missing")
            current: list[dict[str, Any]] = []
            for timeframe in ("1d", "1w"):
                output = item["outputs"][f"gold/{timeframe}"]
                counts = {
                    key: output[key]
                    for key in (
                        "rows",
                        "complete_bars",
                        "incomplete_open_bars",
                        "closed_windows",
                        "calendar_conflict_bars",
                        "observed_minutes",
                        "observed_expected_minutes",
                        "expected_minutes",
                    )
                }
                if any(type(value) is not int or value < 0 for value in counts.values()):
                    raise ValueError("Daily/weekly coverage count invalid")
                if (
                    counts["observed_expected_minutes"] > counts["expected_minutes"]
                    or counts["observed_expected_minutes"] > counts["observed_minutes"]
                    or counts["complete_bars"]
                    + counts["incomplete_open_bars"]
                    + counts["closed_windows"]
                    != counts["rows"]
                    or counts["calendar_conflict_bars"] > counts["rows"]
                ):
                    raise ValueError("Daily/weekly coverage counters inconsistent")
                current.append(
                    {
                        "symbol": symbol,
                        "year": year,
                        "timeframe": timeframe,
                        "source": provider,
                        "price_side": scope.price_side,
                        "dataset_id": dataset_id,
                        "manifest_status": "complete",
                        **counts,
                        "coverage_ratio": counts["observed_expected_minutes"]
                        / counts["expected_minutes"]
                        if counts["expected_minutes"]
                        else None,
                        "calendar_is_reference_model": item["calendar_is_reference_model"],
                        "calendar_identity": item["calendar_identity"],
                        "last_refresh": item["last_refresh"],
                    }
                )
            rows.extend(current)
        except (ValueError, OSError, KeyError, TypeError):
            rows.append(
                {
                    "symbol": symbol,
                    "year": year,
                    "dataset_id": dataset_id,
                    "manifest_status": "invalid",
                    "source": provider,
                    "flags": ["daily/weekly metadata unavailable or invalid"],
                }
            )
    return rows


def swing_health_view(root: Path) -> None:
    """Display coverage and source provenance without reading prices or invoking a build."""
    st.subheader("Daily / weekly coverage")
    rows = swing_health_rows(root)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("No admitted daily/weekly derivation metadata is available.")
    st.caption(
        "UTC days / Monday weeks; complete at 95% expected-minute coverage. "
        "Closed windows are not fabricated price bars. HistData closures are a declared "
        "reference model; conflicts remain incomplete. Metadata is not research admission."
    )
