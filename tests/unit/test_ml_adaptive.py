import math

import pytest

from tb.ml.adaptive import DynamicFairValueFilter, RecursiveRidge


@pytest.mark.parametrize("factory", [RecursiveRidge, DynamicFairValueFilter])
def test_adaptive_relationship_learns_without_using_current_target_in_prediction(
    factory: object,
) -> None:
    model = factory()  # type: ignore[operator]
    first = model.update(10.0, 21.0)
    assert first.predicted == 0.0

    last = first
    for value in range(11, 200):
        last = model.update(float(value), 1.0 + 2.0 * value)

    assert abs(last.residual) < 0.1
    assert last.uncertainty >= 0


def test_adaptive_filters_are_deterministic() -> None:
    left = DynamicFairValueFilter()
    right = DynamicFairValueFilter()
    assert [left.update(x, 3 + 0.5 * x) for x in range(20)] == [
        right.update(x, 3 + 0.5 * x) for x in range(20)
    ]


@pytest.mark.parametrize(
    "call",
    [
        lambda: RecursiveRidge(forgetting=0),
        lambda: RecursiveRidge(initial_precision=0),
        lambda: DynamicFairValueFilter(process_variance=-1),
        lambda: DynamicFairValueFilter(observation_variance=0),
        lambda: RecursiveRidge().update(math.nan, 1),
        lambda: DynamicFairValueFilter().update(1, math.inf),
    ],
)
def test_adaptive_inputs_fail_closed(call: object) -> None:
    with pytest.raises(ValueError):
        call()  # type: ignore[operator]
