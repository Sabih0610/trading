"""Fixed demo JSON channel: explicit read-message allowlist and bounded event queue."""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from websockets.sync.client import ClientConnection, connect

from tb.ingest.broker.book import integer
from tb.ingest.broker.models import BrokerRefused

DEMO_URL = "wss://demo.ctraderapi.com:5036"
# Required/optional fields per inspected official schema. All other messages fail before send.
READ_FIELDS: dict[int, tuple[frozenset[str], frozenset[str]]] = {
    51: (frozenset(), frozenset()),
    2100: (frozenset({"clientId", "clientSecret"}), frozenset()),
    2102: (frozenset({"ctidTraderAccountId", "accessToken"}), frozenset()),
    2112: (frozenset({"ctidTraderAccountId"}), frozenset()),
    2114: (frozenset({"ctidTraderAccountId"}), frozenset({"includeArchivedSymbols"})),
    2116: (frozenset({"ctidTraderAccountId", "symbolId"}), frozenset()),
    2121: (frozenset({"ctidTraderAccountId"}), frozenset()),
    2127: (frozenset({"ctidTraderAccountId", "symbolId", "subscribeToSpotTimestamp"}), frozenset()),
    2129: (frozenset({"ctidTraderAccountId", "symbolId"}), frozenset()),
    2149: (frozenset({"accessToken"}), frozenset()),
}
RESPONSES = {
    2100: 2101,
    2102: 2103,
    2112: 2113,
    2114: 2115,
    2116: 2117,
    2121: 2122,
    2127: 2128,
    2129: 2130,
    2149: 2150,
}
FATAL_EVENTS = frozenset({50, 2120, 2123, 2142, 2147, 2148, 2164})


def validate_request(kind: int, payload: dict[str, Any]) -> None:
    """Default-deny types and fields, including parameters smuggled into a read request."""
    if type(kind) is not int or kind not in READ_FIELDS:
        raise BrokerRefused("broker_message_not_allowlisted")
    required, optional = READ_FIELDS[kind]
    if not required <= payload.keys() or not payload.keys() <= required | optional:
        raise BrokerRefused("broker_request_fields_refused")
    if "ctidTraderAccountId" in payload and integer(payload["ctidTraderAccountId"]) <= 0:
        raise BrokerRefused("broker_account_pin_invalid")
    if "symbolId" in payload and (
        not isinstance(payload["symbolId"], list)
        or not 1 <= len(payload["symbolId"]) <= 2
        or any(integer(s) <= 0 for s in payload["symbolId"])
    ):
        raise BrokerRefused("broker_symbol_request_invalid")
    if kind == 2127 and payload["subscribeToSpotTimestamp"] is not True:
        raise BrokerRefused("broker_source_timestamp_required")


class ReadChannel(Protocol):
    def request(self, kind: int, payload: dict[str, Any]) -> dict[str, Any]: ...
    def receive(self) -> dict[str, Any]: ...
    def close(self) -> None: ...


class DemoJsonChannel:
    """No endpoint override or broad SDK; JSON wire logging is disabled even at DEBUG."""

    def __init__(self) -> None:
        self._socket: ClientConnection | None = None
        self._pending: deque[dict[str, Any]] = deque()
        self._sent: deque[float] = deque()
        self._heartbeat = time.monotonic()
        self._deadline = self._heartbeat + 60
        quiet = logging.getLogger("tb.broker.private_wire")
        quiet.disabled, quiet.propagate = True, False
        try:
            self._socket = connect(
                DEMO_URL,
                open_timeout=8,
                close_timeout=2,
                max_size=262144,
                max_queue=16,
                proxy=None,
                compression=None,
                logger=quiet,
            )
        except Exception:
            raise BrokerRefused("broker_demo_transport_unavailable") from None

    def _send(self, kind: int, payload: dict[str, Any], identifier: str) -> None:
        validate_request(kind, payload)
        now = time.monotonic()
        while self._sent and now - self._sent[0] >= 1:
            self._sent.popleft()
        if len(self._sent) >= 10 or self._socket is None or now >= self._deadline:
            raise BrokerRefused("broker_read_rate_or_connection_refused")
        self._sent.append(now)
        self._socket.send(
            json.dumps(
                {"payloadType": kind, "clientMsgId": identifier, "payload": payload},
                allow_nan=False,
            )
        )

    def _receive(self) -> dict[str, Any]:
        if self._socket is None:
            raise BrokerRefused("broker_disconnected")
        if time.monotonic() - self._heartbeat >= 8:
            self._send(51, {}, uuid4().hex)
            self._heartbeat = time.monotonic()
        try:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise BrokerRefused("broker_finite_connection_deadline_reached")
            message = self._socket.recv(timeout=min(2, remaining))
            value = json.loads(message)
            if not isinstance(value, dict) or not isinstance(value.get("payload"), dict):
                raise ValueError
            if integer(value.get("payloadType")) in FATAL_EVENTS:
                raise ValueError
            value["_received_at"] = datetime.now(UTC)
            return value
        except Exception:
            self.close()
            raise BrokerRefused("broker_connection_message_or_authorization_refused") from None

    def request(self, kind: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Correlate bounded replies; fail on unsolicited authority/identity changes."""
        validate_request(kind, payload)
        identifier = uuid4().hex
        try:
            self._send(kind, payload, identifier)
            expires = min(self._deadline, time.monotonic() + 8)
            for _ in range(128):
                if time.monotonic() >= expires:
                    raise BrokerRefused("broker_request_deadline_reached")
                message = self._receive()
                incoming = integer(message.get("payloadType"))
                if incoming == 51:
                    continue
                if incoming == RESPONSES.get(kind) and message.get("clientMsgId") == identifier:
                    body: dict[str, Any] = message["payload"]
                    return body
                if incoming != 2131 or len(self._pending) >= 128:
                    raise BrokerRefused("broker_unexpected_reply_or_queue_overflow")
                self._pending.append(message)
            raise BrokerRefused("broker_reply_bound_exceeded")
        except Exception:
            self.close()
            raise BrokerRefused("broker_read_request_refused") from None

    def receive(self) -> dict[str, Any]:
        """At most one bounded event; callers re-check permission and clocks first."""
        return self._pending.popleft() if self._pending else self._receive()

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
        self._socket = None
        self._pending.clear()


class MockReadChannel:
    """Owned scripted transport; cannot open a socket or claim genuine evidence."""

    def __init__(
        self,
        responder: Callable[[int, dict[str, Any]], dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> None:
        self.responder, self.events = responder, deque(events)
        self.calls: list[int] = []
        self.closed = False

    def request(self, kind: int, payload: dict[str, Any]) -> dict[str, Any]:
        validate_request(kind, payload)
        self.calls.append(kind)
        return self.responder(kind, payload)

    def receive(self) -> dict[str, Any]:
        if not self.events or self.closed:
            raise BrokerRefused("owned_mock_connection_finished")
        event = self.events.popleft()
        if integer(event.get("payloadType")) in FATAL_EVENTS:
            raise BrokerRefused("broker_authorization_or_metadata_changed")
        return event

    def close(self) -> None:
        self.closed = True
