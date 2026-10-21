"""Immutable content snapshots and explicit coverage reports."""

from datetime import UTC, date, datetime
from pathlib import Path

from tb.ingest.calendar.models import build_calendar_event
from tb.ingest.content_store import (
    SnapshotStatus,
    commit_calendar_snapshot,
    store_raw_payload,
)
from tb.ingest.coverage import calendar_coverage
from tb.ingest.history.validation import validate_bronze


def _event(month: int, source: str = "bls"):
    return build_calendar_event(
        name="US CPI",
        country="US",
        currency="USD",
        importance="high",
        scheduled_utc=datetime(2026, month, 10, 12, 30, tzinfo=UTC),
        source=source,
        source_url="https://example.test/calendar",
        fetched_at=datetime(2026, 10, 21, tzinfo=UTC),
    )


def test_raw_and_normalized_snapshots_are_content_addressed_and_resumable(
    tmp_path: Path,
) -> None:
    payload = b"source payload"
    fetched = datetime(2026, 10, 21, tzinfo=UTC)
    first_raw = store_raw_payload(
        tmp_path,
        dataset="calendar",
        source="bls",
        payload=payload,
        fetched_at=fetched,
        extension="html",
    )
    second_raw = store_raw_payload(
        tmp_path,
        dataset="calendar",
        source="bls",
        payload=payload,
        fetched_at=fetched,
        extension="html",
    )
    first = commit_calendar_snapshot(
        tmp_path,
        source="bls",
        source_url="https://example.test/calendar",
        source_payload=payload,
        events=[_event(10)],
        code_version="test",
        resume=True,
    )
    second = commit_calendar_snapshot(
        tmp_path,
        source="bls",
        source_url="https://example.test/calendar",
        source_payload=payload,
        events=[_event(10)],
        code_version="test",
        resume=True,
    )

    assert first_raw == second_raw
    assert (first, second) == (SnapshotStatus.WRITTEN, SnapshotStatus.SKIPPED)
    assert validate_bronze(tmp_path).ok


def test_coverage_reports_empty_months_and_source_mix() -> None:
    report = calendar_coverage([_event(1), _event(3, "ecb")], date(2026, 1, 1), date(2026, 3, 31))

    assert report.total == 2
    assert report.missing_months == ("2026-02",)
    assert report.source_mix == {"bls": 1, "ecb": 1}


def test_snapshot_accepts_late_non_null_value_after_many_nulls(tmp_path: Path) -> None:
    events = [
        _event(month=(index % 12) + 1).model_copy(
            update={
                "event_id": f"{index:064x}",
                "name": f"Event {index}",
                "actual": "1.0" if index == 119 else None,
            }
        )
        for index in range(120)
    ]

    status = commit_calendar_snapshot(
        tmp_path,
        source="bls",
        source_url="https://example.test/calendar",
        source_payload=b"many events",
        events=events,
        code_version="test",
        resume=True,
    )

    assert status is SnapshotStatus.WRITTEN
