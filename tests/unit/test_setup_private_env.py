"""Exercise only setup's private-file function against an owned temporary file."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tb.ingest.broker.onboarding.private import require_private

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.name != "nt" or shutil.which("pwsh") is None, reason="Windows ACL test")
def test_setup_creates_owner_system_acl_and_preserves_existing_file(tmp_path):
    template = tmp_path / "example"
    template.write_text("EXAMPLE_KEY=\n")
    destination = tmp_path / ".env"
    command = """
$tokens = $null; $errors = $null
$tree = [Management.Automation.Language.Parser]::ParseFile($env:TB_SETUP_SOURCE, [ref]$tokens, [ref]$errors)
$function = $tree.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'New-PrivateEnvFile'}, $true)
. ([scriptblock]::Create($function.Extent.Text))
New-PrivateEnvFile -Template $env:TB_SETUP_TEMPLATE -Destination $env:TB_SETUP_DESTINATION
$before = (Get-Acl -LiteralPath $env:TB_SETUP_DESTINATION).Sddl
New-PrivateEnvFile -Template 'missing-template' -Destination $env:TB_SETUP_DESTINATION
if ($before -ne (Get-Acl -LiteralPath $env:TB_SETUP_DESTINATION).Sddl) { throw 'Existing ACL changed' }
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        env={
            **os.environ,
            "TB_SETUP_SOURCE": str(ROOT / "scripts/setup.ps1"),
            "TB_SETUP_TEMPLATE": str(template),
            "TB_SETUP_DESTINATION": str(destination),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    require_private(destination)
    assert destination.read_bytes() == template.read_bytes()
