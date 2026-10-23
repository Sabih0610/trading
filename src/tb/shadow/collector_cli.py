"""Explicit supervised M5 collector; default rights refuse before credentials or new data."""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime

import yaml

from tb.core.config import repo_root
from tb.ingest.assessment import source_version
from tb.ingest.history.core import atomic_write_json
from tb.ingest.mt5.cli import collector_lease
from tb.ingest.mt5.models import FeedConfig, FeedUnavailable
from tb.ingest.mt5.qualification import clock_reference_passes, independent_utc
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.rights import SHADOW_USAGES, load_rights
from tb.ingest.twelve_data.adapter import TwelveDataFeed
from tb.ingest.twelve_data.client import CreditBudget, TwelveDataClient, TwelveDataSettings
from tb.shadow.collection import collect_m5_once, latest_due_close
from tb.shadow.journal import digest
from tb.shadow.models import ShadowConfig, SourcePin


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supervised-minutes", type=int, choices=range(1, 121), required=True)
    args = parser.parse_args()
    root, started = repo_root(), datetime.now(UTC)
    rights = load_rights(root / "config/data_rights.yaml")
    for symbol in ("EURUSD", "XAUUSD"):
        rights.require(
            SHADOW_USAGES,
            provider="twelve_data",
            identity=rights.account_fingerprint or "unconfigured",
            symbol=symbol,
            now=started,
        )
    # Only a later explicitly launched, rights-approved process can reach the key or storage.
    config = ShadowConfig.model_validate(
        yaml.safe_load((root / "config/shadow.yaml").read_text(encoding="utf-8"))
    )
    settings = TwelveDataSettings.from_root(root)
    if not settings.api_key.get_secret_value():
        raise FeedUnavailable("Twelve Data disabled: key missing")
    import hashlib

    scope = hashlib.sha256(settings.api_key.get_secret_value().encode()).hexdigest()
    budget = CreditBudget(
        root / "data/twelve_data/credits.sqlite", scope, daily_ceiling=config.daily_credit_ceiling
    )
    client = TwelveDataClient(settings, budget, rights=rights)
    feed = TwelveDataFeed(client)
    version = source_version(root)
    store = FeedStore(
        root,
        FeedConfig(poll_seconds=300, max_rows=10),
        code_version=version,
        provider="twelve_data",
    )
    pin = SourcePin(
        mode="genuine_shadow",
        provider="twelve_data",
        identity=client.source_identity,
        source_version=version,
        consumer_version=version.split("+tree.")[-1],
        rights_digest=rights.digest,
        config_digest=digest(config.model_dump(mode="json")),
    )
    try:
        rights.require(
            SHADOW_USAGES,
            provider=pin.provider,
            identity=pin.identity,
            symbol="EURUSD",
            now=started,
        )
        with collector_lease(root / "data/twelve_data/collector.lock"):
            client.get("api_usage")
            atomic_write_json(root / "reports/shadow/genuine/source-pin.json", pin)
            deadline = time.monotonic() + args.supervised_minutes * 60
            previous_slot = None
            while time.monotonic() < deadline:
                current = load_rights(root / "config/data_rights.yaml")
                if current.digest != rights.digest:
                    raise FeedUnavailable("shadow_collection_rights_changed")
                now = datetime.now(UTC)
                slot = latest_due_close(now)
                if slot != previous_slot and 120 <= (now - slot).total_seconds() <= 180:
                    references = independent_utc()
                    if not clock_reference_passes(references, datetime.now(UTC)):
                        raise FeedUnavailable("shadow_collection_host_UTC_refused")
                    collect_m5_once(feed, store, current, started_at=started, now=datetime.now(UTC))
                    previous_slot = slot
                time.sleep(min(30, max(0, deadline - time.monotonic())))
    finally:
        feed.close()
        budget.close()
        store.close()


if __name__ == "__main__":
    try:
        main()
    except (FeedUnavailable, ValueError, OSError):
        raise SystemExit(
            "M5 collector refused by rights, quota, clock or source safeguards; no orders"
        ) from None
