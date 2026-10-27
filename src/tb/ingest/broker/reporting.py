"""Small immutable evidence snapshots; raw events remain inside the existing private pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from tb.ingest.broker.evaluation import qualify
from tb.ingest.broker.models import (
    BrokerContract,
    BrokerQuote,
    BrokerRefused,
    ReferenceQuoteLink,
    Symbol,
)
from tb.ingest.broker.storage import BrokerStore
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.retention import EvidenceLifetime, require_lifetime
from tb.risk.config import load_policy_bundle


def publish(
    store: BrokerStore,
    contracts: dict[Symbol, BrokerContract],
    *,
    folder: Path,
    now: datetime,
) -> Path:
    """Project only committed evidence; never use a duplicate receipt as a new quote."""
    mode: Literal["owned_fixture", "genuine"] = store.identity.evidence
    for symbol in contracts:
        store._permit(symbol)
    counts: dict[str, dict[str, int]] = {}
    quotes: dict[Symbol, BrokerQuote] = {}
    alignments: list[ReferenceQuoteLink] = []
    lifetimes: list[EvidenceLifetime] = []
    for record in store.feed.db.execute("SELECT payload_json FROM decisions ORDER BY rowid"):
        import json

        value = json.loads(record[0])
        if mode == "genuine":
            lifetimes.append(require_lifetime(store.rights, value.get("retention"), now))
        symbol = value["symbol"]
        counts.setdefault(
            symbol, {"raw_observations": 0, "admissible_quotes": 0, "aligned_observations": 0}
        )
        counts[symbol]["raw_observations"] += 1
        if value["quote"]:
            quote = BrokerQuote.model_validate(value["quote"])
            quotes[quote.symbol] = quote
            counts[symbol]["admissible_quotes"] += 1
        if value["alignment"]:
            link = ReferenceQuoteLink.model_validate(value["alignment"])
            if link.status == "observed":
                counts[symbol]["aligned_observations"] += 1
            alignments.append(link)
            alignments = alignments[-20:]
    bundle = load_policy_bundle()
    instruments = []
    for symbol, contract in contracts.items():
        q = quotes.get(symbol)
        permission = store.rights.permissions.get("private_display")
        display = bool(permission and permission.allows(now))
        result = qualify(contract, q, now=now, bundle=bundle)
        instruments.append(
            {
                **result.model_dump(mode="json"),
                "broker_symbol": contract.broker_symbol,
                "contract_version": contract.digest,
                "minimum_units": str(contract.min_units) if contract.min_units else None,
                "cost_metadata_fields": sorted(contract.native_costs),
                "source_timestamp": q.source_at.isoformat() if q else None,
                "receipt_utc": q.received_at.isoformat() if q else None,
                "quote_age_at_receipt_seconds": q.age_seconds if q else None,
                "bid": str(q.bid) if q and display else None,
                "ask": str(q.ask) if q and display else None,
                "spread": str(q.spread) if q and display else None,
                "display_status": "permitted_owned_or_approved"
                if display
                else "withheld_unconfirmed_rights",
                "counts": counts.get(symbol, {}),
            }
        )
        if not display:
            # A notional computed from a price is also price-reconstructible.
            instruments[-1]["minimum_notional"] = None
            instruments[-1]["minimum_capital_with_known_costs"] = None
    links = [link.model_dump(mode="json", exclude={"spread"}) for link in alignments]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "mode": mode,
        "generated_at": now.isoformat(),
        "identity": store.identity.model_dump(mode="json"),
        "rights_digest": store.rights.digest,
        "reference_provider": "owned_fixture_inputs" if mode == "owned_fixture" else "twelve_data",
        "broker_provider": "ctrader_demo",
        "source_code_digest": store.code_digest,
        "connection_status": "stopped_finite_evidence_only",
        "instruments": instruments,
        "alignments": links,
        "risk_limits": bundle.risk.limits.model_dump(mode="json"),
        "genuine_connectivity_verified": mode == "genuine",
        "external_orders_enabled": False,
        "fills_created": 0,
        "positions_created": 0,
        "p11b2": "NO-GO",
    }
    authorization = None
    if mode == "genuine":
        if not lifetimes:
            raise BrokerRefused("broker_retained_evidence_required_for_publication")
        retained = EvidenceLifetime(
            acquired_at=min(v.acquired_at for v in lifetimes),
            expires_at=min(v.expires_at for v in lifetimes),
            rights_digest=store.rights.digest,
        )
        authorization = {
            "provider": "ctrader_demo",
            "identity": store.identity.account_fingerprint,
            "rights_digest": store.rights.digest,
            "instruments": list(store.rights.instruments),
            "retention": retained.model_dump(mode="json"),
        }
        payload["authorization"] = authorization
    folder.mkdir(parents=True, exist_ok=True)
    if sum(p.stat().st_size for p in folder.glob("*.json")) > 8 * 1024 * 1024:
        raise BrokerRefused("broker_report_storage_cap_reached")
    from tb.ingest.broker.storage import canonical_hash

    path = folder / (canonical_hash(payload) + ".json")
    if not path.exists():
        atomic_write_json(path, payload)
    atomic_write_json(
        folder / "current.json",
        {"file": path.name, "sha256": sha256_file(path), "authorization": authorization},
    )
    return path
