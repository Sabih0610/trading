"""Immutable, complete per-run backtest artifact writer."""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from tb.backtest.engine import BacktestResult, EquityPoint, RejectionRecord, TradeRecord
from tb.backtest.metrics import BacktestMetrics

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class BacktestArtifacts(BaseModel):
    """Paths written for one immutable run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    root: Path
    summary: Path
    trades: Path
    equity: Path
    rejections: Path
    report: Path
    config: Path
    code_version: Path


def resolve_code_version(repo_root: Path = Path(".")) -> str:
    """Return the current Git object ID, or a stable marker outside a checkout."""

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else "unavailable"


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal | Path | Enum):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _write_models_csv(path: Path, rows: Sequence[BaseModel], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            values = row.model_dump(mode="json")
            writer.writerow({field: values[field] for field in fields})


def _report_markdown(
    run_id: str,
    metrics: BacktestMetrics,
    result: BacktestResult,
    code_version: str,
) -> str:
    profit_factor = "undefined" if metrics.profit_factor is None else str(metrics.profit_factor)
    sharpe = "undefined" if metrics.sharpe is None else str(metrics.sharpe)
    sortino = "undefined" if metrics.sortino is None else str(metrics.sortino)
    caveats = "\n".join(f"- {item}" for item in metrics.caveats)
    return f"""# Backtest report — {run_id}

This report is a deterministic research artifact. It is not an execution instruction.

## Result

| Metric | Value |
|---|---:|
| Ending equity | {metrics.ending_equity} |
| Net P&L | {metrics.net_pnl} |
| Return | {metrics.return_pct}% |
| Trades | {metrics.trade_count} |
| Rejections | {len(result.rejections)} |
| Expectancy | {metrics.expectancy} |
| Profit factor | {profit_factor} |
| Maximum drawdown | {metrics.max_drawdown_pct}% |
| Sharpe | {sharpe} |
| Sortino | {sortino} |
| Exposure time | {metrics.exposure_time_pct}% |
| Trials disclosed | {metrics.trial_count} |

## Caveats

{caveats}

Code version: `{code_version}`
"""


def write_backtest_artifacts(
    output_root: Path,
    run_id: str,
    *,
    result: BacktestResult,
    metrics: BacktestMetrics,
    config: Mapping[str, Any],
    code_version: str | None = None,
) -> BacktestArtifacts:
    """Write a complete run into a new directory and never overwrite an old run."""

    if _RUN_ID.fullmatch(run_id) is None:
        raise ValueError("run_id must use 1-100 safe filename characters")
    destination = output_root / run_id
    if destination.exists():
        raise FileExistsError(f"Backtest run already exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=output_root))
    version = resolve_code_version() if code_version is None else code_version
    try:
        _write_json(temporary / "summary.json", metrics.model_dump(mode="json"))
        _write_json(temporary / "config.json", dict(config))
        _write_models_csv(
            temporary / "trades.csv",
            result.trades,
            tuple(TradeRecord.model_fields),
        )
        _write_models_csv(
            temporary / "equity.csv",
            result.equity,
            tuple(EquityPoint.model_fields),
        )
        _write_models_csv(
            temporary / "rejections.csv",
            result.rejections,
            tuple(RejectionRecord.model_fields),
        )
        (temporary / "report.md").write_text(
            _report_markdown(run_id, metrics, result, version), encoding="utf-8"
        )
        (temporary / "code_version.txt").write_text(version + "\n", encoding="utf-8")
        temporary.replace(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return BacktestArtifacts(
        root=destination,
        summary=destination / "summary.json",
        trades=destination / "trades.csv",
        equity=destination / "equity.csv",
        rejections=destination / "rejections.csv",
        report=destination / "report.md",
        config=destination / "config.json",
        code_version=destination / "code_version.txt",
    )
