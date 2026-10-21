"""Strict decoders for keyless Dukascopy candle and tick BI5 payloads."""

from __future__ import annotations

import lzma
import struct
from datetime import UTC, date, datetime, timedelta
from typing import Literal

import polars as pl

CANDLE_RECORD = struct.Struct(">IIIIIf")
TICK_RECORD = struct.Struct(">IIIff")
Side = Literal["BID", "ASK"]

KEYLESS_DATAFEED_BASE_URL = "https://datafeed.dukascopy.com/datafeed"

PRICE_SCALES: dict[str, int] = {
    "EURUSD": 100_000,
    "GBPUSD": 100_000,
    "USDCAD": 100_000,
    "USDCHF": 100_000,
    "USDSEK": 100_000,
    "USDJPY": 1_000,
    "XAUUSD": 1_000,
    "WTI": 1_000,
}
SOURCE_SYMBOLS = {"WTI": "LIGHTCMDUSD"}


def candle_url(symbol: str, day: date, side: Side) -> str:
    """Build the legacy keyless M1 candle URL with Dukascopy's zero-based month."""

    normalized = symbol.strip().upper()
    if normalized not in PRICE_SCALES:
        raise ValueError(f"Unsupported Dukascopy symbol: {normalized}")
    source_symbol = SOURCE_SYMBOLS.get(normalized, normalized)
    return (
        f"{KEYLESS_DATAFEED_BASE_URL}/{source_symbol}/{day.year:04d}/{day.month - 1:02d}/"
        f"{day.day:02d}/{side}_candles_min_1.bi5"
    )


def tick_url(symbol: str, hour: datetime) -> str:
    """Build a recent hourly tick URL; only XAUUSD ticks are allowlisted."""

    if hour.tzinfo is None or hour.utcoffset() is None:
        raise ValueError("Tick hour must be timezone-aware")
    instant = hour.astimezone(UTC)
    normalized = symbol.strip().upper()
    if normalized != "XAUUSD":
        raise ValueError("Only recent XAUUSD ticks are in the P02 scope")
    return (
        f"{KEYLESS_DATAFEED_BASE_URL}/{normalized}/{instant.year:04d}/"
        f"{instant.month - 1:02d}/{instant.day:02d}/{instant.hour:02d}h_ticks.bi5"
    )


def _decompress(payload: bytes, record_size: int) -> bytes:
    try:
        raw = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
    except lzma.LZMAError as exc:
        raise ValueError("Invalid Dukascopy LZMA-alone payload") from exc
    if len(raw) % record_size:
        raise ValueError(
            f"Decoded BI5 size {len(raw)} is not divisible by record size {record_size}"
        )
    return raw


def decode_candles(payload: bytes, symbol: str, day: date, side: Side) -> pl.DataFrame:
    """Decode raw M1 candle integers while retaining their original source fields."""

    normalized = symbol.strip().upper()
    try:
        scale = PRICE_SCALES[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown price scale for {normalized}") from exc
    raw = _decompress(payload, CANDLE_RECORD.size)
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    records: list[dict[str, int | float | str]] = []
    previous_seconds = -1
    for seconds, open_raw, close_raw, low_raw, high_raw, volume in CANDLE_RECORD.iter_unpack(raw):
        if seconds >= 86_400 or seconds <= previous_seconds:
            raise ValueError("Candle offsets must be strictly increasing within one UTC day")
        if not low_raw <= min(open_raw, close_raw) <= max(open_raw, close_raw) <= high_raw:
            raise ValueError("Candle OHLC values are internally inconsistent")
        previous_seconds = seconds
        timestamp = start + timedelta(seconds=seconds)
        records.append(
            {
                "timestamp_ns": int(timestamp.timestamp() * 1_000_000_000),
                "seconds_from_day_start": seconds,
                "open_raw": open_raw,
                "close_raw": close_raw,
                "low_raw": low_raw,
                "high_raw": high_raw,
                "volume": volume,
                "price_scale": scale,
                "side": side,
            }
        )
    return pl.DataFrame(records) if records else _empty_candles()


def _empty_candles() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "timestamp_ns": pl.Int64,
            "seconds_from_day_start": pl.Int64,
            "open_raw": pl.Int64,
            "close_raw": pl.Int64,
            "low_raw": pl.Int64,
            "high_raw": pl.Int64,
            "volume": pl.Float64,
            "price_scale": pl.Int64,
            "side": pl.String,
        }
    )


def decode_ticks(payload: bytes, symbol: str, hour: datetime) -> pl.DataFrame:
    """Decode recent hourly XAUUSD ticks with raw bid/ask integer prices."""

    if hour.tzinfo is None or hour.utcoffset() is None:
        raise ValueError("Tick hour must be timezone-aware")
    normalized = symbol.strip().upper()
    if normalized != "XAUUSD":
        raise ValueError("Only XAUUSD tick decoding is allowlisted")
    start = hour.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    raw = _decompress(payload, TICK_RECORD.size)
    records: list[dict[str, int | float]] = []
    previous_ms = -1
    for milliseconds, ask_raw, bid_raw, ask_volume, bid_volume in TICK_RECORD.iter_unpack(raw):
        if milliseconds >= 3_600_000 or milliseconds < previous_ms:
            raise ValueError("Tick offsets must be monotonic within one UTC hour")
        if ask_raw < bid_raw:
            raise ValueError("Tick ask price cannot be below bid price")
        previous_ms = milliseconds
        timestamp = start + timedelta(milliseconds=milliseconds)
        records.append(
            {
                "timestamp_ns": int(timestamp.timestamp() * 1_000_000_000),
                "milliseconds_from_hour_start": milliseconds,
                "ask_raw": ask_raw,
                "bid_raw": bid_raw,
                "ask_volume": ask_volume,
                "bid_volume": bid_volume,
                "price_scale": PRICE_SCALES[normalized],
            }
        )
    return (
        pl.DataFrame(records)
        if records
        else pl.DataFrame(
            schema={
                "timestamp_ns": pl.Int64,
                "milliseconds_from_hour_start": pl.Int64,
                "ask_raw": pl.Int64,
                "bid_raw": pl.Int64,
                "ask_volume": pl.Float64,
                "bid_volume": pl.Float64,
                "price_scale": pl.Int64,
            }
        )
    )
