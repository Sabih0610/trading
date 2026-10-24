"""Finite owned-scenario demonstration; no providers, credentials, accounts or schedules."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from tb.core.config import repo_root
from tb.dashboard.shadow import read_shadow_snapshot
from tb.ingest.history.core import atomic_write_json
from tb.shadow.fixtures import SCENARIOS


def main() -> None:
    """Run ten independent immutable owned studies with their frozen configured hypotheses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=int, choices=range(80, 181), default=128)
    args = parser.parse_args()
    root = repo_root()
    results = []
    for scenario in SCENARIOS:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "tb.shadow.cli",
                "replay",
                "--scenario",
                scenario,
                "--bars",
                str(args.bars),
            ],
            cwd=root,
            check=True,
        )
        value = read_shadow_snapshot(
            root / "reports/shadow/price_only" / scenario / "runtime/snapshots",
            mode="fixture_replay",
        )
        results.append(
            {"scenario": scenario, "counts": value.counts, "evaluation": value.evaluation}
        )
    atomic_write_json(
        root / "reports/shadow/price_only/demonstration.json",
        {"mode": "owned_synthetic_only", "results": results, "external_orders_enabled": False},
    )
    print(json.dumps({"scenarios": len(results), "mode": "owned_synthetic_only", "orders": False}))


if __name__ == "__main__":
    main()
