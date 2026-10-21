"""Properties proving causal feature output is immune to later bars."""

from datetime import UTC, datetime, timedelta

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from tb.features.engine import compute_features_batch


def _bars(count: int) -> pl.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    closes = [100.0 + index / 10 for index in range(count)]
    return pl.DataFrame(
        {
            "timestamp_utc": [start + timedelta(minutes=index) for index in range(count)],
            "open": closes,
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "volume": [1.0] * count,
            "trading_day_id": ["2026-01-01"] * count,
            "session_asia": [True] * count,
            "session_london": [False] * count,
            "session_new_york": [False] * count,
        }
    )


@given(
    future_closes=st.lists(st.floats(min_value=1.0, max_value=1_000_000.0), min_size=1, max_size=20)
)
def test_random_future_bars_cannot_change_past(future_closes: list[float]) -> None:
    past = _bars(60)
    expected = compute_features_batch(past)
    start = past["timestamp_utc"][-1]
    future = pl.DataFrame(
        {
            "timestamp_utc": [
                start + timedelta(minutes=index + 1) for index in range(len(future_closes))
            ],
            "open": future_closes,
            "high": [value + 1 for value in future_closes],
            "low": [max(value - 1, 0.1) for value in future_closes],
            "close": future_closes,
            "volume": [1.0] * len(future_closes),
            "trading_day_id": ["2026-01-01"] * len(future_closes),
            "session_asia": [True] * len(future_closes),
            "session_london": [False] * len(future_closes),
            "session_new_york": [False] * len(future_closes),
        }
    )

    observed = compute_features_batch(pl.concat([past, future], how="vertical_relaxed")).head(60)

    assert observed.equals(expected)
