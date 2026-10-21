"""Properties for Silver ordering, deduplication, and aggregation causality."""

from datetime import UTC, datetime, timedelta

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from tb.silver.market import clean_minute_bars, resample_completed_bars

_MINUTE_NS = 60_000_000_000
_START = datetime(2026, 1, 1, tzinfo=UTC)
_START_NS = int(_START.timestamp() * 1_000_000_000)


def _frame(offsets: list[int]) -> pl.DataFrame:
    values = [100.0 + index / 100 for index in range(len(offsets))]
    return pl.DataFrame(
        {
            "timestamp_ns": [_START_NS + offset * _MINUTE_NS for offset in offsets],
            "open": values,
            "high": [value + 1.0 for value in values],
            "low": [value - 1.0 for value in values],
            "close": values,
            "volume": [1.0] * len(values),
            "symbol": ["BTCUSDT"] * len(values),
            "source": ["test_feed"] * len(values),
        }
    )


@given(offsets=st.lists(st.integers(min_value=0, max_value=500), min_size=1, max_size=100))
def test_cleaned_timestamps_are_sorted_and_unique(offsets: list[int]) -> None:
    result = clean_minute_bars(_frame(offsets), market_kind="continuous")

    observed = result.frame["timestamp_ns"].to_list()
    assert observed == sorted(set(observed))
    assert result.duplicates_removed == len(offsets) - len(set(offsets))


@given(future_close=st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False))
def test_future_unfinished_value_cannot_change_completed_bar(future_close: float) -> None:
    clean = clean_minute_bars(_frame(list(range(5))), market_kind="continuous").frame
    baseline = resample_completed_bars(clean, "5m", cutoff=_START + timedelta(minutes=5))
    future = clean.tail(1).with_columns(
        pl.col("timestamp_ns") + _MINUTE_NS,
        (pl.col("timestamp_utc") + timedelta(minutes=1)).cast(
            pl.Datetime(time_unit="ns", time_zone="UTC")
        ),
        pl.lit(future_close).alias("open"),
        pl.lit(future_close + 1).alias("high"),
        pl.lit(max(future_close - 1, 0.1)).alias("low"),
        pl.lit(future_close).alias("close"),
    )

    observed = resample_completed_bars(
        pl.concat([clean, future]), "5m", cutoff=_START + timedelta(minutes=5)
    )

    assert observed.equals(baseline)
