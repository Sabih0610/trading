"""Causality and parity tests for the shared feature engine."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

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


def test_partitioned_replay_matches_one_continuous_batch() -> None:
    bars = _bars(80)
    expected = compute_features_batch(bars)
    engine = FeatureEngine()

    observed = pl.concat(
        [
            compute_features_batch(bars.head(40), engine=engine),
            compute_features_batch(bars.tail(40), engine=engine),
        ],
        how="vertical_relaxed",
    )

    assert observed.equals(expected)


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


def test_confirmed_level_wick_and_reclaim_emits_sweep() -> None:
    bars = _bars(7).with_columns(
        pl.Series("high", [2.0, 3.0, 4.0, 10.0, 4.0, 3.0, 2.0]),
        pl.Series("low", [1.0] * 7),
        pl.Series("open", [1.5] * 7),
        pl.Series("close", [1.5] * 7),
    )
    engine = FeatureEngine()
    for row in bars.to_dicts():
        engine.update(row)
    sweep = bars.tail(1).to_dicts()[0]
    sweep.update(
        timestamp_utc=bars["timestamp_utc"][-1] + timedelta(minutes=1),
        high=11.0,
        low=8.0,
        open=9.0,
        close=9.0,
    )

    result = engine.update(sweep)

    assert result["sweep_event"] == "high_reclaimed"


def test_atr_filtered_three_bar_gap_is_created_causally() -> None:
    bars = _bars(16)
    rows = bars.to_dicts()
    rows[-1].update(open=110.0, high=111.0, low=109.0, close=110.0)
    engine = FeatureEngine()
    outputs = [engine.update(row) for row in rows]

    assert outputs[-1]["fvg_direction"] == "bullish"
    assert outputs[-1]["fvg_lower"] == pytest.approx(rows[-3]["high"])
