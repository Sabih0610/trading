"""Instrument-specific coverage assessment that never moves an existing holdout."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from tb.backtest.validation import FINAL_TEST_START, TRAIN_START
from tb.core.config import load_config
from tb.risk.config import PolicyModel


class InstrumentResearchPolicy(PolicyModel):
    """Verified venue inception plus immutable chronological research boundaries."""

    symbol: str
    venue: str
    market_inception: AwareDatetime | None = None
    inception_source: str | None = None
    requested_start: AwareDatetime = TRAIN_START
    validation_start: AwareDatetime = datetime(2024, 1, 1, tzinfo=UTC)
    holdout_start: AwareDatetime = FINAL_TEST_START

    @model_validator(mode="after")
    def preserve_holdout(self) -> Self:
        """Reject later locks, unsourced inception and overlapping discovery windows."""

        if self.holdout_start > FINAL_TEST_START:
            raise ValueError("Cannot move the existing final-test lock later")
        if not self.requested_start < self.validation_start < self.holdout_start:
            raise ValueError("Research boundaries must be chronological")
        if self.market_inception is not None and not self.inception_source:
            raise ValueError("Venue inception requires a primary source")
        return self


class ResearchPolicies(PolicyModel):
    """Human-edited venue-specific research plans."""

    schema_version: Literal[1]
    instruments: tuple[InstrumentResearchPolicy, ...]

    def policy(self, symbol: str) -> InstrumentResearchPolicy:
        """Return the instrument policy or refuse an unknown research route."""

        return next(item for item in self.instruments if item.symbol == symbol)


class ResearchCoverage(PolicyModel):
    """Manifest-verified coverage, with venue identity and synthetic provenance."""

    symbol: str
    venue: str
    first: AwareDatetime
    last: AwareDatetime
    rows: int = Field(gt=0)
    manifest_verified: bool
    synthetic: bool

    @model_validator(mode="after")
    def ordered(self) -> Self:
        """Reject inverted coverage."""

        if self.first > self.last:
            raise ValueError("Coverage is inverted")
        return self


class ResearchAssessment(PolicyModel):
    """Metadata assessment, not a strategy evaluation or permission to read a holdout."""

    status: Literal["INSUFFICIENT_HISTORY", "COVERAGE_ONLY"]
    reason: str
    train_start: AwareDatetime | None = None
    train_end_exclusive: AwareDatetime | None = None
    validation_start: AwareDatetime | None = None
    validation_end_exclusive: AwareDatetime | None = None
    empirical_trials: Literal[0] = 0


def load_research_policies() -> ResearchPolicies:
    """Load the repository-relative human research plan."""

    return load_config("research.yaml", ResearchPolicies)


def assess_research(
    policy: InstrumentResearchPolicy, coverage: ResearchCoverage | None
) -> ResearchAssessment:
    """Intersect authentic venue coverage with discovery windows without reading observations."""

    def insufficient(reason: str) -> ResearchAssessment:
        return ResearchAssessment(status="INSUFFICIENT_HISTORY", reason=reason)

    if policy.market_inception is not None and policy.market_inception >= policy.holdout_start:
        return insufficient(
            "Venue began after the existing final-test lock; collect forward evidence"
        )
    if coverage is None:
        return insufficient("No verified market-data volume is attached")
    if coverage.synthetic or not coverage.manifest_verified:
        return insufficient(
            "Synthetic or unverified data cannot establish real historical coverage"
        )
    if coverage.symbol != policy.symbol or coverage.venue != policy.venue:
        return insufficient(
            "Reference prices or another venue cannot substitute for instrument history"
        )
    start = max(policy.requested_start, coverage.first, policy.market_inception or TRAIN_START)
    if start >= policy.validation_start or coverage.last < policy.holdout_start:
        return insufficient("Insufficient separate training and validation coverage before holdout")
    return ResearchAssessment(
        status="COVERAGE_ONLY",
        reason="Coverage only; quality, samples and strategy value unproven",
        train_start=start,
        train_end_exclusive=policy.validation_start,
        validation_start=policy.validation_start,
        validation_end_exclusive=policy.holdout_start,
    )
