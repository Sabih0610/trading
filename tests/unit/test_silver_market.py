"""Unit and scenario tests for Silver market cleaning."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from tb.silver.adapters import dukascopy_candles_to_canonical
from tb.silver.market import (
    SilverValidationError,
    align_xaut_xau_basis,
    clean_minute_bars,
    resample_completed_bars,
)

_MINUTE_NS = 60_000_000_000


def _bars(
    timestamps_ns: list[int],
    closes: list[float] | None = None,
    *,
    symbol: str = "BTCUSDT",
    source: str = "test_feed",
) -> pl.DataFrame:
    values = [100.0] * len(timestamps_ns) if closes is None else closes
    return pl.DataFrame(
        {
            "timestamp_ns": timestamps_ns,
            "open": values,
            "high": [value + 1 for value in values],
            "low": [value - 1 for value in values],
            "close": values,
            "volume": [1.0] * len(values),
            "symbol": [symbol] * len(values),
            "source": [source] * len(values),
        }
    )


def _ns(instant: datetime) -> int:
    return int(instant.timestamp() * 1_000_000_000)


def test_out_of_order_duplicates_are_sorted_and_last_observation_wins() -> None:
    start = _ns(datetime(2026, 1, 1, tzinfo=UTC))
    frame = _bars(
        [start + _MINUTE_NS, start, start + _MINUTE_NS],
        [101.0, 100.0, 102.0],
    )

    result = clean_minute_bars(frame, market_kind="continuous")

    assert result.frame["timestamp_ns"].to_list() == [start, start + _MINUTE_NS]
    assert result.frame["close"].to_list() == [100.0, 102.0]
    assert result.duplicates_removed == 1


def test_thirty_minute_outage_is_preserved_and_counted() -> None:
    start = _ns(datetime(2026, 1, 1, tzinfo=UTC))
    result = clean_minute_bars(_bars([start, start + 31 * _MINUTE_NS]), market_kind="continuous")

    assert result.frame["gap_minutes_before"].to_list() == [0, 30]
    assert result.gap_count == 1
    assert result.missing_minutes == 30


def test_flash_spike_is_flagged_but_not_removed() -> None:
    start = _ns(datetime(2026, 1, 1, tzinfo=UTC))
    timestamps = [start + index * _MINUTE_NS for index in range(25)]
    closes = [100.0] * 24 + [150.0]

    result = clean_minute_bars(
        _bars(timestamps, closes),
        market_kind="continuous",
        spike_window=20,
        minimum_spike_history=10,
    )

    assert result.frame.height == 25
    assert result.frame["is_spike"][-1]
    assert result.flagged_spikes == 1


def test_london_session_follows_dst() -> None:
    winter = datetime(2026, 1, 15, 8, 30, tzinfo=UTC)
    summer = datetime(2026, 7, 15, 7, 30, tzinfo=UTC)
    frame = _bars([_ns(winter), _ns(summer)])

    result = clean_minute_bars(frame, market_kind="weekday")

    assert result.frame["session_london"].to_list() == [True, True]


def test_weekend_crypto_is_tagged_without_being_removed() -> None:
    saturday = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)

    result = clean_minute_bars(_bars([_ns(saturday)]), market_kind="continuous")

    assert result.frame.height == 1
    assert result.frame["is_weekend"].to_list() == [True]


def test_resampling_excludes_unfinished_window_and_has_no_lookahead() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    timestamps = [_ns(start + timedelta(minutes=index)) for index in range(7)]
    clean = clean_minute_bars(_bars(timestamps), market_kind="continuous").frame

    first = resample_completed_bars(clean, "5m", cutoff=start + timedelta(minutes=7))
    extended = pl.concat(
        [
            clean,
            clean.tail(1).with_columns(
                pl.col("timestamp_ns") + _MINUTE_NS,
                (pl.col("timestamp_utc") + timedelta(minutes=1)).cast(
                    pl.Datetime(time_unit="ns", time_zone="UTC")
                ),
                pl.lit(10_000.0).alias("close"),
            ),
        ]
    )
    second = resample_completed_bars(extended, "5m", cutoff=start + timedelta(minutes=7))

    assert first.height == 1
    assert first.equals(second)
    assert first["bar_end_utc"].to_list() == [start + timedelta(minutes=5)]


def test_xaut_basis_is_null_when_exact_xau_minute_is_absent() -> None:
    start = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)
    xaut = pl.DataFrame(
        {"timestamp_utc": [start, start + timedelta(minutes=1)], "close": [2000.0, 2001.0]}
    )
    xau = pl.DataFrame({"timestamp_utc": [start], "close": [1990.0]})

    result = align_xaut_xau_basis(xaut, xau)

    assert result["basis_bps"][0] == pytest.approx((2000 / 1990 - 1) * 10_000)
    assert result["basis_bps"][1] is None


def test_xaut_basis_is_null_on_tagged_weekend_even_if_xau_row_exists() -> None:
    saturday = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)
    xaut = pl.DataFrame({"timestamp_utc": [saturday], "close": [2000.0]})
    xau = pl.DataFrame({"timestamp_utc": [saturday], "close": [1990.0], "is_weekend": [True]})

    result = align_xaut_xau_basis(xaut, xau)

    assert result["basis_bps"].to_list() == [None]


def test_invalid_ohlc_fails_closed() -> None:
    frame = _bars([_ns(datetime(2026, 1, 1, tzinfo=UTC))]).with_columns(pl.lit(50.0).alias("high"))

    with pytest.raises(SilverValidationError, match="OHLC"):
        clean_minute_bars(frame, market_kind="continuous")


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -1.0])
def test_invalid_numeric_values_fail_closed(bad_value: float) -> None:
    frame = _bars([_ns(datetime(2026, 1, 1, tzinfo=UTC))]).with_columns(
        pl.lit(bad_value).alias("close")
    )

    with pytest.raises(SilverValidationError):
        clean_minute_bars(frame, market_kind="continuous")


def test_empty_partition_fails_closed() -> None:
    with pytest.raises(SilverValidationError, match="cannot be empty"):
        clean_minute_bars(_bars([]), market_kind="continuous")


def test_unpaired_dukascopy_sides_fail_closed() -> None:
    frame = pl.DataFrame(
        {
            "timestamp_ns": [1, 2, 1],
            "open_raw": [100, 100, 99],
            "high_raw": [101, 101, 100],
            "low_raw": [99, 99, 98],
            "close_raw": [100, 100, 99],
            "volume": [1.0, 1.0, 1.0],
            "price_scale": [1, 1, 1],
            "side": ["ASK", "ASK", "BID"],
        }
    )

    with pytest.raises(SilverValidationError, match="pair exactly"):
        dukascopy_candles_to_canonical(frame, symbol="XAUUSD")
