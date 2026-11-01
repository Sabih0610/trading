"""The PowerShell command must not mistake its subcommand for a Python executable."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.name != "nt", reason="Windows launcher used by the supported PowerShell script"
)
@pytest.mark.parametrize(
    "arguments,expected",
    [([], ["status"]), (["download", "fixture-id"], ["download", "fixture-id"])],
)
def test_medallion_script_forwards_positional_command(tmp_path, arguments, expected):
    root = tmp_path / "workspace with space"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    original = Path(__file__).resolve().parents[2] / "scripts/medallion.ps1"
    target = scripts / "medallion.ps1"
    shutil.copyfile(original, target)
    launcher = root / ".venv/Scripts/python.exe"
    launcher.parent.mkdir(parents=True)
    shutil.copyfile(sys.executable, launcher)
    shutil.copyfile(Path(sys.prefix) / "pyvenv.cfg", root / ".venv/pyvenv.cfg")
    for package in ("tb", "tb/ingest", "tb/ingest/history"):
        folder = root / package
        folder.mkdir(exist_ok=True)
        (folder / "__init__.py").write_text("")
    (root / "tb/ingest/history/vision_cli.py").write_text(
        "import json, sys\nprint(json.dumps(sys.argv[1:]))\n"
    )
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(target), *arguments],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
