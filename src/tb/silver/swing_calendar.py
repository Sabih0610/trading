"""Frozen calendar policy loader; source timestamps keep the approved HistData clock."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tb.ingest.history.core import sha256_file
from tb.research.models import ResearchRefused
from tb.silver.swing import COVERAGE_THRESHOLD, CalendarClosure, SwingCalendar


def load_swing_calendar(symbol: str, *, path: Path | None = None) -> tuple[SwingCalendar, str]:
    """Admit a fixed pre-data reference policy, or the explicit 24/7 source contract."""
    if symbol != "XAUUSD":
        calendar = SwingCalendar(symbol, "binance_vision", "trade", "continuous-24x7-v1")
        return calendar, calendar.identity
    policy_path = path or Path(__file__).resolve().parents[3] / "config/swing-calendar.json"
    if policy_path.is_symlink() or not policy_path.is_file() or policy_path.stat().st_size > 65536:
        raise ResearchRefused("swing_calendar_policy_missing_or_invalid")
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("calendar_id") != "histdata-xau-reference-closures-v1"
        or payload.get("symbol") != "XAUUSD"
        or payload.get("source") != "histdata"
        or payload.get("price_side") != "bid"
        or payload.get("reference_only") is not True
        or payload.get("reference_timezone") != "America/New_York"
        or payload.get("coverage_threshold") != COVERAGE_THRESHOLD
        or not isinstance(payload.get("closures"), list)
        or not payload["closures"]
    ):
        raise ResearchRefused("swing_calendar_policy_identity_changed")
    closures = []
    previous: datetime | None = None
    zone = ZoneInfo("America/New_York")
    for row in payload["closures"]:
        holiday = date.fromisoformat(row["reference_date"])
        left = datetime.combine(holiday - timedelta(days=1), time(17), zone).astimezone(UTC)
        right = datetime.combine(holiday, time(18), zone).astimezone(UTC)
        start, stop = datetime.fromisoformat(row["start"]), datetime.fromisoformat(row["stop"])
        if (
            start != left
            or stop != right
            or not 2021 <= holiday.year <= 2024
            or (previous is not None and start < previous)
        ):
            raise ResearchRefused("swing_calendar_policy_conversion_changed")
        closures.append(CalendarClosure(start, stop, row["evidence"], row["label"]))
        previous = stop
    return (
        SwingCalendar("XAUUSD", "histdata", "bid", payload["calendar_id"], tuple(closures), True),
        sha256_file(policy_path),
    )
