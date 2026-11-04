"""Read-only data health from JSON metadata; never opens Parquet, ZIPs or price rows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import streamlit as st

from tb.research.registry import read_metadata, safe

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSD", "EURUSD")
PROVIDERS = ("binance_vision", "histdata", "dukascopy")


def health_rows(root: Path) -> list[dict[str, Any]]:
    """Bound the historical view to pre-holdout symbol-years and handle incomplete metadata."""
    rows: list[dict[str, Any]] = []
    paths = [
        (provider, path)
        for provider in PROVIDERS
        for path in sorted(safe(root, f"data/manifests/{provider}").glob("*/*.json"))
    ]
    for provider, path in paths:
        base = f"data/manifests/{provider}"
        match = re.fullmatch(r"(BTCUSDT|ETHUSDT|SOLUSDT|XAUUSD|EURUSD)-(202[0-4])", path.stem)
        if not match:
            continue
        symbol, year_text = match.groups()
        item: dict[str, Any] = {
            "symbol": symbol,
            "year": int(year_text),
            "dataset_id": path.parent.name,
            "source": provider,
        }
        try:
            manifest = read_metadata(root, path.relative_to(root).as_posix(), base=base)
            if (
                manifest["symbol"] != symbol
                or manifest["year"] != int(year_text)
                or manifest["dataset_id"] != path.parent.name
                or manifest.get("source", provider) != provider
                or (symbol in {"XAUUSD", "EURUSD"} and provider == "binance_vision")
                or (symbol not in {"XAUUSD", "EURUSD"} and provider != "binance_vision")
            ):
                raise ValueError("metadata identity mismatch")
            item.update(
                {
                    "manifest_status": manifest["status"],
                    "price_side": manifest.get("price_side", "trade"),
                    "terms_version": manifest["terms_version"],
                    "last_refresh": manifest["last_refresh"],
                    "quality_score": None,
                    "flags": ["quality report missing or stale"],
                    "gap_heat_strip": [],
                }
            )
            try:
                report = read_metadata(
                    root,
                    manifest.get("quality_path", f"reports/data_quality/{symbol}-{year_text}.json"),
                    base="reports/data_quality",
                )
                if (
                    report["generation"] != manifest["generation"]
                    or report["dataset_id"] != manifest["dataset_id"]
                ):
                    raise ValueError("stale report")
                score = report["quality_score"]
                if not isinstance(score, int | float) or not 0 <= score <= 100:
                    raise ValueError("invalid score")
                item.update(
                    {
                        "quality_score": score,
                        "flags": report["flags"],
                        "gap_heat_strip": report["gap_heat_strip"],
                    }
                )
            except (ValueError, OSError, KeyError):
                pass
        except (ValueError, OSError, KeyError):
            item.update(
                {
                    "manifest_status": "invalid",
                    "quality_score": None,
                    "flags": ["manifest unavailable or invalid"],
                    "gap_heat_strip": [],
                }
            )
        rows.append(item)
    present = {(row["symbol"], row["year"]) for row in rows}
    for symbol in SYMBOLS:
        for year in range(2020, 2025):
            if (symbol, year) not in present:
                rows.append(
                    {
                        "symbol": symbol,
                        "year": year,
                        "manifest_status": "missing",
                        "quality_score": None,
                        "flags": ["no admitted dataset"],
                        "gap_heat_strip": [],
                    }
                )
    return sorted(rows, key=lambda row: (row["symbol"], row["year"]))


def data_health_view(root: Path) -> None:
    """Display metadata evidence without exposing any market data or mutation control."""
    st.subheader("Data Health")
    from tb.dashboard.yields import treasury_health_view

    treasury_health_view(root)
    st.caption("Manifest and quality metadata only · Historical scope ends 2024-12-31 UTC")
    st.write("Sealed XAUT collector health", collector_health(root))
    from tb.dashboard.venue_status import venue_health_view

    venue_health_view(root)
    rows = health_rows(root)
    st.dataframe(
        [{k: v for k, v in row.items() if k != "gap_heat_strip"} for row in rows],
        hide_index=True,
        width="stretch",
    )
    if not any(row["manifest_status"] == "complete" for row in rows):
        st.info(
            "BLOCKED — DATASET NOT AUTHORIZED. No admitted historical price dataset is available in the collection below."
        )
    for row in rows:
        months = row["gap_heat_strip"]
        if months:
            # Explicit missing/expected fractions; solid squares show months with gaps.
            strip = " ".join(
                f"{month['month']:02d}:{'■' if month['missing'] else '□'}" for month in months
            )
            st.text(f"{row['symbol']} {row['year']}  {strip}")
    st.caption(
        "■ gaps present · □ complete month. Metadata does not establish strategy profitability or current data rights."
    )


def collector_health(root: Path) -> dict[str, Any]:
    """Project an exact operational allowlist; never open a sealed file or expose market fields."""
    allowed = {
        "collector_start",
        "heartbeat",
        "uptime_seconds",
        "sequence_gap_count",
        "reconnects",
        "file_sizes",
        "files_by_utc_hour",
        "flush_interval_seconds",
        "connected",
        "last_error_category",
    }
    try:
        value = read_metadata(
            root, "reports/data_quality/xaut-collector-health.json", base="reports/data_quality"
        )
        return {key: value[key] for key in allowed if key in value}
    except (ValueError, OSError):
        return {"status": "collector health unavailable"}
