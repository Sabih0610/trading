"""Evidence-bound source clocks. No profile is learned or promoted from a price offset."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import AwareDatetime, Field, model_validator

from tb.risk.config import PolicyModel


class ClockRefused(ValueError):
    """A sanitized, unqualified source-clock result."""


class ClockState(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    PROVISIONAL = "PROVISIONAL"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"


class ClockEvidence(PolicyModel):
    kind: Literal["official_spec", "provider_confirmation", "measurement", "community", "fixture"]
    reference: str
    provider: str
    server: str
    captured_at: AwareDatetime
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ClockPeriod(PolicyModel):
    """Half-open UTC applicability; overlap in wall time at DST folds is refused."""

    start: AwareDatetime
    end: AwareDatetime
    offset_seconds: int = Field(ge=-50400, le=50400)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Clock period must have positive duration")
        return self


class ClockStamp(PolicyModel):
    provider: str
    server: str
    identity_fingerprint: str
    profile_id: str
    profile_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    raw_representation: str
    raw_at: AwareDatetime
    normalized_at: AwareDatetime
    rule: str
    profile_state: Literal["VERIFIED"] = "VERIFIED"


class ClockProfile(PolicyModel):
    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{2,100}$")
    provider: str
    broker: str
    server: str
    environment: Literal["demo", "practice"]
    instruments: tuple[Literal["EURUSD", "XAUUSD"], ...] = Field(min_length=1)
    builds: tuple[int, ...] = ()
    semantics: Literal["utc_epoch", "broker_wall_epoch", "rfc3339_utc"]
    state: ClockState = ClockState.UNVERIFIED
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    verified_at: AwareDatetime | None = None
    effective_from: AwareDatetime | None = None
    effective_to: AwareDatetime | None = None
    reviewed_by: str | None = None
    timezone: str | None = None
    periods: tuple[ClockPeriod, ...] = ()
    evidence: tuple[ClockEvidence, ...] = ()
    validation_samples: int = Field(default=0, ge=0)
    validation_started: AwareDatetime | None = None
    validation_ended: AwareDatetime | None = None
    independent_utc_sources: tuple[str, ...] = ()
    maximum_residual_seconds: float | None = Field(default=None, ge=0)
    tolerance_seconds: float = Field(default=2, gt=0, le=2)
    validated_kinds: tuple[Literal["quote", "tick", "candle"], ...] = ()
    validation_environment: Literal["genuine", "fixture"] = "genuine"
    refresh_conditions: tuple[str, ...] = (
        "expiry",
        "server/build change",
        "source shift",
        "provider notice",
    )

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    @model_validator(mode="after")
    def supported(self) -> Self:
        if self.expires_at <= self.issued_at or (self.timezone and self.periods):
            raise ValueError("Clock lifetime or conversion rule invalid")
        periods = sorted(self.periods, key=lambda p: p.start)
        if (self.effective_to or self.expires_at) <= (self.effective_from or self.issued_at):
            raise ValueError("Source clock effective range invalid")
        if any(a.end > b.start for a, b in pairwise(periods)):
            raise ValueError("Overlapping effective UTC periods refused")
        if self.timezone:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError:
                raise ValueError("Unknown verified timezone") from None
        if self.semantics != "broker_wall_epoch" and (self.timezone or self.periods):
            raise ValueError("UTC semantics cannot carry a broker offset")
        if self.state == ClockState.VERIFIED:
            authoritative = any(
                e.kind in {"official_spec", "provider_confirmation"}
                and e.provider == self.provider
                and e.server == self.server
                and e.reference.startswith("https://")
                for e in self.evidence
            )
            if (
                not authoritative
                or not self.reviewed_by
                or self.verified_at is None
                or self.validation_samples < 3
                or len(set(self.independent_utc_sources)) < 2
                or self.maximum_residual_seconds is None
                or self.maximum_residual_seconds > self.tolerance_seconds
                or not self.validated_kinds
                or self.validation_started is None
                or self.validation_ended is None
                or (self.validation_ended - self.validation_started).total_seconds() < 10
                or not self.issued_at <= self.verified_at < self.expires_at
                or not self.validation_started <= self.validation_ended <= self.verified_at
            ):
                raise ValueError(
                    "VERIFIED requires scoped authoritative evidence and repeated UTC validation"
                )
            if self.semantics == "broker_wall_epoch" and not (self.timezone or self.periods):
                raise ValueError("Verified broker clock needs an explicit verified rule")
        return self

    def effective_state(self, now: datetime) -> ClockState:
        """Expiry is evaluated at receipt/usage time, never at an old market timestamp."""
        if now.tzinfo is None or now < self.issued_at:
            return ClockState.INVALID
        if now >= self.expires_at:
            return ClockState.EXPIRED
        if self.verified_at is not None and now < self.verified_at:
            return ClockState.INVALID
        return self.state

    def normalize(
        self,
        raw_at: datetime,
        *,
        raw_representation: str,
        provider: str,
        broker: str,
        server: str,
        environment: str,
        instrument: str,
        build: int,
        identity_fingerprint: str,
        now: datetime,
        kind: str,
    ) -> ClockStamp:
        """Return unique UTC only under a live, reviewed profile of the exact source."""
        try:
            # Pydantic model_copy deliberately skips validation; a changed state must not
            # promote a provisional object without rechecking its evidence contract.
            ClockProfile.model_validate(self.model_dump())
        except ValueError:
            raise ClockRefused("source_clock_profile_evidence_invalid") from None
        if self.effective_state(now) != ClockState.VERIFIED:
            raise ClockRefused("source_clock_profile_not_verified_or_expired")
        if (
            provider != self.provider
            or broker != self.broker
            or server != self.server
            or environment != self.environment
            or instrument not in self.instruments
            or (self.builds and build not in self.builds)
            or kind not in self.validated_kinds
        ):
            raise ClockRefused("source_clock_profile_scope_mismatch")
        if raw_at.tzinfo is None:
            raise ClockRefused("raw_clock_representation_must_be_explicit")
        raw_at = raw_at.astimezone(UTC)
        rule: str = self.semantics
        candidates: set[datetime] = set()
        if self.semantics in {"utc_epoch", "rfc3339_utc"}:
            candidates.add(raw_at)
        elif self.periods:
            for period in self.periods:
                candidate = raw_at - timedelta(seconds=period.offset_seconds)
                if period.start <= candidate < period.end:
                    candidates.add(candidate)
            rule = "verified_effective_utc_periods"
        elif self.timezone:
            zone = ZoneInfo(self.timezone)
            wall = raw_at.replace(tzinfo=None)
            for fold in (0, 1):
                candidate = wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
                if candidate.astimezone(zone).replace(tzinfo=None) == wall:
                    candidates.add(candidate)
            rule = "verified_iana:" + self.timezone
        if len(candidates) != 1:
            raise ClockRefused("ambiguous_or_uncovered_source_clock_period")
        normalized = next(iter(candidates))
        if (
            not (self.effective_from or self.issued_at)
            <= normalized
            < (self.effective_to or self.expires_at)
        ):
            raise ClockRefused("source_date_outside_verified_effective_range")
        return ClockStamp(
            provider=provider,
            server=server,
            identity_fingerprint=identity_fingerprint,
            profile_id=self.profile_id,
            profile_digest=self.digest,
            raw_representation=raw_representation,
            raw_at=raw_at,
            normalized_at=normalized,
            rule=rule,
        )


def load_profiles(path: Path) -> tuple[ClockProfile, ...]:
    """Read public versioned rules; a duplicate identifier cannot silently replace a profile."""
    profiles = tuple(
        ClockProfile.model_validate(p)
        for p in yaml.safe_load(path.read_text(encoding="utf-8"))["profiles"]
    )
    if len({p.profile_id for p in profiles}) != len(profiles):
        raise ClockRefused("duplicate_clock_profile_identifier")
    return profiles


class ClockSequence:
    """Detect unexpected normalized clock jumps independently of the fixed offset rule."""

    def __init__(self) -> None:
        self.previous: tuple[datetime, datetime] | None = None

    def observe(self, source: datetime, receipt: datetime) -> None:
        if self.previous:
            source_elapsed = (source - self.previous[0]).total_seconds()
            receipt_elapsed = (receipt - self.previous[1]).total_seconds()
            if receipt_elapsed < 0 or abs(source_elapsed - receipt_elapsed) > 120:
                raise ClockRefused("unexpected_source_or_receipt_clock_shift")
            if source < self.previous[0]:
                raise ClockRefused("out_of_order_source_quote")
        self.previous = source, receipt
