"""Exercise the installer against an owned fake Git; no repo download or skill execution."""

import json
import shutil
import subprocess

import pytest

from tb.core.config import repo_root

PINS = {
    "claude-trading-skills": "cb0f3aadffed6d1089db4b224162c964368baa46",
    "antigravity-awesome-skills": "32b8ad933cfb84065a4ce5304c2557c9e39b25fa",
}


@pytest.mark.parametrize("scenario", ["pinned", "dirty", "wrong_identity"])
def test_only_reviewed_detached_commits_can_be_listed(tmp_path, scenario):
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell7 unavailable")
    root = tmp_path / "owned repo with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    target = scripts / "install-skills.ps1"
    target.write_bytes((repo_root() / "scripts/install-skills.ps1").read_bytes())
    trace = root / "git-trace.jsonl"
    marker = root / ".cache/skill-sources/claude-trading-skills/keep.txt"
    if scenario == "dirty":
        marker.parent.mkdir(parents=True)
        marker.write_text("owned local changes stay untouched")
    wrapper = root / "owned-git.ps1"
    wrapper.write_text(
        r"""
$ErrorActionPreference='Stop'
$global:OwnedTrace=Join-Path $PSScriptRoot 'git-trace.jsonl'
$global:OwnedScenario='SCENARIO'
function global:git {
    $items=@($args | ForEach-Object { [string]$_ })
    [IO.File]::AppendAllText($global:OwnedTrace, (ConvertTo-Json -Compress -InputObject $items) + "`n")
    $global:LASTEXITCODE=0
    if ($items[0] -eq 'init') {
        New-Item -ItemType Directory -Force -Path $items[1] | Out-Null
        return
    }
    $destination=$items[1]
    $name=Split-Path -Leaf $destination
    if ($items[2] -eq 'remote' -and $items[3] -eq 'get-url') {
        if ($name -eq 'claude-trading-skills') { 'https://github.com/tradermonty/claude-trading-skills' }
        else { 'https://github.com/sickn33/antigravity-awesome-skills' }
    }
    elseif ($items[2] -eq 'status' -and $global:OwnedScenario -eq 'dirty') { ' M keep.txt' }
    elseif ($items[2] -eq 'rev-parse') {
        if ($global:OwnedScenario -eq 'wrong_identity') { 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' }
        elseif ($name -eq 'claude-trading-skills') { 'cb0f3aadffed6d1089db4b224162c964368baa46' }
        else { '32b8ad933cfb84065a4ce5304c2557c9e39b25fa' }
    }
}
& (Join-Path $PSScriptRoot 'scripts/install-skills.ps1') -ListOnly
""".replace("SCENARIO", scenario),
        encoding="utf-8",
    )
    result = subprocess.run(
        [executable, "-NoProfile", "-File", str(wrapper)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    if scenario == "dirty":
        assert result.returncode != 0
        assert marker.read_text() == "owned local changes stay untouched"
        assert not any("fetch" in call for call in calls)
    elif scenario == "wrong_identity":
        assert result.returncode != 0 and "identity mismatch" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        fetches = [call for call in calls if "fetch" in call]
        assert len(fetches) == 2
        assert {call[-1] for call in fetches} == set(PINS.values())
        assert all(
            call[2:] == ["fetch", "--no-tags", "--depth", "1", "origin", call[-1]]
            for call in fetches
        )
        checkouts = [call for call in calls if "checkout" in call]
        assert len(checkouts) == 2
        assert all(
            call[2:] == ["checkout", "--detach", call[-1]] and call[-1] in PINS.values()
            for call in checkouts
        )
        assert not any("pull" in call or "clone" in call for call in calls)
