"""Locally validate owner gating, action pins, network refusal and Windows fail-fast checks."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_is_owner_gated_public_windows_without_secrets_or_uploads():
    text = (ROOT / ".github/workflows/offline-quality.yml").read_text()
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["offline"]
    assert "OFFLINE_CI_APPROVED_FREE_RUNNER == 'true'" in job["if"]
    assert "github.event.repository.private == false" in job["if"]
    assert job["runs-on"] == "windows-2025" and int(job["timeout-minutes"]) <= 20
    actions = [s for s in job["steps"] if "uses" in s]
    assert len(actions) == 2 and all(
        re.fullmatch(r"[\w/-]+@[0-9a-f]{40}", a["uses"]) for a in actions
    )
    assert actions[0]["with"]["persist-credentials"] == "false"
    assert actions[1]["with"]["enable-cache"] == "false"
    assert actions[1]["with"]["python-version"].startswith("3.12.")
    assert not any(
        s in text
        for s in ("secrets.", "upload-artifact", "continue-on-error", "pull_request_target")
    )


@pytest.mark.parametrize(
    "host,port", [("example.com", 443), ("1.1.1.1", 443), ("127.0.0.1", 22346)]
)
def test_ci_network_guard_refuses_before_any_external_connection(host, port):
    env = {
        **os.environ,
        "TB_OFFLINE_VALIDATION": "1",
        "PYTHONPATH": str(ROOT / "scripts/offline_guard"),
    }
    result = subprocess.run(
        [sys.executable, "-c", f"import socket; socket.create_connection(({host!r}, {port}))"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Offline validation refused" in result.stderr


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="Windows/PowerShell acceptance")
@pytest.mark.parametrize(
    "failed", ["ruff check", "ruff format", "mypy src", "pytest -q", "tb.paper.smoke"]
)
def test_windows_entrypoint_propagates_each_quality_failure(tmp_path, failed):
    fake = tmp_path / "fake uv.ps1"
    trace = tmp_path / "calls.txt"
    fake.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\n"
        "$line = $Arguments -join ' '\n"
        "Add-Content -LiteralPath $env:TB_TEST_TRACE -Value $line\n"
        "if ($line.Contains($env:TB_TEST_FAILURE)) { exit 19 }\nexit 0\n"
    )
    env = {**os.environ, "TB_TEST_TRACE": str(trace), "TB_TEST_FAILURE": failed}
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/check-offline.ps1"),
            "-Uv",
            str(fake),
            "-TemporaryRoot",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode != 0
    calls = trace.read_text().splitlines()
    assert failed in calls[-1] and not any("offline.cli demo" in c for c in calls)
