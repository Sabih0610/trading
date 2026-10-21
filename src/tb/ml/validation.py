"""Interval-aware leakage checks and purged validation folds."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class LeakageDetectedError(ValueError):
    """Raised before model fitting when any feature was not yet knowable."""


class ModelSample(BaseModel):
    """One labeled setup with explicit feature and label availability times."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_id: str = Field(min_length=1)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    feature_known_at: tuple[AwareDatetime, ...]

    @model_validator(mode="after")
    def interval_is_ordered(self) -> ModelSample:
        if self.ends_at < self.starts_at:
            raise ValueError("sample label interval is inverted")
        return self


class PurgedFold(BaseModel):
    """Integer indices for one test block and its non-overlapping training rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def assert_leakage_free(samples: Sequence[ModelSample]) -> None:
    """Reject future-known features and unordered or duplicate setup rows."""

    identifiers: set[str] = set()
    previous: datetime | None = None
    for sample in samples:
        if sample.sample_id in identifiers:
            raise LeakageDetectedError("duplicate sample identifier")
        if previous is not None and sample.starts_at <= previous:
            raise LeakageDetectedError("samples must be strictly ordered by setup time")
        if any(known_at > sample.starts_at for known_at in sample.feature_known_at):
            raise LeakageDetectedError("feature was known after the candidate setup")
        identifiers.add(sample.sample_id)
        previous = sample.starts_at


def purged_kfold(
    samples: Sequence[ModelSample], *, n_splits: int, embargo: timedelta
) -> tuple[PurgedFold, ...]:
    """Build contiguous test folds and remove overlapping/embargoed training labels."""

    assert_leakage_free(samples)
    if n_splits < 2 or n_splits > len(samples):
        raise ValueError("n_splits must be between two and the sample count")
    if embargo < timedelta(0):
        raise ValueError("embargo cannot be negative")
    base, remainder = divmod(len(samples), n_splits)
    folds: list[PurgedFold] = []
    cursor = 0
    for fold_number in range(n_splits):
        width = base + int(fold_number < remainder)
        test_indices = tuple(range(cursor, cursor + width))
        test_start = samples[test_indices[0]].starts_at
        test_end = max(samples[index].ends_at for index in test_indices)
        embargo_end = test_end + embargo
        train_indices = tuple(
            index
            for index, sample in enumerate(samples)
            if index not in test_indices
            and (sample.ends_at < test_start or sample.starts_at > embargo_end)
        )
        folds.append(PurgedFold(train_indices=train_indices, test_indices=test_indices))
        cursor += width
    return tuple(folds)


def expanding_purged_folds(
    samples: Sequence[ModelSample], *, n_splits: int, embargo: timedelta
) -> tuple[PurgedFold, ...]:
    """Keep only past training indices from purged folds for deployment-like scoring."""

    return tuple(
        PurgedFold(
            train_indices=tuple(
                index
                for index in fold.train_indices
                if samples[index].ends_at < samples[fold.test_indices[0]].starts_at - embargo
            ),
            test_indices=fold.test_indices,
        )
        for fold in purged_kfold(samples, n_splits=n_splits, embargo=embargo)
        if fold.test_indices[0] > 0
    )
