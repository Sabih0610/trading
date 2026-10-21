"""Point-in-time context and live-book feature calculations."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import polars as pl


def add_event_proximity(features: pl.DataFrame, calendar: pl.DataFrame) -> pl.DataFrame:
    """Add minutes to the next high-impact schedule already known at each bar."""

    if "timestamp_utc" not in features.columns:
        raise ValueError("features require timestamp_utc")
    required = {"timestamp_utc", "known_at", "importance"}
    missing = sorted(required.difference(calendar.columns))
    if missing:
        raise ValueError(f"calendar is missing: {', '.join(missing)}")
    events = calendar.filter(pl.col("importance") == "high").select("timestamp_utc", "known_at")
    event_rows = events.to_dicts()
    values: list[float | None] = []
    for bar_time in features["timestamp_utc"].to_list():
        if not isinstance(bar_time, datetime):
            raise ValueError("feature timestamps must be datetimes")
        candidates = [
            row["timestamp_utc"]
            for row in event_rows
            if row["known_at"] <= bar_time <= row["timestamp_utc"]
        ]
        next_event = min(candidates) if candidates else None
        values.append(None if next_event is None else (next_event - bar_time).total_seconds() / 60)
    return features.with_columns(
        pl.Series("minutes_to_high_impact_event", values, dtype=pl.Float64)
    )


def add_basis_features(
    features: pl.DataFrame,
    basis: pl.DataFrame,
    *,
    window: int = 60,
) -> pl.DataFrame:
    """Exact-time join nominal XAUT/XAU basis and its trailing z-score."""

    if window < 2:
        raise ValueError("window must be at least 2")
    required = {"timestamp_utc", "basis_bps"}
    missing = sorted(required.difference(basis.columns))
    if missing:
        raise ValueError(f"basis is missing: {', '.join(missing)}")
    joined = features.join(
        basis.select("timestamp_utc", "basis_bps"), on="timestamp_utc", how="left", validate="1:1"
    )
    return joined.with_columns(
        (
            (pl.col("basis_bps") - pl.col("basis_bps").rolling_mean(window_size=window))
            / pl.col("basis_bps").rolling_std(window_size=window)
        ).alias("basis_zscore")
    )


def add_unavailable_macro(features: pl.DataFrame) -> pl.DataFrame:
    """Expose gated macro inputs as unavailable rather than manufacturing values."""

    return features.with_columns(
        pl.lit(None, dtype=pl.Float64).alias("usd_index_change"),
        pl.lit(False).alias("usd_index_available"),
        pl.lit(None, dtype=pl.Float64).alias("yield_change"),
        pl.lit(False).alias("yield_available"),
    )


def add_historical_book_placeholders(features: pl.DataFrame) -> pl.DataFrame:
    """Add nullable live-only book fields to historical Gold rows."""

    return features.with_columns(
        pl.lit(False).alias("book_available"),
        pl.lit(None, dtype=pl.Float64).alias("spread_bps"),
        pl.lit(None, dtype=pl.Float64).alias("top_book_imbalance"),
        pl.lit(None, dtype=pl.Float64).alias("weighted_quote"),
        pl.lit(None, dtype=pl.Float64).alias("trade_flow_imbalance"),
        pl.lit(None, dtype=pl.Float64).alias("bid_depth_5bps"),
        pl.lit(None, dtype=pl.Float64).alias("ask_depth_5bps"),
        pl.lit(None, dtype=pl.Float64).alias("bid_depth_10bps"),
        pl.lit(None, dtype=pl.Float64).alias("ask_depth_10bps"),
        pl.lit(None, dtype=pl.Float64).alias("bid_depth_25bps"),
        pl.lit(None, dtype=pl.Float64).alias("ask_depth_25bps"),
    )


def compute_live_book_features(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    *,
    buyer_quantity: float = 0.0,
    seller_quantity: float = 0.0,
) -> dict[str, Any]:
    """Calculate transparent features from one synchronized Binance Spot book snapshot."""

    if not bids or not asks:
        raise ValueError("Both book sides require at least one level")
    if any(price <= 0 or quantity < 0 for price, quantity in [*bids, *asks]):
        raise ValueError("Book prices must be positive and quantities nonnegative")
    if buyer_quantity < 0 or seller_quantity < 0:
        raise ValueError("Trade quantities cannot be negative")
    best_bid, bid_quantity = max(bids, key=lambda level: level[0])
    best_ask, ask_quantity = min(asks, key=lambda level: level[0])
    if best_bid >= best_ask:
        raise ValueError("Book must have a positive spread")
    midpoint = (best_bid + best_ask) / 2
    total_touch = bid_quantity + ask_quantity
    imbalance = bid_quantity / total_touch if total_touch > 0 else None
    weighted_quote = (
        (best_ask * bid_quantity + best_bid * ask_quantity) / total_touch
        if total_touch > 0
        else None
    )
    total_trade = buyer_quantity + seller_quantity
    trade_flow = (buyer_quantity - seller_quantity) / total_trade if total_trade > 0 else None
    result: dict[str, Any] = {
        "book_available": True,
        "spread_bps": (best_ask - best_bid) / midpoint * 10_000,
        "top_book_imbalance": imbalance,
        "weighted_quote": weighted_quote,
        "trade_flow_imbalance": trade_flow,
    }
    for band in (5, 10, 25):
        lower = midpoint * (1 - band / 10_000)
        upper = midpoint * (1 + band / 10_000)
        result[f"bid_depth_{band}bps"] = sum(quantity for price, quantity in bids if price >= lower)
        result[f"ask_depth_{band}bps"] = sum(quantity for price, quantity in asks if price <= upper)
    if not all(
        value is None or not isinstance(value, float) or math.isfinite(value)
        for value in result.values()
    ):
        raise ValueError("Book calculation produced a non-finite value")
    return result
