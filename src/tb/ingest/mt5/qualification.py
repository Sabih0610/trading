"""Bounded UTC references and fresh, demo-bound admission for genuine acquisition."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from uuid import uuid4

import httpx

from tb.ingest.clock_profiles import ClockState
from tb.ingest.mt5.adapter import MT5Feed
from tb.ingest.mt5.mcp import ReadOnlyMCP
from tb.ingest.mt5.models import AdmissionCheck, FeedUnavailable
from tb.ingest.mt5.timestamps import EPOCH, parse_explicit_utc


def independent_utc(
    *,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
) -> list[dict[str, Any]]:
    """Read TLS time references only; never store trace IPs, cookies or entire responses."""
    references: list[dict[str, Any]] = []
    sources = (
        ("cloudflare_trace", "https://www.cloudflare.com/cdn-cgi/trace"),
        ("microsoft_http_date", "https://www.microsoft.com/"),
    )
    with httpx.Client(
        timeout=8,
        trust_env=False,
        follow_redirects=False,
        transport=transport,
        headers={"Cache-Control": "no-cache"},
    ) as client:
        for name, url in sources:
            before, mono = clock(), monotonic()
            item: dict[str, Any] = {
                "source": name,
                "before_utc": before.isoformat(),
                "accepted": False,
            }
            try:
                with client.stream("GET", url, params={"utc_probe": uuid4().hex}) as response:
                    content = bytearray()
                    # Microsoft only needs headers; no large page is downloaded.
                    if name == "cloudflare_trace":
                        for block in response.iter_bytes(4096):
                            content.extend(block)
                            if len(content) > 32768:
                                raise FeedUnavailable("clock_reference_too_large")
                    received, elapsed = clock(), monotonic() - mono
                    if name == "cloudflare_trace":
                        fields = dict(
                            line.split("=", 1)
                            for line in content.decode().splitlines()
                            if "=" in line
                        )
                        # Decimal strings avoid local timezone conversion.
                        at = parse_explicit_utc(
                            datetime.fromtimestamp(float(fields["ts"]), UTC).isoformat()
                        )
                    else:
                        at = parsedate_to_datetime(response.headers["Date"]).astimezone(UTC)
                    delta = (at - received).total_seconds()
                    wall_elapsed = (received - before).total_seconds()
                    accepted = (
                        200 <= response.status_code < 400
                        and response.headers.get("Age", "0") == "0"
                        and 0 <= elapsed <= 5
                        and abs(wall_elapsed - elapsed) <= 2
                        and abs(delta) <= 2 + elapsed
                    )
                    item.update(
                        received_utc=received.isoformat(),
                        reference_utc=at.isoformat(),
                        elapsed_seconds=round(elapsed, 6),
                        reference_minus_receipt_seconds=delta,
                        status=response.status_code,
                        accepted=accepted,
                    )
            except (httpx.HTTPError, ValueError, KeyError, OverflowError, UnicodeError):
                item["reason"] = "independent_utc_unavailable"
            references.append(item)
    return references


def clock_reference_passes(references: list[dict[str, Any]], now: datetime) -> bool:
    """An unavailable/stale or disagreeing independent reference cannot admit acquisition."""
    if not references:
        return False
    valid = []
    for item in references:
        if item.get("accepted") is not True:
            continue
        try:
            age = (now - parse_explicit_utc(item["received_utc"])).total_seconds()
            valid.append(0 <= age <= 60)
        except (FeedUnavailable, KeyError, TypeError):
            return False
    # A reachable but disagreeing clock is a refusal, not a vote to ignore.
    disagreement = any(
        "reference_utc" in item and item.get("accepted") is not True for item in references
    )
    return any(valid) and not disagreement


class AdmissionMonitor:
    """Recheck native safety and source validity each poll; cache external UTC for at most 30s."""

    def __init__(self, feed: MT5Feed, mcp: ReadOnlyMCP) -> None:
        self.feed, self.mcp = feed, mcp
        self.references: list[dict[str, Any]] = []
        self.reference_checked: datetime | None = None

    def __call__(self) -> AdmissionCheck:
        now = self.feed.clock()
        identity = self.feed.verify()
        reasons: list[str] = []
        native: bool | None = None
        shell: bool | None = None
        try:
            self.mcp.discover()
            terminal = self.mcp.call("terminal_get_info", {})
            pinned = self.mcp.call("get_trading_account_info", {})
            if pinned["fingerprint"] != identity.fingerprint:
                reasons.append("mcp_python_identity_disagreement")
            native = terminal["native_mcp_trading_permission"]
            shell = self.mcp.dangerous_shell_tool_available
        except (FeedUnavailable, KeyError, TypeError, ValueError):
            reasons.append("native_security_unverified")
        security = native is False and shell is False and not reasons
        if not security:
            reasons.append("native_trading_or_shell_permission_not_closed")
        if (
            self.reference_checked is None
            or not 0 <= (now - self.reference_checked).total_seconds() < 30
        ):
            self.references = independent_utc(clock=self.feed.clock)
            self.reference_checked = now
        clock_ok = clock_reference_passes(self.references, self.feed.clock())
        if not clock_ok:
            reasons.append("host_utc_reference_unverified")
        try:
            native_clock = self.mcp.call("get_time_information", {})
            native_utc = parse_explicit_utc(native_clock["utc_time"])
            if abs((native_utc - self.feed.clock()).total_seconds()) > 3:
                raise FeedUnavailable("native_utc_disagrees")
        except (FeedUnavailable, KeyError, TypeError, ValueError):
            clock_ok = False
            reasons.append("native_utc_unverified")
        instruments: dict[str, bool] = {}
        instrument_reasons: dict[str, tuple[str, ...]] = {}
        for symbol in self.feed.config.symbols:
            try:
                if not self.feed.synthetic and (
                    self.feed.clock_profile is None
                    or self.feed.clock_profile.validation_environment != "genuine"
                    or self.feed.clock_profile.effective_state(self.feed.clock())
                    != ClockState.VERIFIED
                ):
                    raise FeedUnavailable("source_clock_profile_not_verified")
                facts = self.feed.metadata(symbol)
                if facts.visible is not True or facts.selected is not True:
                    raise FeedUnavailable("visibility_unverified")
                quote, _ = self.feed.quote(symbol)
                lag = (quote.received_at - quote.source_at).total_seconds()
                if not 0 <= lag <= self.feed.config.max_tick_age_seconds:
                    raise FeedUnavailable("source_not_fresh")
                instruments[symbol] = True
            except (FeedUnavailable, ValueError, ArithmeticError):
                instruments[symbol] = False
                instrument_reasons[symbol] = ("source_clock_profile_or_quote_invalid",)
        clock_ok = clock_ok and any(instruments.values())
        if not any(instruments.values()):
            reasons.append("no_instrument_passed_source_qualification")
        return AdmissionCheck(
            checked_at=self.feed.clock(),
            identity_fingerprint=identity.fingerprint,
            security_passed=security,
            clock_passed=clock_ok,
            reasons=tuple(sorted(set(reasons))),
            native_trading_allowed=native,
            dangerous_shell_tool_available=shell,
            instruments=instruments,
            instrument_reasons=instrument_reasons,
        )


def seconds_interpretation(seconds: int) -> str:
    """Return an exact UTC epoch interpretation without a broker timezone correction."""
    from datetime import timedelta

    return (EPOCH + timedelta(seconds=seconds)).isoformat()
