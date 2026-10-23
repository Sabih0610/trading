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
        source_version="owned-M5-fixture-1.0.0",
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


def write_fixture(folder: Path, pin: SourcePin, bars: int = 64) -> Path:
    """Bounded owned fixture; never overwrite a dataset or pretend replay is genuine."""
    manifest = folder / "input.manifest.json"
    if manifest.exists() or (folder / "events.jsonl").exists():
        raise ShadowRefused("fixture_already_exists; choose a new run directory")
    path = folder / "events.jsonl"
    atomic_write_bytes(
        path, b"".join((e.model_dump_json() + "\n").encode() for e in fixture_events(pin, bars))
    )
    atomic_write_json(
        manifest,
        {
            "schema": 1,
            "pin": pin.model_dump(mode="json"),
            "file": path.name,
            "rows": bars * 2,
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
