"""Finite offline research commands. Never initializes a provider, key or trading interface."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from tb.core.config import repo_root
from tb.research.fixtures import generate
from tb.research.importer import import_dataset
from tb.research.models import ResearchProtocol
from tb.research.registry import check, inventory, load, read_metadata, register, safe
from tb.research.runner import read_result, replay, run


def status(root: Path, now: datetime) -> dict[str, Any]:
    rows = []
    for path in sorted(safe(root, "work/research/registry").glob("*.json")):
        try:
            record = read_metadata(root, path.relative_to(root).as_posix())
            p = load(root, record["policy"]["dataset_id"], now)
            rows.append(
                {
                    "dataset_id": p.dataset_id,
                    "source_class": p.source_class,
                    "provider": p.provider,
                    "instruments": list(p.instruments),
                    "price_type": p.price_type,
                    "coverage": [p.coverage_start.isoformat(), p.coverage_end.isoformat()],
                    "expires_at": p.retention.expires_at.isoformat(),
                    "status": "AUTHORIZED_LOCAL_RESEARCH",
                }
            )
        except (ValueError, OSError, KeyError):
            rows.append({"dataset_id": path.stem, "status": "BLOCKED — RIGHTS OR IDENTITY INVALID"})
    return {
        "datasets": rows,
        "genuine_historical_evaluation": "BLOCKED — DATASET NOT AUTHORIZED"
        if not any(r.get("source_class") == "licensed_historical" for r in rows)
        else "qualified_local_dataset_available",
        "provider_connections": 0,
        "external_orders": 0,
        "protected_holdout": "LOCKED_2025_PLUS",
    }


def demo(root: Path, now: datetime) -> dict[str, Any]:
    outputs = []
    for name, fmt, timeframe, bars_count in [
        ("owned-m5-csv", "csv", "M5", 320),
        ("owned-m1-parquet", "parquet", "M1", 1024),
    ]:
        generate(root, name, now, file_format=fmt, timeframe=timeframe, bars=bars_count)  # type: ignore[arg-type]
        imported = import_dataset(root, name, clock=lambda: now)
        value = run(root, name, ResearchProtocol(), clock=lambda: now)
        proof = replay(root, value["run_id"], clock=lambda: now)
        outputs.append(
            {
                "dataset_id": name,
                "run_id": value["run_id"],
                "quality": imported["counts"],
                "report": f"data/gold/research/{value['run_id']}/report.md",
                "replay_identical": proof["identical"],
                "decisions_sha256": value["decision_sha256"],
                "label": "SOFTWARE TEST ONLY",
            }
        )
    return {
        "owned_runs": outputs,
        "provider_connections": 0,
        "external_orders": 0,
        "genuine_historical_evaluation": "BLOCKED — DATASET NOT AUTHORIZED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        help="Explicit credential-free research workspace; default is this repository",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    sub.add_parser("demo")
    sub.add_parser("inventory")
    for name in ("check", "register"):
        p = sub.add_parser(name)
        p.add_argument("proposal", help="Relative metadata path under work/research/proposals")
    p = sub.add_parser("fixture")
    p.add_argument("dataset_id")
    p.add_argument("--format", choices=("csv", "parquet"), default="csv")
    p.add_argument("--timeframe", choices=("M1", "M5"), default="M5")
    p.add_argument("--bars", type=int, default=320)
    p.add_argument(
        "--price-type",
        choices=("reference_midpoint", "bid_only", "bid_ask"),
        default="reference_midpoint",
    )
    p = sub.add_parser("import")
    p.add_argument("dataset_id")
    p = sub.add_parser("run")
    p.add_argument("dataset_id")
    p.add_argument("--split", choices=("research", "validation"), default="validation")
    for name in ("replay", "report"):
        p = sub.add_parser(name)
        p.add_argument("run_id")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else repo_root()
    now = datetime.now(UTC)
    if (root / ".env").exists():
        parser.exit(2, "Research commands require a credential-free workspace.\n")
    try:
        result: Any
        if args.action == "status":
            result = status(root, now)
        elif args.action == "inventory":
            result = inventory(root, now)
        elif args.action == "demo":
            result = demo(root, now)
        elif args.action == "fixture":
            result = {
                "dataset_id": generate(
                    root,
                    args.dataset_id,
                    now,
                    file_format=args.format,
                    timeframe=args.timeframe,
                    bars=args.bars,
                    price_type=args.price_type,
                )
            }
        elif args.action == "check":
            checked = check(root, args.proposal, now)
            result = {
                "dataset_id": checked.dataset_id,
                "permissions_checked": True,
                "source_content_opened": False,
                "source_hash_verification": "REQUIRED_AT_IMPORT",
                "approval_created": False,
            }
        elif args.action == "register":
            result = {"dataset_id": register(root, args.proposal, now), "approval_created": False}
        elif args.action == "import":
            result = import_dataset(root, args.dataset_id, clock=lambda: datetime.now(UTC))
        elif args.action == "run":
            result = run(
                root,
                args.dataset_id,
                ResearchProtocol(split=args.split),
                clock=lambda: datetime.now(UTC),
            )
        elif args.action == "replay":
            result = replay(root, args.run_id, clock=lambda: datetime.now(UTC))
        else:
            result = read_result(root, args.run_id, now=now)
        print(json.dumps(result, indent=2, default=str))
    except (
        ValueError,
        OSError,
        KeyError,
        RuntimeError,
        TypeError,
        csv.Error,
        sqlite3.Error,
        pl.exceptions.PolarsError,
    ):
        parser.exit(
            2,
            "Research refused: check source identity, current permissions, lifetime, input quality, immutable evidence and the protected holdout. No provider or order was called.\n",
        )


if __name__ == "__main__":
    main()
