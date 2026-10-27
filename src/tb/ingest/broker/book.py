"""Bounded quote-side state; partial updates never renew the other side."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tb.ingest.broker.models import BrokerContract, BrokerIdentity, BrokerQuote, BrokerRefused
from tb.ingest.history.core import sha256_bytes


def integer(value: object) -> int:
    """JSON int64 may be encoded as decimal text; bool/float are not integers here."""
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 19:
        return int(value)
    raise BrokerRefused("broker_integer_field_invalid")


def market_open(contract: BrokerContract, source_at: datetime) -> bool:
    """Only an explicit calendar is evidence of an open session."""
    if not contract.schedule or not contract.schedule_timezone or contract.holidays is None:
        raise BrokerRefused("broker_session_or_holidays_unverified")
    try:
        local = source_at.astimezone(ZoneInfo(contract.schedule_timezone))
    except (ZoneInfoNotFoundError, ValueError):
        raise BrokerRefused("broker_session_timezone_unverified") from None
    # Preserve holidays as supplied; do not guess provider holiday offset/recurrence semantics.
    if contract.holidays:
        raise BrokerRefused("broker_holiday_interpretation_requires_review")
    second = ((local.weekday() + 1) % 7) * 86400
    second += local.hour * 3600 + local.minute * 60 + local.second
    return any(start <= second < end for start, end in contract.schedule)


class QuoteBook:
    """At most two instruments and 1,024 recent event identities in memory."""

    def __init__(self) -> None:
        self.sides: dict[int, dict[str, tuple[int, datetime, datetime]]] = {}
        self.seen: OrderedDict[str, None] = OrderedDict()
        self.last: dict[int, datetime] = {}
        self.last_receipt: datetime | None = None
        self.reason = "waiting_for_both_sides"

    def clear(self) -> None:
        """Reconnect, identity changes and refusals cannot retain an old counterpart."""
        self.sides.clear()
        self.last.clear()
        self.last_receipt = None

    def accept(
        self,
        event: dict[str, object],
        contract: BrokerContract,
        identity: BrokerIdentity,
        received: datetime,
        rights_digest: str,
    ) -> BrokerQuote | None:
        """Validate first, then atomically advance only genuine source-side updates."""
        try:
            return self._accept(event, contract, identity, received, rights_digest)
        except (ValueError, OverflowError, OSError, ArithmeticError):
            self.clear()
            raise BrokerRefused("broker_quote_clock_price_identity_or_session_refused") from None

    def _accept(
        self,
        event: dict[str, object],
        contract: BrokerContract,
        identity: BrokerIdentity,
        received: datetime,
        rights_digest: str,
    ) -> BrokerQuote | None:
        identity.require(received)
        BrokerContract.model_validate(contract.model_dump())
        if (
            received.tzinfo is None
            or received.utcoffset() is None
            or (self.last_receipt is not None and received < self.last_receipt)
            or contract.account_fingerprint != identity.account_fingerprint
            or contract.account_currency != identity.account_currency
            or contract.evidence != identity.evidence
            or not 0 <= (received - contract.observed_at).total_seconds() <= 86400
        ):
            raise BrokerRefused("broker_metadata_or_clock_scope_refused")
        sid, timestamp = integer(event.get("symbolId")), integer(event.get("timestamp"))
        at = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=timestamp)
        if sid != contract.symbol_id or not 0 <= (received - at).total_seconds() <= 5:
            raise BrokerRefused("broker_quote_time_or_symbol_refused")
        if not market_open(contract, at):
            raise BrokerRefused("broker_market_closed")
        raw = {"symbolId": sid, "timestamp": timestamp}
        for side in ("bid", "ask"):
            if side in event:
                value = integer(event[side])
                if value <= 0 or (Decimal(value) / 100000) % contract.tick_size:
                    raise BrokerRefused("broker_quote_price_grid_invalid")
                raw[side] = value
        if len(raw) == 2:
            raise BrokerRefused("broker_quote_has_no_sides")
        eid = sha256_bytes(
            (identity.account_fingerprint + json.dumps(raw, sort_keys=True)).encode()
        )
        if eid in self.seen:
            self.reason = "duplicate_raw_update"
            return None
        previous = self.last.get(sid)
        if previous is not None and at < previous:
            raise BrokerRefused("broker_out_of_order_quote")
        if previous is not None and (at - previous).total_seconds() > 5:
            self.sides.pop(sid, None)
        candidate = self.sides.get(sid, {}).copy()
        for side in ("bid", "ask"):
            if side in raw:
                candidate[side] = raw[side], at, received
        # An old side is unavailable, never retimestamped to the new event.
        candidate = {k: v for k, v in candidate.items() if (received - v[1]).total_seconds() <= 5}
        self.last[sid], self.last_receipt = at, received
        self.seen[eid] = None
        if len(self.seen) > 1024:
            self.seen.popitem(last=False)
        if set(candidate) != {"bid", "ask"}:
            self.sides[sid] = candidate
            self.reason = "waiting_for_fresh_counterpart"
            return None
        bid, ask = candidate["bid"], candidate["ask"]
        quote = BrokerQuote(
            account_fingerprint=identity.account_fingerprint,
            symbol=contract.symbol,
            broker_symbol=contract.broker_symbol,
            symbol_id=sid,
            metadata_digest=contract.digest,
            source_at=at,
            received_at=received,
            bid_source_at=bid[1],
            ask_source_at=ask[1],
            bid_received_at=bid[2],
            ask_received_at=ask[2],
            raw_timestamp=timestamp,
            original_timestamp=str(event["timestamp"]),
            bid_relative=bid[0],
            ask_relative=ask[0],
            bid=Decimal(bid[0]) / 100000,
            ask=Decimal(ask[0]) / 100000,
            raw_event=raw,
            event_id=eid,
            rights_digest=rights_digest,
            evidence=identity.evidence,
        )
        self.sides[sid] = candidate
        self.reason = "admissible_indicative_quote"
        return quote
