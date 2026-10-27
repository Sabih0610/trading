"""Finite owned-only paper demonstration. No external provider or credential setup exists."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tb.core.config import repo_root
from tb.ingest.history.core import atomic_write_bytes, atomic_write_json, sha256_file
from tb.paper.offline.fixtures import CASES, package, strategy_inputs
from tb.paper.offline.models import PaperInput, PaperRefused
from tb.paper.offline.reporting import projection, publish
from tb.paper.offline.store import PaperStore, code_digest
from tb.risk.config import load_policy_bundle


def demonstrate(
    root: Path, *, cases: tuple[str, ...] = CASES, bars: int = 90
) -> tuple[Path, list[dict[str, Any]]]:
    """Commit, close, reopen, reconcile and replay; never clear a prior account."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    bundle, code = load_policy_bundle(), code_digest()
    studies = []
    for case in cases:
        if case not in CASES:
            raise PaperRefused("unknown_owned_case")
        p = package(
            case,
            symbol="XAUUSD" if case == "gold_reversal" else "EURUSD",
            strategy="price_channel_reference"
            if case == "channel_breakout"
            else "ema_trend_reference",
        )
        folder = root / "work/offline_paper" / code[:12] / case
        source, manifest = folder / "inputs.jsonl", folder / "inputs.manifest.json"
        if source.exists() != manifest.exists():
            raise PaperRefused("owned_input_package_incomplete")
        if not source.exists():
            events = strategy_inputs(folder / "reference", p, case=case, bars=bars)
            atomic_write_bytes(
                source, b"".join((e.model_dump_json() + "\n").encode() for e in events)
            )
            atomic_write_json(
                manifest,
                {
                    "version": p.version,
                    "package_sha256": p.digest,
                    "code_sha256": code,
                    "bars": bars,
                    "rows": len(events),
                    "source_sha256": sha256_file(source),
                    "provider": "owned_fixture",
                },
            )
        if source.stat().st_size > 4194304 or manifest.stat().st_size > 8192:
            raise PaperRefused("owned_input_size_bound")
        facts = json.loads(manifest.read_text(encoding="utf-8"))
        if facts != {
            "version": p.version,
            "package_sha256": p.digest,
            "code_sha256": code,
            "bars": bars,
            "rows": sum(1 for _ in source.open(encoding="utf-8")),
            "source_sha256": sha256_file(source),
            "provider": "owned_fixture",
        }:
            raise PaperRefused("owned_input_manifest_or_configuration_changed")
        events = [
            PaperInput.model_validate_json(line)
            for line in source.read_text(encoding="utf-8").splitlines()
        ]
        if len(events) > p.max_events:
            raise PaperRefused("owned_input_count_bound")
        store = PaperStore(folder / "account", p, bundle, create=True)
        try:
            for event in events:
                store.process(event)
            before = store.state.model_dump_json()
        finally:
            store.close()
        store = PaperStore(folder / "account", p, bundle)
        try:
            if (
                not all(store.process(e) == "duplicate" for e in events)
                or store.state.model_dump_json() != before
            ):
                raise PaperRefused("owned_restart_changed_account")
            studies.append(projection(store, root))
        finally:
            store.close()
    return publish(root, studies, code_sha256=code), studies


def main() -> None:
    """Default status is inert; demo always generates owned input rather than reading feeds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=["status", "demo"], default="status")
    parser.add_argument("--provider", choices=["owned_fixture"], default="owned_fixture")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if args.action == "status":
        print(
            json.dumps(
                {
                    "mode": "owned_offline_paper",
                    "external_orders_enabled": False,
                    "genuine_sources_enabled": False,
                    "network_called": False,
                }
            )
        )
        return
    root = repo_root() if args.output_root is None else args.output_root.resolve()
    path, studies = demonstrate(root)
    print(
        json.dumps(
            {
                "snapshot": path.relative_to(root).as_posix(),
                "studies": len(studies),
                "accounts": [
                    {
                        "study": s["name"],
                        "totals": {
                            k: {
                                "cash": a["cash"],
                                "fills": a["fill_count"],
                                "completed": a["completed_trades"],
                            }
                            for k, a in s["state"]["accounts"].items()
                        },
                    }
                    for s in studies
                ],
                "mode": "SYNTHETIC SOFTWARE TEST ONLY",
                "external_orders": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
