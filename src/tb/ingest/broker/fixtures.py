"""Owned protocol examples only; none describes an actual broker account or market."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from tb.ingest.broker.ctrader import BrokerAccess, CTraderQuoteSource, CTraderSettings
from tb.ingest.broker.models import Symbol
from tb.ingest.broker.transport import MockReadChannel
from tb.ingest.history.core import sha256_bytes
from tb.ingest.rights import DataRights, Permission, Usage
from tb.shadow.models import ResearchDecision

START = datetime(2024, 1, 8, 12, tzinfo=UTC)
SYMBOL_IDS: dict[Symbol, int] = {"EURUSD": 101, "XAUUSD": 202}


class FixtureClock:
    def __init__(self, now: datetime = START) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def fixture_settings() -> CTraderSettings:
    return CTraderSettings(
        client_id=SecretStr("owned-client"),
        client_secret=SecretStr("owned-fixture-only"),
        access_token=SecretStr("owned-fixture-only"),
        account_id=SecretStr("777"),
        access_expires_at=START + timedelta(days=1),
    )


def fixture_rights(*, reference: bool = False) -> DataRights:
    identity = (
        sha256_bytes(b"owned-reference-identity") if reference else fixture_settings().fingerprint
    )
    usages: tuple[Usage, ...] = (
        "retrieval",
        "private_display",
        "raw_cache",
        "historical_storage",
        "derived_storage",
        "persistent_collection",
    )
    return DataRights(
        policy_id="owned-broker-protocol-fixtures",
        version="1.0.0",
        provider="owned_fixture",
        account_fingerprint=identity,
        instruments=("EURUSD", "XAUUSD"),
        reviewed_at=START - timedelta(days=1),
        permissions={
            u: Permission(
                status="confirmed",
                approved=True,
                approved_by="owned-fixture-author",
                evidence="OWNED SOFTWARE FIXTURES ONLY",
                expires_at=START + timedelta(days=1),
                permitted_retention_seconds=86400,
            )
            for u in usages
        },
    )


def symbol_reply(symbol: Symbol) -> dict[str, Any]:
    gold = symbol == "XAUUSD"
    return {
        "symbolId": SYMBOL_IDS[symbol],
        "digits": 2 if gold else 5,
        "pipPosition": 2 if gold else 4,
        "lotSize": 10000 if gold else 10000000,
        "minVolume": 100 if gold else 100000,
        "maxVolume": 1000000 if gold else 1000000000,
        "stepVolume": 100 if gold else 100000,
        "schedule": [{"startSecond": 86400, "endSecond": 518400}],
        "scheduleTimeZone": "UTC",
        "holiday": [],
        "slDistance": 10,
        "distanceSetIn": 1,
    }


def responder(kind: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Only the fixed protocol read operations exist in this owned responder."""
    if kind == 2100:
        return {}
    if kind == 2149:
        return {
            "accessToken": payload["accessToken"],
            "permissionScope": 0,
            "ctidTraderAccount": [
                {
                    "ctidTraderAccountId": 777,
                    "isLive": False,
                    "brokerTitleShort": "Owned protocol fixture",
                }
            ],
        }
    answer: dict[str, Any] = {"ctidTraderAccountId": 777}
    if kind == 2121:
        answer["trader"] = {"ctidTraderAccountId": 777, "depositAssetId": 1}
    elif kind == 2112:
        answer["asset"] = [
            {"assetId": i, "name": name} for i, name in [(1, "USD"), (2, "EUR"), (3, "XAU")]
        ]
    elif kind == 2114:
        answer["symbol"] = [
            {
                "symbolId": sid,
                "symbolName": symbol,
                "enabled": True,
                "baseAssetId": 2 if symbol == "EURUSD" else 3,
                "quoteAssetId": 1,
            }
            for symbol, sid in SYMBOL_IDS.items()
        ]
    elif kind == 2116:
        answer["symbol"] = [
            symbol_reply(s) for s, sid in SYMBOL_IDS.items() if sid in payload["symbolId"]
        ]
    return answer


def spot(
    symbol: Symbol,
    milliseconds: int,
    *,
    bid: int | None = None,
    ask: int | None = None,
    receipt_lag_ms: int = 100,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ctidTraderAccountId": 777,
        "symbolId": SYMBOL_IDS[symbol],
        "timestamp": int(START.timestamp() * 1000) + milliseconds,
    }
    if bid is not None:
        data["bid"] = bid
    if ask is not None:
        data["ask"] = ask
    return {
        "payloadType": 2131,
        "payload": data,
        "_received_at": START + timedelta(milliseconds=milliseconds + receipt_lag_ms),
    }


class OwnedChannel(MockReadChannel):
    def __init__(self, clock: FixtureClock, events: list[dict[str, Any]]) -> None:
        super().__init__(responder, events)
        self.clock = clock

    def receive(self) -> dict[str, Any]:
        value = super().receive()
        if "_received_at" in value:
            self.clock.now = value["_received_at"]
        return value


def fixture_source(
    root: Path, events: list[dict[str, Any]] | None = None
) -> tuple[CTraderQuoteSource, FixtureClock, OwnedChannel]:
    clock = FixtureClock()
    if events is None:
        events = []
        examples: list[tuple[Symbol, int, int]] = [
            ("EURUSD", 110000, 110002),
            ("XAUUSD", 240000000, 240020000),
        ]
        for symbol, bid, ask in examples:
            events.extend(
                [
                    spot(symbol, 0, bid=bid),
                    spot(symbol, 200, ask=ask),
                    spot(symbol, 400, bid=bid, ask=ask),
                    spot(symbol, 600, bid=bid),
                    spot(symbol, 800, ask=ask),
                ]
            )
        events.sort(key=lambda v: v["_received_at"])
    channel = OwnedChannel(clock, events)
    source = CTraderQuoteSource(
        fixture_settings(),
        fixture_rights(),
        root=root,
        access=BrokerAccess(broker_pin="Owned protocol fixture"),
        channel=channel,
        clock=clock,
    )
    return source, clock, channel


def fixture_decision(symbol: Symbol) -> ResearchDecision:
    """Owned bridge input, not a claim that an empirical strategy generated a trade."""
    return ResearchDecision(
        id="owned-reference-" + symbol,
        event_id="owned-event-" + symbol,
        evidence_id="owned-bridge-fixture",
        mode="fixture_replay",
        provider="owned_fixture",
        symbol=symbol,
        strategy="owned_bridge_input",
        strategy_version="owned-input-1.0.0",
        source_open_at=START - timedelta(minutes=7),
        source_close_at=START - timedelta(minutes=2),
        received_at=START - timedelta(seconds=1),
        information_available_at=START - timedelta(seconds=1),
        decision_at=START,
        signal="BUY",
        status="candidate",
        reasons=("owned_input_only",),
        features={},
        features_sha256=sha256_bytes(b"{}"),
        rights_digest=fixture_rights(reference=True).digest,
        source_version="owned-1.0.0",
        consumer_version="owned-1.0.0",
        runtime_milliseconds=0,
    )
