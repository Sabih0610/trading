"""Explicit optional CFTC COT acquisition; imports/startup never fetch data."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

from tb.core.config import repo_root
from tb.ingest.sec_fsds_cli import read_user_agent
from tb.research.cftc_registry import register_cftc_plan
from tb.research.models import ResearchRefused
from tb.silver.cftc_cot import build


def main() -> None:
    """Register actual evidence, then explicitly build the approved quarters."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--proposal", required=True)
    sub.add_parser("build")
    args = parser.parse_args()
    root = args.root.resolve()
    if (repo_root() / ".env").exists() or (root / ".env").exists():
        raise ResearchRefused("cftc_cot_credential_free_checkout_required")
    if args.command == "register":
        print(
            json.dumps({"registered": register_cftc_plan(root, args.proposal, datetime.now(UTC))})
        )
        return
    agent = read_user_agent(root)
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
        raise ResearchRefused("cftc_cot_commit_source_before_genuine_build")
    with httpx.Client(
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": agent, "Accept-Encoding": "gzip, deflate"},
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
