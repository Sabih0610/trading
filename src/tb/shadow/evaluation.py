"""Later frozen-decision directional labels; no executable fills or profit calculations."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from tb.ingest.rights import SHADOW_USAGES, DataRights
from tb.shadow.journal import ShadowJournal, ShadowRefused, digest
from tb.shadow.models import ResearchDecision, ShadowEvent


def directional_label(
    decision: ResearchDecision, later: ShadowEvent, now: datetime
) -> Literal["UP", "DOWN", "FLAT", "NOT_DIRECTIONAL"]:
    """Use a full interval beginning AFTER decision availability, never the old input close."""
    row = later.observation
    if (
        decision.provider != later.pin.provider
        or decision.mode != later.pin.mode
        or decision.symbol != row.symbol
    ):
        raise ShadowRefused("shadow_label_provider_or_instrument_mismatch")
    if row.source_at < decision.decision_at or row.received_at > now or not row.interval_complete:
        raise ShadowRefused("shadow_label_uses_predecision_or_unavailable_prices")
    expected = decision.decision_at.replace(
        minute=decision.decision_at.minute // 5 * 5, second=0, microsecond=0
    )
    if expected < decision.decision_at:
        from datetime import timedelta

        expected += timedelta(minutes=5)
    if row.source_at != expected:
        raise ShadowRefused("shadow_label_fixed_next_full_M5_horizon_missing")
    if decision.signal == "WAIT":
        return "NOT_DIRECTIONAL"
    assert row.open is not None and row.close is not None
    return "UP" if row.close > row.open else "DOWN" if row.close < row.open else "FLAT"


def append_directional_label(
    journal: ShadowJournal, rights: DataRights, decision_id: str, later: ShadowEvent, now: datetime
) -> bool:
    """Append a fixed-horizon label once; never rewrite the decision or treat it as a fill."""
    journal.quota()
    if later.pin != journal.pin or journal.existing(later) != later.evidence_id:
        raise ShadowRefused("shadow_label_requires_committed_same_source_event")
    stored = journal.db.execute(
        "SELECT payload FROM shadow_events WHERE id=?", (later.interval_id,)
    ).fetchone()
    later = ShadowEvent.model_validate_json(stored[0])
    rights.require(
        SHADOW_USAGES,
        provider=later.pin.provider,
        identity=later.pin.identity,
        symbol=later.observation.symbol,
        now=now,
    )
    row = journal.db.execute(
        "SELECT payload_json FROM decisions WHERE id=?", (decision_id,)
    ).fetchone()
    if row is None:
        raise ShadowRefused("shadow_label_decision_missing")
    decision = ResearchDecision.model_validate_json(row[0])
    result = directional_label(decision, later, now)
    if result == "NOT_DIRECTIONAL":
        return False
    key = digest([decision.id, "next-full-M5-direction-1.0.0"])
    payload = {
        "decision_id": decision.id,
        "decision_sha256": digest(json.loads(row[0])),
        "later_evidence_id": later.evidence_id,
        "label": result,
        "available_at": now.isoformat(),
        "protocol": "next-full-M5-direction-1.0.0",
        "not_trade_profitability": True,
    }
    with journal.db:
        inserted = journal.db.execute(
            "INSERT OR IGNORE INTO shadow_labels VALUES(?,?,?)",
            (key, json.dumps(payload), digest(payload)),
        )
    return inserted.rowcount == 1
