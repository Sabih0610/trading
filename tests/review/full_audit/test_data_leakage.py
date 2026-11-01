"""Independent full-audit tests: lookahead, final-test lock, CV purging and fill realism.

Written by the reviewer (Claude) without reusing Codex's tests. Tests marked
``xfail(strict=True)`` document verified findings (FINDING D-n) and must keep failing until
the underlying code is fixed; they never weaken a rule.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tb.backtest.engine import BacktestEngine, Bar, EntryOrderType, EntrySignal, ExitReason
from tb.backtest.validation import (
    FINAL_TEST_START,
    EvaluationWindow,
    FinalTestLockedError,
    WalkForwardRunner,
    authorize_evaluation,
)
from tb.features.engine import FeatureEngine, compute_features_batch
from tb.features.pipeline import build_feature_frame
from tb.ml.labeling import BarrierOutcome, CandidateSetup, LabelBar, label_candidates
from tb.ml.validation import (
    ModelSample,
    combinatorial_purged_folds,
    expanding_purged_folds,
    purged_kfold,
)
from tb.research.models import HOLDOUT, HistoricalBar, ResearchRefused
from tb.shadow.evaluation import future_start
from tb.silver.market import clean_minute_bars, resample_completed_bars
from tb.silver.pipeline import calendar_to_silver

_T0 = datetime(2023, 3, 6, 0, 0, tzinfo=UTC)  # Monday


# --------------------------------------------------------------------------- helpers


def _walk(n: int, seed: int, *, gaps: bool = False, step: timedelta = timedelta(minutes=1)):
    rng = random.Random(seed)
    price = 100.0
    rows = []
    t = _T0
    for _ in range(n):
        t += step
        if gaps and rng.random() < 0.03:
            t += step * rng.randint(1, 5)
        op = price
        cl = max(1.0, op * math.exp(rng.gauss(0, 0.004)))
        hi = max(op, cl) * (1 + abs(rng.gauss(0, 0.002)))
        lo = min(op, cl) * (1 - abs(rng.gauss(0, 0.002)))
        rows.append(
            {
                "timestamp_utc": t,
                "open": op,
                "high": hi,
                "low": lo,
                "close": cl,
                "volume": rng.uniform(1, 50),
            }
        )
        price = cl
    return pl.DataFrame(rows).with_columns(pl.col("timestamp_utc").dt.cast_time_unit("us"))


def _assert_frames_equal_prefix(full: pl.DataFrame, part: pl.DataFrame) -> None:
    head = full.head(part.height)
    assert head.columns == part.columns
    for column in part.columns:
        left = head[column].to_list()
        right = part[column].to_list()
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            if isinstance(a, float) and isinstance(b, float):
                assert (math.isnan(a) and math.isnan(b)) or a == pytest.approx(b, rel=1e-12), (
                    column,
                    index,
                )
            else:
                assert a == b, (column, index, a, b)


# --------------------------------------------------------------------------- feature lookahead


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 10_000), cut=st.integers(5, 299), gaps=st.booleans())
def test_feature_engine_prefix_invariance(seed: int, cut: int, gaps: bool) -> None:
    """Truncating future bars must not change any already-emitted feature value."""

    from tb.features.pipeline import prepare_feature_input

    frame = prepare_feature_input(_walk(300, seed, gaps=gaps)).with_columns(
        pl.lit(None, dtype=pl.Int64).alias("htf_structure_direction")
    )
    full = compute_features_batch(frame)
    part = compute_features_batch(frame.head(cut))
    _assert_frames_equal_prefix(full, part)


@settings(max_examples=15, deadline=None)
@given(seed=st.integers(0, 10_000), cut=st.integers(30, 250))
def test_future_shock_does_not_change_past_features(seed: int, cut: int) -> None:
    """An adversarial crash after bar ``cut`` must leave features up to ``cut`` untouched."""

    from tb.features.pipeline import prepare_feature_input

    base = prepare_feature_input(_walk(300, seed)).with_columns(
        pl.lit(None, dtype=pl.Int64).alias("htf_structure_direction")
    )
    shocked = base.with_columns(
        [
            pl.when(pl.int_range(pl.len()) > cut)
            .then(pl.col(c) * 0.5)
            .otherwise(pl.col(c))
            .alias(c)
            for c in ("open", "high", "low", "close")
        ]
    )
    a = compute_features_batch(base).head(cut + 1)
    b = compute_features_batch(shocked).head(cut + 1)
    _assert_frames_equal_prefix(a, b)


def test_swing_pivot_is_only_reported_after_three_bar_confirmation() -> None:
    """A spike high at bar i may appear as a confirmed swing no earlier than bar i+3."""

    engine = FeatureEngine()
    spike_index = 10
    emitted_at = None
    for i in range(20):
        high = 150.0 if i == spike_index else 101.0
        out = engine.update(
            {
                "timestamp_utc": _T0 + timedelta(minutes=i),
                "open": 100.0,
                "high": high,
                "low": 99.0,
                "close": 100.0,
                "volume": 1.0,
                "trading_day_id": "d",
                "session_asia": False,
                "session_london": False,
                "session_new_york": False,
            }
        )
        if out["confirmed_swing_high"] == 150.0:
            emitted_at = i
    assert emitted_at == spike_index + 3


def test_build_feature_frame_prefix_invariance_with_future_htf_and_calendar() -> None:
    """Gold builder: HTF frame and calendar that extend into the future must not leak."""

    silver = _walk(240, 7)
    htf_times = [_T0 + timedelta(minutes=15 * k) for k in range(1, 40)]  # well past the cut
    htf = pl.DataFrame(
        {
            "bar_end_utc": htf_times,
            "structure_direction": [(-1) ** k for k in range(len(htf_times))],
        }
    ).with_columns(pl.col("bar_end_utc").dt.cast_time_unit("us"))
    calendar = pl.DataFrame(
        {
            "timestamp_utc": [_T0 + timedelta(minutes=200)],
            "known_at": [_T0 + timedelta(minutes=190)],
            "importance": ["high"],
        }
    ).with_columns(pl.col("timestamp_utc", "known_at").dt.cast_time_unit("us"))
    full = build_feature_frame(silver, timeframe="1m", higher_timeframe=htf, calendar=calendar)
    cut = 120
    part = build_feature_frame(
        silver.head(cut), timeframe="1m", higher_timeframe=htf, calendar=calendar
    )
    _assert_frames_equal_prefix(full, part)
    # HTF value attached to each 1m row must come from a HTF bar that had already ended.
    ends = dict(zip(htf_times, htf["structure_direction"].to_list(), strict=True))
    for row in full.iter_rows(named=True):
        known = [t for t in htf_times if t <= row["timestamp_utc"]]
        expected = ends[max(known)] if known else None
        assert row["htf_structure_direction"] == expected


@pytest.mark.xfail(
    strict=True,
    reason="FINDING D-5: calendar_to_silver sets known_at=scheduled_utc, so the "
    "minutes_to_high_impact_event feature is null before every event (lead time never usable)",
)
def test_calendar_event_lead_time_is_available_before_event() -> None:
    event_time = _T0 + timedelta(minutes=60)
    raw = pl.DataFrame(
        {
            "event_id": ["cpi"],
            "name": ["CPI"],
            "country": ["US"],
            "currency": ["USD"],
            "importance": ["high"],
            "scheduled_utc": [event_time],
            "source": ["x"],
            "source_url": ["https://example.invalid"],
            "fetched_at": [_T0 - timedelta(days=7)],
            "time_conflict": [False],
        }
    )
    silver = _walk(40, 3)
    result = build_feature_frame(silver, timeframe="1m", calendar=calendar_to_silver(raw))
    assert result["minutes_to_high_impact_event"].drop_nulls().len() > 0


# --------------------------------------------------------------------------- silver


def _canonical(timestamps_ns: list[int], closes: list[float]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp_ns": timestamps_ns,
            "open": closes,
            "high": [c * 1.001 for c in closes],
            "low": [c * 0.999 for c in closes],
            "close": closes,
            "volume": [1.0] * len(closes),
            "symbol": ["BTCUSDT"] * len(closes),
            "source": ["binance_spot"] * len(closes),
        }
    )


def test_silver_spike_flags_are_past_only_and_dedup_keeps_last() -> None:
    base_ns = int(_T0.timestamp() * 1e9)
    minute = 60_000_000_000
    rng = random.Random(1)
    closes = [100 * math.exp(rng.gauss(0, 0.0005) * i**0.5) for i in range(200)]
    closes[150] = closes[149] * 1.2  # spike
    stamps = [base_ns + i * minute for i in range(200)]
    full = clean_minute_bars(_canonical(stamps, closes), market_kind="continuous").frame
    part = clean_minute_bars(_canonical(stamps[:160], closes[:160]), market_kind="continuous").frame
    assert full["is_spike"].head(160).to_list() == part["is_spike"].to_list()
    assert full["is_spike"][150]
    # duplicate row: the later revision wins, nothing forward-filled across a gap
    dup = _canonical([stamps[0], stamps[0], stamps[3]], [100.0, 101.0, 102.0])
    cleaned = clean_minute_bars(dup, market_kind="continuous")
    assert cleaned.frame["close"].to_list() == [101.0, 102.0]
    assert cleaned.missing_minutes == 2 and cleaned.frame.height == 2


def test_resample_never_emits_bar_whose_end_is_after_cutoff() -> None:
    base_ns = int(_T0.timestamp() * 1e9)
    minute = 60_000_000_000
    stamps = [base_ns + i * minute for i in range(130)]  # 2h10m
    cleaned = clean_minute_bars(_canonical(stamps, [100.0] * 130), market_kind="continuous").frame
    cutoff = _T0 + timedelta(minutes=130)
    hourly = resample_completed_bars(cleaned, "1h", cutoff=cutoff)
    assert hourly.height == 2
    assert all(end <= cutoff for end in hourly["bar_end_utc"].to_list())
    assert hourly["bar_end_utc"].to_list()[-1] == _T0 + timedelta(hours=2)


@pytest.mark.parametrize(
    ("instant", "expected_london"),
    [
        (datetime(2024, 7, 1, 7, 30, tzinfo=UTC), True),  # 08:30 BST
        (datetime(2024, 1, 8, 7, 30, tzinfo=UTC), False),  # 07:30 GMT
        (datetime(2024, 3, 31, 7, 0, tzinfo=UTC), True),  # DST day, 08:00 BST
    ],
)
def test_session_flags_follow_dst(instant: datetime, expected_london: bool) -> None:
    ns = int(instant.timestamp() * 1e9)
    frame = clean_minute_bars(_canonical([ns], [100.0]), market_kind="continuous").frame
    assert frame["session_london"][0] is expected_london
    assert frame["trading_day_id"][0] == instant.date().isoformat()


# --------------------------------------------------------------------------- final-test lock


def test_final_test_lock_uses_absolute_instant_across_timezones(tmp_path: Path) -> None:
    ny = ZoneInfo("America/New_York")
    window = EvaluationWindow(
        name="edge",
        train_start=datetime(2023, 1, 1, tzinfo=UTC),
        train_end=datetime(2023, 12, 31, tzinfo=UTC),
        evaluate_start=datetime(2024, 1, 1, tzinfo=UTC),
        evaluate_end=datetime(2024, 12, 31, 23, 30, tzinfo=ny),  # = 2025-01-01 04:30 UTC
    )
    log = tmp_path / "final_test_log.md"
    with pytest.raises(FinalTestLockedError):
        authorize_evaluation(window, final_test=False, log_path=log, run_id="r")
    assert not log.exists()
    authorize_evaluation(window, final_test=True, log_path=log, run_id="r1")
    assert "r1" in log.read_text(encoding="utf-8")


def test_walk_forward_never_hands_2025_bars_to_builder_or_engine(tmp_path: Path) -> None:
    bars = []
    t = datetime(2024, 12, 31, 22, 0, tzinfo=UTC)
    for i in range(240):
        bars.append(
            Bar(
                timestamp=t + timedelta(minutes=i),
                open=Decimal(100),
                high=Decimal(101),
                low=Decimal(99),
                close=Decimal(100),
                volume=Decimal(10),
            )
        )
    early = [
        Bar(
            timestamp=datetime(2023, 6, 1, tzinfo=UTC),
            open=Decimal(100),
            high=Decimal(101),
            low=Decimal(99),
            close=Decimal(100),
            volume=Decimal(10),
        )
    ]
    seen: list[datetime] = []

    def builder(training, evaluation):  # type: ignore[no-untyped-def]
        seen.extend(b.timestamp for b in (*training, *evaluation))
        return []

    WalkForwardRunner(lambda: BacktestEngine("BTCUSDT", initial_cash=Decimal(10000))).run(
        early + bars, builder, run_id="x", final_test_log=tmp_path / "log.md"
    )
    assert seen and max(seen) < FINAL_TEST_START
    assert not (tmp_path / "log.md").exists()


@pytest.mark.parametrize(
    ("zone", "local", "refused"),
    [
        ("America/New_York", "2024-12-31T23:30:00", True),  # 2025-01-01 04:30Z
        ("Asia/Tokyo", "2025-01-01T08:00:00", False),  # 2024-12-31 23:00Z
    ],
)
def test_research_importer_holdout_is_utc_based(zone: str, local: str, refused: bool) -> None:
    from types import SimpleNamespace

    from tb.research.importer import at

    policy = SimpleNamespace(timestamp_format="iso8601", source_timezone=zone)
    instant = at(local, policy)  # type: ignore[arg-type]
    assert (instant >= HOLDOUT) is refused
    kwargs = dict(
        symbol="XAUUSD",
        timeframe="M5",
        open=Decimal(2000),
        high=Decimal(2001),
        low=Decimal(1999),
        close=Decimal(2000),
    )
    source = instant.replace(minute=instant.minute // 5 * 5)
    if refused:
        with pytest.raises((ResearchRefused, ValueError)):
            HistoricalBar(
                source_at=source,
                available_at=source + timedelta(minutes=5),
                local_available_at=source + timedelta(minutes=5),
                **kwargs,
            )
    else:
        HistoricalBar(
            source_at=source,
            available_at=source + timedelta(minutes=5),
            local_available_at=source + timedelta(minutes=5),
            **kwargs,
        )


@settings(max_examples=200, deadline=None)
@given(st.datetimes(min_value=datetime(2021, 1, 1), max_value=datetime(2024, 12, 31)))
def test_label_window_starts_at_or_after_decision(naive: datetime) -> None:
    decision = naive.replace(tzinfo=UTC)
    start = future_start(decision)
    assert start >= decision
    assert start - decision < timedelta(minutes=5)
    assert start.minute % 5 == 0 and start.second == 0 and start.microsecond == 0


# --------------------------------------------------------------------------- purged CV


def _samples(n: int, seed: int) -> list[ModelSample]:
    rng = random.Random(seed)
    out = []
    t = datetime(2021, 1, 1, tzinfo=UTC)
    for i in range(n):
        t += timedelta(minutes=rng.randint(1, 30))
        out.append(
            ModelSample(
                sample_id=str(i),
                starts_at=t,
                ends_at=t + timedelta(minutes=rng.randint(0, 240)),
                feature_known_at=(t - timedelta(minutes=1),),
            )
        )
    return out


@settings(max_examples=30, deadline=None)
@given(
    seed=st.integers(0, 1000),
    n=st.integers(20, 120),
    k=st.integers(2, 6),
    embargo_min=st.integers(0, 120),
)
def test_purged_folds_never_overlap_test_label_intervals(
    seed: int, n: int, k: int, embargo_min: int
) -> None:
    samples = _samples(n, seed)
    embargo = timedelta(minutes=embargo_min)
    for fold in purged_kfold(samples, n_splits=k, embargo=embargo):
        test = [samples[i] for i in fold.test_indices]
        lo = min(s.starts_at for s in test)
        hi = max(s.ends_at for s in test) + embargo
        for i in fold.train_indices:
            s = samples[i]
            assert s.ends_at < lo or s.starts_at > hi
    for fold in expanding_purged_folds(samples, n_splits=k, embargo=embargo):
        first = samples[fold.test_indices[0]].starts_at
        assert all(samples[i].ends_at < first - embargo for i in fold.train_indices)
    for fold in combinatorial_purged_folds(samples, n_groups=k, test_groups=1, embargo=embargo):
        assert not set(fold.train_indices) & set(fold.test_indices)


def test_triple_barrier_same_bar_is_adverse() -> None:
    t = datetime(2024, 1, 2, tzinfo=UTC)
    bars = [
        LabelBar(timestamp=t, high=Decimal(101), low=Decimal(99), close=Decimal(100)),
        LabelBar(
            timestamp=t + timedelta(minutes=5),
            high=Decimal(120),
            low=Decimal(80),
            close=Decimal(100),
        ),
    ]
    setup = CandidateSetup(
        setup_id="a",
        timestamp=t,
        entry_price=Decimal(100),
        stop_price=Decimal(95),
        target_price=Decimal(110),
        max_holding_bars=1,
    )
    (label,) = label_candidates(bars, [setup])
    assert label.outcome is BarrierOutcome.LOSS and label.meta_label == 0


@pytest.mark.xfail(
    strict=True,
    reason="FINDING D-4: triple-barrier LOSS realized_return is pinned to the stop price even "
    "when the whole bar traded below the stop (gap), understating losses in labels",
)
def test_triple_barrier_gap_through_stop_is_not_filled_at_stop() -> None:
    t = datetime(2024, 1, 2, tzinfo=UTC)
    bars = [
        LabelBar(timestamp=t, high=Decimal(101), low=Decimal(99), close=Decimal(100)),
        LabelBar(
            timestamp=t + timedelta(minutes=5), high=Decimal(90), low=Decimal(85), close=Decimal(88)
        ),
    ]
    setup = CandidateSetup(
        setup_id="a",
        timestamp=t,
        entry_price=Decimal(100),
        stop_price=Decimal(95),
        target_price=Decimal(110),
        max_holding_bars=1,
    )
    (label,) = label_candidates(bars, [setup])
    assert label.realized_return <= Decimal(90) / Decimal(100) - 1


# --------------------------------------------------------------------------- backtest realism

_BT0 = datetime(2026, 1, 5, 12, tzinfo=UTC)  # Monday


def _bar(i: int, o: str, h: str, low: str, c: str, v: str = "100000") -> Bar:
    return Bar(
        timestamp=_BT0 + timedelta(minutes=i),
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(low),
        close=Decimal(c),
        volume=Decimal(v),
    )


def test_market_signal_fills_next_bar_open_with_costs_on_both_sides() -> None:
    engine = BacktestEngine("BTCUSDT", initial_cash=Decimal(10000))
    bars = [
        _bar(0, "100", "101", "99", "100.5"),
        _bar(1, "102", "103", "101", "102"),
        _bar(2, "102", "103", "101", "102"),
    ]
    signal = EntrySignal(
        timestamp=_BT0, symbol="BTCUSDT", stop_price=Decimal(90), target_price=Decimal(150)
    )
    result = engine.run(bars, [signal])
    (trade,) = result.trades
    costs = engine.costs
    assert trade.entry_time == bars[1].timestamp  # never the signal bar
    assert trade.entry_price == costs.entry_price(Decimal("102"))
    assert trade.entry_price > Decimal("102")
    assert trade.exit_reason is ExitReason.END_OF_DAY or trade.exit_time == bars[-1].timestamp
    assert trade.exit_price < Decimal("102")
    assert trade.entry_fee == costs.fee(trade.quantity * trade.entry_price)
    assert trade.exit_fee == costs.fee(trade.quantity * trade.exit_price)
    assert costs.fee_bps == Decimal("10") and costs.spread_bps == Decimal("2")
    assert costs.slippage_bps == Decimal("3")
    assert trade.pnl < 0  # flat price round trip must lose costs


def test_stop_and_target_same_bar_resolves_to_stop_for_market_entry() -> None:
    bars = [
        _bar(0, "100", "101", "99", "100"),
        _bar(1, "100", "120", "80", "100"),
        _bar(2, "100", "101", "99", "100"),
    ]
    signal = EntrySignal(
        timestamp=_BT0, symbol="BTCUSDT", stop_price=Decimal(95), target_price=Decimal(110)
    )
    (trade,) = BacktestEngine("BTCUSDT", initial_cash=Decimal(10000)).run(bars, [signal]).trades
    assert trade.exit_reason is ExitReason.STOP


def test_limit_fill_cannot_also_take_profit_in_the_same_bar() -> None:
    bars = [
        _bar(0, "100", "101", "99", "100"),
        _bar(1, "100", "110", "95", "100"),
        _bar(2, "100", "101", "99", "100"),
    ]
    signal = EntrySignal(
        timestamp=_BT0,
        symbol="BTCUSDT",
        order_type=EntryOrderType.LIMIT,
        limit_price=Decimal(96),
        stop_price=Decimal(90),
        target_price=Decimal(105),
    )
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal(10000)).run(bars, [signal])
    assert result.trades, "precondition: limit order was filled"
    entry_bar_exits = [
        t
        for t in result.trades
        if t.exit_time == t.entry_time and t.exit_reason is ExitReason.TARGET
    ]
    assert not entry_bar_exits


def test_fill_size_does_not_depend_on_fill_bar_future_volume() -> None:
    def run(fill_volume: str) -> Decimal:
        bars = [
            _bar(0, "100", "101", "99", "100"),
            _bar(1, "100", "101", "99", "100", fill_volume),
            _bar(2, "100", "101", "99", "100"),
        ]
        signal = EntrySignal(
            timestamp=_BT0, symbol="BTCUSDT", stop_price=Decimal(95), target_price=Decimal(150)
        )
        result = BacktestEngine("BTCUSDT", initial_cash=Decimal(10000)).run(bars, [signal])
        return result.trades[0].quantity

    assert run("100000") == run("20")


@pytest.mark.xfail(
    strict=True,
    reason="FINDING D-3: a limit buy is filled when the bar low merely touches the limit "
    "(low == limit); no trade-through or queue position is required",
)
def test_limit_touch_without_trade_through_is_not_filled() -> None:
    bars = [
        _bar(0, "100", "101", "99", "100"),
        _bar(1, "100", "101", "96", "100"),
        _bar(2, "100", "101", "99", "100"),
    ]
    signal = EntrySignal(
        timestamp=_BT0,
        symbol="BTCUSDT",
        order_type=EntryOrderType.LIMIT,
        limit_price=Decimal(96),
        stop_price=Decimal(90),
        target_price=Decimal(130),
    )
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal(10000)).run(bars, [signal])
    assert not result.trades
