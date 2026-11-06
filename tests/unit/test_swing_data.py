"""Owned fixtures for UTC coverage, causal feature availability and private day bounds."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tb.backtest.intrabar import _DayPathAccessor
from tb.features.engine import FeatureEngine
from tb.research.models import ResearchRefused
from tb.silver.swing import (
    CalendarClosure,
    SwingCalendar,
    add_swing_features,
    aggregate_daily,
    aggregate_weekly,
)
from tb.silver.swing_calendar import load_swing_calendar
from tb.silver.swing_source import CRYPTO_DATASET, GOLD_DATASET, SwingSource, swing_scope

START = datetime(2023, 1, 2, tzinfo=UTC)
DAY = timedelta(days=1)


def minutes(
    start=START, count=1440, *, symbol="BTCUSDT", source="binance_vision", side="trade", price=100
):
    return pl.DataFrame(
        {
            "timestamp_utc": pl.datetime_range(
                start,
                start + timedelta(minutes=count),
                interval="1m",
                closed="left",
                time_unit="ns",
                eager=True,
            ),
            "open": [float(price)] * count,
            "high": [float(price + 1)] * count,
            "low": [float(price - 1)] * count,
            "close": [float(price)] * count,
            "volume": [1.0] * count,
            "symbol": [symbol] * count,
            "source": [source] * count,
            "price_side": [side] * count,
        }
    )


def calendar():
    return SwingCalendar("BTCUSDT", "binance_vision", "trade", "owned-continuous")


def feature_bar(index, *, close=None):
    price = float(index + 10 if close is None else close)
    stamp = START + index * DAY
    return {
        "timestamp_utc": stamp,
        "bar_end_utc": stamp + DAY,
        "open": price,
        "high": price + 1,
        "low": price - 1,
        "close": price,
        "complete": True,
        "symbol": "BTCUSDT",
        "source": "binance_vision",
        "price_side": "trade",
        "volume": 1.0,
    }


def test_exact_95_percent_boundary_and_no_price_fill():
    enough = aggregate_daily(
        minutes(count=1368), start=START, stop=START + DAY, calendar=calendar()
    ).row(0, named=True)
    short = aggregate_daily(
        minutes(count=1367), start=START, stop=START + DAY, calendar=calendar()
    ).row(0, named=True)
    assert enough["expected_minutes"] == 1440 and enough["observed_minutes"] == 1368
    assert enough["complete"] is True and short["complete"] is False
    days = add_swing_features(
        aggregate_daily(minutes(), start=START, stop=START + 2 * DAY, calendar=calendar()),
        timeframe="1d",
    )
    missing = days.row(1, named=True)
    assert missing["observed_minutes"] == 0 and missing["expected_minutes"] == 1440
    assert all(missing[name] is None for name in ("open", "high", "low", "close", "volume"))
    assert missing["complete"] is False and missing["available_at"] is None
    assert (
        missing["history_barrier"] is True and missing["coverage_available_at"] == START + 2 * DAY
    )


def test_week_monday_anchor_and_partial_edges_remain_incomplete():
    start = START - DAY
    daily = aggregate_daily(
        minutes(start, count=8 * 1440), start=start, stop=START + 7 * DAY, calendar=calendar()
    )
    weekly = aggregate_weekly(daily, start=start, stop=START + 7 * DAY, calendar=calendar())
    first, last = weekly.iter_rows(named=True)
    assert first["timestamp_utc"] == START - 7 * DAY and first["bar_end_utc"] == START
    assert first["complete"] is False and first["window_closed"] is True
    assert first["window_within_scope"] is False
    assert last["timestamp_utc"] == START and last["bar_end_utc"] == START + 7 * DAY
    assert (
        last["complete"] is True and last["observed_minutes"] == last["expected_minutes"] == 10080
    )
    with pytest.raises(ResearchRefused, match="future_or_prior_source"):
        aggregate_weekly(daily, start=start, stop=START + 6 * DAY, calendar=calendar())
    partial_daily = aggregate_daily(
        minutes(start, count=7 * 1440), start=start, stop=START + 6 * DAY, calendar=calendar()
    )
    trailing = aggregate_weekly(
        partial_daily, start=start, stop=START + 6 * DAY, calendar=calendar()
    ).row(-1, named=True)
    assert trailing["window_closed"] is False and trailing["complete"] is False
    assert trailing["coverage_available_at"] is None and trailing["history_barrier"] is False


def test_xau_weekend_rollover_and_explicit_holiday_are_not_missing_minutes():
    saturday = datetime(2023, 7, 1, tzinfo=UTC)
    holiday = datetime(2023, 7, 3, tzinfo=UTC)
    reference = SwingCalendar(
        "XAUUSD",
        "histdata",
        "bid",
        "owned-reference",
        (
            CalendarClosure(
                holiday,
                holiday + DAY,
                "https://example.invalid/owned-holiday",
                "fictional declared closure",
            ),
        ),
        True,
    )
    empty = minutes(saturday, 0, symbol="XAUUSD", source="histdata", side="bid")
    rows = aggregate_daily(empty, start=saturday, stop=holiday + DAY, calendar=reference)
    sat, _, closed = rows.iter_rows(named=True)
    assert sat["expected_minutes"] == 0 and sat["market_closed"] is True
    assert closed["expected_minutes"] == 0 and closed["market_closed"] is True
    assert sat["complete"] is False and closed["complete"] is False
    assert not sat["history_barrier"] and not closed["history_barrier"]
    normal = SwingCalendar("XAUUSD", "histdata", "bid", "owned-reference", (), True)
    count = normal.grid(holiday, holiday + DAY)["expected_open"].sum()
    assert count == 1380  # One known daily rollover hour is excluded.


def test_declared_calendar_conflict_is_retained_and_incomplete():
    reference = SwingCalendar(
        "XAUUSD",
        "histdata",
        "bid",
        "owned-reference",
        (
            CalendarClosure(
                START, START + DAY, "https://example.invalid/owned", "fictional holiday"
            ),
        ),
        True,
    )
    row = aggregate_daily(
        minutes(count=1, symbol="XAUUSD", source="histdata", side="bid"),
        start=START,
        stop=START + DAY,
        calendar=reference,
    ).row(0, named=True)
    assert row["observed_minutes"] == 1 and row["unexpected_minutes"] == 1
    assert row["open"] == 100 and row["volume"] is None
    assert (
        row["calendar_conflict"] is True
        and row["complete"] is False
        and row["history_barrier"] is True
    )


def test_reference_policy_has_fixed_evidence_and_dst_conversion():
    reference, checksum = load_swing_calendar("XAUUSD")
    assert reference.reference_only is True and len(checksum) == 64
    assert reference.source == "histdata" and reference.price_side == "bid"
    assert any(item.start == datetime(2021, 4, 1, 21, tzinfo=UTC) for item in reference.closures)
    assert any(item.start == datetime(2023, 12, 24, 22, tzinfo=UTC) for item in reference.closures)
    assert all(item.evidence.startswith("https://") for item in reference.closures)


@pytest.mark.parametrize("symbol", ["BTCUSDT", "PAXGUSDT"])
def test_continuous_source_labels_and_real_volume_kept(symbol):
    model, _ = load_swing_calendar(symbol)
    day = datetime(2024, 1, 2, tzinfo=UTC)
    row = aggregate_daily(
        minutes(day, symbol=symbol), start=day, stop=day + DAY, calendar=model
    ).row(0, named=True)
    assert (
        row["symbol"] == symbol
        and row["source"] == "binance_vision"
        and row["price_side"] == "trade"
    )
    assert row["volume"] == 1440 and row["expected_minutes"] == 1440


def test_2025_minute_refused_and_wrong_source_refused():
    frame = minutes(datetime(2024, 12, 31, 23, 59, tzinfo=UTC), 2)
    with pytest.raises(ResearchRefused, match="outside_admitted"):
        aggregate_daily(
            frame,
            start=datetime(2024, 12, 31, tzinfo=UTC),
            stop=datetime(2025, 1, 1, tzinfo=UTC),
            calendar=calendar(),
        )
    with pytest.raises(ResearchRefused, match="source_labels"):
        aggregate_daily(
            minutes(symbol="PAXGUSDT"), start=START, stop=START + DAY, calendar=calendar()
        )


@settings(max_examples=8, deadline=3000)
@given(st.integers(min_value=102, max_value=100000))
def test_future_minute_spike_cannot_change_completed_daily_bar_or_features(spike):
    original = minutes()
    future = minutes(START + DAY, count=1, price=spike)
    prefix = add_swing_features(
        aggregate_daily(original, start=START, stop=START + DAY, calendar=calendar()),
        timeframe="1d",
    )
    extended = add_swing_features(
        aggregate_daily(
            pl.concat([original, future]), start=START, stop=START + 2 * DAY, calendar=calendar()
        ),
        timeframe="1d",
    )
    assert prefix.to_dicts() == extended.head(1).to_dicts()


@settings(max_examples=20)
@given(st.floats(min_value=1000, max_value=100000, allow_nan=False, allow_infinity=False))
def test_future_feature_bar_does_not_change_prior_outputs(spike):
    bars = [feature_bar(index) for index in range(205)]
    first = FeatureEngine(timeframe=DAY)
    expected = [first.update_swing(bar) for bar in bars]
    extended = FeatureEngine(timeframe=DAY)
    actual = [extended.update_swing(bar) for bar in [*bars, feature_bar(205, close=spike)]]
    assert actual[:205] == expected
    assert expected[199]["sma200"] == pytest.approx(sum(range(10, 210)) / 200)
    assert expected[19]["ema20"] == expected[19]["sma20"]
    assert expected[20]["donchian_high20"] == 30  # Current high31 is excluded.
    assert expected[18]["sma20"] is None


def test_pivot_visible_only_after_three_later_completed_bars():
    engine = FeatureEngine(timeframe=DAY)
    highs = [5, 6, 7, 10, 7, 6, 5]
    output = []
    for i, high in enumerate(highs):
        bar = feature_bar(i, close=3)
        bar.update(high=high, low=1)
        output.append(engine.update_swing(bar))
    assert all(row["confirmed_swing_high"] is None for row in output[:6])
    assert output[6]["confirmed_swing_high"] == 10
    assert output[6]["confirmed_swing_high_bar_utc"] == START + 3 * DAY
    assert output[6]["swing_high_confirmed_at"] == START + 7 * DAY


def test_expected_open_gap_resets_but_closed_day_does_not():
    bars = []
    for index in range(21):
        bar = feature_bar(index)
        bar.update(market_closed=False, calendar_conflict=False)
        if index == 10:
            bar.update(complete=False, open=None, high=None, low=None, close=None, volume=None)
        bars.append(bar)
    missing = add_swing_features(pl.DataFrame(bars), timeframe="1d")
    assert missing.row(11, named=True)["swing_input_gap"] is True
    assert missing.row(20, named=True)["sma20"] is None
    bars[10]["market_closed"] = True
    closed = add_swing_features(pl.DataFrame(bars), timeframe="1d")
    assert closed.row(11, named=True)["swing_input_gap"] is False
    assert closed.row(20, named=True)["sma20"] is not None


@pytest.mark.parametrize(
    "dataset,symbol,year",
    [
        (CRYPTO_DATASET, "BTCUSDT", 2025),
        (GOLD_DATASET, "XAUUSD", 2020),
        (GOLD_DATASET, "XAUUSD", 2024),
    ],
)
def test_partition_scope_refused_before_registry_access(
    tmp_path, monkeypatch, dataset, symbol, year
):
    source = SwingSource(tmp_path, dataset, symbol)
    monkeypatch.setattr(
        source, "plan", lambda: pytest.fail("registry accessed before year refusal")
    )
    with pytest.raises(ResearchRefused, match="before_access"):
        source.manifest(year)


def test_intrabar_refuses_other_day_and_future_path_before_io():
    source = SimpleNamespace(
        scope=swing_scope(CRYPTO_DATASET, "BTCUSDT"),
        scan=lambda _: pytest.fail("unexpected data access"),
    )
    accessor = _DayPathAccessor(source, START.date())
    with pytest.raises(ResearchRefused, match="other_day"):
        accessor.read((START + DAY).date(), as_of=START + 2 * DAY)
    with pytest.raises(ResearchRefused, match="not_yet_complete"):
        accessor.read(START.date(), as_of=START + timedelta(hours=23))


def test_intrabar_returns_only_bound_day_immutable_points():
    frame = minutes(START - DAY, count=3 * 1440)
    source = SimpleNamespace(
        scope=swing_scope(CRYPTO_DATASET, "BTCUSDT"),
        scan=lambda _: (frame.lazy(), None),
        verify=lambda _: None,
    )
    points = _DayPathAccessor(source, START.date()).read(START.date(), as_of=START + DAY)
    assert len(points) == 1440 and all(
        point.timestamp_utc.date() == START.date() for point in points
    )
    assert points[0].timestamp_utc == START and points[-1].timestamp_utc == START + DAY - timedelta(
        minutes=1
    )
    with pytest.raises(FrozenInstanceError):
        points[0].close = 200
    accessor = _DayPathAccessor(source, START.date())
    with pytest.raises(FrozenInstanceError):
        accessor._day = (START + DAY).date()
    with pytest.raises(ResearchRefused):
        _DayPathAccessor(source, date(2025, 1, 1))
