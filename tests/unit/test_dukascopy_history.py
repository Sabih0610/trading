"""Offline binary fixtures for Dukascopy M1 candles and recent XAU ticks."""

import lzma
import struct
from datetime import UTC, date, datetime

import pytest

from tb.ingest.history.dukascopy import candle_url, decode_candles, decode_ticks, tick_url


def _compress(raw: bytes) -> bytes:
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


def test_candle_url_uses_zero_based_month() -> None:
    assert candle_url("eurusd", date(2026, 1, 2), "BID").endswith(
        "/EURUSD/2026/00/02/BID_candles_min_1.bi5"
    )
    assert "/LIGHTCMDUSD/" in candle_url("WTI", date(2026, 1, 2), "ASK")


def test_candle_decoder_preserves_raw_fields_and_utc_time() -> None:
    record = struct.pack(">IIIIIf", 60, 110000, 110100, 109900, 110200, 12.5)

    frame = decode_candles(_compress(record), "EURUSD", date(2026, 1, 2), "BID")

    assert frame.height == 1
    assert frame["open_raw"][0] == 110000
    assert frame["price_scale"][0] == 100_000
    assert frame["timestamp_ns"][0] == 1_767_312_060_000_000_000
    assert frame["side"][0] == "BID"


def test_candle_decoder_rejects_bad_record_size_order_and_ohlc() -> None:
    with pytest.raises(ValueError, match="not divisible"):
        decode_candles(_compress(b"bad"), "EURUSD", date(2026, 1, 2), "ASK")
    duplicate_offsets = b"".join(
        [
            struct.pack(">IIIIIf", 60, 100, 100, 90, 110, 1.0),
            struct.pack(">IIIIIf", 60, 100, 100, 90, 110, 1.0),
        ]
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        decode_candles(_compress(duplicate_offsets), "EURUSD", date(2026, 1, 2), "ASK")
    invalid_ohlc = struct.pack(">IIIIIf", 60, 100, 100, 101, 110, 1.0)
    with pytest.raises(ValueError, match="internally inconsistent"):
        decode_candles(_compress(invalid_ohlc), "EURUSD", date(2026, 1, 2), "ASK")


def test_tick_decoder_is_xau_only_and_validates_spread() -> None:
    hour = datetime(2026, 7, 2, 5, tzinfo=UTC)
    record = struct.pack(">IIIff", 250, 3_300_100, 3_300_000, 1.5, 2.5)

    frame = decode_ticks(_compress(record), "XAUUSD", hour)

    assert frame["ask_raw"][0] == 3_300_100
    assert tick_url("XAUUSD", hour).endswith("/XAUUSD/2026/06/02/05h_ticks.bi5")
    with pytest.raises(ValueError, match="Only recent XAUUSD"):
        tick_url("EURUSD", hour)
    inverted = struct.pack(">IIIff", 250, 3_299_000, 3_300_000, 1.0, 1.0)
    with pytest.raises(ValueError, match="below bid"):
        decode_ticks(_compress(inverted), "XAUUSD", hour)
