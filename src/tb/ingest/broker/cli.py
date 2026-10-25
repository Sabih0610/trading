"""Explicit finite broker data commands; default status performs no network operation."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

from tb.core.config import repo_root
from tb.ingest.broker.ctrader import BrokerAccess, CTraderQuoteSource, CTraderSettings
from tb.ingest.broker.evaluation import align_reference
from tb.ingest.broker.fixtures import fixture_decision, fixture_rights, fixture_source
from tb.ingest.broker.models import BrokerRefused, Symbol
from tb.ingest.broker.reporting import publish
from tb.ingest.broker.storage import BrokerStore, source_code_digest
from tb.ingest.rights import load_rights


def run_owned(root: Path) -> Path:
    """Ten raw updates, eight quote observations; owned bridge inputs, no market skill."""
    workspace = root / "work/p11b1" / ("owned-broker-study-" + source_code_digest()[:12])
    source, clock, _channel = fixture_source(workspace)
    started = clock()
    identity = source.connect()
    contracts = {s: source.metadata(s) for s in source.access.symbols}
    store = BrokerStore(workspace, identity, source.rights, started_at=started, clock=clock)
    try:
        for _ in range(10):
            quote = source.read()
            raw = source.latest_raw
            if raw is None:
                continue
            symbol = next(s for s, c in contracts.items() if c.symbol_id == int(raw["symbolId"]))
            link = (
                align_reference(
                    fixture_decision(symbol),
                    quote,
                    now=clock(),
                    reference_rights=fixture_rights(reference=True),
                )
                if quote
                else None
            )
            store.record(
                symbol,
                raw,
                quote=quote,
                contract=contracts[symbol],
                link=link,
                reason=source.reason,
            )
        return publish(store, contracts, folder=root / "reports/broker_quotes/fixture", now=clock())
    finally:
        store.close()
        source.close()


def genuine_smoke(root: Path, seconds: int, max_events: int) -> Path:
    """Owner-provisioned scope/rights only; one demo socket, at most sixty seconds."""
    if not 1 <= seconds <= 60 or not 1 <= max_events <= 1000:
        raise BrokerRefused("broker_smoke_bounds_invalid")
    settings = CTraderSettings.from_root(root)
    if not settings.configured:
        raise BrokerRefused("CTRADER_DEMO credentials missing; genuine connectivity unverified")
    rights_path, access_path = (
        root / "config/broker_data_rights.yaml",
        root / "config/broker_access.yaml",
    )
    if not rights_path.is_file() or not access_path.is_file() or access_path.stat().st_size > 32768:
        raise BrokerRefused("broker_access_and_documentary_rights_unconfigured")
    rights = load_rights(rights_path)
    access = BrokerAccess.model_validate(yaml.safe_load(access_path.read_text(encoding="utf-8")))
    source = CTraderQuoteSource(settings, rights, root=root, access=access, rights_path=rights_path)
    begin, deadline = datetime.now(UTC), time.monotonic() + seconds
    identity = source.connect()
    contracts = {s: source.metadata(s) for s in source.instruments}
    store: BrokerStore | None = None
    try:
        store = BrokerStore(
            root,
            identity,
            rights,
            started_at=begin,
            clock=lambda: datetime.now(UTC),
            rights_path=rights_path,
        )
        for _ in range(max_events):
            if time.monotonic() >= deadline:
                break
            quote = source.read()
            if source.identity is None:
                raise BrokerRefused("broker_view_identity_lost")
            store.refresh_identity(source.identity)
            if source.latest_raw is None:
                continue
            raw = source.latest_raw
            symbol: Symbol = next(
                s for s, c in contracts.items() if c.symbol_id == int(raw["symbolId"])
            )
            store.record(symbol, raw, quote=quote, contract=contracts[symbol], reason=source.reason)
        return publish(
            store, contracts, folder=root / "reports/broker_quotes/genuine", now=datetime.now(UTC)
        )
    finally:
        if store:
            store.close()
        source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", nargs="?", default="status", choices=["status", "owned-demo", "genuine-smoke"]
    )
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--max-events", type=int, default=100)
    args = parser.parse_args()
    root = repo_root()
    try:
        if args.action == "status":
            configured = CTraderSettings.from_root(root).configured
            print(
                json.dumps(
                    {
                        "provider": "ctrader_demo",
                        "credentials_configured": configured,
                        "reason": "credentials missing; broker feed disabled"
                        if not configured
                        else "access, scope and rights require verification",
                        "genuine_connectivity": "unverified",
                        "scope": "unverified",
                        "network_called": False,
                        "p11b2": "NO-GO",
                    }
                )
            )
        elif args.action == "owned-demo":
            print(run_owned(root).relative_to(root))
        else:
            print(genuine_smoke(root, args.seconds, args.max_events).relative_to(root))
    except (ValueError, OSError, KeyError, yaml.YAMLError):
        raise SystemExit(
            "Broker read-only command refused: credentials, exact demo/view scope, clocks and affirmative rights required; no external actions"
        ) from None


if __name__ == "__main__":
    main()
