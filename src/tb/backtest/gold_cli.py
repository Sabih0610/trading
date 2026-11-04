"""Frozen, approved, credential-free one-shot gold development entrypoint."""

from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path
from typing import Any

import psutil

from tb.backtest.gold_development import REGISTRATION_SHA, GoldBatch, implementation_identity
from tb.core.leases import writer_lease
from tb.ingest.history.core import sha256_file
from tb.research.gold_development_data import GoldSource
from tb.research.models import ResearchRefused, digest
from tb.research.registry import safe

REVIEW_SHA = "c7aaf4ddfb617258ae2c7d4086c4aa42f8c2b8bf36e8ba8d7addc874688bd12a"
FREEZE_PATH = "reports/validation/P11g-PartB/freeze.json"


def configuration_identity(repo: Path) -> str:
    """Hash the precise funded policy/configuration used by this registered run."""
    return digest(
        [
            (p.relative_to(repo).as_posix(), sha256_file(p))
            for p in sorted((repo / "config").rglob("*.yaml"))
        ]
    )


def require_frozen_approval(repo: Path) -> dict[str, Any]:
    """Approval, amended bytes and passed complete source gate precede data admission."""
    if sha256_file(repo / "reports/reviews/P11g-prereg-review.md") != REVIEW_SHA:
        raise ResearchRefused("gold_approved_review_changed")
    implementation = implementation_identity(repo)
    record = json.loads((repo / FREEZE_PATH).read_text(encoding="utf-8"))
    if (
        record.get("kind") != "gold_development_pre_data_freeze"
        or record.get("gate_status") != "passed"
        or record.get("registration_sha256") != REGISTRATION_SHA
        or record.get("review_sha256") != REVIEW_SHA
        or record.get("implementation_sha256") != implementation
        or record.get("configuration_sha256") != configuration_identity(repo)
    ):
        raise ResearchRefused("gold_complete_source_not_frozen_and_gated")
    return dict(record)


def main() -> None:
    """Run or resume identical technical checkpoints; never search a new batch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    if (repo / ".env").exists() or (args.data_root / ".env").exists():
        raise ResearchRefused("gold_credential_free_checkouts_required")
    require_frozen_approval(repo)
    batch = GoldBatch(repo, GoldSource(args.data_root))
    done = threading.Event()

    def sample_memory() -> None:
        process = psutil.Process()
        while not done.wait(0.2):
            batch.peak_rss = max(batch.peak_rss, process.memory_info().rss)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        with writer_lease(safe(args.data_root, batch.store.base + "/run.lock")):
            result = batch.run()
        print(
            json.dumps(
                {
                    "complete": True,
                    "experiments": len(result["verdicts"]),
                    "registration_sha256": REGISTRATION_SHA,
                }
            )
        )
    finally:
        done.set()
        sampler.join(timeout=5)


if __name__ == "__main__":
    main()
