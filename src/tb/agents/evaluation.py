"""Reproducible, keyless P09 arena smoke run and report generation."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from tb.agents.arena import Arena
from tb.agents.budget import load_ai_budget
from tb.agents.cache import ResponseCache
from tb.agents.providers import MockProvider
from tb.agents.schemas import MaskedSnapshot
from tb.ingest.history.core import atomic_write_json
from tb.ledger import DecisionLedger, LedgerVersions


class ArenaSmokeReport(BaseModel):
    """Machine-readable proof that P09 works with no key or market data."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    generated_at_utc: str
    mode: str = "offline_mock"
    paid_calls: int = 0
    decision_id: str
    independent_answers: int = Field(ge=0)
    cross_reviews: int = Field(ge=0)
    hypotheses_queued: int = Field(ge=0)
    veto: bool
    size_multiplier: float = Field(ge=0.0, le=1.0)
    herding: bool
    exported_tables: int = Field(ge=0)
    final_test_reads: int = 0


def run_mock_evaluation(root: Path, *, now: datetime | None = None) -> ArenaSmokeReport:
    """Run the complete P09 path locally and export append-only evidence to Gold."""

    instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
    state = root / ".cache" / "p09"
    ledger = DecisionLedger(state / "decision-ledger.sqlite")
    arena = Arena(
        ledger=ledger,
        cache=ResponseCache(state / "response-cache.sqlite"),
        budget=load_ai_budget(config_dir=root / "config"),
        providers=[MockProvider()],
        versions=LedgerVersions(
            model_version="mock-v1",
            prompt_version="arena-p09-v1",
            question_set_version="pre-trade-review-v1",
            features_version="gold-features-v3-continuous-state",
        ),
    )
    result = arena.run(
        MaskedSnapshot(
            features={
                "trend_score": 0.4,
                "volatility_zscore": 1.2,
                "event_proximity_minutes": 90.0,
            },
            feature_set_version="gold-features-v3-continuous-state",
        ),
        questions=[
            "Does the feature-only evidence justify vetoing this existing setup?",
            "If not vetoed, should its risk-approved size be reduced?",
        ],
        now=instant,
    )
    exported = ledger.export_gold(root / "data" / "gold" / "ledger", exported_at=instant)
    report = ArenaSmokeReport(
        generated_at_utc=instant.isoformat(),
        decision_id=result.decision_id,
        independent_answers=sum(item.answer is not None for item in result.answers),
        cross_reviews=sum(item.answer is not None for item in result.cross_reviews),
        hypotheses_queued=len(result.hypotheses),
        veto=result.veto,
        size_multiplier=result.size_multiplier,
        herding=result.herding,
        exported_tables=len(exported),
    )
    atomic_write_json(root / "reports" / "arena" / "P09.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for the offline P09 acceptance run."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = run_mock_evaluation(args.root.resolve())
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
