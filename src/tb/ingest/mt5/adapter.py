"""Optional official Python reader with an immutable whitelist and repeated demo checks."""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import psutil

from tb.core.instruments import ContractSpec, MarketQuote
from tb.ingest.mt5.models import (
    TIMEFRAMES,
    DemoIdentity,
    FeedConfig,
    FeedUnavailable,
    IdentityRefused,
    InstrumentFacts,
    Observation,
)

PYTHON_READS = frozenset(
    {
        "initialize",
        "shutdown",
        "terminal_info",
        "account_info",
        "symbols_get",
        "symbol_info",
        "symbol_info_tick",
        "copy_rates_from_pos",
        "copy_ticks_from",
        "last_error",
    }
)


class ReaderClient(Protocol):
    """Only whitelisted data reads cross this injectable native boundary."""

    synthetic: bool

    def read(self, name: str, *args: object, **kwargs: object) -> Any:
        """Perform one declared read operation, rejecting everything else."""
        ...


class PythonReader:
    """Capture only read callables; never give downstream code the SDK module."""

    synthetic = False

    def __init__(self) -> None:
        try:
            module = importlib.import_module("MetaTrader5")
        except ImportError:
            raise FeedUnavailable(
                "Optional MT5 package unavailable; use offline fixtures"
            ) from None
        self._functions: dict[str, Callable[..., Any]] = {
            name: getattr(module, name) for name in PYTHON_READS
        }

    def read(self, name: str, *args: object, **kwargs: object) -> Any:
        if name not in PYTHON_READS:
            raise FeedUnavailable("Operation outside the read-only Python boundary")
        if name == "initialize":
            if len(args) != 1 or set(kwargs) - {"timeout"}:
                raise FeedUnavailable("Only an existing terminal attachment is permitted")
            executable = Path(str(args[0])).resolve()
            running = False
            for process in psutil.process_iter(["exe"]):
                try:
                    if process.info["exe"] and Path(process.info["exe"]).resolve() == executable:
                        running = True
                        break
                except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                    continue
            if not running:
                raise FeedUnavailable(
                    "Explicit terminal is not already running; automatic launch refused"
                )
        try:
            return self._functions[name](*args, **kwargs)
        except Exception:
            # Native exceptions can include account paths or arguments. Never propagate them.
            raise FeedUnavailable("Native market-data read failed") from None


def as_dict(value: Any) -> dict[str, Any]:
    """Normalize native namedtuple/NumPy records without exposing their representations."""
    if value is None:
        raise FeedUnavailable("Native market-data facts unavailable")
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    if hasattr(value, "_asdict"):
        return cast(dict[str, Any], value._asdict())
    if getattr(getattr(value, "dtype", None), "names", None):
        return {name: value[name].item() for name in value.dtype.names}
    raise FeedUnavailable("Native record shape unavailable")


def fingerprint(login: object, server: object) -> str:
    """Public evidence contains only a one-way identity fingerprint."""
    return hashlib.sha256(f"mt5-demo:{server}:{login}".encode()).hexdigest()


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result > 0 else None
    except ArithmeticError:
        return None


class MT5Feed:
    """Finite data reads from one explicitly pinned, already authenticated demo terminal."""

    def __init__(
        self,
        client: ReaderClient,
        config: FeedConfig,
        *,
        terminal_path: Path,
        login: str,
        server: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.client, self.config = client, config
        self.path, self.login, self.server = terminal_path, login, server
        self.clock = clock or (lambda: datetime.now(UTC))
        self.identity_record: DemoIdentity | None = None
        self.latest_raw: dict[str, Any] = {}
        if not terminal_path.is_absolute() or not login or not server:
            raise IdentityRefused("Explicit terminal path and demo identity pins required")

    @property
    def synthetic(self) -> bool:
        return self.client.synthetic

    def connect(self) -> DemoIdentity:
        """Attach without account login, password, selection or trading permission changes."""
        if not self.client.read("initialize", str(self.path), timeout=5000):
            raise FeedUnavailable("Terminal unavailable; authenticated demo terminal required")
        try:
            return self.verify()
        except FeedUnavailable:
            self.close()
            raise

    def verify(self) -> DemoIdentity:
        """Check before and after each data call; refuse any account/path/server switch."""
        terminal = as_dict(self.client.read("terminal_info"))
        account = as_dict(self.client.read("account_info"))
        actual_path = Path(str(terminal.get("path", ""))).resolve()
        if not terminal.get("connected"):
            raise FeedUnavailable("Pinned terminal disconnected")
        if (
            actual_path != self.path.parent.resolve()
            or account.get("trade_mode") != 0
            or str(account.get("login")) != self.login
            or account.get("server") != self.server
        ):
            self.identity_record = None
            raise IdentityRefused("Pinned demo terminal/account identity or connection refused")
        self.identity_record = DemoIdentity(
            fingerprint=fingerprint(self.login, self.server),
            server=self.server,
            broker=str(account.get("company", "unavailable")),
            currency=str(account.get("currency", "")),
            terminal_build=int(terminal["build"]),
            verified_at=self.clock(),
        )
        return self.identity_record

    def _read(self, name: str, *args: object, **kwargs: object) -> Any:
        self.verify()
        result = self.client.read(name, *args, **kwargs)
        self.verify()
        return result

    def metadata(self, symbol: str) -> InstrumentFacts:
        """Accept an exact configured alias only when its base/quote facts agree."""
        if symbol not in self.config.symbols:
            raise FeedUnavailable("Canonical symbol not configured")
        broker_symbol = self.config.symbols[symbol]
        # Catalog discovery never selects/unhides a symbol or mutates Market Watch.
        matches = self._read("symbols_get", group=broker_symbol)
        if matches is None:
            raise FeedUnavailable("Symbol catalog unavailable")
        exact = [as_dict(row) for row in matches if as_dict(row).get("name") == broker_symbol]
        if len(exact) != 1:
            raise FeedUnavailable("Exact broker alias missing or ambiguous")
        info = as_dict(self._read("symbol_info", broker_symbol))
        base = "XAU" if symbol == "XAUUSD" else "EUR"
        if (
            info.get("name") != broker_symbol
            or info.get("currency_base") != base
            or info.get("currency_profit") != "USD"
        ):
            raise FeedUnavailable(
                "Broker symbol currencies or identity do not match canonical instrument"
            )
        identity = self.verify()
        return InstrumentFacts(
            symbol=cast(Literal["XAUUSD", "EURUSD"], symbol),
            broker_symbol=broker_symbol,
            description=str(info.get("description", "unavailable")),
            base_currency=base,
            quote_currency="USD",
            account_currency=identity.currency,
            point=_decimal(info.get("point")),
            tick_size=_decimal(info.get("trade_tick_size")),
            digits=info.get("digits"),
            contract_size=_decimal(info.get("trade_contract_size")),
            volume_min=_decimal(info.get("volume_min")),
            volume_max=_decimal(info.get("volume_max")),
            volume_step=_decimal(info.get("volume_step")),
            tick_value=_decimal(info.get("trade_tick_value")),
            trade_mode=info.get("trade_mode"),
            reported_spread_points=info.get("spread"),
            observed_at=self.clock(),
            source="synthetic" if self.synthetic else "mt5_demo",
            conversion_required=identity.currency != "USD",
        )

    def contract(self, symbol: str) -> ContractSpec:
        """Honor the original feed protocol without inventing execution-cost/pip assumptions."""
        self.metadata(symbol)
        raise FeedUnavailable(
            "Sizing contract unavailable: costs, pip definition and conversion require separate policy"
        )

    def quote(self, symbol: str) -> tuple[Observation, dict[str, Any]]:
        """Return actual millisecond source time and local receipt time, never midpoint fills."""
        facts = self.metadata(symbol)
        raw = as_dict(self._read("symbol_info_tick", facts.broker_symbol))
        self.latest_raw = raw
        received = self.clock()
        millis = int(raw.get("time_msc", 0))
        at = datetime.fromtimestamp(millis / 1000 if millis else int(raw["time"]), UTC)
        if (at - received).total_seconds() > self.config.future_tolerance_seconds:
            raise FeedUnavailable("Quote timestamp is in the future")
        observation = Observation(
            symbol=facts.symbol,
            broker_symbol=facts.broker_symbol,
            kind="quote",
            timeframe="tick",
            source_at=at,
            received_at=received,
            evidence="synthetic" if self.synthetic else "historical_backfill",
            bid=raw.get("bid"),
            ask=raw.get("ask"),
            tick_volume=raw.get("volume"),
            real_volume=raw.get("volume_real"),
            flags=raw.get("flags"),
            spread_points=facts.reported_spread_points,
        )
        return observation, raw

    def quotes(self, symbol: str) -> Iterator[MarketQuote]:
        """Yield one finite validated quote; scheduling belongs to the deterministic collector."""
        observation, _ = self.quote(symbol)
        assert observation.bid is not None and observation.ask is not None
        yield MarketQuote(
            symbol=symbol, timestamp=observation.source_at, bid=observation.bid, ask=observation.ask
        )

    def candles(
        self, symbol: str, timeframe: str
    ) -> tuple[list[Observation], list[dict[str, Any]]]:
        """Fetch a bounded tail and exclude every currently unfinished candle."""
        if timeframe not in TIMEFRAMES:
            raise FeedUnavailable("Unsupported bounded candle timeframe")
        seconds = TIMEFRAMES[timeframe]
        # Official TIMEFRAME constants encode hours as 0x4000 + hour count.
        native_tf = seconds // 60 if seconds < 3600 else 16384 + seconds // 3600
        facts = self.metadata(symbol)
        rows = self._read(
            "copy_rates_from_pos", facts.broker_symbol, native_tf, 0, self.config.max_rows
        )
        if rows is None:
            raise FeedUnavailable("Completed broker candles unavailable")
        now = self.clock()
        observations: list[Observation] = []
        raw: list[dict[str, Any]] = []
        for item in rows[: self.config.max_rows]:
            value = as_dict(item)
            raw.append(value)
            at = datetime.fromtimestamp(int(value["time"]), UTC)
            if (at - now).total_seconds() > self.config.future_tolerance_seconds:
                raise FeedUnavailable(
                    "Broker candle clock is in the future; no time shift is inferred"
                )
            if at + timedelta(seconds=seconds) > now:
                continue
            observations.append(
                Observation(
                    symbol=facts.symbol,
                    broker_symbol=facts.broker_symbol,
                    kind="candle",
                    timeframe=timeframe,
                    source_at=at,
                    received_at=now,
                    evidence="synthetic" if self.synthetic else "historical_backfill",
                    open=value.get("open"),
                    high=value.get("high"),
                    low=value.get("low"),
                    close=value.get("close"),
                    tick_volume=value.get("tick_volume"),
                    real_volume=value.get("real_volume"),
                    spread_points=value.get("spread"),
                )
            )
        return observations, raw

    def ticks(self, symbol: str) -> tuple[list[Observation], list[dict[str, Any]]]:
        """Historical tick retrieval stays backfill even when downloaded during a forward session."""
        facts = self.metadata(symbol)
        now = self.clock()
        start = now - timedelta(seconds=self.config.tick_history_seconds)
        rows = self._read("copy_ticks_from", facts.broker_symbol, start, self.config.max_rows, 0)
        if rows is None:
            raise FeedUnavailable("Bounded tick history unavailable")
        out: list[Observation] = []
        raw: list[dict[str, Any]] = []
        for item in rows[: self.config.max_rows]:
            value = as_dict(item)
            at = datetime.fromtimestamp(
                int(value.get("time_msc", value["time"] * 1000)) / 1000, UTC
            )
            if not start <= at <= now:
                continue
            raw.append(value)
            out.append(
                Observation(
                    symbol=facts.symbol,
                    broker_symbol=facts.broker_symbol,
                    kind="tick",
                    timeframe="tick",
                    source_at=at,
                    received_at=now,
                    evidence="synthetic" if self.synthetic else "historical_backfill",
                    bid=value.get("bid"),
                    ask=value.get("ask"),
                    tick_volume=value.get("volume"),
                    real_volume=value.get("volume_real"),
                    flags=value.get("flags"),
                )
            )
        return out, raw

    def close(self) -> None:
        """Release only this Python IPC connection, without changing terminal identity."""
        self.client.read("shutdown")


class UnavailableFeed:
    """Explicit disabled implementation used when package, configuration or terminal is missing."""

    def contract(self, symbol: str) -> ContractSpec:
        raise FeedUnavailable("Market feed unavailable")

    def quotes(self, symbol: str) -> Iterator[MarketQuote]:
        raise FeedUnavailable("Market feed unavailable")
