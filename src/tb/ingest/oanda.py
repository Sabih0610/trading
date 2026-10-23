"""Optional GET-only v20 Practice adapter. Genuine access is separately evidence-gated."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import AwareDatetime, SecretStr, StrictBool
from pydantic_settings import BaseSettings, SettingsConfigDict

from tb.core.instruments import ContractSpec, MarketQuote
from tb.ingest.clock_profiles import ClockProfile, ClockSequence, ClockStamp
from tb.ingest.mt5.models import (
    TIMEFRAMES,
    AdmissionCheck,
    DemoIdentity,
    FeedConfig,
    FeedUnavailable,
    IdentityRefused,
    InstrumentFacts,
    Observation,
)
from tb.ingest.mt5.qualification import clock_reference_passes, independent_utc
from tb.ingest.mt5.timestamps import parse_explicit_utc
from tb.risk.config import PolicyModel

PRACTICE_HOST = "https://api-fxpractice.oanda.com"
SYMBOLS = {"EURUSD": "EUR_USD", "XAUUSD": "XAU_USD"}


class OandaSettings(BaseSettings):
    """Names only are public; optional credentials stay in the ignored root .env."""

    model_config = SettingsConfigDict(env_prefix="OANDA_PRACTICE_", extra="ignore")
    token: SecretStr = SecretStr("")
    account_id: SecretStr = SecretStr("")

    @classmethod
    def from_root(cls, root: Path) -> OandaSettings:
        arguments: dict[str, Any] = {"_env_file": root / ".env"}
        return cls(**arguments)


class PracticeAccess(PolicyModel):
    """Human/provider authorization evidence, distinct from credentials and clock semantics."""

    pakistan_demo_access_verified: StrictBool = False
    practice_api_verified: StrictBool = False
    no_funding_required_verified: StrictBool = False
    storage_rights_reviewed: StrictBool = False
    evidence_references: tuple[str, ...] = ()
    expires_at: AwareDatetime | None = None

    def permits(self, now: datetime) -> bool:
        return (
            self.pakistan_demo_access_verified
            and self.practice_api_verified
            and self.no_funding_required_verified
            and self.storage_rights_reviewed
            and bool(self.evidence_references)
            and self.expires_at is not None
            and now < self.expires_at
        )


class OandaPracticeFeed:
    """No arbitrary URL, verb, account switch or broker mutation operation is accepted."""

    provider = "oanda_practice"

    def __init__(
        self,
        settings: OandaSettings,
        *,
        profile: ClockProfile | None,
        access: PracticeAccess | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        fixture: bool = False,
    ) -> None:
        self.clock, self.clock_profile, self.access = clock, profile, access or PracticeAccess()
        self.synthetic = fixture
        self.config = FeedConfig(symbols=SYMBOLS.copy())
        self.latest_raw: dict[str, Any] = {}
        self._account = settings.account_id.get_secret_value()
        token = settings.token.get_secret_value()
        if not token or not self._account:
            raise FeedUnavailable("OANDA_PRACTICE credentials missing; alternative feed disabled")
        if not all(c.isdigit() or c == "-" for c in self._account):
            raise FeedUnavailable("Practice account pin invalid")
        if fixture and not isinstance(transport, httpx.MockTransport):
            raise FeedUnavailable("Fixture adapter requires mocked transport")
        if not fixture and (
            not self.access.permits(clock())
            or profile is None
            or profile.validation_environment != "genuine"
        ):
            raise FeedUnavailable(
                "Pakistan Practice API access/rights or genuine clock evidence unverified"
            )
        self._http = httpx.Client(
            base_url=PRACTICE_HOST,
            headers={"Authorization": "Bearer " + token, "Accept-Datetime-Format": "RFC3339"},
            timeout=8,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        self._identity: DemoIdentity | None = None
        self._sequences: dict[str, ClockSequence] = {}

    def _get(
        self, operation: str, *, symbol: str = "EURUSD", timeframe: str = "M1"
    ) -> dict[str, Any]:
        if symbol not in SYMBOLS or timeframe not in TIMEFRAMES:
            raise FeedUnavailable("Practice instrument/timeframe refused")
        params: dict[str, str | int] = {}
        if operation == "summary":
            path = f"/v3/accounts/{self._account}/summary"
        elif operation == "instruments":
            path = f"/v3/accounts/{self._account}/instruments"
            params = {"instruments": SYMBOLS[symbol]}
        elif operation == "pricing":
            path = f"/v3/accounts/{self._account}/pricing"
            params = {"instruments": SYMBOLS[symbol]}
        elif operation == "candles":
            path = f"/v3/instruments/{SYMBOLS[symbol]}/candles"
            params = {"granularity": timeframe, "count": self.config.max_rows, "price": "B"}
        else:
            raise FeedUnavailable("Operation outside Practice read-only boundary")
        try:
            with self._http.stream("GET", path, params=params) as response:
                if response.status_code != 200:
                    raise FeedUnavailable("Practice read unavailable or permission refused")
                data = bytearray()
                for block in response.iter_bytes(65536):
                    data.extend(block)
                    if len(data) > 2_000_000:
                        raise FeedUnavailable("Practice response exceeds read bound")
            import json

            value = json.loads(data)
            if not isinstance(value, dict):
                raise FeedUnavailable("Practice native response shape invalid")
            return value
        except (httpx.HTTPError, ValueError):
            raise FeedUnavailable("Practice read refused or unavailable") from None

    def verify(self) -> DemoIdentity:
        """Pin the account and Practice host; never output balance, account ID or personal name."""
        if not self.synthetic and not self.access.permits(self.clock()):
            raise IdentityRefused("Practice access evidence expired")
        account = self._get("summary").get("account")
        if not isinstance(account, dict) or account.get("id") != self._account:
            raise IdentityRefused("Practice identity refused")
        currency = account.get("currency")
        if not isinstance(currency, str) or len(currency) != 3:
            raise FeedUnavailable("Practice account currency unavailable")
        if self._identity and currency != self._identity.currency:
            raise IdentityRefused("Practice account currency changed")
        self._identity = DemoIdentity(
            fingerprint=hashlib.sha256((PRACTICE_HOST + ":" + self._account).encode()).hexdigest(),
            broker="OANDA Practice",
            server="api-fxpractice.oanda.com",
            currency=currency,
            terminal_build=0,
            verified_at=self.clock(),
            environment="practice",
        )
        return self._identity

    def connect(self) -> DemoIdentity:
        """Read the pinned existing Practice account; no creation or login mutation."""
        return self.verify()

    def metadata(self, symbol: str) -> InstrumentFacts:
        """Preserve unavailable contract/tick facts; OANDA units are not invented MT5 lots."""
        identity = self.verify()
        rows = self._get("instruments", symbol=symbol).get("instruments", [])
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
            or rows[0].get("name") != SYMBOLS[symbol]
        ):
            raise FeedUnavailable("Practice instrument identity unavailable")
        row = rows[0]
        self.verify()
        return InstrumentFacts(
            symbol=LiteralSymbol(symbol),
            broker_symbol=SYMBOLS[symbol],
            description=SYMBOLS[symbol],
            base_currency="EUR" if symbol == "EURUSD" else "XAU",
            quote_currency="USD",
            account_currency=identity.currency,
            point=None,
            tick_size=None,
            digits=row.get("displayPrecision"),
            contract_size=None,
            volume_min=row.get("minimumTradeSize"),
            volume_max=row.get("maximumOrderUnits"),
            volume_step=None,
            tick_value=None,
            trade_mode=None,
            reported_spread_points=None,
            observed_at=self.clock(),
            source="synthetic" if self.synthetic else "oanda_practice",
            conversion_required=identity.currency != "USD",
            profit_currency="USD",
            visible=True,
            selected=True,
        )

    def _stamp(self, timestamp: str, symbol: str, kind: str, receipt: datetime) -> ClockStamp:
        if (
            not isinstance(timestamp, str)
            or not timestamp.endswith("Z")
            or self.clock_profile is None
        ):
            raise FeedUnavailable("Explicit Z timestamp and verified clock profile required")
        identity = self.verify()
        at = parse_explicit_utc(timestamp)
        stamp = self.clock_profile.normalize(
            at,
            raw_representation=timestamp,
            provider=self.provider,
            broker=identity.broker,
            server=identity.server,
            environment="practice",
            instrument=symbol,
            build=0,
            identity_fingerprint=identity.fingerprint,
            now=receipt,
            kind=kind,
        )
        if stamp.normalized_at > receipt + timedelta(seconds=self.config.future_tolerance_seconds):
            raise FeedUnavailable("Practice future timestamp refused")
        return stamp

    def quote(self, symbol: str) -> tuple[Observation, dict[str, Any]]:
        self.metadata(symbol)
        before, mono = self.clock(), time.monotonic()
        result = self._get("pricing", symbol=symbol)
        receipt, elapsed = self.clock(), time.monotonic() - mono
        if abs((receipt - before).total_seconds() - elapsed) > 2:
            raise FeedUnavailable("Practice receipt clock stepped")
        prices = result.get("prices")
        if not isinstance(prices, list) or len(prices) != 1 or not isinstance(prices[0], dict):
            raise FeedUnavailable("Practice quote unavailable")
        raw = prices[0]
        self.latest_raw = {
            k: raw[k] for k in ("instrument", "time", "status", "bids", "asks") if k in raw
        }
        if raw.get("instrument") != SYMBOLS[symbol] or raw.get("status") != "tradeable":
            raise FeedUnavailable("Practice instrument mismatch or market unavailable")
        stamp = self._stamp(raw["time"], symbol, "quote", receipt)
        bid = max(Decimal(str(r["price"])) for r in raw["bids"])
        ask = min(Decimal(str(r["price"])) for r in raw["asks"])
        row = Observation(
            symbol=LiteralSymbol(symbol),
            broker_symbol=SYMBOLS[symbol],
            kind="quote",
            timeframe="tick",
            source_at=stamp.normalized_at,
            received_at=receipt,
            clock_stamp=stamp,
            evidence="synthetic" if self.synthetic else "historical_backfill",
            bid=bid,
            ask=ask,
        )
        self._sequences.setdefault(symbol, ClockSequence()).observe(row.source_at, receipt)
        return row, self.latest_raw

    def candles(
        self, symbol: str, timeframe: str
    ) -> tuple[list[Observation], list[dict[str, Any]]]:
        self.metadata(symbol)
        result = self._get("candles", symbol=symbol, timeframe=timeframe)
        if result.get("instrument") != SYMBOLS[symbol] or result.get("granularity") != timeframe:
            raise FeedUnavailable("Practice candle identity mismatch")
        receipt = self.clock()
        out: list[Observation] = []
        raw_rows = result.get("candles")
        if not isinstance(raw_rows, list) or len(raw_rows) > self.config.max_rows:
            raise FeedUnavailable("Practice candle bound refused")
        for raw in raw_rows:
            if not isinstance(raw, dict) or raw.get("complete") is not True:
                continue
            stamp = self._stamp(raw["time"], symbol, "candle", receipt)
            if stamp.normalized_at + timedelta(seconds=TIMEFRAMES[timeframe]) > receipt:
                raise FeedUnavailable("Practice unfinished candle refused")
            bar = raw["bid"]
            out.append(
                Observation(
                    symbol=LiteralSymbol(symbol),
                    broker_symbol=SYMBOLS[symbol],
                    kind="candle",
                    timeframe=timeframe,
                    source_at=stamp.normalized_at,
                    received_at=receipt,
                    clock_stamp=stamp,
                    evidence="synthetic" if self.synthetic else "historical_backfill",
                    open=bar["o"],
                    high=bar["h"],
                    low=bar["l"],
                    close=bar["c"],
                    tick_volume=raw.get("volume"),
                )
            )
        return out, raw_rows

    def ticks(self, symbol: str) -> tuple[list[Observation], list[dict[str, Any]]]:
        raise FeedUnavailable("Practice adapter has no complete historical tick claim")

    def contract(self, symbol: str) -> ContractSpec:
        raise FeedUnavailable("Practice contract costs/constraints incomplete; sizing disabled")

    def quotes(self, symbol: str) -> Iterator[MarketQuote]:
        row, _ = self.quote(symbol)
        assert row.bid is not None and row.ask is not None
        yield MarketQuote(symbol=symbol, timestamp=row.source_at, bid=row.bid, ask=row.ask)

    def admission(self) -> AdmissionCheck:
        """Independently admit each instrument under authorized UTC, never under mock success."""
        identity = self.verify()
        host_ok = clock_reference_passes(independent_utc(clock=self.clock), self.clock())
        valid: dict[str, bool] = {}
        for symbol in self.config.symbols:
            try:
                row, _ = self.quote(symbol)
                valid[symbol] = (
                    0
                    <= (row.received_at - row.source_at).total_seconds()
                    <= self.config.max_tick_age_seconds
                )
            except (ValueError, KeyError, ArithmeticError):
                valid[symbol] = False
        return AdmissionCheck(
            checked_at=self.clock(),
            identity_fingerprint=identity.fingerprint,
            provider="oanda_practice",
            source_authorized=self.access.permits(self.clock()),
            security_passed=self.access.permits(self.clock()),
            clock_passed=host_ok and any(valid.values()),
            instruments=valid,
            reasons=() if host_ok else ("host_utc_unverified",),
        )

    def close(self) -> None:
        self._http.close()


def LiteralSymbol(symbol: str) -> Literal["EURUSD", "XAUUSD"]:
    """Validate canonical instrument before it reaches a source projection."""
    if symbol == "EURUSD":
        return "EURUSD"
    if symbol == "XAUUSD":
        return "XAUUSD"
    raise FeedUnavailable("Practice canonical symbol refused")
