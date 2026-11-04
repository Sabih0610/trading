"""Pure, opt-in Treasury context on a strictly prior public-availability clock."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import polars as pl
from pydantic import AwareDatetime, model_validator

from tb.core.holdout import require_unsealed
from tb.ingest.treasury import END, START, publication_known_at
from tb.research.models import ResearchRefused
from tb.risk.config import PolicyModel

VERSION = "treasury-context-1.0.0"
COLUMNS = (
    "treasury_2y_pct",
    "treasury_10y_pct",
    "treasury_2s10s_pp",
    "treasury_2y_change_1d_pp",
    "treasury_10y_change_1d_pp",
    "treasury_2s10s_change_1d_pp",
)


class TreasuryFeature(PolicyModel):
    publication_date: date
    known_at: AwareDatetime
    treasury_2y_pct: Decimal | None
    treasury_10y_pct: Decimal | None
    treasury_2s10s_pp: Decimal | None
    treasury_2y_change_1d_pp: Decimal | None
    treasury_10y_change_1d_pp: Decimal | None
    treasury_2s10s_change_1d_pp: Decimal | None

    @model_validator(mode="after")
    def coherent(self) -> TreasuryFeature:
        if (
            not START <= self.publication_date <= END
            or self.known_at != publication_known_at(self.publication_date)
            or any(
                v is not None and not v.is_finite()
                for v in (getattr(self, column) for column in COLUMNS)
            )
        ):
            raise ResearchRefused("treasury_feature_scope_or_clock_invalid")
        return self


def gold_frame(silver: pl.DataFrame) -> pl.DataFrame:
    """Adjacent publication-day changes; no calendar row creation or interpolation."""
    require_unsealed(silver)
    if silver.is_empty():
        raise ResearchRefused("treasury_empty_silver")
    dates = silver["publication_date"].to_list()
    if any(not START <= d <= END for d in dates) or len(set(dates)) != len(dates):
        raise ResearchRefused("treasury_gold_date_scope_or_duplicates")
    ordered = silver.sort("publication_date").select(
        "publication_date",
        "known_at",
        pl.col("2y").alias("treasury_2y_pct"),
        pl.col("10y").alias("treasury_10y_pct"),
        (pl.col("10y") - pl.col("2y")).alias("treasury_2s10s_pp"),
    )
    return ordered.with_columns(
        (pl.col("treasury_2y_pct") - pl.col("treasury_2y_pct").shift(1)).alias(
            "treasury_2y_change_1d_pp"
        ),
        (pl.col("treasury_10y_pct") - pl.col("treasury_10y_pct").shift(1)).alias(
            "treasury_10y_change_1d_pp"
        ),
        (pl.col("treasury_2s10s_pp") - pl.col("treasury_2s10s_pp").shift(1)).alias(
            "treasury_2s10s_change_1d_pp"
        ),
    ).with_columns(pl.col(COLUMNS).cast(pl.Decimal(16, 6)))


class TreasuryContext:
    """Bounded immutable daily context with strict backward-as-of semantics."""

    def __init__(self, records: Sequence[TreasuryFeature]) -> None:
        self.records = tuple(records)
        if len(records) > 1200:
            raise ResearchRefused("treasury_context_row_bound")
        self._times = tuple(r.known_at for r in records)
        if any(b <= a for a, b in zip(self._times, self._times[1:], strict=False)):
            raise ResearchRefused("treasury_context_not_strictly_ordered")

    @classmethod
    def from_frame(cls, frame: pl.DataFrame) -> TreasuryContext:
        require_unsealed(frame)
        return cls(tuple(TreasuryFeature.model_validate(r) for r in frame.iter_rows(named=True)))

    def at(self, timestamp: datetime) -> dict[str, Any]:
        """The exact known_at event cannot use its own value; only a later bar can."""
        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset() != timedelta(0)
            or not datetime(2020, 10, 1, tzinfo=UTC) <= timestamp < datetime(2025, 1, 1, tzinfo=UTC)
        ):
            raise ResearchRefused("treasury_bar_clock_or_holdout_refused")
        index = bisect_left(self._times, timestamp) - 1
        if index < 0:
            return {
                "treasury_available": False,
                "treasury_known_at": None,
                **{column: None for column in COLUMNS},
            }
        record = self.records[index]
        return {
            "treasury_available": True,
            "treasury_known_at": record.known_at,
            **{column: getattr(record, column) for column in COLUMNS},
        }
