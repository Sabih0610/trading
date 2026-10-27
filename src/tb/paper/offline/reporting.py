"""Immutable bounded projections derived exclusively from committed owned paper evidence."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.paper.offline.models import VERSION, PaperRefused, digest
from tb.paper.offline.store import PaperStore


def projection(store: PaperStore, root: Path) -> dict[str, Any]:
    """Export committed totals and lifecycle reasons; no empirical return statistics."""
    store.require_writer()
    row = store.db.execute(
        "SELECT state_json FROM paper_events ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    if row is None or digest(store.state.model_dump(mode="json")) != digest(json.loads(row[0])):
        raise PaperRefused("paper_export_requires_committed_state")
    effects = store.effects()
    return {
        "name": store.package.name,
        "package": store.package.model_dump(mode="json"),
        "state": store.state.model_dump(mode="json"),
        "state_sha256": digest(store.state.model_dump(mode="json")),
        "journal": store.path.relative_to(root).as_posix(),
        "chain_sha256": store.chain,
        "checkpoint_events": store.state.events,
        "recovered_events": store.recovered_events,
        "recoveries": [
            json.loads(row[0])
            for row in store.db.execute("SELECT payload_json FROM paper_recoveries ORDER BY id")
        ],
        "effect_counts": dict(Counter(str(e["kind"]) for e in effects)),
        "journal_tail": effects[-250:],
        "fills": [e for e in effects if e["kind"] == "hypothetical_fill"],
        "closed_trades": [e for e in effects if e["kind"] == "position_closed"],
        "risk_events": [e for e in effects if e["kind"] == "risk_shutdown"],
        "order_transitions": [e for e in effects if e["kind"] == "order_transition"],
        "input_count": store.state.events,
        "integrity": "replayed_and_reconciled",
        "external_orders_enabled": False,
    }


def publish(root: Path, studies: list[dict[str, Any]], *, code_sha256: str) -> Path:
    """Content-addressed snapshot; a repeat run must keep the same account totals."""
    value = {
        "schema_version": 1,
        "version": VERSION,
        "mode": "owned_offline_paper",
        "label": "SYNTHETIC — SOFTWARE TEST ONLY",
        "code_sha256": code_sha256,
        "studies": studies,
        "genuine_sources_enabled": False,
        "external_orders_enabled": False,
        "partial_fills_supported": False,
        "genuine_performance_claim": False,
    }
    folder = root / "reports/offline_paper"
    path = folder / (digest(value) + ".json")
    atomic_write_json(path, value)
    if path.stat().st_size > 8388608:
        raise PaperRefused("offline_snapshot_bound_exceeded")
    atomic_write_json(folder / "current.json", {"file": path.name, "sha256": sha256_file(path)})
    return path
