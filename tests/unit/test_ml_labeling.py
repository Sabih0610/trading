from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tb.ml.labeling import BarrierOutcome, CandidateSetup, LabelBar, label_candidates

_START = datetime(2024, 1, 1, tzinfo=UTC)


def _bar(index: int, *, high: str = "101", low: str = "99", close: str = "100") -> LabelBar:
    return LabelBar(
        timestamp=_START + timedelta(minutes=index),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


def _candidate(identifier: str, index: int = 0, holding: int = 2) -> CandidateSetup:
    return CandidateSetup(
        setup_id=identifier,
        timestamp=_START + timedelta(minutes=index),
        entry_price=Decimal("100"),
        stop_price=Decimal("95"),
        target_price=Decimal("105"),
        max_holding_bars=holding,
    )


def test_labels_win_loss_timeout_and_adverse_same_bar() -> None:
    win = label_candidates([_bar(0), _bar(1, high="106"), _bar(2)], [_candidate("win")])
    loss = label_candidates([_bar(0), _bar(1, low="94"), _bar(2)], [_candidate("loss")])
    both = label_candidates([_bar(0), _bar(1, high="106", low="94"), _bar(2)], [_candidate("both")])
    timeout = label_candidates(
        [_bar(0), _bar(1), _bar(2, high="102", close="102")], [_candidate("time")]
    )

    assert win[0].outcome is BarrierOutcome.WIN and win[0].meta_label == 1
    assert loss[0].outcome is BarrierOutcome.LOSS and loss[0].meta_label == 0
    assert both[0].outcome is BarrierOutcome.LOSS
    assert timeout[0].outcome is BarrierOutcome.TIMEOUT
    assert timeout[0].realized_return == Decimal("0.02")


def test_right_censored_candidate_is_omitted() -> None:
    assert label_candidates([_bar(0), _bar(1)], [_candidate("late", holding=2)]) == ()


def test_label_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="stop < entry"):
        CandidateSetup.model_validate(
            _candidate("bad").model_dump() | {"stop_price": Decimal("101")}
        )
    with pytest.raises(ValueError, match="strictly increasing"):
        label_candidates([_bar(1), _bar(0)], [])
    with pytest.raises(ValueError, match="does not align"):
        label_candidates([_bar(0), _bar(1), _bar(2)], [_candidate("missing", index=5)])
    with pytest.raises(ValueError, match="unique"):
        label_candidates([_bar(0), _bar(1), _bar(2)], [_candidate("same"), _candidate("same")])
