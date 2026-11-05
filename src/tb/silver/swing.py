"""UTC daily/weekly bars with explicit calendar coverage and causal shared features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import polars as pl

from tb.core.holdout import require_unsealed
from tb.features.engine import FeatureEngine
from tb.features.swing import SWING_FLOAT_FIELDS
from tb.research.models import HOLDOUT, ResearchRefused, digest
from tb.silver.forex import calendar_grid

SWING_VERSION = "swing-medallion-v1"
COVERAGE_THRESHOLD = 0.95
PERIODS = {"1d": timedelta(days=1), "1w": timedelta(weeks=1)}
_OHLC = ("open", "high", "low", "close")
_COUNTS = ("observed_minutes", "observed_expected_minutes", "unexpected_minutes")
_BAR_COLUMNS = (
    "timestamp_utc",
    "bar_end_utc",
    "symbol",
    "source",
    "price_side",
    "timeframe",
    *_OHLC,
    "volume",
    "first_observed_minute_utc",
    "last_observed_minute_utc",
    *_COUNTS,
    "expected_minutes",
    "coverage_ratio",
    "market_closed",
    "window_closed",
    "window_within_scope",
    "complete",
    "calendar_conflict",
    "coverage_available_at",
    "history_barrier",
    "calendar_identity",
    "calendar_is_reference_model",
)


@dataclass(frozen=True)
class CalendarClosure:
    """Predeclared left-closed UTC reference interval, never inferred from absent data."""

    start: datetime
    stop: datetime
    evidence: str
    label: str

    def __post_init__(self) -> None:
        if (
            self.start.utcoffset() != timedelta(0)
            or self.stop.utcoffset() != timedelta(0)
            or self.stop <= self.start
            or not self.evidence.startswith("https://")
            or not self.label
        ):
            raise ValueError("Invalid evidence-bearing UTC calendar closure")
        if any((t.second or t.microsecond) for t in (self.start, self.stop)):
            raise ValueError("Calendar closure must be minute-aligned")


@dataclass(frozen=True)
class SwingCalendar:
    """An explicit source identity, session model and frozen reference closures."""

    symbol: str
    source: str
    price_side: str
    calendar_id: str
    closures: tuple[CalendarClosure, ...] = ()
    reference_only: bool = False

    def __post_init__(self) -> None:
        continuous = self.symbol in {"BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"}
        gold = self.symbol == "XAUUSD"
        if (
            not self.calendar_id
            or not (continuous or gold)
            or (continuous and (self.source != "binance_vision" or self.price_side != "trade"))
            or (continuous and (self.closures or self.reference_only))
            or (gold and (self.source != "histdata" or self.price_side != "bid"))
            or (gold and not self.reference_only)
        ):
            raise ValueError("Swing calendar source identity refused")

    @property
    def identity(self) -> str:
        """Hash all declared semantics before any price-bearing source access."""
        return digest(
            {
                "version": SWING_VERSION,
                "calendar_id": self.calendar_id,
                "symbol": self.symbol,
                "source": self.source,
                "price_side": self.price_side,
                "reference_only": self.reference_only,
                "threshold": COVERAGE_THRESHOLD,
                "closures": [
                    {
                        "start": item.start.isoformat(),
                        "stop": item.stop.isoformat(),
                        "evidence": item.evidence,
                        "label": item.label,
                    }
                    for item in self.closures
                ],
            }
        )

    def grid(self, start: datetime, stop: datetime) -> pl.DataFrame:
        """Return calendar expectations, not observed or interpolated price data."""
        if self.symbol == "XAUUSD":
            frame = calendar_grid(start, stop, "histdata", "XAUUSD").select(
                "timestamp_utc", pl.col("expected_open").alias("expected_open")
            )
        else:
            frame = pl.DataFrame(
                {
                    "timestamp_utc": pl.datetime_range(
                        start, stop, interval="1m", closed="left", time_unit="ns", eager=True
                    )
                }
            ).with_columns(pl.lit(True).alias("expected_open"))
        expression = pl.col("expected_open")
        for item in self.closures:
            expression = expression & ~(
                (pl.col("timestamp_utc") >= item.start) & (pl.col("timestamp_utc") < item.stop)
            )
        return frame.with_columns(expression.alias("expected_open"))


def _bounds(start: datetime, stop: datetime, timeframe: str) -> tuple[datetime, datetime]:
    if (
        timeframe not in PERIODS
        or start.utcoffset() != timedelta(0)
        or stop.utcoffset() != timedelta(0)
        or start >= stop
        or stop > HOLDOUT
    ):
        raise ResearchRefused("swing_window_outside_pre_holdout_scope")
    left = datetime(start.year, start.month, start.day, tzinfo=UTC)
    if timeframe == "1w":
        left -= timedelta(days=left.weekday())
    duration = PERIODS[timeframe]
    right = left
    while right < stop:
        right += duration
    return left, right


def _expectations(
    start: datetime, stop: datetime, timeframe: str, calendar: SwingCalendar
) -> pl.DataFrame:
    left, right = _bounds(start, stop, timeframe)
    if calendar.symbol != "XAUUSD":
        return pl.DataFrame(
            {
                "timestamp_utc": pl.datetime_range(
                    left, right, interval=timeframe, closed="left", time_unit="ns", eager=True
                )
            }
        ).with_columns(
            pl.lit(int(PERIODS[timeframe].total_seconds() // 60))
            .cast(pl.Int64)
            .alias("expected_minutes")
        )
    return (
        calendar.grid(left, right)
        .group_by_dynamic("timestamp_utc", every=timeframe, closed="left", start_by="monday")
        .agg(pl.col("expected_open").sum().cast(pl.Int64).alias("expected_minutes"))
    )


def _validate_minutes(
    frame: pl.DataFrame, start: datetime, stop: datetime, calendar: SwingCalendar
) -> None:
    require_unsealed(frame)
    required = {"timestamp_utc", "symbol", "source", "price_side", *_OHLC}
    if not required.issubset(frame.columns):
        raise ResearchRefused("swing_minute_schema_missing")
    if frame.is_empty():
        return
    if frame.height > 2_000_000:
        raise ResearchRefused("swing_minutes_exceed_bounded_year")
    stamps = frame["timestamp_utc"]
    if stamps.dtype != pl.Datetime("ns", "UTC"):
        raise ResearchRefused("swing_minutes_require_utc_nanoseconds")
    if (
        stamps.null_count()
        or frame.filter(
            (pl.col("timestamp_utc") < start)
            | (pl.col("timestamp_utc") >= stop)
            | (pl.col("timestamp_utc") >= HOLDOUT)
        ).height
    ):
        raise ResearchRefused("swing_minute_outside_admitted_window")
    nanos = stamps.dt.epoch("ns")
    if (
        nanos.n_unique() != frame.height
        or not nanos.is_sorted()
        or (nanos % 60_000_000_000 != 0).any()
    ):
        raise ResearchRefused("swing_minutes_not_unique_ordered_aligned")
    if frame.filter(
        pl.col("symbol").is_null()
        | (pl.col("symbol") != calendar.symbol)
        | pl.col("source").is_null()
        | (pl.col("source") != calendar.source)
        | pl.col("price_side").is_null()
        | (pl.col("price_side") != calendar.price_side)
    ).height:
        raise ResearchRefused("swing_minute_source_labels_changed")
    invalid = ~pl.all_horizontal(
        pl.col(name).is_not_null() & pl.col(name).is_finite() & (pl.col(name) > 0) for name in _OHLC
    )
    invalid = invalid | (pl.col("high") < pl.max_horizontal(*_OHLC))
    invalid = invalid | (pl.col("low") > pl.min_horizontal(*_OHLC))
    if frame.filter(invalid).height:
        raise ResearchRefused("swing_minute_ohlc_invalid")
    if calendar.price_side == "trade" and (
        "volume" not in frame.columns
        or frame.filter(
            pl.col("volume").is_null() | ~pl.col("volume").is_finite() | (pl.col("volume") < 0)
        ).height
    ):
        raise ResearchRefused("swing_trade_volume_invalid")


def _finish(
    values: pl.DataFrame,
    *,
    start: datetime,
    stop: datetime,
    timeframe: str,
    calendar: SwingCalendar,
) -> pl.DataFrame:
    result = _expectations(start, stop, timeframe, calendar).join(
        values, on="timestamp_utc", how="left", validate="1:1"
    )
    return (
        result.with_columns(pl.col(name).fill_null(0).cast(pl.Int64) for name in _COUNTS)
        .with_columns(
            (pl.col("timestamp_utc") + PERIODS[timeframe]).alias("bar_end_utc"),
            pl.lit(calendar.symbol).alias("symbol"),
            pl.lit(calendar.source).alias("source"),
            pl.lit(calendar.price_side).alias("price_side"),
            pl.lit(timeframe).alias("timeframe"),
            pl.lit(calendar.identity).alias("calendar_identity"),
            pl.lit(calendar.reference_only).alias("calendar_is_reference_model"),
        )
        .with_columns(
            (pl.col("expected_minutes") == 0).alias("market_closed"),
            (pl.col("bar_end_utc") <= stop).alias("window_closed"),
            ((pl.col("timestamp_utc") >= start) & (pl.col("bar_end_utc") <= stop)).alias(
                "window_within_scope"
            ),
            pl.when(pl.col("expected_minutes") > 0)
            .then(pl.col("observed_expected_minutes") / pl.col("expected_minutes"))
            .otherwise(None)
            .alias("coverage_ratio"),
        )
        .with_columns(
            (
                (pl.col("coverage_ratio") >= COVERAGE_THRESHOLD)
                & pl.col("window_closed")
                & pl.col("window_within_scope")
                & (pl.col("unexpected_minutes") == 0)
            )
            .fill_null(False)
            .alias("complete"),
            (pl.col("unexpected_minutes") > 0).alias("calendar_conflict"),
        )
        .with_columns(
            pl.when(pl.col("window_closed"))
            .then(pl.col("bar_end_utc"))
            .otherwise(None)
            .alias("coverage_available_at"),
            (
                pl.col("window_closed")
                & ~pl.col("complete")
                & (~pl.col("market_closed") | pl.col("calendar_conflict"))
            ).alias("history_barrier"),
        )
        .select(*_BAR_COLUMNS)
        .sort("timestamp_utc")
    )


def aggregate_daily(
    frame: pl.DataFrame, *, start: datetime, stop: datetime, calendar: SwingCalendar
) -> pl.DataFrame:
    """Aggregate one bounded source slice; missing/closed windows retain null OHLC."""
    _bounds(start, stop, "1d")
    _validate_minutes(frame, start, stop, calendar)
    if frame.is_empty():
        values = pl.DataFrame(
            schema={
                "timestamp_utc": pl.Datetime("ns", "UTC"),
                "first_observed_minute_utc": pl.Datetime("ns", "UTC"),
                "last_observed_minute_utc": pl.Datetime("ns", "UTC"),
                **dict.fromkeys((*_OHLC, "volume"), pl.Float64),
                **dict.fromkeys(_COUNTS, pl.Int64),
            }
        )
    else:
        flags = calendar.grid(start, stop)
        observed = frame.join(flags, on="timestamp_utc", how="left", validate="1:1")
        values = observed.group_by_dynamic(
            "timestamp_utc", every="1d", closed="left", start_by="monday"
        ).agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("timestamp_utc").first().alias("first_observed_minute_utc"),
            pl.col("timestamp_utc").last().alias("last_observed_minute_utc"),
            (
                pl.col("volume").sum()
                if calendar.price_side == "trade"
                else pl.lit(None, dtype=pl.Float64)
            ).alias("volume"),
            pl.len().cast(pl.Int64).alias("observed_minutes"),
            pl.col("expected_open").sum().cast(pl.Int64).alias("observed_expected_minutes"),
            (~pl.col("expected_open")).sum().cast(pl.Int64).alias("unexpected_minutes"),
        )
    return _finish(values, start=start, stop=stop, timeframe="1d", calendar=calendar)


def aggregate_weekly(
    daily: pl.DataFrame, *, start: datetime, stop: datetime, calendar: SwingCalendar
) -> pl.DataFrame:
    """Sum observed minute counts across days; full Monday weeks keep boundary flags."""
    require_unsealed(daily)
    _bounds(start, stop, "1w")
    if daily.is_empty() or daily.filter(pl.col("timeframe") != "1d").height:
        raise ResearchRefused("swing_weekly_requires_daily_windows")
    if daily["timestamp_utc"].n_unique() != daily.height:
        raise ResearchRefused("swing_weekly_duplicate_day")
    if daily.filter(
        (pl.col("timestamp_utc") >= stop)
        | (pl.col("first_observed_minute_utc") < start)
        | (pl.col("last_observed_minute_utc") >= stop)
    ).height:
        raise ResearchRefused("swing_weekly_future_or_prior_source_refused")
    if daily.filter(
        (pl.col("symbol") != calendar.symbol)
        | (pl.col("source") != calendar.source)
        | (pl.col("price_side") != calendar.price_side)
        | (pl.col("calendar_identity") != calendar.identity)
        | (pl.col("timestamp_utc") >= HOLDOUT)
    ).height:
        raise ResearchRefused("swing_weekly_identity_changed")
    values = (
        daily.sort("timestamp_utc")
        .group_by_dynamic("timestamp_utc", every="1w", closed="left", start_by="monday")
        .agg(
            pl.col("open").drop_nulls().first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").drop_nulls().last(),
            pl.col("first_observed_minute_utc").min(),
            pl.col("last_observed_minute_utc").max(),
            (
                pl.when(pl.col("observed_minutes").sum() > 0).then(pl.col("volume").sum())
                if calendar.price_side == "trade"
                else pl.lit(None, dtype=pl.Float64)
            ).alias("volume"),
            *(pl.col(name).sum().cast(pl.Int64) for name in _COUNTS),
        )
    )
    return _finish(values, start=start, stop=stop, timeframe="1w", calendar=calendar)


def add_swing_features(frame: pl.DataFrame, *, timeframe: str) -> pl.DataFrame:
    """Use FeatureEngine only on complete windows; known closed windows don't reset history."""
    require_unsealed(frame)
    if timeframe not in PERIODS:
        raise ValueError("Unknown swing timeframe")
    engine = FeatureEngine(timeframe=PERIODS[timeframe])
    interrupted = True
    records = []
    datetimes = (
        "confirmed_swing_high_bar_utc",
        "confirmed_swing_low_bar_utc",
        "swing_high_confirmed_at",
        "swing_low_confirmed_at",
        "available_at",
    )
    for bar in frame.sort("timestamp_utc").iter_rows(named=True):
        if bar["complete"]:
            features = engine.update_swing(bar, calendar_contiguous=not interrupted)
            interrupted = False
            records.append({**bar, **features, "feature_computed": True})
        else:
            if not bar["market_closed"] or bar["calendar_conflict"]:
                interrupted = True
            records.append(
                {
                    **bar,
                    **dict.fromkeys(SWING_FLOAT_FIELDS),
                    **dict.fromkeys(datetimes),
                    "swing_input_gap": None,
                    "feature_computed": False,
                }
            )
    result = pl.DataFrame(records, infer_schema_length=None)
    if result.is_empty():
        return frame
    return result.with_columns(
        *(pl.col(name).cast(pl.Float64) for name in (*_OHLC, "volume", *SWING_FLOAT_FIELDS)),
        pl.col("timestamp_utc", "bar_end_utc").cast(pl.Datetime("ns", "UTC")),
        *(
            pl.col(name).cast(pl.Datetime("ns", "UTC"))
            for name in (
                "first_observed_minute_utc",
                "last_observed_minute_utc",
                "coverage_available_at",
            )
            if name in result.columns
        ),
        *(pl.col(name).cast(pl.Datetime("ns", "UTC")) for name in datetimes),
        pl.col("swing_input_gap").cast(pl.Boolean),
    )
