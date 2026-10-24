"""Causal deterministic research-only event consumer, isolated from execution/account writers."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from tb.core.instruments import assert_eligible
from tb.features.engine import FeatureEngine
from tb.ingest.rights import SHADOW_USAGES, DataRights
from tb.risk.config import AssetRegistry
from tb.shadow.journal import ShadowJournal, ShadowRefused, digest
from tb.shadow.models import ResearchDecision, ShadowEvent
from tb.shadow.strategies import compatibility
from tb.strategies.reference import REFERENCE_STRATEGIES, PriceOnlyStrategy, ReferenceSignal


class ShadowRuntime:
    """Reconstruct bounded in-memory feature state, then freeze one decision set per interval."""

    def __init__(
        self,
        journal: ShadowJournal,
        rights: DataRights,
        registry: AssetRegistry,
        *,
        started_at: datetime,
    ) -> None:
        self.journal, self.rights, self.registry = journal, rights, registry
        self.started_at = started_at
        if journal.pin.rights_digest != rights.digest:
            raise ShadowRefused("shadow_rights_version_changed_before_recovery")
        for symbol in ("EURUSD", "XAUUSD"):
            rights.require(
                SHADOW_USAGES,
                provider=journal.pin.provider,
                identity=journal.pin.identity,
                symbol=symbol,
                now=started_at,
            )
        self.engines: dict[str, FeatureEngine] = {}
        self.plugins: dict[str, dict[str, PriceOnlyStrategy]] = {}
        self.previous: dict[str, tuple[datetime, datetime]] = {}
        for event in journal.events():
            self._reference_signals(event, self._features(event))
            if event.observation.received_at <= started_at:
                self._label(event, started_at)
        journal.health(
            "recovered" if self.previous else "started", started_at, mode=journal.pin.mode
        )

    def _features(self, event: ShadowEvent) -> dict[str, Any]:
        row = event.observation
        reference = self.journal.config.reference_strategies
        engine = self.engines.setdefault(
            row.symbol,
            FeatureEngine(
                timeframe=timedelta(minutes=5),
                reference_periods=reference.periods if reference else None,
            ),
        )
        result = engine.update(
            {
                "timestamp_utc": row.source_at,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
            },
            reference_only=True,
        )
        self.previous[row.symbol] = row.source_at, row.received_at
        # JSON input version includes available price features only; no fake volume/sessions.
        result["timestamp_utc"] = row.source_at.isoformat()
        return result

    def _reference_signals(
        self, event: ShadowEvent, features: dict[str, Any]
    ) -> dict[str, ReferenceSignal]:
        config, symbol = self.journal.config.reference_strategies, event.observation.symbol
        if config is None:
            return {}
        if symbol not in self.plugins:
            self.plugins[symbol] = {
                name: cls(symbol, config) for name, cls in REFERENCE_STRATEGIES.items()
            }
        return {
            name: plugin.evaluate(symbol, features) for name, plugin in self.plugins[symbol].items()
        }

    def _label(self, event: ShadowEvent, now: datetime) -> None:
        if self.journal.config.reference_strategies is not None:
            from tb.shadow.evaluation import evaluate_event

            evaluate_event(self.journal, self.rights, event, now)

    def process(
        self, event: ShadowEvent, now: datetime, *, before_commit: Callable[[], None] | None = None
    ) -> str:
        """Receipt-time availability precedes every frozen decision; duplicates never mutate it."""
        self.journal.require_writer()
        ShadowEvent.model_validate(event.model_dump())
        if event.pin != self.journal.pin or event.pin.rights_digest != self.rights.digest:
            raise ShadowRefused("shadow_source_credential_clock_version_or_rights_changed")
        row, config = event.observation, self.journal.config
        self.rights.require(
            SHADOW_USAGES,
            provider=event.pin.provider,
            identity=event.pin.identity,
            symbol=row.symbol,
            now=now,
        )
        assert_eligible(row.symbol, "reference_data", self.registry)
        previous_id = self.journal.existing(event)
        if previous_id:
            reason = "duplicate" if previous_id == event.evidence_id else "revision_frozen_interval"
            self.journal.health(reason, now, symbol=row.symbol, event_id=event.interval_id)
            if reason == "duplicate":
                self._label(event, now)
            return reason
        completion_lag = (row.received_at - event.closes_at).total_seconds()
        if (
            row.interval_complete is not True
            or not config.post_close_seconds <= completion_lag <= config.maximum_publication_seconds
        ):
            raise ShadowRefused("shadow_unfinished_or_publication_window_invalid")
        if not 0 <= (now - row.received_at).total_seconds() <= config.maximum_processing_seconds:
            raise ShadowRefused("shadow_future_receipt_stale_or_catchup_event")
        if row.source_at.minute % 5 or row.source_at.second or row.source_at.microsecond:
            raise ShadowRefused("shadow_M5_source_alignment_invalid")
        if row.source_at.weekday() >= 5 or (
            row.source_at.weekday() == 4 and row.source_at.hour >= 21
        ):
            raise ShadowRefused("shadow_weekend_composite_is_not_a_tradable_session")
        if (
            row.source_at < self.started_at
            or row.coverage_started_at is None
            or row.coverage_started_at > row.source_at
        ):
            raise ShadowRefused("shadow_retrospective_or_interrupted_coverage")
        previous = self.previous.get(row.symbol)
        if previous and (row.source_at <= previous[0] or row.received_at < previous[1]):
            raise ShadowRefused("shadow_source_or_receipt_clock_regressed")
        started = time.perf_counter()
        features = self._features(event)
        signals = self._reference_signals(event, features)
        decisions = []
        for strategy, reasons in compatibility(
            row.symbol, self.registry, reference_enabled=config.reference_strategies is not None
        ).items():
            result = signals.get(strategy)
            strategy_config = (
                config.reference_strategies.model_dump(mode="json")
                if result and config.reference_strategies
                else {}
            )
            decision = ResearchDecision(
                id=digest([event.interval_id, strategy]),
                event_id=event.interval_id,
                evidence_id=event.evidence_id,
                mode=event.pin.mode,
                provider=event.pin.provider,
                symbol=row.symbol,
                strategy=strategy,
                source_open_at=row.source_at,
                source_close_at=event.closes_at,
                received_at=row.received_at,
                information_available_at=row.received_at,
                decision_at=now + timedelta(seconds=time.perf_counter() - started),
                signal=result.signal if result else "WAIT",
                status=result.state
                if result
                else "control"
                if strategy == "do_nothing"
                else "blocked",
                reasons=result.reasons if result else reasons,
                strategy_version=config.strategy_version,
                feature_version=config.feature_version,
                features=features,
                features_sha256=digest(features),
                strategy_config=strategy_config,
                strategy_config_sha256=digest(strategy_config) if strategy_config else None,
                rights_digest=self.rights.digest,
                source_version=event.pin.source_version,
                consumer_version=event.pin.consumer_version,
                runtime_milliseconds=(time.perf_counter() - started) * 1000,
            )
            decisions.append(decision)
        try:
            self.journal.commit(event, decisions, before_commit=before_commit)
            self._label(event, now)
        except BaseException:
            self.journal.poisoned = True
            raise
        return "committed"

    def stop(self, at: datetime) -> None:
        self.journal.health("stopped", at)
