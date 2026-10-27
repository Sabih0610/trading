"""Explicit synthetic native-client fixture. It never generates purported real prices."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from tb.ingest.mt5.adapter import PYTHON_READS
from tb.ingest.mt5.models import FeedUnavailable


class FakeReader:
    """Deterministic fixture behind the same constrained native-client interface."""

    synthetic = True

    def __init__(self, path: Path, clock: Callable[[], datetime]) -> None:
        self.path, self.clock = path, clock
        self.calls: list[str] = []
        self.connected = True
        self.login = 900001
        self.server = "Offline-Demo"
        self.trade_mode = 0
        self.quote_overrides: dict[str, Any] = {}
        self.info_overrides: dict[str, Any] = {}
        self.missing_candles = False
        self.aliases = {"XAUUSD": "XAUUSD", "EURUSD": "EURUSD"}

    def read(self, name: str, *args: object, **kwargs: object) -> Any:
        if name not in PYTHON_READS:
            raise FeedUnavailable("Operation outside fake read boundary")
        self.calls.append(name)
        if name == "initialize":
            return self.connected
        if name == "shutdown":
            return None
        if name == "terminal_info":
            return {"path": str(self.path.parent), "connected": self.connected, "build": 6060}
        if name == "account_info":
            return {
                "login": self.login,
                "server": self.server,
                "trade_mode": self.trade_mode,
                "company": "Synthetic fixture",
                "currency": "USD",
            }
        if name == "last_error":
            return (1, "Synthetic fixture")
        broker_symbol = str(args[0] if args else kwargs.get("group", ""))
        canonical = next(
            (key for key, value in self.aliases.items() if value == broker_symbol), None
        )
        if canonical is None:
            return None
        info = {
            "name": broker_symbol,
            "description": "Synthetic " + canonical,
            "currency_base": "XAU" if canonical == "XAUUSD" else "EUR",
            "currency_profit": "USD",
            "point": 0.01 if canonical == "XAUUSD" else 0.00001,
            "trade_tick_size": 0.01 if canonical == "XAUUSD" else 0.00001,
            "digits": 2 if canonical == "XAUUSD" else 5,
            "trade_contract_size": 100 if canonical == "XAUUSD" else 100000,
            "volume_min": 0.01,
            "volume_max": 10,
            "volume_step": 0.01,
            "trade_tick_value": 1,
            "trade_mode": 4,
            "spread": 2,
        }
        info.update(self.info_overrides)
        if name == "symbols_get":
            return [info]
        if name == "symbol_info":
            return info
        price = 2300 if canonical == "XAUUSD" else 1.1
        now = self.clock()
        if name == "symbol_info_tick":
            return {
                "time": int(now.timestamp()),
                "time_msc": int(now.timestamp() * 1000),
                "bid": price,
                "ask": price + (0.02 if canonical == "XAUUSD" else 0.00002),
                "volume": 1,
                "volume_real": 0,
                "flags": 6,
                **self.quote_overrides,
            }
        if name == "copy_rates_from_pos":
            if self.missing_candles:
                return None
            native_tf, count = int(str(args[1])), int(str(args[3]))
            seconds = (native_tf - 16384) * 3600 if native_tf >= 16384 else native_tf * 60
            floor = int(now.timestamp()) // seconds * seconds
            return [
                {
                    "time": floor - i * seconds,
                    "open": price,
                    "high": price + 0.001,
                    "low": price - 0.001,
                    "close": price,
                    "tick_volume": 5,
                    "real_volume": 0,
                    "spread": 2,
                }
                for i in reversed(range(count))
            ]
        if name == "copy_ticks_from":
            return [
                {
                    "time": int(now.timestamp()) - 10,
                    "time_msc": int(now.timestamp() * 1000) - 10000,
                    "bid": price,
                    "ask": price + 0.00002,
                    "volume": 1,
                    "volume_real": 0,
                    "flags": 6,
                }
            ]
        raise FeedUnavailable("Unknown fake read")
