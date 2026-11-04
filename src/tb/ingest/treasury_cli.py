"""Explicit optional Treasury acquisition; imports/startup never fetch data."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

from tb.core.config import repo_root
from tb.research.models import ResearchRefused
from tb.research.treasury_registry import register_treasury_plan
from tb.silver.treasury import build


def main() -> None:
    """Register actual evidence, then explicitly build approved historical daily context."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root())
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--proposal", required=True)
    sub.add_parser("build")
    args = parser.parse_args()
    root = args.root.resolve()
    if (repo_root() / ".env").exists() or (root / ".env").exists():
        raise ResearchRefused("treasury_credential_free_checkout_required")
    if args.command == "register":
        dataset = register_treasury_plan(root, args.proposal, datetime.now(UTC))
        print(json.dumps({"registered": dataset}))
        return
    version = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_root(), text=True
    ).strip()
    if subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "src",
            "pyproject.toml",
            "uv.lock",
        ],
        cwd=repo_root(),
    ):
        raise ResearchRefused("treasury_commit_source_before_genuine_build")
    with httpx.Client(
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "TradingBotPrivateResearch/1.0"},
    ) as client:
        result = build(root, client, code_version=version)
    print(
        json.dumps(
            {
                "status": result["status"],
                "dataset_id": result["dataset_id"],
                "private_quality": result["quality_path"],
            }
        )
    )


if __name__ == "__main__":
    main()
