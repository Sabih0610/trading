"""Optional cTrader demo source; fixed read interface, explicit view scope and rights."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import AwareDatetime, Field, SecretStr, StrictBool
from pydantic_settings import BaseSettings, SettingsConfigDict

from tb.ingest.broker.book import QuoteBook, integer
from tb.ingest.broker.models import (
    SERVER,
    BrokerContract,
    BrokerIdentity,
    BrokerQuote,
    BrokerRefused,
    Symbol,
)
from tb.ingest.broker.onboarding.models import AccessRights, parse_access_rights
from tb.ingest.broker.transport import DemoJsonChannel, MockReadChannel, ReadChannel
from tb.ingest.history.core import sha256_file
from tb.ingest.rights import SHADOW_USAGES, DataRights
from tb.ingest.rights_review import check_review, require_retention_window
from tb.risk.config import PolicyModel


class CTraderSettings(BaseSettings):
    """Optional root .env credentials; no redirect, account creation or token refresh."""

    model_config = SettingsConfigDict(env_prefix="CTRADER_DEMO_", extra="ignore")
    client_id: SecretStr = SecretStr("")
    client_secret: SecretStr = SecretStr("")
    access_token: SecretStr = SecretStr("")
    account_id: SecretStr = SecretStr("")
    access_expires_at: AwareDatetime | None = None
    requested_scope: Literal["accounts"] = "accounts"

    @classmethod
    def from_root(cls, root: Path) -> CTraderSettings:
        arguments: dict[str, Any] = {"_env_file": root / ".env"}
        return cls(**arguments)

    @property
    def configured(self) -> bool:
        return (
            all(
                v.get_secret_value()
                for v in (self.client_id, self.client_secret, self.access_token, self.account_id)
            )
            and self.access_expires_at is not None
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            (SERVER + ":" + self.account_id.get_secret_value()).encode()
        ).hexdigest()


def default_symbols() -> dict[Symbol, str]:
    return {"EURUSD": "EURUSD", "XAUUSD": "XAUUSD"}


class BrokerAccess(PolicyModel):
    """Public documentary preconditions; setting flags alone is not a provider verification."""

    broker_pin: str = Field(default="unconfigured", min_length=1, max_length=100)
    symbols: dict[Symbol, str] = Field(default_factory=default_symbols)
    pakistan_demo_verified: StrictBool = False
    no_funding_verified: StrictBool = False
    application_approved: StrictBool = False
    source_clock_verified: StrictBool = False
    independent_utc_checked_at: AwareDatetime | None = None
    evidence_reference: str | None = None
    evidence_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    expires_at: AwareDatetime | None = None

    def require(self, now: datetime) -> None:
        BrokerAccess.model_validate(self.model_dump())
        if not (
            self.symbols
            and len(self.symbols) <= 2
            and self.pakistan_demo_verified
            and self.no_funding_verified
            and self.application_approved
            and self.source_clock_verified
            and self.evidence_reference
            and self.evidence_sha256
            and self.expires_at
            and now < self.expires_at
            and self.independent_utc_checked_at
            and 0 <= (now - self.independent_utc_checked_at).total_seconds() <= 60
        ):
            raise BrokerRefused("broker_access_application_or_independent_clock_unverified")


COST_FIELDS = (
    "commission",
    "commissionType",
    "minCommission",
    "minCommissionType",
    "minCommissionAsset",
    "preciseTradingCommissionRate",
    "preciseMinCommission",
    "swapLong",
    "swapShort",
    "swapCalculationType",
    "swapPeriod",
    "swapTime",
    "swapRollover3Days",
    "skipSWAPPeriods",
    "chargeSwapAtWeekends",
    "rolloverCommission",
    "rolloverCommission3Days",
    "skipRolloverDays",
    "pnlConversionFeeRate",
    "measurementUnits",
    "tradingMode",
)


class CTraderQuoteSource:
    """No generic broker commands, account switching or SDK message constructors exposed."""

    def __init__(
        self,
        settings: CTraderSettings,
        rights: DataRights,
        *,
        root: Path,
        access: BrokerAccess | None = None,
        rights_path: Path | None = None,
        channel: MockReadChannel | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.settings, self.rights, self.root, self.clock = settings, rights, root, clock
        self.access, self.rights_path = access or BrokerAccess(), rights_path
        self.synthetic = isinstance(channel, MockReadChannel)
        self._channel: ReadChannel | None = channel
        self._identity: BrokerIdentity | None = None
        self._contracts: dict[Symbol, BrokerContract] = {}
        self._book = QuoteBook()
        self._rights_pin = rights.digest
        self._assets: dict[int, str] = {}
        self._light: dict[Symbol, dict[str, Any]] = {}
        self.latest_raw: dict[str, int | str] | None = None
        self.connected_at: datetime | None = None
        self._account = (
            integer(settings.account_id.get_secret_value()) if settings.configured else 0
        )

    @property
    def reason(self) -> str:
        return self._book.reason

    @property
    def identity(self) -> BrokerIdentity | None:
        return self._identity

    @property
    def instruments(self) -> tuple[Symbol, ...]:
        return tuple(self._contracts)

    def _permit(self) -> None:
        now = self.clock()
        if not self.settings.configured:
            raise BrokerRefused("CTRADER_DEMO credentials missing; broker feed disabled")
        if self.settings.access_expires_at is None or now >= self.settings.access_expires_at:
            raise BrokerRefused("broker_access_token_expired")
        if self.rights.digest != self._rights_pin:
            raise BrokerRefused("broker_rights_changed_or_revoked")
        provider = "owned_fixture" if self.synthetic else "ctrader_demo"
        for symbol in self.access.symbols:
            self.rights.require(
                SHADOW_USAGES,
                provider=provider,
                identity=self.settings.fingerprint,
                symbol=symbol,
                now=now,
            )
        if not self.synthetic:
            self.access.require(now)
            artifact = (self.root / (self.access.evidence_reference or "")).resolve()
            if (
                not artifact.is_relative_to((self.root / "work/rights").resolve())
                or artifact.name.startswith(".env")
                or not artifact.is_file()
                or artifact.stat().st_size > 131072
                or sha256_file(artifact) != self.access.evidence_sha256
            ):
                raise BrokerRefused("broker_access_and_clock_documentary_artifact_unverified")
            if self.rights_path is None:
                raise BrokerRefused("broker_documentary_rights_unverified")
            reviewed = check_review(self.root, self.rights_path, now, provider="ctrader_demo")
            if reviewed.digest != self._rights_pin:
                raise BrokerRefused("broker_rights_artifact_changed")
            require_retention_window(self.rights, 60)

    def _request(self, kind: int, values: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._channel is None:
            raise BrokerRefused("broker_not_connected")
        payload = {"ctidTraderAccountId": self._account, **(values or {})}
        reply = self._channel.request(kind, payload)
        if integer(reply.get("ctidTraderAccountId")) != self._account:
            raise BrokerRefused("broker_response_account_mismatch")
        return reply

    def _verify(self) -> BrokerIdentity:
        self._permit()
        if self._channel is None:
            raise BrokerRefused("broker_not_connected")
        token = self.settings.access_token.get_secret_value()
        listing = self._channel.request(2149, {"accessToken": token})
        if listing.get("accessToken") != token:
            raise BrokerRefused("broker_token_scope_binding_refused")
        scope = listing.get("permissionScope")
        if not ((type(scope) is int and scope == 0) or scope == "SCOPE_VIEW"):
            raise BrokerRefused("broker_view_scope_missing_or_escalated")
        accounts = listing.get("ctidTraderAccount", [])
        if not isinstance(accounts, list) or len(accounts) != 1:
            raise BrokerRefused("broker_account_list_invalid")
        rows = [
            a
            for a in accounts
            if isinstance(a, dict) and integer(a.get("ctidTraderAccountId")) == self._account
        ]
        if len(rows) != 1 or rows[0].get("isLive") is not False:
            raise BrokerRefused("broker_pinned_demo_account_unverified")
        if rows[0].get("brokerTitleShort") != self.access.broker_pin:
            raise BrokerRefused("broker_identity_pin_mismatch")
        if self._identity is None:
            self._request(2102, {"accessToken": token})
        trader = self._request(2121).get("trader")
        if (
            not isinstance(trader, dict)
            or integer(trader.get("ctidTraderAccountId")) != self._account
        ):
            raise BrokerRefused("broker_trader_identity_mismatch")
        if parse_access_rights(trader.get("accessRights")) is AccessRights.NO_LOGIN:
            raise BrokerRefused("broker_account_login_refused")
        if not self._assets:
            assets = self._request(2112).get("asset", [])
            if not isinstance(assets, list) or len(assets) > 2000:
                raise BrokerRefused("broker_asset_list_invalid")
            self._assets = {integer(a["assetId"]): str(a["name"]) for a in assets}
        currency = self._assets.get(integer(trader.get("depositAssetId")))
        if currency is None or (self._identity and currency != self._identity.account_currency):
            raise BrokerRefused("broker_account_currency_changed")
        self._identity = BrokerIdentity(
            account_fingerprint=self.settings.fingerprint,
            broker=self.access.broker_pin,
            account_currency=currency,
            checked_at=self.clock(),
            evidence="owned_fixture" if self.synthetic else "genuine",
        )
        return self._identity

    def verify(self) -> BrokerIdentity:
        try:
            return self._verify()
        except Exception:
            self.close()
            raise BrokerRefused("broker_view_identity_or_rights_verification_refused") from None

    def connect(self) -> BrokerIdentity:
        """Permission gates precede socket construction; discovery is exact, never fuzzy."""
        try:
            self._permit()
            self.connected_at = self.clock()
            if self._channel is None:
                if self.synthetic:
                    raise BrokerRefused("owned_source_restart_requires_new_mock_transport")
                self._channel = DemoJsonChannel()
            self._channel.request(
                2100,
                {
                    "clientId": self.settings.client_id.get_secret_value(),
                    "clientSecret": self.settings.client_secret.get_secret_value(),
                },
            )
            identity = self._verify()
            symbols = self._request(2114, {"includeArchivedSymbols": False}).get("symbol", [])
            if not isinstance(symbols, list) or len(symbols) > 20000:
                raise BrokerRefused("broker_symbol_catalog_invalid")
            for canonical, exact in self.access.symbols.items():
                rows = [s for s in symbols if s.get("symbolName") == exact]
                if len(rows) != 1 or rows[0].get("enabled") is not True:
                    continue
                row = rows[0]
                if (
                    self._assets.get(integer(row.get("baseAssetId")))
                    != ("EUR" if canonical == "EURUSD" else "XAU")
                    or self._assets.get(integer(row.get("quoteAssetId"))) != "USD"
                ):
                    raise BrokerRefused("broker_exact_instrument_assets_mismatch")
                self._light[canonical] = row
            if not self._light:
                raise BrokerRefused("broker_no_verified_instruments")
            for symbol in self._light:
                self.metadata(symbol)
            self._request(
                2127,
                {
                    "symbolId": [c.symbol_id for c in self._contracts.values()],
                    "subscribeToSpotTimestamp": True,
                },
            )
            return identity
        except Exception:
            self.close()
            raise BrokerRefused(
                "broker_connect_authentication_scope_or_instrument_refused"
            ) from None

    def metadata(self, symbol: Symbol) -> BrokerContract:
        """Preserve source field presence; no defaults pretending to be financial facts."""
        try:
            self._permit()
            if self._identity is None or symbol not in self._light:
                raise BrokerRefused("broker_instrument_not_verified")
            self._identity.require(self.clock())
            if symbol in self._contracts:
                return self._contracts[symbol]
            light = self._light[symbol]
            sid = integer(light["symbolId"])
            rows = self._request(2116, {"symbolId": [sid]}).get("symbol", [])
            if len(rows) != 1 or integer(rows[0].get("symbolId")) != sid:
                raise BrokerRefused("broker_contract_symbol_mismatch")
            row = rows[0]
            units = {
                name: Decimal(integer(row[field])) / 100 if field in row else None
                for name, field in [
                    ("lot_units", "lotSize"),
                    ("min_units", "minVolume"),
                    ("max_units", "maxVolume"),
                    ("step_units", "stepVolume"),
                ]
            }
            costs = {k: row[k] for k in COST_FIELDS if k in row}
            value = BrokerContract(
                account_fingerprint=self.settings.fingerprint,
                symbol=symbol,
                broker_symbol=light["symbolName"],
                symbol_id=sid,
                base_currency="EUR" if symbol == "EURUSD" else "XAU",
                account_currency=self._identity.account_currency,
                digits=integer(row.get("digits")),
                pip_position=integer(row.get("pipPosition")),
                lot_units=units["lot_units"],
                min_units=units["min_units"],
                max_units=units["max_units"],
                step_units=units["step_units"],
                native_costs=costs,
                native_contract={
                    k: row[k]
                    for k in (
                        "digits",
                        "pipPosition",
                        "lotSize",
                        "minVolume",
                        "maxVolume",
                        "stepVolume",
                        "slDistance",
                        "tpDistance",
                        "distanceSetIn",
                        "measurementUnits",
                        "tradingMode",
                    )
                    if k in row
                },
                observed_at=self.clock(),
                schedule=tuple(
                    (integer(v["startSecond"]), integer(v["endSecond"]))
                    for v in row.get("schedule", [])
                ),
                schedule_timezone=row.get("scheduleTimeZone"),
                holidays=tuple(row["holiday"]) if "holiday" in row else None,
                stop_distance=integer(row["slDistance"]) if "slDistance" in row else None,
                distance_unit=integer(row["distanceSetIn"]) if "distanceSetIn" in row else None,
                evidence=self._identity.evidence,
            )
            self._contracts[symbol] = value
            return value
        except Exception:
            self.close()
            raise BrokerRefused("broker_contract_metadata_refused") from None

    def read(self) -> BrokerQuote | None:
        """Read one bounded event; re-authenticate at most every twenty seconds."""
        try:
            self.latest_raw = None
            self._permit()
            if self._identity is None or self._channel is None:
                raise BrokerRefused("broker_not_connected")
            if (self.clock() - self._identity.checked_at).total_seconds() >= 20:
                self.verify()
            self._identity.require(self.clock())
            message = self._channel.receive()
            self._permit()
            if integer(message.get("payloadType")) == 51:
                return None
            if integer(message.get("payloadType")) != 2131:
                raise BrokerRefused("broker_unexpected_event_refused")
            event = message.get("payload")
            if (
                not isinstance(event, dict)
                or integer(event.get("ctidTraderAccountId")) != self._account
            ):
                raise BrokerRefused("broker_event_account_mismatch")
            contracts = [
                c for c in self._contracts.values() if c.symbol_id == integer(event.get("symbolId"))
            ]
            if len(contracts) != 1:
                raise BrokerRefused("broker_event_instrument_changed")
            self.latest_raw = {
                key: event[key]
                for key in ("symbolId", "timestamp", "bid", "ask")
                if key in event
                and isinstance(event[key], (int, str))
                and not isinstance(event[key], bool)
                and len(str(event[key])) <= 19
            }
            stamp = integer(event.get("timestamp"))
            if self.connected_at is None or stamp < int(self.connected_at.timestamp() * 1000):
                raise BrokerRefused("broker_preconnection_source_snapshot_refused")
            received = message.get("_received_at", self.clock())
            if (
                not isinstance(received, datetime)
                or received.tzinfo is None
                or not 0 <= (self.clock() - received).total_seconds() <= 5
            ):
                raise BrokerRefused("broker_buffered_receipt_stale_or_invalid")
            return self._book.accept(
                event, contracts[0], self._identity, received, self.rights.digest
            )
        except Exception:
            self.close()
            raise BrokerRefused("broker_quote_or_permission_refused") from None

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
        self._channel = None
        self._identity = None
        self._contracts.clear()
        self._light.clear()
        self._assets.clear()
        self._book.clear()
