"""Owned gap-label regressions; no model fitting or provider inputs."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.ml.labeling import BarrierOutcome, CandidateSetup, LabelBar, label_candidates

START = datetime(2023, 6, 5, 12, tzinfo=UTC)


def bar(index, *, open="100", high="101", low="99", close="100"):
    return LabelBar(
        timestamp=START + timedelta(minutes=5 * index),
        **{
            name: Decimal(value)
            for name, value in {"open": open, "high": high, "low": low, "close": close}.items()
        },
    )


def candidate(holding=1):
    return CandidateSetup(
        setup_id="owned",
        timestamp=START,
        entry_price=100,
        stop_price=95,
        target_price=110,
        max_holding_bars=holding,
    )


@pytest.mark.parametrize(
    "open,high,low,close,price",
    [
        ("90", "94", "89", "91", "90"),
        ("90", "112", "89", "111", "90"),  # gap loss wins over a later target print
        ("95", "100", "94", "99", "95"),
        ("100", "112", "94", "111", "95"),  # no gap: original adverse same-bar ordering
        ("100", "101", "95", "99", "95"),  # exact stop touch
    ],
)
def test_gap_loss_uses_open_or_stop_whichever_is_lower(open, high, low, close, price):
    evaluation = bar(1, open=open, high=high, low=low, close=close)
    (label,) = label_candidates([bar(0), evaluation], [candidate()])
    assert label.outcome is BarrierOutcome.LOSS and label.meta_label == 0
    assert label.realized_return == Decimal(price) / Decimal("100") - 1
    assert label.ends_at == evaluation.timestamp and label.bars_observed == 1


def test_future_gap_cannot_change_a_label_that_already_hit_its_target():
    first = [bar(0), bar(1, high="111"), bar(2)]
    future = [*first[:2], bar(2, open="50", high="55", low="45", close="51")]
    before = label_candidates(first, [candidate(holding=2)])
    after = label_candidates(future, [candidate(holding=2)])
    assert before == after
    assert before[0].outcome is BarrierOutcome.WIN
    assert before[0].realized_return == Decimal("0.1")


def test_unknown_open_is_refused_instead_of_invented_from_close_or_stop():
    payload = bar(0).model_dump(exclude={"open"})
    with pytest.raises(ValidationError, match="open"):
        LabelBar.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("open", "0"),
        ("open", "NaN"),
        ("open", "Infinity"),
        ("open", "102"),
        ("open", "98"),
        ("high", "98"),
        ("low", "102"),
    ],
)
def test_label_ohlc_refuses_invalid_open_and_inconsistent_bounds(field, value):
    payload = bar(0).model_dump() | {field: Decimal(value)}
    with pytest.raises(ValidationError):
        LabelBar.model_validate(payload)


def test_gap_label_preserves_censoring_and_does_not_create_candidates():
    gap = [bar(0), bar(1, open="90", high="94", low="89", close="91")]
    assert label_candidates(gap, []) == ()
    assert label_candidates(gap, [candidate(holding=2)]) == ()
