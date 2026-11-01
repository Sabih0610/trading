"""Explicit prospective approval and pre-2025 historical medallion commands."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from tb.core.config import repo_root
from tb.core.logging import configure_cli_logging
from tb.features.engine import FeatureEngine
from tb.ingest.history.cli import _code_version, plan_archive_periods
from tb.ingest.history.core import require_disk_space
from tb.ingest.history.vision import download_archive
from tb.research.registry import load_vision_plan, register_vision_plan, safe
from tb.silver.vision import build_year


def status(root: Path, now: datetime) -> dict[str, Any]:
    """Admission status reads only public registry/evidence metadata, never market files."""
    rows = []
    for path in sorted(safe(root, "work/research/registry/vision").glob("*.json")):
        try:
            plan = load_vision_plan(root, path.stem, now)
            rows.append(
                {
                    "dataset_id": plan.dataset_id,
                    "status": "AUTHORIZED_PRIVATE_RESEARCH",
                    "terms_version": plan.terms_version,
                    "expires_at": plan.retention.expires_at.isoformat(),
                }
            )
        except (ValueError, OSError, KeyError):
            rows.append({"dataset_id": path.stem, "status": "BLOCKED — DATASET NOT AUTHORIZED"})
    return {
        "status": "authorized_plan_available"
        if any(r["status"] == "AUTHORIZED_PRIVATE_RESEARCH" for r in rows)
        else "BLOCKED — DATASET NOT AUTHORIZED",
        "datasets": rows,
        "strategy_evaluation": "NOT RUN IN P11d",
        "historical_cutoff": "2024-12-31T23:59:00Z",
    }


def main() -> None:
    """No provider client is constructed until an explicit admitted download command."""
    configure_cli_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    registration = commands.add_parser("register")
    registration.add_argument("proposal")
    for name in ("download", "build"):
        command = commands.add_parser(name)
        command.add_argument("dataset_id")
    args = parser.parse_args()
    root = args.root.resolve()
    value: dict[str, Any]
    if (root / ".env").exists():
        raise SystemExit("Use a separate credential-free medallion checkout")

    def now() -> datetime:
        return datetime.now(UTC)

    try:
        if args.command == "status":
            print(json.dumps(status(root, now()), indent=2))
            return
        if args.command == "register":
            print(register_vision_plan(root, args.proposal, now()))
            return
        plan = load_vision_plan(root, args.dataset_id, now())
        if args.command == "download":
            # Only monthly/daily 1m scope is bulk-plannable; seconds have no bulk CLI.
            if "1m" not in plan.intervals:
                raise ValueError("No approved 1m interval")
            periods = plan_archive_periods(plan.coverage_start.date(), plan.coverage_end.date())
            require_disk_space(root, len(periods) * len(plan.instruments) * 100 * 1024**2)
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=30) as client:
                for symbol in plan.instruments:
                    for period, cadence in periods:
                        value = download_archive(
                            root,
                            plan.dataset_id,
                            client,
                            symbol=symbol,
                            period=period,
                            cadence=cadence,
                            code_version=_code_version(),
                            clock=now,
                        )
                        print(symbol, period, value["status"])
        elif args.command == "build":
            for symbol in plan.instruments:
                engines: dict[str, FeatureEngine] = {}
                previous: int | None = None
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
                        # Last timestamp is price-free metadata, carried across UTC years.
                        previous = int(value["quality"]["last_timestamp_ns"])
                    print(symbol, year, value["status"])
    except (ValueError, OSError, KeyError):
        raise SystemExit("BLOCKED — DATASET NOT AUTHORIZED OR DATA VALIDATION FAILED") from None


if __name__ == "__main__":
    main()
