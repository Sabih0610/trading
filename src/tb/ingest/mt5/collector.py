"""Bounded deterministic data-only polling; no strategies, risk actions or order routing."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.mt5.adapter import MT5Feed
from tb.ingest.mt5.models import (
    TIMEFRAMES,
    FeedState,
    FeedUnavailable,
    Health,
    IdentityRefused,
    Observation,
    StorageRefused,
    quote_health,
)
from tb.ingest.mt5.storage import FeedStore


def classify_forward(
    row: Observation, started: datetime, *, coverage_start: datetime | None, maximum_lag: float
) -> Observation:
    """Only timely observations from a prospectively recorded session may leave quarantine."""
    if row.evidence in {"synthetic", "historical_research"}:
        return row
    evidence = "historical_backfill"
    if row.kind == "quote":
        age = (row.received_at - row.source_at).total_seconds()
        if row.source_at >= started and 0 <= age <= maximum_lag:
            evidence = "forward_observed"
    elif row.kind == "candle" and coverage_start is not None:
        end = row.source_at + timedelta(seconds=TIMEFRAMES[row.timeframe])
        lag = (row.received_at - end).total_seconds()
        if row.source_at >= max(started, coverage_start) and 0 <= lag <= maximum_lag:
            evidence = "forward_observed"
    return row.model_copy(
        update={
            "evidence": evidence,
            "coverage_started_at": coverage_start
            if evidence == "forward_observed" and row.kind == "candle"
            else None,
        }
    )


class Collector:
    """Persist each successful group before exporting a separately labeled monitoring snapshot."""

    def __init__(
        self,
        feed: MT5Feed,
        store: FeedStore,
        export_root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.feed, self.store, self.export_root = feed, store, export_root
        self.clock = clock or (lambda: datetime.now(UTC))
        self.sleep = sleep
        self.coverage: dict[str, datetime] = {}
        self.last_poll: dict[str, datetime] = {}
        self.recent: dict[str, Observation] = {}
        self.recent_candles: dict[str, Observation] = {}

    def _connect(self) -> None:
        for attempt in range(self.feed.config.reconnect_attempts):
            try:
                self.feed.connect()
                return
            except IdentityRefused:
                raise  # An identity change is never retried into a different account.
            except FeedUnavailable:
                if attempt + 1 == self.feed.config.reconnect_attempts:
                    raise
                self.sleep(min(2**attempt, 16))

    def run(self, *, max_polls: int | None = None, tick_history: bool = False) -> dict[str, Any]:
        """Bounded data collection only; returns after the explicitly configured poll count."""
        polls = self.feed.config.max_polls if max_polls is None else max_polls
        if not 1 <= polls <= self.feed.config.max_polls:
            raise FeedUnavailable("Requested polls exceed configured bound")
        try:
            self.store.last_commit()
            self._connect()
            identity = self.feed.verify()
        except FeedUnavailable:
            self._export(
                "unverified",
                self.clock(),
                {},
                [],
                [
                    Health(
                        symbol=symbol,
                        state=FeedState.DISCONNECTED,
                        checked_at=self.clock(),
                        reason="Startup identity, checkpoint or connection unverified",
                    )
                    for symbol in self.feed.config.symbols
                ],
                ["collection_start_refused"],
                running=False,
            )
            self.store.health({"event": "collection_start_refused", "at": self.clock().isoformat()})
            self.feed.close()
            raise
        session, started = self.store.session(
            identity.fingerprint, self.clock(), synthetic=self.feed.synthetic
        )
        self.store.health(
            {
                "event": "collector_start_or_restart",
                "at": self.clock().isoformat(),
                "session_id": session,
            }
        )
        next_candles = self.clock()
        result: dict[str, Any] = {}
        try:
            for index in range(polls):
                before = self.clock()
                states: list[Health] = []
                warnings: list[str] = []
                facts = []
                for symbol in self.feed.config.symbols:
                    try:
                        self.feed.verify()
                        metadata = self.feed.metadata(symbol)
                        facts.append(metadata.model_dump(mode="json"))
                        self.feed.latest_raw = {}
                        observation, raw = self.feed.quote(symbol)
                        now = self.clock()
                        previous = self.last_poll.get(symbol)
                        if (
                            previous is None
                            or (now - previous).total_seconds() > self.feed.config.poll_seconds * 3
                        ):
                            self.coverage[symbol] = now
                            if previous is not None:
                                warnings.append("collection_gap_coverage_reset")
                        self.last_poll[symbol] = now
                        observation = classify_forward(
                            observation,
                            started,
                            coverage_start=None,
                            maximum_lag=self.feed.config.max_tick_age_seconds,
                        )
                        self.store.commit(
                            session, [observation], [raw], received_at=now, warnings=[]
                        )
                        self.recent[symbol] = observation
                        states.append(
                            quote_health(
                                symbol,
                                observation.source_at,
                                observation.received_at,
                                now,
                                self.feed.config,
                                connected=True,
                            )
                        )
                        if before >= next_candles:
                            for timeframe in TIMEFRAMES:
                                try:
                                    rows, raw_rows = self.feed.candles(symbol, timeframe)
                                    classified = [
                                        classify_forward(
                                            r,
                                            started,
                                            coverage_start=self.coverage.get(symbol),
                                            maximum_lag=self.feed.config.poll_seconds * 3,
                                        )
                                        for r in rows
                                    ]
                                    self.store.commit(
                                        session,
                                        classified,
                                        raw_rows,
                                        received_at=self.clock(),
                                        warnings=[],
                                    )
                                    for row in classified:
                                        if row.evidence in {"forward_observed", "synthetic"}:
                                            self.recent_candles[
                                                f"{symbol}:{timeframe}:{row.source_at.isoformat()}"
                                            ] = row
                                    self.recent_candles = dict(
                                        list(self.recent_candles.items())[-100:]
                                    )
                                except StorageRefused:
                                    raise
                                except FeedUnavailable:
                                    warnings.append(f"{symbol}_{timeframe}_candles_unavailable")
                            if tick_history:
                                rows, raw_rows = self.feed.ticks(symbol)
                                self.store.commit(
                                    session, rows, raw_rows, received_at=self.clock(), warnings=[]
                                )
                    except StorageRefused:
                        raise
                    except IdentityRefused:
                        self.coverage.clear()
                        result = self._export(
                            session,
                            started,
                            identity.model_dump(mode="json"),
                            [],
                            [
                                Health(
                                    symbol=symbol,
                                    state=FeedState.DISCONNECTED,
                                    checked_at=self.clock(),
                                    reason="Pinned identity refused",
                                )
                            ],
                            ["identity_changed_collection_stopped"],
                            running=False,
                        )
                        raise
                    except (FeedUnavailable, ValueError, ArithmeticError, KeyError) as problem:
                        self.coverage.pop(symbol, None)
                        warnings.append(f"{symbol}_invalid_or_unavailable_observation")
                        if self.feed.latest_raw:
                            self.store.commit(
                                session,
                                [],
                                [{"symbol": symbol, "raw_quote": self.feed.latest_raw}],
                                received_at=self.clock(),
                                warnings=["invalid_quote_quarantined"],
                            )
                        try:
                            self.feed.verify()
                        except IdentityRefused:
                            raise
                        except FeedUnavailable:
                            states.append(
                                Health(
                                    symbol=symbol,
                                    state=FeedState.DISCONNECTED,
                                    checked_at=self.clock(),
                                    reason="Pinned terminal disconnected",
                                )
                            )
                            self.feed.close()
                            try:
                                self._connect()
                            except IdentityRefused:
                                raise
                            except FeedUnavailable:
                                pass
                        else:
                            missing = not self.feed.latest_raw or not any(
                                f["symbol"] == symbol for f in facts
                            )
                            reason = (
                                "Broker symbol metadata unavailable"
                                if missing
                                else "Quote rejected by validation"
                            )
                            if "future" in str(problem):
                                reason = (
                                    "Future source timestamp refused; source clock basis unverified"
                                )
                                warnings.append(f"{symbol}_future_timestamp_refused")
                            states.append(
                                Health(
                                    symbol=symbol,
                                    state=FeedState.INSTRUMENT_UNAVAILABLE
                                    if missing
                                    else FeedState.UNKNOWN,
                                    checked_at=self.clock(),
                                    reason=reason,
                                )
                            )
                if before >= next_candles:
                    next_candles = before + timedelta(seconds=self.feed.config.candle_poll_seconds)
                result = self._export(
                    session, started, identity.model_dump(mode="json"), facts, states, warnings
                )
                self.store.health(
                    {
                        "event": "poll",
                        "at": self.clock().isoformat(),
                        "session_id": session,
                        "states": [state.model_dump(mode="json") for state in states],
                        "warnings": warnings,
                    }
                )
                if index + 1 < polls:
                    self.sleep(
                        max(
                            0,
                            self.feed.config.poll_seconds - (self.clock() - before).total_seconds(),
                        )
                    )
            return result
        finally:
            self.feed.close()
            if result:
                stopped = [
                    Health.model_validate(h).model_copy(
                        update={
                            "state": FeedState.DISCONNECTED
                            if h["state"] == FeedState.CONNECTED
                            else FeedState(h["state"]),
                            "reason": h["reason"] + "; bounded collector stopped",
                        }
                    )
                    for h in result["health"]
                ]
                self._export(
                    session,
                    started,
                    identity.model_dump(mode="json"),
                    result["facts"],
                    stopped,
                    result["warnings"],
                    running=False,
                )
            self.store.health(
                {
                    "event": "collector_stopped",
                    "at": self.clock().isoformat(),
                    "session_id": session,
                }
            )

    def _export(
        self,
        session: str,
        started: datetime,
        identity: dict[str, Any],
        facts: list[dict[str, Any]],
        states: list[Health],
        warnings: list[str],
        *,
        running: bool = True,
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "schema_version": 1,
            "source": "synthetic" if self.feed.synthetic else "mt5_demo",
            "session_id": session,
            "session_started": started.isoformat(),
            "generated_at": self.clock().isoformat(),
            "identity": identity,
            "facts": facts,
            "health": [h.model_dump(mode="json") for h in states],
            "quotes": [
                r.model_dump(mode="json")
                for r in self.recent.values()
                if r.evidence in {"forward_observed", "synthetic"}
            ],
            "candles": [r.model_dump(mode="json") for r in self.recent_candles.values()],
            "warnings": sorted(set(warnings)),
            "historical_backfill_displayed": False,
            "external_orders_enabled": False,
            "poll_seconds": self.feed.config.poll_seconds,
            "collector_running": running,
        }
        self.export_root.mkdir(parents=True, exist_ok=True)
        # Unique payload first, atomic pointer last: a crash never mixes old data and new checksum.
        payload = self.export_root / f"snapshot-{session}-{uuid4().hex}.json"
        atomic_write_json(payload, snapshot)
        atomic_write_json(
            self.export_root / "current.json",
            {"file": payload.name, "sha256": sha256_file(payload)},
        )
        return snapshot
