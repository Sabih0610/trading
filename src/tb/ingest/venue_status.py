"""Approved public Spot status metadata and pure, entry-only veto decisions."""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from tb.core.holdout import require_unsealed
from tb.ingest.history.core import atomic_write_json

SYMBOLS = ("XAUTUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")
ENDPOINT = "https://api.binance.com/api/v3/exchangeInfo"
TERMS_NOTICE = "https://developers.binance.com/en/docs/products/spot/PROD-TERMS-OF-USE"
TERMS_NOTICE_MODIFIED = "2026-10-30"
TERMS_OBSERVED = "2026-11-03"
Evidence = Literal["public_api", "owned_fixture"]
VetoReason = Literal["venue_unknown", "venue_stale", "venue_not_trading", "venue_trading"]


class VenueRefused(ValueError):
    """Static refusal category for status metadata, never a provider response body."""


def utc(value: datetime) -> datetime:
    """Reject clocks that cannot establish a UTC receive-time ordering."""
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise VenueRefused("venue_clock_requires_aware_UTC")
    return value


class VenueModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class VenueObservation(VenueModel):
    """A locally received fact; serverTime cannot move its availability clock."""

    symbol: str
    raw_status: str
    known_at: AwareDatetime
    evidence: Evidence = "owned_fixture"

    @field_validator("known_at")
    @classmethod
    def clock(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("symbol")
    @classmethod
    def allowed_symbol(cls, value: str) -> str:
        if value not in SYMBOLS:
            raise VenueRefused("venue_symbol_outside_scope")
        return value

    @field_validator("raw_status")
    @classmethod
    def bounded_status(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z_]{1,40}", value):
            raise VenueRefused("venue_status_malformed")
        return value


class VetoDecision(VenueModel):
    """Permission to proceed to deterministic risk checks, never permission to trade."""

    symbol: str
    at: AwareDatetime
    veto: bool
    reason: VetoReason
    raw_status: str | None = None
    known_at: AwareDatetime | None = None
    evidence: Evidence | None = None

    @field_validator("at", "known_at")
    @classmethod
    def clock(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc(value)

    @model_validator(mode="after")
    def permits_only_fresh_trading(self) -> VetoDecision:
        if not self.veto and (
            self.reason != "venue_trading"
            or self.raw_status != "TRADING"
            or self.known_at is None
            or self.evidence is None
            or not timedelta(0) <= self.at - self.known_at <= timedelta(minutes=10)
        ):
            raise VenueRefused("venue_permissive_decision_without_fresh_TRADING")
        return self


class VenueBook(VenueModel):
    """Bounded immutable facts, with no I/O, clock or access to positions/exits."""

    observations: tuple[VenueObservation, ...] = Field(default=(), max_length=4100)

    def venue_veto(self, symbol: str, at: datetime) -> VetoDecision:
        """Fail closed on unknown/nontrading/stale entry status, using no future facts."""
        utc(at)
        known = [o for o in self.observations if o.symbol == symbol and o.known_at <= at]
        latest = max(known, key=lambda o: o.known_at, default=None)
        reason: VetoReason = "venue_unknown"
        if latest is not None:
            if len({o.raw_status for o in known if o.known_at == latest.known_at}) != 1:
                return VetoDecision(symbol=symbol, at=at, veto=True, reason="venue_unknown")
            reason = (
                "venue_stale"
                if at - latest.known_at > timedelta(minutes=10)
                else "venue_not_trading"
                if latest.raw_status != "TRADING"
                else "venue_trading"
            )
        return VetoDecision(
            symbol=symbol,
            at=at,
            veto=reason != "venue_trading",
            reason=reason,
            raw_status=latest.raw_status if latest else None,
            known_at=latest.known_at if latest else None,
            evidence=latest.evidence if latest else None,
        )


def parse_status(
    payload: bytes, received_at: datetime, *, evidence: Evidence = "public_api"
) -> tuple[VenueObservation, ...]:
    """Project status strings only, refusing missing/duplicate symbols and malformed JSON."""
    utc(received_at)
    if not payload or len(payload) > 2 * 1024**2:
        raise VenueRefused("venue_response_size_refused")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_: str) -> None:
        raise ValueError("nonfinite JSON number")

    try:
        value = json.loads(payload, object_pairs_hook=object_pairs, parse_constant=constant)
        rows = value["symbols"]
        if not isinstance(rows, list) or len(rows) != len(SYMBOLS):
            raise ValueError
        observations = tuple(
            VenueObservation(
                symbol=row["symbol"],
                raw_status=row["status"],
                known_at=received_at,
                evidence=evidence,
            )
            for row in rows
        )
        if {o.symbol for o in observations} != set(SYMBOLS):
            raise ValueError
        return observations
    except (ValueError, KeyError, TypeError, RecursionError):
        raise VenueRefused("venue_response_malformed") from None


_SCHEMA = """
CREATE TABLE venue_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE status_changes(seq INTEGER PRIMARY KEY, symbol TEXT NOT NULL,
 old_status TEXT, new_status TEXT NOT NULL, known_at TEXT NOT NULL, raw_status TEXT NOT NULL);
CREATE TABLE current_status(symbol TEXT PRIMARY KEY, raw_status TEXT NOT NULL,
 last_seen TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE TABLE polling(id INTEGER PRIMARY KEY CHECK(id=1), next_at TEXT NOT NULL,
 failures INTEGER NOT NULL, last_error TEXT);
CREATE TRIGGER changes_no_update BEFORE UPDATE ON status_changes
 BEGIN SELECT RAISE(ABORT,'status changes are append only'); END;
CREATE TRIGGER changes_no_delete BEFORE DELETE ON status_changes
 BEGIN SELECT RAISE(ABORT,'status changes are append only'); END;
"""


def schema_rows(db: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    """Pin journal tables and append-only triggers without repairing an existing database."""
    return db.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()


def delay_deadline(now: datetime, delay: float) -> datetime:
    """An enormous Retry-After closes the gate instead of overflowing into early retries."""
    remaining = (datetime.max.replace(tzinfo=UTC) - now).total_seconds() - 1
    return now + timedelta(seconds=min(delay, remaining))


class VenueStore:
    """Private SQLite journal: changes append; latest poll receipt is operational state."""

    def __init__(
        self, path: Path, *, evidence: Evidence = "public_api", create: bool = False
    ) -> None:
        require_unsealed(path)
        self.path, self.evidence = path.resolve(), evidence
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() and not create:
            raise VenueRefused("venue_store_missing")
        fresh = not self.path.exists()
        if not fresh and self.path.stat().st_size > 64 * 1024**2:
            raise VenueRefused("venue_store_size_refused")
        self.db = sqlite3.connect(self.path, timeout=5)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA foreign_keys=ON")
        if fresh:
            self.db.executescript(_SCHEMA)
            self.db.executemany(
                "INSERT INTO venue_meta VALUES (?,?)",
                [
                    ("version", "venue-status-1"),
                    ("evidence", evidence),
                    ("source", ENDPOINT),
                    ("terms_notice", TERMS_NOTICE),
                    ("terms_notice_modified", TERMS_NOTICE_MODIFIED),
                    ("terms_observed", TERMS_OBSERVED),
                    ("full_product_terms_version", "unverified"),
                ],
            )
            self.db.execute(
                "INSERT INTO polling VALUES(1,?,0,NULL)",
                (datetime(1970, 1, 1, tzinfo=UTC).isoformat(),),
            )
            self.db.commit()
        meta = dict(self.db.execute("SELECT key,value FROM venue_meta"))
        if meta.get("version") != "venue-status-1" or meta.get("evidence") != evidence:
            self.db.close()
            raise VenueRefused("venue_store_identity_refused")
        with sqlite3.connect(":memory:") as expected:
            expected.executescript(_SCHEMA)
            if schema_rows(self.db) != schema_rows(expected):
                self.db.close()
                raise VenueRefused("venue_store_schema_refused")

    def close(self) -> None:
        """Release the private metadata database handle."""
        self.db.close()

    def reserve_poll(self, now: datetime, interval: float) -> bool:
        """Persist minimum cadence before issuing HTTP, including restart/concurrent callers."""
        utc(now)
        if not math.isfinite(interval) or interval < 60:
            raise VenueRefused("venue_poll_interval_below_60s")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            stamp, failures = self.db.execute(
                "SELECT next_at,failures FROM polling WHERE id=1"
            ).fetchone()
            if now < datetime.fromisoformat(stamp):
                self.db.rollback()
                return False
            self.db.execute(
                "UPDATE polling SET next_at=?,failures=? WHERE id=1",
                (delay_deadline(now, interval).isoformat(), 0 if failures >= 3 else failures),
            )
            self.db.commit()
            return True
        except BaseException:
            self.db.rollback()
            raise

    def accept(self, observations: tuple[VenueObservation, ...]) -> int:
        """Commit one whole received poll; duplicates update freshness without history rows."""
        if self.path.stat().st_size > 64 * 1024**2:
            raise VenueRefused("venue_store_size_refused")
        if (
            len(observations) != 4
            or {o.symbol for o in observations} != set(SYMBOLS)
            or len({o.known_at for o in observations}) != 1
            or any(o.evidence != self.evidence for o in observations)
        ):
            raise VenueRefused("venue_poll_identity_refused")
        changed = 0
        with self.db:
            for observation in observations:
                VenueObservation.model_validate(observation.model_dump())
                previous = self.db.execute(
                    "SELECT raw_status,last_seen,changed_at FROM current_status WHERE symbol=?",
                    (observation.symbol,),
                ).fetchone()
                if previous and observation.known_at < datetime.fromisoformat(previous[1]):
                    raise VenueRefused("venue_receipt_clock_regressed")
                if (
                    previous
                    and observation.known_at == datetime.fromisoformat(previous[1])
                    and observation.raw_status != previous[0]
                ):
                    raise VenueRefused("venue_conflicting_same_receipt")
                stamp = observation.known_at.isoformat()
                if previous is None or observation.raw_status != previous[0]:
                    self.db.execute(
                        "INSERT INTO status_changes(symbol,old_status,new_status,known_at,raw_status) VALUES (?,?,?,?,?)",
                        (
                            observation.symbol,
                            previous[0] if previous else None,
                            observation.raw_status,
                            stamp,
                            observation.raw_status,
                        ),
                    )
                    changed += 1
                    changed_at = stamp
                else:
                    changed_at = previous[2]
                self.db.execute(
                    "INSERT INTO current_status VALUES(?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET raw_status=excluded.raw_status,last_seen=excluded.last_seen,changed_at=excluded.changed_at",
                    (observation.symbol, observation.raw_status, stamp, changed_at),
                )
            self.db.execute("UPDATE polling SET failures=0,last_error=NULL WHERE id=1")
        return changed

    def back_off(self, now: datetime, reason: str, minimum_delay: float) -> None:
        """Persist a server/exponential wait; three failed attempts require a longer cooldown."""
        utc(now)
        with self.db:
            stamp, failures = self.db.execute(
                "SELECT next_at,failures FROM polling WHERE id=1"
            ).fetchone()
            failures += 1
            delay = max(minimum_delay, 600 if failures >= 3 else 60 * 2 ** (failures - 1))
            deadline = max(datetime.fromisoformat(stamp), delay_deadline(now, delay))
            self.db.execute(
                "UPDATE polling SET next_at=?,failures=?,last_error=? WHERE id=1",
                (deadline.isoformat(), failures, reason),
            )

    def book(self) -> VenueBook:
        """Load bounded change facts plus latest successful receipts; no fabricated history."""
        values = [
            VenueObservation(
                symbol=s,
                raw_status=status,
                known_at=datetime.fromisoformat(stamp),
                evidence=self.evidence,
            )
            for s, status, stamp in self.db.execute(
                "SELECT symbol,raw_status,known_at FROM status_changes ORDER BY seq DESC LIMIT 4096"
            )
        ]
        values += [
            VenueObservation(
                symbol=s,
                raw_status=status,
                known_at=datetime.fromisoformat(stamp),
                evidence=self.evidence,
            )
            for s, status, stamp in self.db.execute(
                "SELECT symbol,raw_status,last_seen FROM current_status"
            )
        ]
        return VenueBook(observations=tuple(values))

    def health(self, at: datetime) -> dict[str, Any]:
        """Project four current statuses and change times, never raw HTTP bodies."""
        book = self.book()
        next_at, failures, last_error = self.db.execute(
            "SELECT next_at,failures,last_error FROM polling WHERE id=1"
        ).fetchone()
        changes = {
            s: stamp for s, stamp in self.db.execute("SELECT symbol,changed_at FROM current_status")
        }
        return {
            "source": ENDPOINT,
            "evidence": self.evidence,
            "observed_at": utc(at).isoformat(),
            "terms_notice_modified": TERMS_NOTICE_MODIFIED,
            "terms_observed": TERMS_OBSERVED,
            "full_product_terms_version": "unverified",
            "code_version": "venue-status-1",
            "next_poll_at": next_at,
            "consecutive_failures": failures,
            "last_error_category": last_error,
            "symbols": [
                {
                    **book.venue_veto(symbol, at).model_dump(mode="json"),
                    "last_change": changes.get(symbol),
                }
                for symbol in SYMBOLS
            ],
        }


class PollOutcome(VenueModel):
    attempted: bool
    changes: int = 0
    category: str


def retry_after(value: str | None, received_at: datetime) -> float:
    """Honor both numeric and HTTP-date Retry-After without capping away server waits."""
    if value is None:
        return 60
    try:
        delay = float(value)
        if math.isfinite(delay) and delay >= 0:
            return delay
    except ValueError:
        pass
    try:
        stamp = parsedate_to_datetime(value)
        return max(0, (stamp.astimezone(UTC) - received_at).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return 60


class VenueMonitor:
    """One bounded public GET per due cycle; three failures then >=10 minute cooldown."""

    def __init__(
        self,
        store: VenueStore,
        client: httpx.Client,
        *,
        interval: float = 60,
        clock: Callable[[], datetime] | None = None,
        elapsed: Callable[[], float] | None = None,
    ) -> None:
        if interval < 60 or not math.isfinite(interval):
            raise VenueRefused("venue_poll_interval_below_60s")
        if client.auth is not None or any(
            name in client.headers for name in ("Authorization", "X-MBX-APIKEY")
        ):
            raise VenueRefused("venue_client_must_be_public_without_credentials")
        self.store, self.client, self.interval = store, client, interval
        self.clock = clock or (lambda: datetime.now(UTC))
        self.elapsed = elapsed or time.monotonic

    def poll_once(self) -> PollOutcome:
        if not self.store.reserve_poll(self.clock(), self.interval):
            return PollOutcome(attempted=False, category="not_due")
        received = self.clock()
        request_started = self.elapsed()
        try:
            with self.client.stream(
                "GET",
                ENDPOINT,
                params={"symbols": json.dumps(SYMBOLS, separators=(",", ":"))},
                timeout=10,
                follow_redirects=False,
            ) as response:
                if response.status_code in (418, 429):
                    received = self.clock()
                    delay = retry_after(response.headers.get("Retry-After"), received)
                    self.store.back_off(
                        received,
                        "rate_limited",
                        max(
                            delay,
                            3600
                            if response.status_code == 418 and "Retry-After" not in response.headers
                            else 60,
                        ),
                    )
                    return PollOutcome(attempted=True, category="rate_limited")
                if response.status_code != 200:
                    raise VenueRefused("venue_http_refused")
                body = bytearray()
                for chunk in response.iter_bytes():
                    if self.elapsed() - request_started > 20:
                        raise VenueRefused("venue_response_deadline")
                    body.extend(chunk)
                    if len(body) > 2 * 1024**2:
                        raise VenueRefused("venue_response_size_refused")
                received = self.clock()
                observations = parse_status(bytes(body), received, evidence=self.store.evidence)
            changes = self.store.accept(observations)
            return PollOutcome(attempted=True, changes=changes, category="ok")
        except (httpx.HTTPError, VenueRefused, ValueError):
            self.store.back_off(self.clock(), "request_or_response_refused", 60)
            return PollOutcome(attempted=True, category="request_or_response_refused")


def main() -> None:
    """Run approved status-only monitoring; no keys, prices, orders or announcement scraping."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--seconds", type=float, default=0)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds < 0:
        parser.error("--seconds must be finite and nonnegative")
    root = Path(__file__).resolve().parents[3]
    if (root / ".env").exists():
        raise VenueRefused("venue_monitor_requires_credential_free_checkout")
    store = VenueStore(root / "work/venue_status/status.sqlite", create=True)
    started = time.monotonic()
    try:
        with httpx.Client(follow_redirects=False, trust_env=False, timeout=10) as client:
            monitor = VenueMonitor(store, client, interval=args.interval)
            while args.seconds <= 0 or time.monotonic() - started < args.seconds:
                outcome = monitor.poll_once()
                if outcome.attempted:
                    atomic_write_json(
                        root / "reports/data_quality/venue-status-health.json",
                        store.health(datetime.now(UTC)),
                    )
                time.sleep(
                    min(5, max(0, args.seconds - (time.monotonic() - started)))
                    if args.seconds > 0
                    else 5
                )
    except KeyboardInterrupt:
        pass
    finally:
        store.close()


if __name__ == "__main__":
    main()
