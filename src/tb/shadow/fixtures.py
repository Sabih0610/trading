"""Owned deterministic M5 evidence; no network, broker data or historical holdout reads."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from tb.ingest.history.core import atomic_write_bytes, atomic_write_json, sha256_file
from tb.ingest.mt5.models import Observation
from tb.ingest.mt5.storage import record_id
from tb.ingest.rights import SHADOW_USAGES, DataRights, Permission
from tb.ingest.twelve_data.adapter import canonical
from tb.shadow.journal import ShadowRefused, digest
from tb.shadow.models import ShadowConfig, ShadowEvent, SourcePin

FIXTURE_START = datetime(2024, 6, 3, 8, tzinfo=UTC)
FIXTURE_IDENTITY = digest("owned-P11b.0-fixture-v1")
SCENARIOS = (
    "rising",
    "falling",
    "sideways",
    "up_breakout",
    "down_breakout",
    "false_breakout",
    "volatility_spike",
    "gaps",
    "changing_volatility",
    "wait_only",
)


def fixture_rights() -> DataRights:
    """Synthetic permission fixture, not a claim about any Twelve Data account."""
    return DataRights(
        policy_id="owned-synthetic-P11b.0",
        version="1.0.0",
        provider="owned_fixture",
        account_fingerprint=FIXTURE_IDENTITY,
        instruments=("EURUSD", "XAUUSD"),
        reviewed_at=FIXTURE_START,
        permissions={
            u: Permission(
                status="confirmed",
                approved=True,
                approved_by="owner-authorized-owned-fixture-replay",
                evidence="synthetic-generated-test-data; no provider prices",
                expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            )
            for u in SHADOW_USAGES
        },
    )


def fixture_pin(config: ShadowConfig, code_version: str) -> SourcePin:
    return SourcePin(
        mode="fixture_replay",
        provider="owned_fixture",
        identity=FIXTURE_IDENTITY,
        source_version="owned-M5-scenarios-2.0.0"
        if config.reference_strategies
        else "owned-M5-fixture-1.0.0",
        consumer_version=code_version,
        rights_digest=fixture_rights().digest,
        config_digest=digest(config.model_dump(mode="json")),
    )


def fixture_events(pin: SourcePin, bars: int = 64) -> Iterator[ShadowEvent]:
    if pin.mode != "fixture_replay" or not 1 <= bars <= 1000:
        raise ShadowRefused("owned_fixture_bounds_or_identity_refused")
    for index in range(bars):
        opening = FIXTURE_START + timedelta(minutes=5 * index)
        for offset, symbol in enumerate(("EURUSD", "XAUUSD")):
            base = Decimal("1.1") if symbol == "EURUSD" else Decimal("2000")
            step = Decimal("0.0001") if symbol == "EURUSD" else Decimal("0.2")
            price = base + step * (index if index < 32 else 64 - index)
            close = price + step * (1 if index < 32 else -1)
            row = Observation(
                symbol=canonical(symbol),
                broker_symbol="EUR/USD" if symbol == "EURUSD" else "XAU/USD",
                kind="candle",
                timeframe="M5",
                source_at=opening,
                received_at=opening + timedelta(minutes=7, seconds=offset),
                evidence="synthetic",
                open=price,
                high=max(price, close) + step,
                low=min(price, close) - step,
                close=close,
                source_provider="twelve_data",
                price_type="reference_midpoint",
                source_timezone="UTC",
                raw_source_time=opening.strftime("%Y-%m-%d %H:%M:%S"),
                interval_complete=True,
                coverage_started_at=FIXTURE_START,
            )
            yield ShadowEvent(
                pin=pin,
                observation=row,
                evidence_id=record_id(row, pin.identity),
                manifest_sha256=digest("owned-fixture-generator-1.0.0"),
            )


def scenario_prices(scenario: str, index: int) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Construct deliberately simple regimes, including failures, without parameter fitting."""
    if scenario not in SCENARIOS:
        raise ShadowRefused("unknown_owned_scenario")

    def close_at(i: int) -> Decimal:
        if scenario == "rising":
            return Decimal(1000) + Decimal("0.5") * i
        if scenario == "falling":
            return Decimal(1000) - Decimal("0.5") * i
        if scenario == "sideways":
            return Decimal(1000) + Decimal("0.01") * ((i % 4) - 2)
        if scenario in {"up_breakout", "down_breakout", "gaps"}:
            direction = -1 if scenario == "down_breakout" else 1
            return Decimal(1000) + direction * max(0, i - 55) * Decimal("0.5")
        if scenario == "false_breakout":
            return Decimal(1004 if i == 60 else 1005 if i == 61 else 998 if i >= 62 else 1000)
        if scenario == "volatility_spike":
            return Decimal(1040 if i == 60 else 1000)
        if scenario == "changing_volatility":
            return Decimal(1000) + Decimal("0.2") * (i if i < 64 else 128 - i)
        return Decimal(1000)

    opening, close = close_at(max(0, index - 1)), close_at(index)
    width = Decimal("0.3")
    if scenario == "volatility_spike" and index == 60:
        width = Decimal(50)
    elif scenario == "changing_volatility":
        width = Decimal("0.3") if index < 40 else Decimal(3) if index < 80 else Decimal("0.1")
    return opening, max(opening, close) + width, min(opening, close) - width, close


def scenario_events(pin: SourcePin, scenario: str, bars: int = 128) -> Iterator[ShadowEvent]:
    """Owned M5 scenarios, with independent EURUSD/XAUUSD scales and explicit missing intervals."""
    if pin.mode != "fixture_replay" or scenario not in SCENARIOS or not 1 <= bars <= 1000:
        raise ShadowRefused("owned_scenario_bounds_or_identity_refused")
    for index in range(bars):
        if scenario == "gaps" and index in {60, 61}:
            continue
        opening = FIXTURE_START + timedelta(minutes=5 * index)
        prices = scenario_prices(scenario, index)
        for offset, symbol in enumerate(("EURUSD", "XAUUSD")):
            scale = Decimal("0.0011") if symbol == "EURUSD" else Decimal(2)
            op, high, low, close = (v * scale for v in prices)
            row = Observation(
                symbol=canonical(symbol),
                broker_symbol="EUR/USD" if symbol == "EURUSD" else "XAU/USD",
                kind="candle",
                timeframe="M5",
                source_at=opening,
                received_at=opening + timedelta(minutes=7, seconds=offset),
                evidence="synthetic",
                open=op,
                high=high,
                low=low,
                close=close,
                source_provider="twelve_data",
                price_type="reference_midpoint",
                source_timezone="UTC",
                raw_source_time=opening.strftime("%Y-%m-%d %H:%M:%S"),
                interval_complete=True,
                coverage_started_at=FIXTURE_START,
            )
            yield ShadowEvent(
                pin=pin,
                observation=row,
                evidence_id=record_id(row, pin.identity),
                manifest_sha256=digest(["owned-scenario-2.0.0", scenario]),
            )


def write_fixture(
    folder: Path, pin: SourcePin, bars: int = 64, *, scenario: str = "legacy"
) -> Path:
    """Bounded owned fixture; never overwrite a dataset or pretend replay is genuine."""
    manifest = folder / "input.manifest.json"
    if manifest.exists() or (folder / "events.jsonl").exists():
        raise ShadowRefused("fixture_already_exists; choose a new run directory")
    path = folder / "events.jsonl"
    events = list(
        fixture_events(pin, bars) if scenario == "legacy" else scenario_events(pin, scenario, bars)
    )
    atomic_write_bytes(path, b"".join((e.model_dump_json() + "\n").encode() for e in events))
    atomic_write_json(
        manifest,
        {
            "schema": 1,
            "pin": pin.model_dump(mode="json"),
            "file": path.name,
            "rows": len(events),
            "scenario": scenario,
            "sha256": sha256_file(path),
        },
    )
    return manifest


def read_replay(path: Path, pin: SourcePin) -> Iterator[ShadowEvent]:
    """Verify the complete small manifest before yielding any prospective replay event."""
    if path.stat().st_size > 32768:
        raise ShadowRefused("shadow_manifest_too_large")
    value = json.loads(path.read_text(encoding="utf-8"))
    if SourcePin.model_validate(value["pin"]) != pin or value.get("schema") != 1:
        raise ShadowRefused("shadow_manifest_source_identity_mismatch")
    source = (path.parent / value["file"]).resolve()
    if (
        not source.is_relative_to(path.parent.resolve())
        or source.suffix != ".jsonl"
        or source.stat().st_size > 8388608
        or sha256_file(source) != value["sha256"]
    ):
        raise ShadowRefused("shadow_input_manifest_integrity_failed")
    count = 0
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if len(line) > 32768 or count >= 2000:
                raise ShadowRefused("shadow_input_row_bound_refused")
            event = ShadowEvent.model_validate_json(line)
            if event.pin != pin:
                raise ShadowRefused("shadow_input_source_version_changed")
            count += 1
            yield event
    if count != value["rows"]:
        raise ShadowRefused("shadow_input_manifest_row_count_mismatch")
