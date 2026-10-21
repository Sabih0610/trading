"""Opt-in live samples for the public, keyless P02 sources."""

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from tb.ingest.history.pipeline import (
    JobStatus,
    download_binance_archive,
    download_dukascopy_day,
    download_dukascopy_tick_hour,
)


@pytest.mark.live
def test_live_binance_spot_daily_kline_sample(tmp_path: Path) -> None:
    with httpx.Client(headers={"User-Agent": "trading-bot-research-live-test/0.1"}) as client:
        status = download_binance_archive(
            client,
            tmp_path,
            symbol="BTCUSDT",
            timeframe="1m",
            period=date(2026, 10, 10),
            cadence="daily",
            dataset="klines",
            code_version="live-test",
            resume=False,
        )
    assert status is JobStatus.DOWNLOADED


@pytest.mark.live
def test_live_dukascopy_m1_sample(tmp_path: Path) -> None:
    with httpx.Client(headers={"User-Agent": "trading-bot-research-live-test/0.1"}) as client:
        status = download_dukascopy_day(
            client,
            tmp_path,
            symbol="EURUSD",
            day=date(2026, 10, 16),
            code_version="live-test",
            resume=False,
        )
    assert status is JobStatus.DOWNLOADED


@pytest.mark.live
def test_live_dukascopy_xau_tick_sample(tmp_path: Path) -> None:
    with httpx.Client(headers={"User-Agent": "trading-bot-research-live-test/0.1"}) as client:
        status = download_dukascopy_tick_hour(
            client,
            tmp_path,
            hour=datetime(2026, 10, 16, 12, tzinfo=UTC),
            code_version="live-test",
            resume=False,
        )
    assert status is JobStatus.DOWNLOADED
