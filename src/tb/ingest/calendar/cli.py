"""PowerShell-friendly orchestration for permitted economic-calendar sources."""

from __future__ import annotations

import argparse
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from tb.core.config import repo_root
from tb.core.timeutil import utc_now
from tb.ingest.calendar.adapters import (
    parse_bls_schedule,
    parse_ecb_webcasts,
    parse_finance_calendar,
)
from tb.ingest.calendar.models import CalendarEvent
from tb.ingest.calendar.reconcile import reconcile_events
from tb.ingest.content_store import commit_calendar_snapshot, store_raw_payload
from tb.ingest.coverage import calendar_coverage
from tb.ingest.history.core import HistoryError, atomic_write_json
from tb.ingest.http_cache import cached_download

BLS_URL = "https://www.bls.gov/schedule/{year}/home.htm"
ECB_URL = "https://www.ecb.europa.eu/press/tvservices/webcast/html/index.en.html"
FINANCE_CALENDAR_URL = "https://www.financecalendar.com/wp-json/fc/v1/calendar"
ALLOWED_SOURCES = frozenset({"bls", "ecb", "finance_calendar"})


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


def _parse_sources(value: str) -> frozenset[str]:
    selected = frozenset(part.strip().casefold() for part in value.split(",") if part.strip())
    unknown = selected - ALLOWED_SOURCES
    if not selected:
        raise ValueError("At least one calendar source is required")
    if unknown:
        raise ValueError(f"Unsupported calendar sources: {', '.join(sorted(unknown))}")
    return selected


def _code_version() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root(),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _in_range(event: CalendarEvent, start: date, end: date) -> bool:
    return start <= event.scheduled_utc.date() <= end


def _finance_url(start: date, end: date) -> str:
    return str(
        httpx.URL(
            FINANCE_CALENDAR_URL,
            params={
                "from": start.isoformat(),
                "to": end.isoformat(),
                "impact": "high",
                "tz": "UTC",
                "limit": 500,
            },
        )
    )


def _source_snapshot(
    destination: Path,
    *,
    source: str,
    urls: list[str],
    payloads: list[bytes],
    events: list[CalendarEvent],
    version: str,
    resume: bool,
) -> list[CalendarEvent]:
    reconciled = reconcile_events(events)
    if reconciled:
        status = commit_calendar_snapshot(
            destination,
            source=source,
            source_url=" | ".join(urls),
            source_payload=b"".join(payloads),
            events=reconciled,
            code_version=version,
            resume=resume,
        )
        print(f"Calendar {source}: {status.value} ({len(reconciled)} events)")
    return reconciled


def run_calendar_download(
    *,
    sources: str,
    from_value: str,
    to_value: str,
    resume: bool,
    bronze_root: Path | None,
    client: httpx.Client | None = None,
) -> None:
    """Download, normalize, reconcile, store, and report selected calendar sources."""

    selected = _parse_sources(sources)
    start = _parse_date(from_value, "--from")
    end = _parse_date(to_value, "--to")
    if end < start:
        raise ValueError("Calendar end cannot precede start")
    if end > datetime.now(UTC).date() + timedelta(days=400):
        raise ValueError("Calendar end is beyond the supported 400-day forward horizon")
    destination = repo_root() / "data" / "bronze" if bronze_root is None else bronze_root.resolve()
    cache_root = repo_root() / ".cache" / "p03-calendar"
    fetched_at = utc_now()
    version = _code_version()
    owned_client = client is None
    active_client = (
        httpx.Client(
            headers={"User-Agent": "trading-bot-research/0.1 (calendar metadata)"},
            follow_redirects=False,
        )
        if client is None
        else client
    )
    all_events: list[CalendarEvent] = []
    all_payloads: list[bytes] = []
    all_urls: list[str] = []
    failures: list[str] = []
    try:
        if "bls" in selected:
            events: list[CalendarEvent] = []
            payloads: list[bytes] = []
            urls: list[str] = []
            for year in range(start.year, end.year + 1):
                url = BLS_URL.format(year=year)
                try:
                    response = cached_download(
                        active_client,
                        url,
                        cache_root,
                        resume=resume,
                        max_age_seconds=None if year < datetime.now(UTC).year else 86_400,
                    )
                    store_raw_payload(
                        destination,
                        dataset="calendar",
                        source="bls",
                        payload=response.payload,
                        fetched_at=fetched_at,
                        extension="html",
                    )
                    events.extend(
                        event
                        for event in parse_bls_schedule(
                            response.payload,
                            year=year,
                            source_url=url,
                            fetched_at=fetched_at,
                        )
                        if _in_range(event, start, end)
                    )
                    payloads.append(response.payload)
                    urls.append(url)
                except (HistoryError, ValueError) as exc:
                    failures.append(f"bls {year}: {exc}")
            source_events = _source_snapshot(
                destination,
                source="bls",
                urls=urls,
                payloads=payloads,
                events=events,
                version=version,
                resume=resume,
            )
            all_events.extend(source_events)
            all_payloads.extend(payloads)
            all_urls.extend(urls)
        if "ecb" in selected:
            try:
                response = cached_download(
                    active_client,
                    ECB_URL,
                    cache_root,
                    resume=resume,
                    max_age_seconds=86_400,
                )
                store_raw_payload(
                    destination,
                    dataset="calendar",
                    source="ecb",
                    payload=response.payload,
                    fetched_at=fetched_at,
                    extension="html",
                )
                events = [
                    event
                    for event in parse_ecb_webcasts(
                        response.payload,
                        source_url=ECB_URL,
                        fetched_at=fetched_at,
                        start_year=start.year,
                    )
                    if _in_range(event, start, end)
                ]
                source_events = _source_snapshot(
                    destination,
                    source="ecb",
                    urls=[ECB_URL],
                    payloads=[response.payload],
                    events=events,
                    version=version,
                    resume=resume,
                )
                all_events.extend(source_events)
                all_payloads.append(response.payload)
                all_urls.append(ECB_URL)
            except (HistoryError, ValueError) as exc:
                failures.append(f"ecb: {exc}")
        if "finance_calendar" in selected:
            events = []
            payloads = []
            urls = []
            cursor = start
            while cursor <= end:
                chunk_end = min(end, cursor + timedelta(days=91))
                url = _finance_url(cursor, chunk_end)
                try:
                    response = cached_download(
                        active_client,
                        url,
                        cache_root,
                        resume=resume,
                        max_age_seconds=3_600,
                    )
                    store_raw_payload(
                        destination,
                        dataset="calendar",
                        source="finance_calendar",
                        payload=response.payload,
                        fetched_at=fetched_at,
                        extension="json",
                    )
                    events.extend(
                        event
                        for event in parse_finance_calendar(
                            response.payload,
                            fetched_at=fetched_at,
                        )
                        if _in_range(event, start, end)
                    )
                    payloads.append(response.payload)
                    urls.append(url)
                except (HistoryError, ValueError) as exc:
                    failures.append(f"finance_calendar {cursor}/{chunk_end}: {exc}")
                cursor = chunk_end + timedelta(days=1)
            source_events = _source_snapshot(
                destination,
                source="finance_calendar",
                urls=urls,
                payloads=payloads,
                events=events,
                version=version,
                resume=resume,
            )
            all_events.extend(source_events)
            all_payloads.extend(payloads)
            all_urls.extend(urls)
    finally:
        if owned_client:
            active_client.close()

    reconciled = reconcile_events(all_events)
    if not reconciled:
        detail = "; ".join(failures) or "selected sources returned no events"
        raise ValueError(f"Calendar download produced no events: {detail}")
    commit_calendar_snapshot(
        destination,
        source="reconciled",
        source_url=" | ".join(all_urls),
        source_payload=b"".join(all_payloads),
        events=reconciled,
        code_version=version,
        resume=resume,
    )
    report = calendar_coverage(reconciled, start, end)
    report_path = repo_root() / "reports" / "data-quality" / "P03-calendar-coverage.json"
    atomic_write_json(report_path, report)
    print(
        f"Calendar coverage: {report.total} events; "
        f"{len(report.missing_months)} missing months; report={report_path}"
    )
    for failure in failures:
        print(f"Calendar source warning: {failure}")


def main() -> None:
    """Parse command arguments and run calendar ingestion."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--from", dest="from_value", required=True)
    parser.add_argument("--to", dest="to_value", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--bronze-root", type=Path)
    arguments = parser.parse_args()
    try:
        run_calendar_download(
            sources=arguments.sources,
            from_value=arguments.from_value,
            to_value=arguments.to_value,
            resume=arguments.resume,
            bronze_root=arguments.bronze_root,
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
