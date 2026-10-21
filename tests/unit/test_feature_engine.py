"""Causality and parity tests for the shared feature engine."""

from datetime import UTC, datetime, timedelta

import polars as pl

from tb.features.engine import FeatureEngine, compute_features_batch


def _bars(count: int) -> pl.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    closes = [100.0 + index * 0.1 for index in range(count)]
    return pl.DataFrame(
        {
            "timestamp_utc": [start + timedelta(minutes=index) for index in range(count)],
            "open": closes,
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "volume": [2.0] * count,
            "trading_day_id": ["2026-01-01"] * count,
            "session_asia": [True] * count,
            "session_london": [False] * count,
            "session_new_york": [False] * count,
        }
    )


def test_batch_and_streaming_are_identical() -> None:
    bars = _bars(80)
    engine = FeatureEngine()
    streamed = pl.DataFrame(
        [engine.update(row) for row in bars.to_dicts()], infer_schema_length=None
    )

    batch = compute_features_batch(bars)

    assert batch.equals(streamed)


def test_future_poisoning_cannot_change_past_features() -> None:
    bars = _bars(40)
    past = compute_features_batch(bars)
    future = (
        _bars(50)
        .tail(10)
        .with_columns(
            pl.col("timestamp_utc") + timedelta(days=1),
            pl.lit(1_000_000.0).alias("close"),
            pl.lit(1_000_001.0).alias("high"),
            pl.lit(999_999.0).alias("low"),
            pl.lit(1_000_000.0).alias("open"),
        )
    )

    poisoned = compute_features_batch(pl.concat([bars, future], how="vertical_relaxed"))

    assert poisoned.head(40).equals(past)


def test_gap_resets_continuity_dependent_warmup() -> None:
    bars = _bars(25)
    rows = bars.to_dicts()
    rows[-1]["timestamp_utc"] += timedelta(minutes=30)
    engine = FeatureEngine()
    outputs = [engine.update(row) for row in rows]

    assert outputs[-1]["input_gap"] is True
    assert outputs[-1]["log_return"] is None
    assert outputs[-1]["atr14"] is None


def test_pivot_is_visible_only_after_three_right_bars() -> None:
    bars = _bars(7).with_columns(
        pl.Series("high", [2.0, 3.0, 4.0, 10.0, 4.0, 3.0, 2.0]),
        pl.Series("low", [1.0] * 7),
        pl.Series("open", [1.5] * 7),
        pl.Series("close", [1.5] * 7),
    )
    engine = FeatureEngine()
    outputs = [engine.update(row) for row in bars.to_dicts()]

    assert all(row["confirmed_swing_high"] is None for row in outputs[:6])
    assert outputs[6]["confirmed_swing_high"] == 10.0
