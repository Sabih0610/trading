"""Causal triple-barrier labels for every pre-existing strategy candidate."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class BarrierOutcome(StrEnum):
    """Adverse, favorable, or vertical-barrier outcome."""

    LOSS = "loss"
    WIN = "win"
    TIMEOUT = "timeout"


class LabelBar(BaseModel):
    """One completed bar used only after a candidate already exists."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    timestamp: AwareDatetime
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("label bar timestamp must use UTC")
        return value

    @model_validator(mode="after")
    def bounds_are_coherent(self) -> LabelBar:
        if self.high < max(self.low, self.close) or self.low > self.close:
            raise ValueError("label bar bounds are inconsistent")
        return self


class CandidateSetup(BaseModel):
    """Frozen entry/barrier terms emitted by a strategy before its outcome exists."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    setup_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    entry_price: Decimal = Field(gt=0)
    stop_price: Decimal = Field(gt=0)
    target_price: Decimal = Field(gt=0)
    max_holding_bars: int = Field(ge=1, le=10_000)

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("candidate timestamp must use UTC")
        return value

    @model_validator(mode="after")
    def long_barriers_are_ordered(self) -> CandidateSetup:
        if not self.stop_price < self.entry_price < self.target_price:
            raise ValueError("long candidate requires stop < entry < target")
        return self


class CandidateLabel(BaseModel):
    """Auditable meta-label with its full information interval."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    setup_id: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    outcome: BarrierOutcome
    meta_label: int = Field(ge=0, le=1)
    realized_return: Decimal
    bars_observed: int = Field(ge=1)


def label_candidates(
    bars: Sequence[LabelBar], candidates: Sequence[CandidateSetup]
) -> tuple[CandidateLabel, ...]:
    """Label candidates with adverse same-bar ordering and no right-censored rows."""

    if any(current.timestamp <= previous.timestamp for previous, current in pairwise(bars)):
        raise ValueError("label bars must be strictly increasing")
    index_by_time = {bar.timestamp: index for index, bar in enumerate(bars)}
    if len(index_by_time) != len(bars):
        raise ValueError("label bars contain duplicate timestamps")
    labels: list[CandidateLabel] = []
    seen_ids: set[str] = set()
    for candidate in candidates:
        if candidate.setup_id in seen_ids:
            raise ValueError("candidate setup identifiers must be unique")
        seen_ids.add(candidate.setup_id)
        setup_index = index_by_time.get(candidate.timestamp)
        if setup_index is None:
            raise ValueError("candidate timestamp does not align with label bars")
        evaluation = bars[setup_index + 1 : setup_index + 1 + candidate.max_holding_bars]
        if len(evaluation) < candidate.max_holding_bars:
            continue
        outcome = BarrierOutcome.TIMEOUT
        end_bar = evaluation[-1]
        realized = end_bar.close / candidate.entry_price - Decimal("1")
        observed = len(evaluation)
        for offset, bar in enumerate(evaluation, start=1):
            if bar.low <= candidate.stop_price:
                outcome = BarrierOutcome.LOSS
                end_bar = bar
                realized = candidate.stop_price / candidate.entry_price - Decimal("1")
                observed = offset
                break
            if bar.high >= candidate.target_price:
                outcome = BarrierOutcome.WIN
                end_bar = bar
                realized = candidate.target_price / candidate.entry_price - Decimal("1")
                observed = offset
                break
        labels.append(
            CandidateLabel(
                setup_id=candidate.setup_id,
                starts_at=candidate.timestamp,
                ends_at=end_bar.timestamp,
                outcome=outcome,
                meta_label=int(outcome is BarrierOutcome.WIN),
                realized_return=realized,
                bars_observed=observed,
            )
        )
    return tuple(labels)
