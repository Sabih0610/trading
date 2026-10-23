"""Budgeted M5 post-close slots over the existing adapter and immutable FeedStore."""

from __future__ import annotations

from datetime import datetime, timedelta

from tb.ingest.mt5.collector import classify_forward
from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.rights import SHADOW_USAGES, DataRights
from tb.ingest.twelve_data.adapter import TwelveDataFeed


def latest_due_close(now: datetime) -> datetime:
    """Use one120s-delayed M5 slot, never replay all missed historical closes."""
    at = now - timedelta(seconds=120)
    return at.replace(minute=at.minute // 5 * 5, second=0, microsecond=0)


def collect_m5_once(
    feed: TwelveDataFeed,
    store: FeedStore,
    rights: DataRights,
    *,
    started_at: datetime,
    now: datetime,
) -> int:
    """One attempt per symbol/slot; credit reservation precedes every HTTP call."""
    client = feed.client
    identity = client.source_identity
    if not feed.synthetic:
        for symbol in ("EURUSD", "XAUUSD"):
            rights.require(
                SHADOW_USAGES, provider="twelve_data", identity=identity, symbol=symbol, now=now
            )
    if store.provider != "twelve_data" or client.budget.daily_ceiling > 600:
        raise FeedUnavailable("M5_shadow_storage_or_daily_headroom_refused")
    close_at = latest_due_close(now)
    session, _ = store.session(identity, started_at, synthetic=feed.synthetic)
    committed = 0
    for symbol in ("EURUSD", "XAUUSD"):
        if not client.budget.claim_m5(close_at, symbol, now):
            continue
        rows, raw = feed.candles(symbol, "M5")
        if raw[0].get("cached"):
            continue
        admitted = []
        for row in rows:
            lag = (row.received_at - row.source_at).total_seconds() - 300
            candidate = classify_forward(
                row, started_at, coverage_start=started_at, maximum_lag=180
            )
            if not 120 <= lag <= 180 or row.source_at + timedelta(minutes=5) != close_at:
                candidate = candidate.model_copy(
                    update={
                        "evidence": "synthetic" if feed.synthetic else "historical_backfill",
                        "coverage_started_at": None,
                    }
                )
            elif feed.synthetic and row.source_at >= started_at:
                candidate = candidate.model_copy(update={"coverage_started_at": started_at})
            admitted.append(candidate)
        result = store.commit(
            session,
            admitted,
            raw,
            received_at=client.clock(),
            warnings=["M5_elapsed_plus_120s; provider_revisions_not_immutable"],
        )
        committed += int(result["rows"])
    return committed
