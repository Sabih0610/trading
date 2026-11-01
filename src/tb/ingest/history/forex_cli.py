"""Explicit consent-gated FX acquisition and source-separated yearly medallion commands."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from tb.core.config import repo_root
from tb.features.engine import FeatureEngine
from tb.ingest.history.cli import _code_version
from tb.ingest.history.core import IntegrityError, atomic_write_bytes, atomic_write_json
from tb.ingest.history.forex import ProviderFailure, download_period, validate_period
from tb.ingest.mt5.models import FeedUnavailable
from tb.research.forex_registry import load_forex_plan, register_forex_plan
from tb.research.models import ResearchRefused
from tb.research.registry import safe
from tb.silver.forex import build_year


def with_fallback(root: Path, primary: Callable[[], Any], backup: Callable[[], Any]) -> Any:
    """Stop the primary on bounded technical failure, preserve diagnostics, then use backup."""
    try:
        return primary()
    except ProviderFailure as exc:
        fields = (
            "endpoint",
            "utc",
            "http_status",
            "error_class",
            "successful_requests",
            "failed_requests",
            "error_sample",
        )
        lines = [
            "# P11e Dukascopy technical failure",
            "",
            "No market observations are included.",
            "",
        ]
        lines.extend(f"- {key}: {exc.details.get(key, 'unavailable')}" for key in fields)
        atomic_write_bytes(
            safe(root, "reports/phases/P11e-dukascopy-failure.md"),
            ("\n".join(lines) + "\n").encode(),
        )
        return backup()


def download_history(
    root: Path,
    backup_id: str,
    *,
    primary_id: str | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Sequential safe whole archives; no source mixing, and every withheld file has a reason."""
    if (root / ".env").exists():
        raise ResearchRefused("Use a credential-free history checkout")
    backup = load_forex_plan(root, backup_id, clock())
    if backup.provider != "histdata":
        raise ResearchRefused("backup_must_be_approved_histdata")
    primary = load_forex_plan(root, primary_id, clock()) if primary_id else None
    if primary is not None and primary.provider != "dukascopy":
        raise ResearchRefused("primary_must_have_approved_dukascopy_consent")
    results: list[dict[str, Any]] = []
    delivered: set[tuple[str, int]] = set()
    version = _code_version()
    counts = {"successful_requests": 0, "failed_requests": 0}

    def count_request(request: httpx.Request) -> None:
        counts["failed_requests"] += 1

    def count_response(response: httpx.Response) -> None:
        if response.status_code == 200:
            counts["successful_requests"] += 1
            counts["failed_requests"] -= 1

    with httpx.Client(
        trust_env=False,
        follow_redirects=False,
        timeout=30,
        event_hooks={"request": [count_request], "response": [count_response]},
    ) as client:

        def primary_day(symbol: str, day: date) -> dict[str, Any]:
            if primary is None:
                raise ResearchRefused("primary_consent_required")
            try:
                return download_period(
                    root,
                    primary.dataset_id,
                    client,
                    symbol=symbol,
                    period=day,
                    code_version=version,
                    clock=clock,
                )
            except (ResearchRefused, FeedUnavailable):
                raise
            except ProviderFailure as exc:
                exc.details.update(counts)
                raise
            except (IntegrityError, ValueError) as exc:
                raise ProviderFailure(
                    dict(
                        endpoint=primary.source,
                        utc=clock().isoformat(),
                        http_status=200,
                        error_class=type(exc).__name__,
                        **counts,
                        error_sample="M1 archive validation failed; original files retained",
                    )
                ) from None

        def fetch_primary() -> dict[str, Any]:
            if primary is None:
                return fetch_backup()
            for symbol in primary.instruments:
                probe = primary_day(symbol, date(2024, 3, 12))
                if probe["status"] != "complete":
                    raise ProviderFailure(
                        dict(
                            endpoint=primary.source,
                            utc=clock().isoformat(),
                            http_status=200,
                            error_class="EmptyProbe",
                            **counts,
                            error_sample="No aligned BID/ASK M1 probe available",
                        )
                    )
            for symbol in primary.instruments:
                for year in range(primary.coverage_start.year, primary.coverage_end.year + 1):
                    day = max(primary.coverage_start.date(), date(year, 1, 1))
                    stop = min(
                        primary.coverage_end.date() + timedelta(days=1), date(year + 1, 1, 1)
                    )
                    missing = open_days = 0
                    while day < stop:
                        item = primary_day(symbol, day)
                        results.append(item)
                        if day.weekday() < 5:
                            open_days += 1
                            missing += item["status"] != "complete"
                        if open_days >= 10 and missing > open_days / 2:
                            raise ProviderFailure(
                                dict(
                                    endpoint=primary.source,
                                    utc=clock().isoformat(),
                                    http_status=200,
                                    error_class="MostlyEmpty",
                                    **counts,
                                    error_sample="Most weekday M1 files unavailable",
                                )
                            )
                        day += timedelta(days=1)
                    # Only fully supplied source years suppress a backup archive.
                    if not missing:
                        delivered.add((symbol, year))
            return save()

        def save() -> dict[str, Any]:
            value: dict[str, Any] = {
                "updated_at": clock().isoformat(),
                "results": results,
                "primary": primary_id or "Dukascopy consent file not found",
            }
            atomic_write_json(safe(root, "reports/data_quality/P11e-forex-acquisition.json"), value)
            return value

        def fetch_backup() -> dict[str, Any]:
            for symbol in backup.instruments:
                for year in range(backup.coverage_start.year, backup.coverage_end.year + 1):
                    period = date(year, 1, 1)
                    if (symbol, year) in delivered:
                        continue
                    try:
                        validate_period(backup, symbol, period, "yearly")
                    except ResearchRefused:
                        results.append(
                            dict(
                                symbol=symbol,
                                period=period.isoformat(),
                                cadence="yearly",
                                status="withheld",
                                reason="nominal_fixed_EST_archive_crosses_approved_UTC_boundary",
                            )
                        )
                        continue
                    try:
                        results.append(
                            download_period(
                                root,
                                backup.dataset_id,
                                client,
                                symbol=symbol,
                                period=period,
                                cadence="yearly",
                                code_version=version,
                                clock=clock,
                            )
                        )
                    except ProviderFailure as exc:
                        results.append(
                            dict(
                                symbol=symbol,
                                period=period.isoformat(),
                                status="technical_failure",
                                details=exc.details,
                            )
                        )
                        save()
                        raise
                    save()
            return save()

        return with_fallback(root, fetch_primary, fetch_backup) if primary else fetch_backup()


def main() -> None:
    """No dotenv/settings; explicit registration and acquisition commands only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root())
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("register")
    command.add_argument("proposal")
    command = commands.add_parser("download")
    command.add_argument("backup_id")
    command.add_argument("--primary-id")
    command = commands.add_parser("build")
    command.add_argument("dataset_id")
    args = parser.parse_args()
    root = args.root.resolve()
    if (root / ".env").exists():
        raise SystemExit("Use a separate credential-free history checkout")

    def now() -> datetime:
        return datetime.now(UTC)

    if args.command == "register":
        print(register_forex_plan(root, args.proposal, now()))
    elif args.command == "download":
        download_history(root, args.backup_id, primary_id=args.primary_id)
        print("Acquisition record saved privately")
    else:
        plan = load_forex_plan(root, args.dataset_id, now())
        for symbol in plan.instruments:
            engines: dict[str, FeatureEngine] = {}
            previous = None
            for year in range(plan.coverage_start.year, plan.coverage_end.year + 1):
                value = build_year(
                    root,
                    plan.dataset_id,
                    symbol,
                    year,
                    clock=now,
                    engines=engines,
                    previous_timestamp_ns=previous,
                )
                if value["status"] == "complete":
                    previous = int(value["quality"]["last_timestamp_ns"])
                print(symbol, year, value["status"], flush=True)


if __name__ == "__main__":
    main()
