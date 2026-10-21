"""Bronze-to-canonical adapters for Silver 1-minute market bars."""

from __future__ import annotations

import polars as pl

from tb.silver.market import SilverValidationError


def binance_klines_to_canonical(
    frame: pl.DataFrame,
    *,
    symbol: str,
) -> pl.DataFrame:
    """Normalize published Binance spot klines without changing their observations."""

    required = {"open_time_ns", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise SilverValidationError(f"Missing Binance columns: {', '.join(missing)}")
    try:
        return frame.select(
            pl.col("open_time_ns").cast(pl.Int64, strict=True).alias("timestamp_ns"),
            pl.col("open").cast(pl.Float64, strict=True),
            pl.col("high").cast(pl.Float64, strict=True),
            pl.col("low").cast(pl.Float64, strict=True),
            pl.col("close").cast(pl.Float64, strict=True),
            pl.col("volume").cast(pl.Float64, strict=True),
            pl.lit(symbol.upper()).alias("symbol"),
            pl.lit("binance_spot").alias("source"),
        )
    except pl.exceptions.PolarsError as exc:
        raise SilverValidationError(f"Invalid Binance kline values: {exc}") from exc


def dukascopy_candles_to_canonical(
    frame: pl.DataFrame,
    *,
    symbol: str,
) -> pl.DataFrame:
    """Normalize paired Dukascopy BID/ASK candles to midpoint OHLC bars."""

    required = {
        "timestamp_ns",
        "open_raw",
        "high_raw",
        "low_raw",
        "close_raw",
        "volume",
        "price_scale",
        "side",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise SilverValidationError(f"Missing Dukascopy columns: {', '.join(missing)}")
    if set(frame["side"].unique().to_list()) != {"ASK", "BID"}:
        raise SilverValidationError("Dukascopy candles must contain BID and ASK sides")
    if bool(frame.select((pl.col("price_scale") <= 0).any()).item()):
        raise SilverValidationError("Dukascopy price_scale must be positive")

    value_columns = ["open_raw", "high_raw", "low_raw", "close_raw", "volume", "price_scale"]
    ask = frame.filter(pl.col("side") == "ASK").select(
        "timestamp_ns", *(pl.col(name).alias(f"{name}_ask") for name in value_columns)
    )
    bid = frame.filter(pl.col("side") == "BID").select(
        "timestamp_ns", *(pl.col(name).alias(f"{name}_bid") for name in value_columns)
    )
    if ask["timestamp_ns"].n_unique() != ask.height or bid["timestamp_ns"].n_unique() != bid.height:
        raise SilverValidationError("Dukascopy side timestamps must be unique")
    if set(ask["timestamp_ns"].to_list()) != set(bid["timestamp_ns"].to_list()):
        raise SilverValidationError("Dukascopy BID/ASK timestamps must pair exactly")

    paired = ask.join(bid, on="timestamp_ns", how="inner", validate="1:1")
    for suffix in ("ask", "bid"):
        if bool(paired.select((pl.col(f"price_scale_{suffix}") <= 0).any()).item()):
            raise SilverValidationError("Dukascopy price_scale must be positive")

    price_expressions = []
    for name in ("open", "high", "low", "close"):
        ask_price = pl.col(f"{name}_raw_ask") / pl.col("price_scale_ask")
        bid_price = pl.col(f"{name}_raw_bid") / pl.col("price_scale_bid")
        price_expressions.append(((ask_price + bid_price) / 2.0).alias(name))
    return paired.select(
        pl.col("timestamp_ns").cast(pl.Int64, strict=True),
        *price_expressions,
        ((pl.col("volume_ask") + pl.col("volume_bid")) / 2.0).alias("volume"),
        (
            pl.col("close_raw_ask") / pl.col("price_scale_ask")
            - pl.col("close_raw_bid") / pl.col("price_scale_bid")
        ).alias("close_spread"),
        pl.lit(symbol.upper()).alias("symbol"),
        pl.lit("dukascopy").alias("source"),
    )
