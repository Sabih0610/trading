"""Read-only projection of private venue operational metadata, never price observations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tb.ingest.venue_status import SYMBOLS, VenueBook, VenueObservation
from tb.research.registry import read_metadata


def venue_health_rows(root: Path, at: datetime | None = None) -> list[dict[str, Any]]:
    """Recompute freshness now; never trust a stored veto or use future receipt facts."""
    now = datetime.now(UTC) if at is None else at
    changes: dict[str, str | None] = {}
    observations = []
    try:
        value = read_metadata(
            root, "reports/data_quality/venue-status-health.json", base="reports/data_quality"
        )
        rows = value["symbols"]
        if not isinstance(rows, list) or len(rows) > 4:
            raise ValueError("venue_health_shape_refused")
        if len({row["symbol"] for row in rows}) != len(rows):
            raise ValueError("venue_health_duplicates_refused")
        for row in rows:
            if row["symbol"] not in SYMBOLS:
                raise ValueError("venue_health_scope_refused")
            changes[row["symbol"]] = row.get("last_change")
            if row.get("known_at") is not None:
                observations.append(
                    VenueObservation(
                        symbol=row["symbol"],
                        raw_status=row["raw_status"],
                        known_at=datetime.fromisoformat(row["known_at"]),
                        evidence=value["evidence"],
                    )
                )
    except (OSError, ValueError, KeyError, TypeError):
        observations, changes = [], {}
    book = VenueBook(observations=tuple(observations))
    return [
        {**book.venue_veto(symbol, now).model_dump(mode="json"), "last_change": changes.get(symbol)}
        for symbol in SYMBOLS
    ]


def venue_health_view(root: Path) -> None:
    """Show status and last change with no polling, entry or exit action in the UI."""
    import streamlit as st

    st.write("Live Spot venue status — entry veto only")
    st.dataframe(venue_health_rows(root), hide_index=True, width="stretch")
    st.caption(
        "Current metadata only; unavailable to historical backtests. Unknown/stale status blocks entries, never exits."
    )
