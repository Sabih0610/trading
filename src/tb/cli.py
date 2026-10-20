"""Command-line interface for local diagnostics and later phase entry points."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil
import typer
from rich.console import Console
from rich.table import Table

from tb import __version__
from tb.core.config import Settings, features_enabled, load_settings, repo_root

app = typer.Typer(no_args_is_help=True, help="Trading Bot research and operations CLI.")
console = Console()


@app.callback()
def main() -> None:
    """Run Trading Bot research and operations commands."""


def _gpu_name() -> str | None:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = completed.stdout.strip()
    return output if completed.returncode == 0 and output else None


def collect_doctor_report(
    *,
    root: Path | None = None,
    settings: Settings | None = None,
    gpu_probe: Callable[[], str | None] = _gpu_name,
) -> dict[str, Any]:
    """Collect local-only diagnostics; this function never makes a network request."""

    project_root = repo_root() if root is None else root.resolve()
    active_settings = load_settings() if settings is None else settings
    disk_anchor = Path(project_root.anchor or project_root)
    disk = shutil.disk_usage(disk_anchor)
    memory = psutil.virtual_memory()
    data_root = project_root / "data"
    layers = {layer: (data_root / layer).is_dir() for layer in ("bronze", "silver", "gold")}
    return {
        "project_version": __version__,
        "project_root": str(project_root),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "disk_free_gib": round(disk.free / 1024**3, 1),
        "ram_total_gib": round(memory.total / 1024**3, 1),
        "ram_available_gib": round(memory.available / 1024**3, 1),
        "gpu": gpu_probe() or "not detected",
        "data_layers": layers,
        "features": features_enabled(active_settings),
        "network_used": False,
    }


@app.command()
def doctor() -> None:
    """Print offline environment, hardware, feature, and data-folder diagnostics."""

    report = collect_doctor_report()
    environment = Table(title="Trading Bot doctor", show_header=True)
    environment.add_column("Check")
    environment.add_column("Value")
    for key in (
        "project_version",
        "project_root",
        "python",
        "python_executable",
        "platform",
        "disk_free_gib",
        "ram_total_gib",
        "ram_available_gib",
        "gpu",
        "network_used",
    ):
        environment.add_row(key.replace("_", " ").title(), str(report[key]))
    console.print(environment)

    feature_table = Table(title="Optional integrations", show_header=True)
    feature_table.add_column("Feature")
    feature_table.add_column("Status")
    for name, enabled in report["features"].items():
        feature_table.add_row(name, "ON" if enabled else "OFF")
    console.print(feature_table)

    data_table = Table(title="Data layers", show_header=True)
    data_table.add_column("Layer")
    data_table.add_column("Present")
    for name, present in report["data_layers"].items():
        data_table.add_row(name, "yes" if present else "no")
    console.print(data_table)


if __name__ == "__main__":
    app()
