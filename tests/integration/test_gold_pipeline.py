"""Integration tests for Gold feature materialization."""

from datetime import UTC, datetime, timedelta

import polars as pl

from tb.features.pipeline import build_feature_frame


def test_three_month_batch_equals_direct_stream() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    count = 24 * 90
    closes = [100.0 + index / 1000 for index in range(count)]
    frame = pl.DataFrame(
        {
            "timestamp_utc": [start + timedelta(hours=index) for index in range(count)],
            "open": closes,
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "volume": [1.0] * count,
            "symbol": ["BTCUSDT"] * count,
            "source": ["binance_spot"] * count,
        }
    )

    result = build_feature_frame(frame, timeframe="1h")

    assert result.height == count
    assert result["book_available"].all() is False
    assert result["atr14"].null_count() == 13


def test_higher_timeframe_structure_is_visible_only_after_bar_end() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    silver = pl.DataFrame(
        {
            "timestamp_utc": [start + timedelta(minutes=14), start + timedelta(minutes=15)],
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 100.0],
            "volume": [1.0, 1.0],
        }
    )
    higher = pl.DataFrame(
        {
            "bar_end_utc": [start + timedelta(minutes=15)],
            "structure_direction": [1],
        }
    )

    result = build_feature_frame(silver, timeframe="1m", higher_timeframe=higher)

    assert result["htf_structure_direction"].to_list() == [None, 1]
