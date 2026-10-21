"""Pure safety-schema, cache, budget, and scoring tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from tb.agents.budget import load_ai_budget
from tb.agents.cache import ResponseCache, cache_key
from tb.agents.schemas import ArenaAnswer, MaskedSnapshot
from tb.agents.scoring import (
    brier_score,
    calibration_bins,
    error_correlation,
    hedge_weights,
    herding_flag,
    log_loss,
)


@pytest.mark.parametrize(
    "name", ["symbol", "timestamp_utc", "raw_close", "entry_price", "trade_date"]
)
def test_snapshot_rejects_identity_date_and_raw_price_fields(name: str) -> None:
    with pytest.raises(ValidationError, match="forbidden"):
        MaskedSnapshot(features={name: 1.0}, feature_set_version="v1")


def test_snapshot_hash_is_order_independent() -> None:
    left = MaskedSnapshot(features={"atr_zscore": 1.2, "trend_score": 2}, feature_set_version="v1")
    right = MaskedSnapshot(features={"trend_score": 2, "atr_zscore": 1.2}, feature_set_version="v1")
    assert left.content_hash() == right.content_hash()


def test_answer_cannot_increase_size() -> None:
    with pytest.raises(ValidationError):
        ArenaAnswer.model_validate(
            {
                "decision": "take",
                "confidence": 0.9,
                "reason_code": "TRY_ENLARGE",
                "key_risk": "attempt",
                "action": "reduce",
                "size_multiplier": 1.01,
            }
        )


def test_cache_hit_miss_and_expiry(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "cache.sqlite")
    now = datetime(2026, 10, 22, tzinfo=UTC)
    key = cache_key({"b": 2, "a": 1}, "model")
    assert cache.get(key, now=now) is None
    cache.put(key, "value", ttl_seconds=60, now=now)
    assert cache.get(key, now=now + timedelta(seconds=59)) == "value"
    assert cache.get(key, now=now + timedelta(seconds=60)) is None


def test_default_budget_is_strict_and_bounded() -> None:
    budget = load_ai_budget()
    assert budget.monthly_total_usd == 20.0
    assert all(policy.monthly_usd <= 20.0 for policy in budget.providers.values())
    assert not budget.providers["openai"].enabled


def test_scoring_and_ensemble_math() -> None:
    probabilities = [0.1, 0.8, 0.6, 0.2]
    outcomes = [0, 1, 0, 0]
    assert brier_score(probabilities, outcomes) == pytest.approx(0.1125)
    assert log_loss(probabilities, outcomes) > 0
    assert sum(item.count for item in calibration_bins(probabilities, outcomes, bins=5)) == 4
    weights = hedge_weights({"better": 0.1, "worse": 1.0})
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["better"] > weights["worse"]
    assert herding_flag(["same", "same"])
    assert not herding_flag(["same"])
    assert error_correlation([1.0, -1.0], [2.0, -2.0]) == pytest.approx(1.0)
