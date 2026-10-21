"""Deterministic cleaning, session tagging, and resampling for Silver market bars."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from statistics import median
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

import polars as pl

MarketKind = Literal["continuous", "weekday"]

_PRICE_COLUMNS = ("open", "high", "low", "close")
_REQUIRED_COLUMNS = ("timestamp_ns", *_PRICE_COLUMNS, "volume", "symbol", "source")
_TIMEFRAMES: dict[str, tuple[str, int, timedelta]] = {
    "5m": ("5m", 5, timedelta(minutes=5)),
    "15m": ("15m", 15, timedelta(minutes=15)),
    "1h": ("1h", 60, timedelta(hours=1)),
    "4h": ("4h", 240, timedelta(hours=4)),
    "1d": ("1d", 1440, timedelta(days=1)),
}
_LONDON = ZoneInfo("Europe/London")
_NEW_YORK = ZoneInfo("America/New_York")


class SilverValidationError(ValueError):
    """Raised when an input cannot satisfy the Silver bar contract."""


@dataclass(frozen=True)
class CleanResult:
    """Cleaned bars plus deterministic quality counters."""

    frame: pl.DataFrame
    input_rows: int
    duplicates_removed: int
    gap_count: int
    missing_minutes: int
    flagged_spikes: int


class _SessionColumns(TypedDict):
    session_asia: list[bool]
    session_london: list[bool]
    session_new_york: list[bool]
    is_weekend: list[bool]
    trading_day_id: list[str]


def _require_columns(frame: pl.DataFrame, required: tuple[str, ...]) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise SilverValidationError(f"Missing required columns: {', '.join(missing)}")


def _validate_canonical_values(frame: pl.DataFrame) -> None:
    if frame.is_empty():
        raise SilverValidationError("A Silver market partition cannot be empty")
    null_counts = frame.select(pl.col(_REQUIRED_COLUMNS).null_count()).row(0)
    if any(int(value) for value in null_counts):
        raise SilverValidationError("Required Silver values cannot be null")
    numeric = frame.select(pl.col((*_PRICE_COLUMNS, "volume")).cast(pl.Float64, strict=True))
    invalid_finite = numeric.select(
        pl.any_horizontal(pl.all().is_nan() | pl.all().is_infinite()).any()
    ).item()
    if bool(invalid_finite):
        raise SilverValidationError("Prices and volume must be finite")
    invalid_price = numeric.select(pl.any_horizontal(pl.col(_PRICE_COLUMNS) <= 0).any()).item()
    if bool(invalid_price):
        raise SilverValidationError("Prices must be positive")
    if bool(numeric.select((pl.col("volume") < 0).any()).item()):
        raise SilverValidationError("Volume cannot be negative")
    invalid_ohlc = numeric.select(
        (
            (pl.col("high") < pl.max_horizontal("open", "close", "low"))
            | (pl.col("low") > pl.min_horizontal("open", "close", "high"))
        ).any()
    ).item()
    if bool(invalid_ohlc):
        raise SilverValidationError("OHLC bounds are inconsistent")


def _past_only_spike_flags(
    closes: list[float],
    *,
    window: int,
    minimum_history: int,
    threshold: float,
) -> list[bool]:
    """Flag return outliers against prior returns only."""

    history: deque[float] = deque(maxlen=window)
    flags = [False]
    for previous, current in pairwise(closes):
        current_return = math.log(current / previous)
        flagged = False
        if len(history) >= minimum_history:
            center = median(history)
            mad = median(abs(value - center) for value in history)
            distance = abs(current_return - center)
            if mad > 0:
                flagged = distance / (1.4826 * mad) > threshold
            elif distance > 0:
                flagged = True
        flags.append(flagged)
        history.append(current_return)
    return flags


def _session_columns(timestamp_values: list[int]) -> _SessionColumns:
    asia: list[bool] = []
    london: list[bool] = []
    new_york: list[bool] = []
    weekend: list[bool] = []
    trading_days: list[str] = []
    for timestamp_ns in timestamp_values:
        instant = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=UTC)
        london_time = instant.astimezone(_LONDON).time()
        new_york_time = instant.astimezone(_NEW_YORK).time()
        asia.append(0 <= instant.hour < 8)
        london_clock = (london_time.hour, london_time.minute)
        new_york_clock = (new_york_time.hour, new_york_time.minute)
        london.append((8, 0) <= london_clock < (16, 30))
        new_york.append((9, 30) <= new_york_clock < (16, 0))
        weekend.append(instant.weekday() >= 5)
        trading_days.append(instant.date().isoformat())
    return {
        "session_asia": asia,
        "session_london": london,
        "session_new_york": new_york,
        "is_weekend": weekend,
        "trading_day_id": trading_days,
    }


def clean_minute_bars(
    frame: pl.DataFrame,
    *,
    market_kind: MarketKind,
    spike_window: int = 120,
    minimum_spike_history: int = 20,
    spike_threshold: float = 12.0,
) -> CleanResult:
    """Validate, order, deduplicate, and annotate canonical 1-minute bars."""

    if spike_window < 2 or minimum_spike_history < 2 or minimum_spike_history > spike_window:
        raise ValueError("Spike history bounds are invalid")
    if spike_threshold <= 0:
        raise ValueError("spike_threshold must be positive")
    _require_columns(frame, _REQUIRED_COLUMNS)
    _validate_canonical_values(frame)
    if frame["symbol"].n_unique() != 1 or frame["source"].n_unique() != 1:
        raise SilverValidationError("A market partition must contain one symbol and one source")

    input_rows = frame.height
    ordered = (
        frame.with_row_index("_source_order")
        .sort(["timestamp_ns", "_source_order"])
        .unique(subset=["timestamp_ns"], keep="last", maintain_order=True)
        .sort("timestamp_ns")
        .drop("_source_order")
        .with_columns(
            pl.col(_PRICE_COLUMNS).cast(pl.Float64, strict=True),
            pl.col("volume").cast(pl.Float64, strict=True),
            pl.col("timestamp_ns").cast(pl.Int64, strict=True),
        )
    )
    timestamp_values = ordered["timestamp_ns"].to_list()
    if any(current <= previous for previous, current in pairwise(timestamp_values)):
        raise SilverValidationError("Timestamps must be unique and increasing after deduplication")

    missing_minutes = [0]
    for previous, current in pairwise(timestamp_values):
        elapsed = current - previous
        if elapsed % 60_000_000_000 != 0:
            raise SilverValidationError("1-minute bar timestamps must lie on a one-minute cadence")
        missing_minutes.append(max(elapsed // 60_000_000_000 - 1, 0))

    session_values = _session_columns(timestamp_values)
    spike_flags = _past_only_spike_flags(
        ordered["close"].to_list(),
        window=spike_window,
        minimum_history=minimum_spike_history,
        threshold=spike_threshold,
    )
    annotated = ordered.with_columns(
        pl.from_epoch("timestamp_ns", time_unit="ns")
        .dt.replace_time_zone("UTC")
        .alias("timestamp_utc"),
        pl.Series("gap_minutes_before", missing_minutes, dtype=pl.Int64),
        pl.Series("is_spike", spike_flags, dtype=pl.Boolean),
        pl.Series("session_asia", session_values["session_asia"], dtype=pl.Boolean),
        pl.Series("session_london", session_values["session_london"], dtype=pl.Boolean),
        pl.Series("session_new_york", session_values["session_new_york"], dtype=pl.Boolean),
        pl.Series("is_weekend", session_values["is_weekend"], dtype=pl.Boolean),
        pl.Series("trading_day_id", session_values["trading_day_id"], dtype=pl.String),
        pl.lit(market_kind).alias("market_kind"),
    ).with_columns((pl.col("session_london") & pl.col("session_new_york")).alias("session_overlap"))
    gap_count = sum(value > 0 for value in missing_minutes)
    return CleanResult(
        frame=annotated,
        input_rows=input_rows,
        duplicates_removed=input_rows - annotated.height,
        gap_count=gap_count,
        missing_minutes=sum(missing_minutes),
        flagged_spikes=sum(spike_flags),
    )


def resample_completed_bars(
    minute_bars: pl.DataFrame,
    timeframe: str,
    *,
    cutoff: datetime,
) -> pl.DataFrame:
    """Aggregate left-closed bars whose right boundary is no later than cutoff."""

    if timeframe not in _TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")
    required = (
        "timestamp_utc",
        "symbol",
        "source",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "is_spike",
        "gap_minutes_before",
    )
    _require_columns(minute_bars, required)
    every, expected_rows, duration = _TIMEFRAMES[timeframe]
    sorted_bars = minute_bars.sort("timestamp_utc")
    result = (
        sorted_bars.group_by_dynamic(
            "timestamp_utc",
            every=every,
            period=every,
            closed="left",
            label="left",
        )
        .agg(
            pl.col("symbol").first(),
            pl.col("source").first(),
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
            pl.col("is_spike").any(),
            pl.col("gap_minutes_before").max().alias("max_gap_minutes_before"),
            pl.len().alias("source_rows"),
        )
        .with_columns(
            (pl.col("timestamp_utc") + duration).alias("bar_end_utc"),
            (pl.col("source_rows") == expected_rows).alias("has_all_source_minutes"),
            pl.lit(timeframe).alias("timeframe"),
        )
        .filter(pl.col("bar_end_utc") <= cutoff.astimezone(UTC))
        .sort("timestamp_utc")
    )
    return result


def align_xaut_xau_basis(xaut: pl.DataFrame, xau: pl.DataFrame) -> pl.DataFrame:
    """Create an exact-minute XAUT/XAU table; absent XAU minutes stay null."""

    _require_columns(xaut, ("timestamp_utc", "close"))
    _require_columns(xau, ("timestamp_utc", "close"))
    xaut_values = xaut.select("timestamp_utc", pl.col("close").cast(pl.Float64).alias("xaut_usd"))
    xau_values = xau.select("timestamp_utc", pl.col("close").cast(pl.Float64).alias("xau_usd"))
    return (
        xaut_values.join(xau_values, on="timestamp_utc", how="left", validate="1:1")
        .with_columns(
            pl.when(pl.col("xau_usd").is_not_null())
            .then((pl.col("xaut_usd") / pl.col("xau_usd") - 1.0) * 10_000.0)
            .otherwise(None)
            .alias("basis_bps")
        )
        .sort("timestamp_utc")
    )
