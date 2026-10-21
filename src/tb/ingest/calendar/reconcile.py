"""Deterministic cross-source calendar reconciliation."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from tb.ingest.calendar.models import CalendarEvent, make_event_id, normalize_event_name

OFFICIAL_SOURCE_PRIORITY = {
    "bls": 0,
    "bea": 1,
    "federal_reserve": 2,
    "eia": 3,
    "ecb": 4,
}


def _group_key(event: CalendarEvent) -> tuple[str, str, str, str]:
    return (
        normalize_event_name(event.name),
        event.country,
        event.currency,
        event.scheduled_utc.astimezone(UTC).date().isoformat(),
    )


def _rank(event: CalendarEvent) -> tuple[int, str, datetime]:
    return (
        OFFICIAL_SOURCE_PRIORITY.get(event.source, 100),
        event.source,
        event.fetched_at,
    )


def _first_value(events: list[CalendarEvent], field: str) -> str | None:
    for event in events:
        value = getattr(event, field)
        if isinstance(value, str) and value:
            return value
    return None


def reconcile_events(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """Merge equivalent events, flag time disagreements, and prefer official schedules."""

    groups: dict[tuple[str, str, str, str], list[CalendarEvent]] = defaultdict(list)
    for event in events:
        groups[_group_key(event)].append(event)

    reconciled: list[CalendarEvent] = []
    for group in groups.values():
        ordered = sorted(group, key=_rank)
        winner = ordered[0]
        times = tuple(sorted({event.scheduled_utc.astimezone(UTC) for event in ordered}))
        aliases = tuple(sorted({event.source for event in ordered}))
        reconciled.append(
            winner.model_copy(
                update={
                    "event_id": make_event_id(
                        winner.name,
                        winner.country,
                        winner.currency,
                        winner.scheduled_utc,
                    ),
                    "actual": _first_value(ordered, "actual"),
                    "forecast": _first_value(ordered, "forecast"),
                    "previous": _first_value(ordered, "previous"),
                    "source_aliases": aliases,
                    "time_conflict": len(times) > 1,
                    "conflicting_times_utc": times if len(times) > 1 else (),
                }
            )
        )
    return sorted(reconciled, key=lambda item: (item.scheduled_utc, item.event_id))
