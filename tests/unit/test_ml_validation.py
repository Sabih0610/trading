from datetime import UTC, datetime, timedelta

import pytest

from tb.ml.validation import (
    LeakageDetectedError,
    ModelSample,
    assert_leakage_free,
    combinatorial_purged_folds,
    expanding_purged_folds,
    purged_kfold,
)

_START = datetime(2024, 1, 1, tzinfo=UTC)


def _sample(index: int, *, duration: int = 1, future_feature: bool = False) -> ModelSample:
    starts = _START + timedelta(days=index)
    return ModelSample(
        sample_id=str(index),
        starts_at=starts,
        ends_at=starts + timedelta(days=duration),
        feature_known_at=(starts + timedelta(days=int(future_feature)),),
    )


def test_leakage_canary_is_rejected_before_splitting() -> None:
    with pytest.raises(LeakageDetectedError, match="known after"):
        purged_kfold([_sample(0), _sample(1, future_feature=True)], n_splits=2, embargo=timedelta())


def test_purge_removes_overlap_and_embargo_removes_following_rows() -> None:
    samples = [_sample(index, duration=2 if index == 0 else 0) for index in range(6)]

    folds = purged_kfold(samples, n_splits=3, embargo=timedelta(days=1))

    assert folds[0].test_indices == (0, 1)
    assert 2 not in folds[0].train_indices
    assert 3 not in folds[0].train_indices
    assert 4 in folds[0].train_indices
    assert 0 not in folds[1].train_indices


def test_expanding_folds_never_train_on_future_rows() -> None:
    samples = [_sample(index, duration=0) for index in range(8)]

    folds = expanding_purged_folds(samples, n_splits=4, embargo=timedelta())

    assert len(folds) == 3
    assert all(
        max(fold.train_indices) < min(fold.test_indices) for fold in folds if fold.train_indices
    )


def test_combinatorial_folds_cover_every_group_choice_and_purge() -> None:
    samples = [_sample(index, duration=1) for index in range(8)]

    folds = combinatorial_purged_folds(samples, n_groups=4, test_groups=2, embargo=timedelta())

    assert len(folds) == 6
    assert all(len(fold.test_indices) == 4 for fold in folds)
    for fold in folds:
        assert not set(fold.train_indices) & set(fold.test_indices)
        assert all(
            samples[train].ends_at < samples[test].starts_at
            or samples[train].starts_at > samples[test].ends_at
            for train in fold.train_indices
            for test in fold.test_indices
        )


def test_validation_inputs_fail_closed() -> None:
    with pytest.raises(LeakageDetectedError, match="strictly ordered"):
        assert_leakage_free([_sample(1), _sample(0)])
    with pytest.raises(ValueError, match="n_splits"):
        purged_kfold([_sample(0)], n_splits=2, embargo=timedelta())
    with pytest.raises(ValueError, match="embargo"):
        purged_kfold([_sample(0), _sample(1)], n_splits=2, embargo=timedelta(days=-1))
    with pytest.raises(ValueError, match="test_groups"):
        combinatorial_purged_folds(
            [_sample(0), _sample(1)],
            n_groups=2,
            test_groups=2,
            embargo=timedelta(),
        )
