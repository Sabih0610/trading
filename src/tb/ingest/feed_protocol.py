"""Acquisition extension of the shared read-only market-feed interface."""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from tb.core.contracts import ReadOnlyMarketFeed
from tb.ingest.clock_profiles import ClockProfile
from tb.ingest.mt5.models import DemoIdentity, FeedConfig, InstrumentFacts, Observation


class AcquisitionFeed(ReadOnlyMarketFeed, Protocol):
    """Facts-only interface consumed by the existing finite collector and store."""

    config: FeedConfig
    provider: str
    clock_profile: ClockProfile | None
    clock: Callable[[], datetime]
    latest_raw: dict[str, Any]

    @property
    def synthetic(self) -> bool: ...

    def connect(self) -> DemoIdentity: ...
    def verify(self) -> DemoIdentity: ...
    def metadata(self, symbol: str) -> InstrumentFacts: ...
    def quote(self, symbol: str) -> tuple[Observation, dict[str, Any]]: ...
    def candles(
        self, symbol: str, timeframe: str
    ) -> tuple[list[Observation], list[dict[str, Any]]]: ...
    def ticks(self, symbol: str) -> tuple[list[Observation], list[dict[str, Any]]]: ...
    def close(self) -> None: ...
