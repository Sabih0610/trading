"""PowerShell-friendly orchestration for permitted headline metadata feeds."""

from __future__ import annotations

import argparse
import subprocess
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from tb.core.config import features_enabled, load_settings, repo_root
from tb.core.timeutil import utc_now
from tb.ingest.content_store import commit_news_snapshot, store_raw_payload
from tb.ingest.coverage import news_coverage
from tb.ingest.history.core import HistoryError, atomic_write_json
from tb.ingest.http_cache import cached_download
from tb.ingest.news.adapters import parse_gdelt_doc, parse_rss
from tb.ingest.news.models import NewsItem, deduplicate_news

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = (
    '(gold OR bullion OR inflation OR "Federal Reserve" OR bitcoin OR ethereum OR solana OR oil)'
)
RSS_FEEDS = {
    "federal_reserve": "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "ecb": "https://www.ecb.europa.eu/rss/press.html",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss",
    "cointelegraph": "https://cointelegraph.com/rss",
    "decrypt": "https://decrypt.co/feed",
}
KEYED_SOURCES = frozenset({"finnhub", "cryptopanic", "newsdata"})
ALLOWED_SOURCES = frozenset({"gdelt", *RSS_FEEDS, *KEYED_SOURCES})


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


def _parse_sources(value: str) -> frozenset[str]:
    selected = frozenset(part.strip().casefold() for part in value.split(",") if part.strip())
    unknown = selected - ALLOWED_SOURCES
    if not selected:
        raise ValueError("At least one news source is required")
    if unknown:
        raise ValueError(f"Unsupported news sources: {', '.join(sorted(unknown))}")
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


def gdelt_url(day: date) -> str:
    """Build one UTC-day GDELT DOC article-list query."""

    next_day = day + timedelta(days=1)
    return str(
        httpx.URL(
            GDELT_URL,
            params={
                "query": GDELT_QUERY,
                "mode": "artlist",
                "format": "json",
                "maxrecords": 250,
                "sort": "datedesc",
                "startdatetime": f"{day:%Y%m%d}000000",
                "enddatetime": f"{next_day:%Y%m%d}000000",
            },
        )
    )


def _in_range(item: NewsItem, start: date, end: date) -> bool:
    return start <= item.published_utc.date() <= end


def _commit_source_items(
    destination: Path,
    *,
    source: str,
    source_url: str,
    payload: bytes,
    items: list[NewsItem],
    version: str,
    resume: bool,
) -> list[NewsItem]:
    unique = deduplicate_news(items)
    if unique:
        status = commit_news_snapshot(
            destination,
            source=source,
            source_url=source_url,
            source_payload=payload,
            items=unique,
            code_version=version,
            resume=resume,
        )
        print(f"News {source}: {status.value} ({len(unique)} headlines)")
    return unique


def _report_keyed_sources(selected: frozenset[str]) -> None:
    enabled = features_enabled(load_settings())
    for source in selected & KEYED_SOURCES:
        if enabled[source]:
            print(f"News {source}: configured but adapter is deferred; no request made")
        else:
            print(f"News {source}: disabled_missing_key")


def run_news_download(
    *,
    sources: str,
    from_value: str,
    to_value: str,
    resume: bool,
    bronze_root: Path | None,
    client: httpx.Client | None = None,
    pause: Callable[[float], None] = time.sleep,
) -> None:
    """Download, deduplicate, store, and report headline metadata."""

    selected = _parse_sources(sources)
    _report_keyed_sources(selected)
    selected = selected - KEYED_SOURCES
    if not selected:
        return
    start = _parse_date(from_value, "--from")
    end = _parse_date(to_value, "--to")
    today = datetime.now(UTC).date()
    if end < start:
        raise ValueError("News end cannot precede start")
    if end > today:
        raise ValueError("News end cannot be in the future")
    destination = repo_root() / "data" / "bronze" if bronze_root is None else bronze_root.resolve()
    cache_root = repo_root() / ".cache" / "p03-news"
    fetched_at = utc_now()
    version = _code_version()
    owned_client = client is None
    active_client = (
        httpx.Client(
            headers={"User-Agent": "trading-bot-research/0.1 (headline metadata)"},
            follow_redirects=False,
        )
        if client is None
        else client
    )
    all_items: list[NewsItem] = []
    failures: list[str] = []
    source_urls: set[str] = set()
    try:
        if "gdelt" in selected:
            cursor = start
            while cursor <= end:
                url = gdelt_url(cursor)
                should_pause = True
                try:
                    response = cached_download(
                        active_client,
                        url,
                        cache_root,
                        resume=resume,
                        max_age_seconds=None if cursor < today else 900,
                    )
                    should_pause = not response.from_cache
                    store_raw_payload(
                        destination,
                        dataset="news",
                        source="gdelt",
                        payload=response.payload,
                        fetched_at=fetched_at,
                        extension="json",
                    )
                    parsed = [
                        item
                        for item in parse_gdelt_doc(response.payload, fetched_at=fetched_at)
                        if _in_range(item, start, end)
                    ]
                    all_items.extend(
                        _commit_source_items(
                            destination,
                            source="gdelt",
                            source_url=url,
                            payload=response.payload,
                            items=parsed,
                            version=version,
                            resume=resume,
                        )
                    )
                    if len(parsed) >= 250:
                        failures.append(
                            f"gdelt {cursor}: result cap reached; coverage is saturated"
                        )
                    source_urls.add(GDELT_URL)
                except (HistoryError, ValueError) as exc:
                    failures.append(f"gdelt {cursor}: {exc}")
                if cursor < end and should_pause:
                    pause(5.0)
                cursor += timedelta(days=1)
        for source in sorted(selected & RSS_FEEDS.keys()):
            url = RSS_FEEDS[source]
            try:
                response = cached_download(
                    active_client,
                    url,
                    cache_root,
                    resume=resume,
                    max_age_seconds=900,
                )
                store_raw_payload(
                    destination,
                    dataset="news",
                    source=source,
                    payload=response.payload,
                    fetched_at=fetched_at,
                    extension="xml",
                )
                parsed = [
                    item
                    for item in parse_rss(
                        response.payload,
                        source=source,
                        fetched_at=fetched_at,
                    )
                    if _in_range(item, start, end)
                ]
                all_items.extend(
                    _commit_source_items(
                        destination,
                        source=source,
                        source_url=url,
                        payload=response.payload,
                        items=parsed,
                        version=version,
                        resume=resume,
                    )
                )
                source_urls.add(url)
            except (HistoryError, ValueError) as exc:
                failures.append(f"{source}: {exc}")
    finally:
        if owned_client:
            active_client.close()

    unique = deduplicate_news(all_items)
    if not unique:
        detail = "; ".join(failures) or "selected sources returned no in-range headlines"
        raise ValueError(f"News download produced no headlines: {detail}")
    by_month: dict[str, list[NewsItem]] = defaultdict(list)
    for item in unique:
        by_month[item.published_utc.strftime("%Y-%m")].append(item)
    for month, items in sorted(by_month.items()):
        fingerprint = "\n".join(sorted(item.raw_hash for item in items)).encode()
        commit_news_snapshot(
            destination,
            source="reconciled",
            source_url=" | ".join(sorted(source_urls)),
            source_payload=month.encode() + b"\n" + fingerprint,
            items=items,
            code_version=version,
            resume=resume,
        )
    report = news_coverage(unique, start, end)
    report_path = repo_root() / "reports" / "data-quality" / "P03-news-coverage.json"
    atomic_write_json(report_path, report)
    print(
        f"News coverage: {report.total} headlines; "
        f"{len(report.missing_months)} missing months; report={report_path}"
    )
    for failure in failures:
        print(f"News source warning: {failure}")


def main() -> None:
    """Parse command arguments and run news ingestion."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--from", dest="from_value", required=True)
    parser.add_argument("--to", dest="to_value", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--bronze-root", type=Path)
    arguments = parser.parse_args()
    try:
        run_news_download(
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
