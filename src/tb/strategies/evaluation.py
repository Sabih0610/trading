"""Fail-closed P07 evidence inventory and reproducible strategy report."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from tb.backtest.baselines import BaselineName
from tb.backtest.research import assess_research, load_research_policies
from tb.core.config import repo_root
from tb.strategies.scenarios import load_scenarios

_DEVELOPMENT_YEARS = frozenset(range(2020, 2024))
_VALIDATION_YEARS = frozenset({2024})
_ALLOWED_YEARS = _DEVELOPMENT_YEARS | _VALIDATION_YEARS
_YEAR = re.compile(r"^year=(\d{4})$")


@dataclass(frozen=True)
class DatasetCoverage:
    """Partition-year inventory obtained without opening observation files."""

    label: str
    root: Path
    available_years: tuple[int, ...]
    eligible_years: tuple[int, ...]
    locked_years: tuple[int, ...]


@dataclass(frozen=True)
class StrategyEvidence:
    """Evidence status for one frozen strategy hypothesis."""

    name: str
    required_datasets: tuple[str, ...]
    verdict: str
    status: str
    missing_years: tuple[int, ...]


def inventory_partition_years(label: str, root: Path) -> DatasetCoverage:
    """Classify partition paths while refusing to open any observation file."""

    years: set[int] = set()
    if root.exists():
        for candidate in root.rglob("year=*"):
            if not candidate.is_dir():
                continue
            matched = _YEAR.fullmatch(candidate.name)
            if matched is not None:
                years.add(int(matched.group(1)))
    return DatasetCoverage(
        label=label,
        root=root,
        available_years=tuple(sorted(years)),
        eligible_years=tuple(sorted(years & _ALLOWED_YEARS)),
        locked_years=tuple(sorted(year for year in years if year >= 2025)),
    )


def collect_coverage(root: Path | None = None) -> tuple[DatasetCoverage, ...]:
    """Inventory the two P07 inputs from repository-relative locations."""

    base = repo_root() if root is None else root.resolve()
    return (
        inventory_partition_years(
            "XAUTUSDT 5m features", base / "data" / "gold" / "features" / "XAUTUSDT" / "5m"
        ),
        inventory_partition_years(
            "XAUUSD 5m reference",
            base / "data" / "silver" / "dukascopy" / "XAUUSD" / "5m",
        ),
    )


def assess_strategies(coverage: tuple[DatasetCoverage, ...]) -> tuple[StrategyEvidence, ...]:
    """Return REWORK when any required 2020-2024 evidence is unavailable."""

    by_label = {item.label: item for item in coverage}
    requirements = (
        ("A — London sweep → MSS → FVG", ("XAUTUSDT 5m features",)),
        (
            "B — XAUT catch-up lead-lag",
            ("XAUTUSDT 5m features", "XAUUSD 5m reference"),
        ),
        ("C — trend pullback to session VWAP", ("XAUTUSDT 5m features",)),
    )
    assessments: list[StrategyEvidence] = []
    xaut_research = assess_research(load_research_policies().policy("XAUTUSDT"), None)
    for name, labels in requirements:
        present = set.intersection(*(set(by_label[label].eligible_years) for label in labels))
        missing = tuple(sorted(_ALLOWED_YEARS - present))
        if missing or xaut_research.status == "INSUFFICIENT_HISTORY":
            assessments.append(
                StrategyEvidence(
                    name=name,
                    required_datasets=labels,
                    verdict="REWORK",
                    status="NOT EVALUABLE — insufficient venue history before locked holdout",
                    missing_years=missing,
                )
            )
        else:
            assessments.append(
                StrategyEvidence(
                    name=name,
                    required_datasets=labels,
                    verdict="REWORK",
                    status="READY FOR EMPIRICAL EVALUATION",
                    missing_years=(),
                )
            )
    return tuple(assessments)


def _years(values: tuple[int, ...]) -> str:
    return ", ".join(str(value) for value in values) if values else "none"


def render_report(root: Path | None = None) -> str:
    """Render the complete P07 evidence report without accessing locked observations."""

    coverage = collect_coverage(root)
    assessments = assess_strategies(coverage)
    scenarios = load_scenarios(
        (repo_root() if root is None else root) / "config" / "scenarios.yaml"
    )
    coverage_rows = "\n".join(
        f"| {item.label} | {_years(item.available_years)} | {_years(item.eligible_years)} | "
        f"{_years(item.locked_years)} |"
        for item in coverage
    )
    strategy_rows = "\n".join(
        f"| {item.name} | {item.status} | {item.verdict} | {_years(item.missing_years)} |"
        for item in assessments
    )
    scenario_rows = "\n".join(
        f"| {scenario.label} | NOT RUN — required 2020-2024 tradable history unavailable |"
        for scenario in scenarios.scenarios
    )
    baseline_rows = "\n".join(
        f"| {baseline.value} | NOT RUN — same missing tradable history |"
        for baseline in BaselineName
    )
    return f"""# P07 strategy evaluation

This is a deterministic evidence-status report, not a claim of trading performance. The evaluator
found no eligible 2020-2024 XAUT observations and did not open the available 2025+ partitions.
All three hypotheses therefore remain **REWORK / not evaluable**, with zero empirical trials.

## Coverage gate

| Dataset | Years on disk | Eligible years | Locked years (not opened) |
|---|---|---|---|
{coverage_rows}

Legacy discovery dates were 2020-2023 / validation 2024. Binance XAUT/USDT began on
2026-03-26 13:30 UTC, after the existing 2025-01-01 final-test lock. Its pre-lock training and
validation windows are empty. They cannot be repaired by acquiring nonexistent Binance history.
Instrument-specific policies live in `config/research.yaml`; the holdout remains untouched.

## Strategy verdicts

| Strategy | Evidence status | Verdict | Missing years |
|---|---|---|---|
{strategy_rows}

`REWORK` means redesign prospectively and collect forward evidence under a separately frozen
protocol. It does not mean that a performance test failed. XAUUSD may be researched separately in
the local contract simulator; it is never a substitute for executable Binance XAUT history.

## Baselines

| Baseline | Result |
|---|---|
{baseline_rows}

## Scenario matrix

| Scenario | Result |
|---|---|
{scenario_rows}

## Stress matrix

| Stress | Result |
|---|---|
| Costs x2 and x3 | NOT RUN — no eligible trades |
| Added tick slippage | NOT RUN — no eligible trades |
| One-bar entry delay | NOT RUN — no eligible trades |
| Parameter perturbation ±20% | NOT RUN — no eligible trades |
| Seeded trade-order reshuffle | NOT RUN — no eligible trades |
| Remove best 5% | NOT RUN — no eligible trades |

## Trial disclosure

- Empirical configurations tried: **0**.
- Validation looks: **0**.
- Synthetic contract tests exercise the frozen defaults but are not counted as empirical trials.
- No final-test authorization was requested and no final-test log entry was created.
"""


def write_report(output: Path, root: Path | None = None) -> Path:
    """Write the deterministic report, creating only its parent directory."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(root), encoding="utf-8")
    return output


def main() -> None:
    """Run the fail-closed coverage gate and print the report path."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/strategies/P07.md"))
    arguments = parser.parse_args()
    print(write_report(arguments.output))


if __name__ == "__main__":
    main()
