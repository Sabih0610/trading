"""Fixed-host GET-only transport with persisted Basic credit reservations and caching."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.owned_transport import owned_transport
from tb.ingest.retention import EvidenceLifetime, lifetime, require_lifetime
from tb.ingest.rights import DataRights
from tb.ingest.rights_review import check_review

SYMBOLS = {"EURUSD": "EUR/USD", "XAUUSD": "XAU/USD"}
HOST = "https://api.twelvedata.com"


class TwelveDataSettings(BaseSettings):
    """The only credential source is an optional environment/root .env setting."""

    model_config = SettingsConfigDict(extra="ignore", env_prefix="TWELVE_DATA_")
    api_key: SecretStr = SecretStr("")

    @classmethod
    def from_root(cls, root: Path) -> TwelveDataSettings:
        return cls(_env_file=root / ".env", _env_file_encoding="utf-8")  # type: ignore[call-arg]


class QuotaRefused(FeedUnavailable):
    """Retry requires a later bounded invocation after the persisted cooldown."""


class EntitlementRefused(FeedUnavailable):
    """This exact endpoint/instrument is not authorized; never upgrade automatically."""


@dataclass(frozen=True)
class Reply:
    payload: dict[str, Any]
    received_at: datetime
    http_date: datetime
    cached: bool = False
    retention: EvidenceLifetime | None = None


class CreditBudget:
    """Crash-safe reservations, actual usage anchors, account scope and UTC reset windows."""

    def __init__(self, path: Path, scope: str, *, daily_ceiling: int = 800) -> None:
        if not 1 <= daily_ceiling <= 800:
            raise FeedUnavailable("twelve_data_daily_ceiling_refused")
        self.daily_ceiling = daily_ceiling
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=3)
        self.scope = scope
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS credits(scope TEXT, at TEXT, cost INTEGER);
            CREATE TABLE IF NOT EXISTS limits(scope TEXT PRIMARY KEY, payload TEXT);
            CREATE TABLE IF NOT EXISTS cooldown(scope TEXT PRIMARY KEY, until_at TEXT);
            CREATE TABLE IF NOT EXISTS cache(scope TEXT, key TEXT, payload TEXT, receipt TEXT,
                http_date TEXT, PRIMARY KEY(scope,key));
            CREATE TABLE IF NOT EXISTS cache_lifetimes(scope TEXT, key TEXT, payload TEXT,
                PRIMARY KEY(scope,key));
            CREATE TABLE IF NOT EXISTS m5_slots(scope TEXT, close_at TEXT, symbol TEXT,
                PRIMARY KEY(scope,close_at,symbol));
        """)
        self.db.commit()

    def _limits(self) -> dict[str, Any]:
        row = self.db.execute("SELECT payload FROM limits WHERE scope=?", (self.scope,)).fetchone()
        return json.loads(row[0]) if row else {}

    def reserve(self, now: datetime) -> None:
        """Charge before sending; uncertain responses are not refunded or retried."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.db.execute(
                "SELECT MAX(at) FROM credits WHERE scope=?", (self.scope,)
            ).fetchone()[0]
            if previous and datetime.fromisoformat(previous) > now + timedelta(seconds=2):
                raise QuotaRefused("twelve_data_receipt_clock_regressed")
            cooldown = self.db.execute(
                "SELECT until_at FROM cooldown WHERE scope=?", (self.scope,)
            ).fetchone()
            if cooldown and now < datetime.fromisoformat(cooldown[0]):
                raise QuotaRefused("twelve_data_retry_after_active")
            limits = self._limits()
            minute, day = (
                now.replace(second=0, microsecond=0),
                now.replace(hour=0, minute=0, second=0, microsecond=0),
            )
            for start, field, default in (
                (minute, "plan_limit", 8),
                (day, "plan_daily_limit", self.daily_ceiling),
            ):
                used = int(
                    self.db.execute(
                        "SELECT COALESCE(SUM(cost),0) FROM credits WHERE scope=? AND at>=?",
                        (self.scope, start.isoformat()),
                    ).fetchone()[0]
                )
                if limits and datetime.fromisoformat(limits["observed_at"]) >= start:
                    after = int(
                        self.db.execute(
                            "SELECT COALESCE(SUM(cost),0) FROM credits WHERE scope=? AND at>?",
                            (self.scope, limits["observed_at"]),
                        ).fetchone()[0]
                    )
                    upstream = limits["current_usage" if field == "plan_limit" else "daily_usage"]
                    used = max(used, upstream + after)
                if used >= min(default, limits.get(field, default)):
                    raise QuotaRefused("twelve_data_minute_or_daily_budget_exhausted")
            self.db.execute("INSERT INTO credits VALUES(?,?,1)", (self.scope, now.isoformat()))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def usage(self, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
        """A malformed/unknown plan cannot silently enable data calls."""
        fields = ("plan_limit", "plan_daily_limit", "current_usage", "daily_usage")
        if any(type(payload.get(f)) is not int or payload[f] < 0 for f in fields):
            raise FeedUnavailable("twelve_data_usage_schema_refused")
        if payload["plan_limit"] < 1 or payload["plan_daily_limit"] < 1:
            raise FeedUnavailable("twelve_data_zero_credit_plan")
        category = payload.get("plan_category")
        if not isinstance(category, str) or category.lower() != "basic":
            raise FeedUnavailable("twelve_data_basic_plan_not_confirmed")
        value = {f: payload[f] for f in fields}
        value.update(plan_category="basic", observed_at=now.isoformat())
        self.db.execute(
            "INSERT INTO limits VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET payload=excluded.payload",
            (self.scope, json.dumps(value)),
        )
        self.db.commit()
        return value

    def retry_after(self, now: datetime, value: str | None, *, daily: bool) -> None:
        until = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        if daily:
            until = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if value:
            try:
                candidate = now + timedelta(seconds=max(0, int(value)))
            except ValueError:
                try:
                    candidate = parsedate_to_datetime(value).astimezone(UTC)
                except (ValueError, TypeError, OverflowError):
                    candidate = until
            until = max(until, candidate)
        self.db.execute(
            "INSERT INTO cooldown VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET until_at=MAX(until_at,excluded.until_at)",
            (self.scope, until.isoformat()),
        )
        self.db.commit()

    def header_remaining(self, remaining: str | None, now: datetime) -> None:
        """Upstream shared-account consumption can only reduce available minute credits."""
        if remaining is None:
            return
        try:
            available = int(remaining)
        except ValueError:
            raise FeedUnavailable("twelve_data_credit_header_invalid") from None
        if available < 0:
            raise FeedUnavailable("twelve_data_credit_header_invalid")
        limits = self._limits()
        if limits:
            current_minute = now.replace(second=0, microsecond=0)
            used = max(0, min(8, limits["plan_limit"]) - available)
            # Preserve daily reservations since the earlier usage anchor.
            extra = int(
                self.db.execute(
                    "SELECT COALESCE(SUM(cost),0) FROM credits WHERE scope=? AND at>?",
                    (self.scope, limits["observed_at"]),
                ).fetchone()[0]
            )
            same_minute = datetime.fromisoformat(limits["observed_at"]) >= current_minute
            limits["current_usage"] = max(used, limits["current_usage"] if same_minute else 0)
            same_day = datetime.fromisoformat(limits["observed_at"]).date() == now.date()
            limits["daily_usage"] = limits["daily_usage"] + extra if same_day else extra
            limits["observed_at"] = now.isoformat()
            self.db.execute(
                "UPDATE limits SET payload=? WHERE scope=?", (json.dumps(limits), self.scope)
            )
            self.db.commit()

    def cached(
        self,
        key: str,
        now: datetime,
        ttl: int,
        *,
        rights: DataRights | None = None,
        synthetic: bool = False,
    ) -> Reply | None:
        retained = None
        if (
            synthetic
            and self.db.execute(
                "SELECT 1 FROM cache_lifetimes WHERE scope=? AND key=?", (self.scope, key)
            ).fetchone()
        ):
            raise FeedUnavailable("owned_cache_provenance_mismatch")
        if (
            rights is not None
            and self.db.execute(
                "SELECT 1 FROM cache WHERE scope=? AND key=?", (self.scope, key)
            ).fetchone()
        ):
            saved = self.db.execute(
                "SELECT payload FROM cache_lifetimes WHERE scope=? AND key=?", (self.scope, key)
            ).fetchone()
            retained = require_lifetime(rights, json.loads(saved[0]) if saved else None, now)
        row = self.db.execute(
            "SELECT payload,receipt,http_date FROM cache WHERE scope=? AND key=?", (self.scope, key)
        ).fetchone()
        if row and 0 <= (now - datetime.fromisoformat(row[1])).total_seconds() < ttl:
            return Reply(
                json.loads(row[0]),
                datetime.fromisoformat(row[1]),
                datetime.fromisoformat(row[2]),
                True,
                retained,
            )
        return None

    def remember(self, key: str, reply: Reply) -> None:
        if reply.retention is not None:
            self.db.execute(
                "INSERT INTO cache_lifetimes VALUES(?,?,?) ON CONFLICT(scope,key) DO UPDATE SET payload=excluded.payload",
                (self.scope, key, reply.retention.model_dump_json()),
            )
        else:
            self.db.execute(
                "DELETE FROM cache_lifetimes WHERE scope=? AND key=?", (self.scope, key)
            )
        self.db.execute(
            "INSERT INTO cache VALUES(?,?,?,?,?) ON CONFLICT(scope,key) DO UPDATE SET payload=excluded.payload,receipt=excluded.receipt,http_date=excluded.http_date",
            (
                self.scope,
                key,
                json.dumps(reply.payload),
                reply.received_at.isoformat(),
                reply.http_date.isoformat(),
            ),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def claim_m5(self, close_at: datetime, symbol: str, now: datetime) -> bool:
        """Claim one persisted post-close slot; missed windows cannot become live polls."""
        lag = (now - close_at).total_seconds()
        if symbol not in SYMBOLS or close_at.minute % 5 or close_at.second or not 120 <= lag <= 180:
            return False
        if now.weekday() >= 5 or (now.weekday() == 4 and now.hour >= 21):
            return False
        with self.db:
            result = self.db.execute(
                "INSERT OR IGNORE INTO m5_slots VALUES(?,?,?)",
                (self.scope, close_at.isoformat(), symbol),
            )
        return result.rowcount == 1


class TwelveDataClient:
    """Only usage, reference rates and two M1 time series can reach the network."""

    def __init__(
        self,
        settings: TwelveDataSettings,
        budget: CreditBudget,
        *,
        transport: httpx.BaseTransport | None = None,
        fixture_transport: httpx.MockTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        rights: DataRights | None = None,
        rights_root: Path | None = None,
    ) -> None:
        self._key, self.budget = settings.api_key, budget
        expected_scope = hashlib.sha256(self._key.get_secret_value().encode()).hexdigest()
        if self._key.get_secret_value() and budget.scope != expected_scope:
            raise FeedUnavailable("twelve_data_credit_account_scope_mismatch")
        self.clock, self.monotonic = clock, monotonic
        self.rights = rights
        self.rights_root = rights_root
        if transport is not None and fixture_transport is not None:
            raise FeedUnavailable("owned_and_production_transports_are_exclusive")
        self._synthetic = fixture_transport is not None
        if fixture_transport is not None:
            transport = owned_transport(fixture_transport)
        self._http = httpx.Client(
            timeout=httpx.Timeout(10), follow_redirects=False, trust_env=False, transport=transport
        )
        self.plan_confirmed = False
        self.network_requests = 0

    @property
    def synthetic(self) -> bool:
        return self._synthetic

    @property
    def credential_scope(self) -> str:
        return hashlib.sha256(self._key.get_secret_value().encode()).hexdigest()

    @property
    def source_identity(self) -> str:
        return hashlib.sha256(("twelve_data:" + self.credential_scope).encode()).hexdigest()

    def get(self, endpoint: str, symbol: str | None = None, *, timeframe: str = "M1") -> Reply:
        """No arbitrary method, host, headers, params or query keys are accepted."""
        if endpoint not in {"api_usage", "exchange_rate", "time_series"}:
            raise FeedUnavailable("twelve_data_read_allowlist_refused")
        if timeframe not in {"M1", "M5"} or (endpoint != "time_series" and timeframe != "M1"):
            raise FeedUnavailable("twelve_data_timeframe_refused")
        if (endpoint == "api_usage" and symbol is not None) or (
            endpoint != "api_usage" and symbol not in SYMBOLS
        ):
            raise FeedUnavailable("twelve_data_exact_instrument_refused")
        if not self._key.get_secret_value().strip():
            raise FeedUnavailable("Twelve Data disabled: TWELVE_DATA_API_KEY missing")
        if endpoint != "api_usage" and not self.plan_confirmed:
            raise FeedUnavailable("twelve_data_actual_plan_check_required")
        if not self.synthetic:
            if self.rights is None:
                raise FeedUnavailable("data_rights_approval_required; genuine retrieval disabled")
            if (
                self.rights_root is None
                or check_review(
                    self.rights_root, self.rights_root / "config/data_rights.yaml", self.clock()
                ).digest
                != self.rights.digest
            ):
                raise FeedUnavailable("current_documentary_data_rights_required")
            self.rights.require(
                ("retrieval", "raw_cache"),
                provider="twelve_data",
                identity=self.source_identity,
                symbol=symbol or "EURUSD",
                now=self.clock(),
            )
        params = {"timezone": "UTC"}
        if symbol:
            params["symbol"] = SYMBOLS[symbol]
        if endpoint == "time_series":
            params.update(
                interval="5min" if timeframe == "M5" else "1min", outputsize="3", order="asc"
            )
        cache_key = endpoint + ":" + (symbol or "")
        if timeframe == "M5":
            cache_key += ":M5"
        cached = self.budget.cached(
            cache_key,
            self.clock(),
            45 if symbol else 10,
            rights=None if self.synthetic else self.rights,
            synthetic=self.synthetic,
        )
        if cached:
            if endpoint == "api_usage":
                self.budget.usage(cached.payload, cached.received_at)
                self.plan_confirmed = True
            return cached
        before, mono = self.clock(), self.monotonic()
        self.budget.reserve(before)
        self.network_requests += 1
        try:
            with self._http.stream(
                "GET",
                HOST + "/" + endpoint,
                params=params,
                headers={
                    "Authorization": "apikey " + self._key.get_secret_value(),
                    "Cache-Control": "no-cache",
                },
            ) as response:
                body = bytearray()
                for block in response.iter_bytes(8192):
                    body.extend(block)
                    if len(body) > 131072:
                        raise FeedUnavailable("twelve_data_response_too_large")
                receipt, elapsed = self.clock(), self.monotonic() - mono
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise FeedUnavailable("twelve_data_object_required")
                code = payload.get("code", response.status_code)
                if response.status_code == 429 or code == 429:
                    daily = "daily" in str(payload.get("message", "")).lower()
                    self.budget.retry_after(
                        receipt, response.headers.get("Retry-After"), daily=daily
                    )
                    raise QuotaRefused("twelve_data_quota_429; no automatic retry")
                if response.status_code == 403 or code == 403:
                    raise EntitlementRefused("twelve_data_instrument_or_endpoint_not_entitled")
                if response.status_code != 200 or payload.get("status") == "error":
                    raise FeedUnavailable("twelve_data_api_error; payload and credentials withheld")
                # Never persist an upstream echo of a key, even in a nominal success body.
                if self._key.get_secret_value() in body.decode():
                    raise FeedUnavailable("twelve_data_credential_echo_refused")
                http_date = parsedate_to_datetime(response.headers["Date"]).astimezone(UTC)
                if (
                    elapsed < 0
                    or elapsed > 10
                    or abs((receipt - before).total_seconds() - elapsed) > 2
                    or abs((receipt - http_date).total_seconds()) > 5
                    or int(response.headers.get("Age", "0")) > 0
                ):
                    raise FeedUnavailable("twelve_data_receipt_or_http_clock_refused")
                reply = Reply(payload, receipt, http_date)
                if not self.synthetic:
                    assert self.rights is not None
                    reply = replace(reply, retention=lifetime(self.rights, receipt))
                    require_lifetime(self.rights, reply.retention, self.clock())
                if endpoint == "api_usage":
                    self.budget.usage(payload, receipt)
                    self.plan_confirmed = True
                self.budget.header_remaining(response.headers.get("api-credits-left"), receipt)
                if (
                    timeframe == "M5"
                    and not self.synthetic
                    and response.headers.get("api-credits-used") != "1"
                ):
                    self.budget.retry_after(receipt, None, daily=True)
                    self.plan_confirmed = False
                    raise FeedUnavailable("M5_endpoint_credit_weight_unverified; review required")
                self.budget.remember(cache_key, reply)
                return reply
        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
            UnicodeError,
        ) as exc:
            if isinstance(exc, FeedUnavailable):
                raise
            raise FeedUnavailable(
                "twelve_data_transport_or_schema_error:" + type(exc).__name__
            ) from None

    def close(self) -> None:
        self._http.close()
