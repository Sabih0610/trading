"""Later frozen-decision directional labels; no executable fills or profit calculations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Literal

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
    if journal.config.reference_strategies is not None:
        raise ShadowRefused("legacy_label_protocol_not_enabled_for_versioned_reference_study")
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


def future_start(decision_at: datetime) -> datetime:
    """First full M5 opening at or after the frozen decision, never its input close."""
    at = decision_at.replace(minute=decision_at.minute // 5 * 5, second=0, microsecond=0)
    return at + timedelta(minutes=5) if at < decision_at else at


def _utc(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def evaluate_event(
    journal: ShadowJournal, rights: DataRights, later: ShadowEvent, now: datetime
) -> int:
    """Append preregistered labels using only contiguous committed future reference intervals."""
    if journal.config.reference_strategies is None:
        return 0
    journal.quota()
    if later.pin != journal.pin or journal.existing(later) != later.evidence_id:
        raise ShadowRefused("evaluation_requires_committed_same_source_event")
    stored = journal.db.execute(
        "SELECT payload FROM shadow_events WHERE id=?", (later.interval_id,)
    ).fetchone()
    later = ShadowEvent.model_validate_json(stored[0])
    if later.observation.received_at > now:
        raise ShadowRefused("evaluation_future_observation_unavailable")
    rights.require(
        SHADOW_USAGES,
        provider=journal.pin.provider,
        identity=journal.pin.identity,
        symbol=later.observation.symbol,
        now=now,
    )
    if rights.digest != journal.pin.rights_digest:
        raise ShadowRefused("evaluation_rights_version_changed")
    protocol = journal.config.evaluation
    protocol_hash = digest(protocol.model_dump(mode="json"))
    appended = 0
    for horizon in protocol.horizons:
        opening = later.observation.source_at - timedelta(minutes=5 * (horizon - 1))
        rows = journal.db.execute(
            "SELECT payload_json FROM decisions WHERE json_extract(payload_json,'$.symbol')=? AND json_extract(payload_json,'$.decision_at')>? AND json_extract(payload_json,'$.decision_at')<=? ORDER BY rowid LIMIT 12",
            (later.observation.symbol, _utc(opening - timedelta(minutes=5)), _utc(opening)),
        )
        for raw in rows:
            decision = ResearchDecision.model_validate_json(raw[0])
            if decision.signal == "WAIT":
                continue
            if future_start(decision.decision_at) != opening:
                raise ShadowRefused("evaluation_horizon_alignment_refused")
            key = digest([decision.id, protocol_hash, horizon])
            if journal.db.execute("SELECT 1 FROM shadow_labels WHERE id=?", (key,)).fetchone():
                continue
            evidence = [
                ShadowEvent.model_validate_json(v[0])
                for v in journal.db.execute(
                    "SELECT payload FROM shadow_events WHERE symbol=? AND opening>=? AND opening<=? ORDER BY opening LIMIT 7",
                    (decision.symbol, opening.isoformat(), later.observation.source_at.isoformat()),
                )
            ]
            if len(evidence) != horizon:
                continue
            if any(
                e.pin != journal.pin
                or not e.observation.interval_complete
                or e.observation.source_at != opening + timedelta(minutes=5 * i)
                or e.observation.received_at > now
                for i, e in enumerate(evidence)
            ):
                raise ShadowRefused("evaluation_unavailable_or_mixed_future_window")
            first, last = evidence[0].observation, evidence[-1].observation
            assert first.open is not None and last.close is not None
            change_bps = (last.close / first.open - 1) * 10000
            threshold = protocol.flat_threshold_bps
            label = (
                "UP" if change_bps > threshold else "DOWN" if change_bps < -threshold else "FLAT"
            )
            previous = journal.db.execute(
                "SELECT MAX(json_extract(payload,'$.evaluation_end')) FROM shadow_labels WHERE json_extract(payload,'$.protocol_hash')=? AND json_extract(payload,'$.strategy')=? AND json_extract(payload,'$.symbol')=? AND json_extract(payload,'$.horizon_m5')=? AND json_extract(payload,'$.nonoverlapping')=1",
                (protocol_hash, decision.strategy, decision.symbol, horizon),
            ).fetchone()[0]
            independent = previous is None or opening >= datetime.fromisoformat(
                previous.replace("Z", "+00:00")
            )
            prior_move = decision.features.get("log_return")
            prior_prediction = (
                "UP"
                if prior_move and prior_move > 0
                else "DOWN"
                if prior_move and prior_move < 0
                else "WAIT"
            )
            payload = {
                "decision_id": decision.id,
                "decision_sha256": digest(json.loads(raw[0])),
                "strategy": decision.strategy,
                "symbol": decision.symbol,
                "signal": decision.signal,
                "mode": journal.pin.mode,
                "protocol": protocol.version,
                "protocol_hash": protocol_hash,
                "horizon_m5": horizon,
                "flat_threshold_bps": threshold,
                "evaluation_start": _utc(opening),
                "evaluation_end": _utc(later.closes_at),
                "evidence_ids": [e.evidence_id for e in evidence],
                "available_at": _utc(now),
                "label": label,
                "correct": label == ("UP" if decision.signal == "BUY" else "DOWN"),
                "nonoverlapping": independent,
                "always_up_correct": label == "UP",
                "previous_move_prediction": prior_prediction,
                "previous_move_correct": None
                if prior_prediction == "WAIT"
                else label == prior_prediction,
                "not_trade_profitability": True,
            }
            with journal.db:
                journal.db.execute(
                    "INSERT INTO shadow_labels VALUES(?,?,?)",
                    (key, json.dumps(payload), digest(payload)),
                )
            appended += 1
    return appended


def evaluation_summary(journal: ShadowJournal) -> list[dict[str, Any]]:
    """Small price-free groups; overlapping horizons and synthetic evidence never imply skill."""
    from tb.strategies.reference import REFERENCE_STRATEGIES

    if journal.config.reference_strategies is None:
        return []
    groups = []
    for symbol in ("EURUSD", "XAUUSD"):
        latest = journal.db.execute(
            "SELECT MAX(opening) FROM shadow_events WHERE symbol=?", (symbol,)
        ).fetchone()[0]
        latest_open = datetime.fromisoformat(latest) if latest else None
        for strategy in REFERENCE_STRATEGIES:
            for horizon in journal.config.evaluation.horizons:
                missing, pending, directional = 0, 0, 0
                for raw in journal.db.execute(
                    "SELECT payload_json FROM decisions WHERE json_extract(payload_json,'$.symbol')=? AND json_extract(payload_json,'$.strategy')=? AND json_extract(payload_json,'$.signal')!='WAIT'",
                    (symbol, strategy),
                ):
                    decision = ResearchDecision.model_validate_json(raw[0])
                    directional += 1
                    known = journal.db.execute(
                        "SELECT 1 FROM shadow_labels WHERE json_extract(payload,'$.decision_id')=? AND json_extract(payload,'$.horizon_m5')=?",
                        (decision.id, horizon),
                    ).fetchone()
                    if known is None:
                        end_open = future_start(decision.decision_at) + timedelta(
                            minutes=5 * (horizon - 1)
                        )
                        if latest_open is not None and end_open <= latest_open:
                            missing += 1
                        else:
                            pending += 1
                (
                    samples,
                    correct,
                    independent,
                    independent_correct,
                    up_correct,
                    move_n,
                    move_correct,
                ) = journal.db.execute(
                    "SELECT COUNT(*),COALESCE(SUM(json_extract(payload,'$.correct')),0),COALESCE(SUM(json_extract(payload,'$.nonoverlapping')),0),COALESCE(SUM(json_extract(payload,'$.correct')*json_extract(payload,'$.nonoverlapping')),0),COALESCE(SUM(json_extract(payload,'$.always_up_correct')),0),COUNT(json_extract(payload,'$.previous_move_correct')),COALESCE(SUM(json_extract(payload,'$.previous_move_correct')),0) FROM shadow_labels WHERE json_extract(payload,'$.symbol')=? AND json_extract(payload,'$.strategy')=? AND json_extract(payload,'$.horizon_m5')=?",
                    (symbol, strategy, horizon),
                ).fetchone()
                groups.append(
                    {
                        "symbol": symbol,
                        "strategy": strategy,
                        "horizon_m5": horizon,
                        "directional_decisions": directional,
                        "available": samples,
                        "correct_direction": correct,
                        "incorrect_or_flat": samples - correct,
                        "nonoverlapping": independent,
                        "nonoverlapping_correct": independent_correct,
                        "overlapping": samples - independent,
                        "missing_outcomes": missing,
                        "not_yet_available": pending,
                        "directional_accuracy": correct / samples if samples else None,
                        "always_up_correct": up_correct,
                        "previous_move_scored": move_n,
                        "previous_move_correct": move_correct,
                        "always_WAIT_scored": 0,
                        "status": "synthetic_only_no_statistical_inference"
                        if journal.pin.mode == "fixture_replay"
                        else "insufficient_nonoverlapping_samples"
                        if independent < journal.config.evaluation.minimum_nonoverlapping_samples
                        else "descriptive_reference_only_dependence_unresolved",
                    }
                )
    return groups
