"""Documented UTC midpoint/rate and OHLC parsing; executable quotes are unavailable."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from tb.core.instruments import ContractSpec, MarketQuote
from tb.ingest.clock_profiles import ClockSequence
from tb.ingest.mt5.models import FeedUnavailable, Observation
from tb.ingest.twelve_data.client import SYMBOLS, Reply, TwelveDataClient


def canonical(symbol: str) -> Literal["EURUSD", "XAUUSD"]:
    if symbol == "EURUSD":
        return "EURUSD"
    if symbol == "XAUUSD":
        return "XAUUSD"
    raise FeedUnavailable("twelve_data_canonical_instrument_refused")


def positive(value: object) -> Decimal:
    """No boolean, missing, nonfinite or nonpositive price may enter Silver."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise FeedUnavailable("twelve_data_price_schema_refused")
    result = Decimal(str(value))
    if not result.is_finite() or result <= 0:
        raise FeedUnavailable("twelve_data_nonpositive_or_nonfinite_price")
    return result


class TwelveDataFeed:
    """ReadOnlyMarketFeed with explicit refusal of broker quote/contract operations.

    References and candles use the same Observation/FeedStore boundary. A fixture transport
    always labels observations synthetic, independently of any caller assertion.
    """

    provider = "twelve_data"

    def __init__(self, client: TwelveDataClient) -> None:
        self.client = client
        self.synthetic = client.synthetic
        self._sequence: dict[str, ClockSequence] = {}
        self.latest_raw: dict[str, Any] = {}
        self.incomplete_intervals: dict[str, int] = {}

    def reference(self, symbol: str) -> tuple[Observation, dict[str, Any]]:
        symbol_value = canonical(symbol)
        reply = self.client.get("exchange_rate", symbol)
        value = reply.payload
        self.latest_raw = self._raw(reply, "exchange_rate", symbol)
        if value.get("symbol") != SYMBOLS[symbol] or type(value.get("timestamp")) is not int:
            raise FeedUnavailable("twelve_data_reference_identity_or_timestamp_refused")
        source = datetime.fromtimestamp(value["timestamp"], UTC)
        # Forex v2 updates each minute. This is a source cadence allowance, no clock offset.
        age = (reply.received_at - source).total_seconds()
        if not -2 <= age <= 90:
            raise FeedUnavailable("twelve_data_reference_future_or_stale")
        row = Observation(
            symbol=symbol_value,
            broker_symbol=SYMBOLS[symbol],
            kind="reference",
            timeframe="minute_reference",
            source_at=source,
            received_at=reply.received_at,
            evidence="synthetic" if self.synthetic else "historical_backfill",
            source_provider="twelve_data",
            reference_price=positive(value.get("rate")),
            price_type="reference_midpoint",
            source_timezone="UTC",
            source_metadata_timezone="UTC epoch",
            raw_source_time=value["timestamp"],
        )
        if source > reply.received_at:
            # A tolerated rounding boundary is retained raw, never forward-admitted.
            raise FeedUnavailable("twelve_data_source_after_receipt")
        self._sequence.setdefault(symbol, ClockSequence()).observe(source, reply.received_at)
        return row, self.latest_raw

    def candles(
        self, symbol: str, timeframe: str = "M1"
    ) -> tuple[list[Observation], list[dict[str, Any]]]:
        symbol_value = canonical(symbol)
        if timeframe not in {"M1", "M5"}:
            raise FeedUnavailable("twelve_data_bounded_timeframe_only")
        duration = 300 if timeframe == "M5" else 60
        reply = self.client.get("time_series", symbol, timeframe=timeframe)
        value = reply.payload
        self.latest_raw = self._raw(reply, "time_series", symbol)
        meta, values = value.get("meta"), value.get("values")
        if (
            value.get("status") != "ok"
            or not isinstance(meta, dict)
            or meta.get("symbol") != SYMBOLS[symbol]
            or meta.get("interval") != ("5min" if timeframe == "M5" else "1min")
            or meta.get("type") != ("Physical Currency" if symbol == "EURUSD" else "Precious Metal")
            or not isinstance(values, list)
            or not 1 <= len(values) <= 3
        ):
            raise FeedUnavailable("twelve_data_candle_identity_or_schema_refused")
        timezone = meta.get("exchange_timezone")
        # Genuine Forex v2 metadata omits exchange_timezone. Do not invent one:
        # UTC output follows the explicit intraday request contract.
        if timezone is not None and (
            not isinstance(timezone, str) or not timezone or len(timezone) > 80
        ):
            raise FeedUnavailable("twelve_data_source_timezone_invalid")
        rows = []
        for bar in values:
            if not isinstance(bar, dict) or not isinstance(bar.get("datetime"), str):
                raise FeedUnavailable("twelve_data_bar_datetime_refused")
            source = datetime.strptime(bar["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            if (
                source.second != 0
                or source.minute % (5 if timeframe == "M5" else 1)
                or source > reply.received_at + timedelta(seconds=2)
            ):
                raise FeedUnavailable("twelve_data_candle_clock_or_alignment_refused")
            complete = source + timedelta(seconds=duration) <= reply.received_at
            # Incomplete OHLC stays in raw Bronze and is labeled in Silver, never in forward UI.
            rows.append(
                Observation(
                    symbol=symbol_value,
                    broker_symbol=SYMBOLS[symbol],
                    kind="candle",
                    timeframe=timeframe,
                    source_at=source,
                    received_at=reply.received_at,
                    evidence="synthetic" if self.synthetic else "historical_backfill",
                    source_provider="twelve_data",
                    price_type="reference_midpoint",
                    source_timezone="UTC",
                    source_metadata_timezone=timezone,
                    raw_source_time=bar["datetime"],
                    interval_complete=complete,
                    open=positive(bar.get("open")),
                    high=positive(bar.get("high")),
                    low=positive(bar.get("low")),
                    close=positive(bar.get("close")),
                )
            )
        if len({row.source_at for row in rows}) != len(rows):
            raise FeedUnavailable("twelve_data_duplicate_bar_in_response")
        if not any(
            row.interval_complete
            and 0
            <= (reply.received_at - row.source_at).total_seconds() - duration
            <= (180 if timeframe == "M5" else 120)
            for row in rows
        ):
            raise FeedUnavailable("twelve_data_completed_candle_stale_or_missing")
        self.incomplete_intervals[symbol] = sum(not r.interval_complete for r in rows)
        return sorted(rows, key=lambda r: r.source_at), [self.latest_raw]

    @staticmethod
    def _raw(reply: Reply, endpoint: str, symbol: str) -> dict[str, Any]:
        return {
            "provider": "twelve_data",
            "endpoint": endpoint,
            "symbol": SYMBOLS[symbol],
            "requested_timezone": "UTC",
            "acquired_at": reply.received_at.isoformat(),
            "http_date": reply.http_date.isoformat(),
            "cached": reply.cached,
            "response": reply.payload,
        }

    def quote(self, symbol: str) -> tuple[Observation, dict[str, Any]]:
        raise FeedUnavailable("twelve_data_executable_bid_ask_unavailable")

    def quotes(self, symbol: str) -> Iterator[MarketQuote]:
        raise FeedUnavailable("twelve_data_reference_midpoint_is_not_a_MarketQuote")

    def contract(self, symbol: str) -> ContractSpec:
        raise FeedUnavailable("twelve_data_contract_costs_and_execution_unavailable")

    def close(self) -> None:
        self.client.close()
