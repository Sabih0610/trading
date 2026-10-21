"""Fail-closed P08 evidence report that never trains on locked observations."""

from __future__ import annotations

import argparse
from pathlib import Path

from tb.core.config import repo_root
from tb.strategies.evaluation import collect_coverage

_MODEL_ROWS = (
    ("Logistic classification baseline", "LightGBM meta-label classifier"),
    ("Ridge forecast baseline", "Rolling GPR forecast + uncertainty"),
    ("Recursive ridge adaptive baseline", "Dynamic fair-value filter"),
    ("Persistence variance baseline", "HAR-RV and GARCH(1,1)"),
    ("No-regime baseline", "Gaussian HMM regime filter"),
)


def render_ml_report(root: Path | None = None) -> str:
    """Render model evidence status using partition metadata only."""

    base = repo_root() if root is None else root.resolve()
    coverage = collect_coverage(base)
    xaut = next(item for item in coverage if item.label == "XAUTUSDT 5m features")
    eligible = ", ".join(str(year) for year in xaut.eligible_years) or "none"
    locked = ", ".join(str(year) for year in xaut.locked_years) or "none"
    comparisons = "\n".join(
        f"| {baseline} | {challenger} | NOT EVALUABLE — zero eligible labeled setups |"
        for baseline, challenger in _MODEL_ROWS
    )
    return f"""# P08 ML validation report

This report makes no model-value claim. P07 found no eligible 2020-2024 XAUT history, so P08 has
zero authentic labeled candidates. Available locked partitions are named from paths only and are
not opened, trained on, calibrated on, or evaluated.

## Evidence gate

| Item | Result |
|---|---|
| Eligible XAUT years | {eligible} |
| Locked XAUT years (not opened) | {locked} |
| Authentic labeled setups | 0 |
| Training / calibration / validation trials | 0 / 0 / 0 |
| Final-test authorizations | 0 |

## Model comparisons

| Mandatory baseline | Challenger | Validation result |
|---|---|---|
{comparisons}

## Strategy validation comparison

| Validation backtest | Result |
|---|---|
| Strategies without ML filter | NOT EVALUABLE — P07 empirical strategy run is blocked |
| Strategies with ML filter | NOT EVALUABLE — no model may be fit below 200 labeled setups |
| Incremental value after costs | **NOT ESTABLISHED** |

## Implemented safety evidence

- Triple-barrier labels retain their full information intervals and use adverse same-bar ordering.
- Purged, embargoed, expanding, and combinatorial folds reject future-known feature timestamps.
- Isotonic calibration requires at least 1,000 rows; all model fits require at least 200.
- LightGBM is deterministic CPU-only with four worker threads; GPR is capped at 2,000 rows.
- Calibrated probability and predictive uncertainty map only to a multiplier in `[0, 1]`.
- MLflow uses local SQLite metadata and local artifacts; registry roles require a named human and
  explicitly disable automatic deployment.

## Verdict

**REWORK / NOT EVALUABLE.** Add lawful, authentic pre-2025 XAUT candidate history, pass P02-P05
lineage checks, then run one frozen P08 comparison. Do not use synthetic tests as performance
evidence and do not access the locked final period for discovery.
"""


def write_ml_report(output: Path, root: Path | None = None) -> Path:
    """Write the deterministic metadata-only P08 report."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_ml_report(root), encoding="utf-8")
    return output


def main() -> None:
    """Parse the output path and reproduce the P08 evidence report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/ml/P08.md"))
    arguments = parser.parse_args()
    print(write_ml_report(arguments.output))


if __name__ == "__main__":
    main()
