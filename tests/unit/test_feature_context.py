"""Tests for point-in-time context and live-book feature helpers."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from tb.features.context import (
    add_basis_features,
    add_event_proximity,
    add_historical_book_placeholders,
    add_unavailable_macro,
    compute_live_book_features,
)


def test_event_requires_schedule_to_be_known() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    features = pl.DataFrame({"timestamp_utc": [now, now + timedelta(minutes=10)]})
    calendar = pl.DataFrame(
        {
            "timestamp_utc": [now + timedelta(minutes=30)],
            "known_at": [now + timedelta(minutes=5)],
            "importance": ["high"],
        }
    )

    result = add_event_proximity(features, calendar)

    assert result["minutes_to_high_impact_event"].to_list() == [None, 20.0]


def test_basis_join_never_carries_stale_value() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    features = pl.DataFrame(
        {"timestamp_utc": [start + timedelta(minutes=index) for index in range(3)]}
    )
    basis = pl.DataFrame({"timestamp_utc": [start], "basis_bps": [5.0]})

    result = add_basis_features(features, basis, window=2)

    assert result["basis_bps"].to_list() == [5.0, None, None]


def test_unavailable_history_is_explicitly_null() -> None:
    frame = pl.DataFrame({"timestamp_utc": [datetime(2026, 1, 1, tzinfo=UTC)]})
    result = add_historical_book_placeholders(add_unavailable_macro(frame))

    assert result["book_available"].to_list() == [False]
    assert result["usd_index_available"].to_list() == [False]
    assert result["spread_bps"].to_list() == [None]


def test_live_book_features_have_expected_units() -> None:
    result = compute_live_book_features(
        bids=[(99.0, 2.0), (98.9, 3.0)],
        asks=[(101.0, 1.0), (101.1, 4.0)],
        buyer_quantity=3.0,
        seller_quantity=1.0,
    )

    assert result["spread_bps"] == pytest.approx(200.0)
    assert result["top_book_imbalance"] == pytest.approx(2 / 3)
    assert result["weighted_quote"] == pytest.approx((101 * 2 + 99) / 3)
    assert result["trade_flow_imbalance"] == pytest.approx(0.5)


def test_crossed_book_fails_closed() -> None:
    with pytest.raises(ValueError, match="positive spread"):
        compute_live_book_features(bids=[(101.0, 1.0)], asks=[(100.0, 1.0)])
