"""Owned financial-output oracle for F/G symbols under unchanged EOD proposals."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tb.backtest.engine import BacktestEngine, Bar, EntrySignal


@pytest.mark.parametrize("symbol", ["BTCUSDT", "XAUTUSDT"])
def test_original_intraday_financial_results_match_owned_prechange_oracle(symbol):
    oracle = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures/owned_legacy_eod.json").read_text(
            encoding="utf-8"
        )
    )
    assert oracle["evidence"].startswith("FICTIONAL OWNED")
    start = datetime(2024, 1, 1, 23, 57, tzinfo=UTC)
    bars = [
        Bar(
            timestamp=start + timedelta(minutes=i),
            open=100,
            high=101,
            low=99,
            close=100,
            volume=100000,
        )
        for i in range(6)
    ]
    signals = [
        EntrySignal(
            timestamp=bars[i].timestamp,
            symbol=symbol,
            stop_price=95,
            target_price=110,
            requested_quantity=1,
        )
        for i in (0, 3)
    ]
    assert all(signal.flat_by_end_of_day for signal in signals)
    actual = (
        BacktestEngine(symbol, initial_cash=Decimal(10000))
        .run(bars, signals)
        .model_dump(mode="json")
    )
    assert actual == oracle["results"][symbol]
