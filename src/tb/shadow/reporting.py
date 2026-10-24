"""Small price-free read projections over the isolated shadow journal."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.rights import DataRights
from tb.shadow.evaluation import evaluation_summary
from tb.shadow.journal import ShadowJournal
from tb.shadow.models import ShadowSnapshot


def snapshot(
    journal: ShadowJournal, rights: DataRights, *, state: str = "stopped"
) -> ShadowSnapshot:
    db = journal.db
    counts = {
        "events": db.execute("SELECT COUNT(*) FROM shadow_events").fetchone()[0],
        "decisions": db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
    }
    for field, value in (
        ("BUY", "BUY"),
        ("SELL", "SELL"),
        ("WAIT", "WAIT"),
        ("blocked", "blocked"),
        ("control", "control"),
    ):
        key = "signal" if field in {"BUY", "SELL", "WAIT"} else "status"
        counts[field] = int(
            db.execute(
                f"SELECT COUNT(*) FROM decisions WHERE json_extract(payload_json,'$.{key}')=?",
                (value,),
            ).fetchone()[0]
        )
    for name, pattern in (
        ("rejected_events", "shadow_%"),
        ("duplicates", "duplicate"),
        ("revisions", "revision_frozen_interval"),
        ("skipped_batches", "skipped_batch_%"),
    ):
        counts[name] = int(
            db.execute(
                "SELECT COUNT(*) FROM shadow_health WHERE json_extract(payload,'$.reason') LIKE ?",
                (pattern,),
            ).fetchone()[0]
        )
    counts["available_directional_samples"] = int(
        db.execute("SELECT COUNT(*) FROM shadow_labels").fetchone()[0]
    )
    counts["data_gaps"] = int(
        db.execute(
            "SELECT COUNT(*) FROM decisions WHERE json_extract(payload_json,'$.strategy')='do_nothing' AND json_extract(payload_json,'$.features.input_gap')=1"
        ).fetchone()[0]
    )
    instruments = []
    for symbol in ("EURUSD", "XAUUSD"):
        latest = db.execute(
            "SELECT payload_json FROM decisions WHERE json_extract(payload_json,'$.symbol')=? ORDER BY rowid DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        value = json.loads(latest[0]) if latest else {}
        instruments.append(
            {
                "instrument": symbol,
                "readiness": "owned_fixture_mechanics_only"
                if journal.pin.mode == "fixture_replay"
                else "reference_shadow_only",
                "latest_candle_open": value.get("source_open_at"),
                "latest_receipt": value.get("received_at"),
                "latest_decision": value.get("decision_at"),
                "signal": value.get("signal", "unavailable"),
                "reason": "reference hypotheses only; no execution"
                if journal.config.reference_strategies
                else "no eligible directional strategy; no execution",
                "freshness": "virtual_fixture_clock"
                if journal.pin.mode == "fixture_replay"
                else "unavailable"
                if not value
                else "stale"
                if (
                    datetime.now(UTC)
                    - datetime.fromisoformat(value["received_at"].replace("Z", "+00:00"))
                ).total_seconds()
                > 600
                else "recent_reference_only",
                "executable_bid_ask": "unqualified",
            }
        )
    strategy_states = []
    for symbol in ("EURUSD", "XAUUSD"):
        for (strategy,) in db.execute(
            "SELECT DISTINCT json_extract(payload_json,'$.strategy') FROM decisions"
        ):
            raw = db.execute(
                "SELECT payload_json FROM decisions WHERE json_extract(payload_json,'$.symbol')=? AND json_extract(payload_json,'$.strategy')=? ORDER BY rowid DESC LIMIT 1",
                (symbol, strategy),
            ).fetchone()
            if raw is None:
                continue
            v = json.loads(raw[0])
            strategy_states.append(
                {
                    "symbol": symbol,
                    "strategy": strategy,
                    "signal": v["signal"],
                    "status": v["status"],
                    "reasons": v["reasons"],
                    "decision_at": v["decision_at"],
                    "strategy_version": v["strategy_version"],
                    "contiguous_bars": v["features"].get("reference_contiguous_bars"),
                    "warmup_required": v.get("strategy_config", {}).get("minimum_warmup"),
                    "evidence_mode": v["mode"],
                }
            )
    recent_labels = []
    for row in db.execute(
        "SELECT payload FROM shadow_labels WHERE json_extract(payload,'$.horizon_m5') IS NOT NULL ORDER BY rowid DESC LIMIT 20"
    ):
        v = json.loads(row[0])
        recent_labels.append(
            {
                k: v[k]
                for k in (
                    "decision_id",
                    "strategy",
                    "symbol",
                    "signal",
                    "horizon_m5",
                    "label",
                    "correct",
                    "nonoverlapping",
                    "available_at",
                    "evaluation_start",
                    "evaluation_end",
                )
            }
        )
    if journal.config.reference_strategies:
        counts["available_future_labels"] = counts["available_directional_samples"]
        counts["available_directional_samples"] = db.execute(
            "SELECT COUNT(DISTINCT json_extract(payload,'$.decision_id')) FROM shadow_labels"
        ).fetchone()[0]
    latest_decisions = []
    for row in db.execute("SELECT payload_json FROM decisions ORDER BY rowid DESC LIMIT 20"):
        value = json.loads(row[0])
        latest_decisions.append(
            {
                k: value.get(k)
                for k in (
                    "id",
                    "symbol",
                    "strategy",
                    "signal",
                    "status",
                    "decision_at",
                    "received_at",
                    "source_close_at",
                    "reasons",
                    "strategy_version",
                    "feature_version",
                    "strategy_config_sha256",
                )
            }
        )
    failures = [
        json.loads(row[0])
        for row in db.execute("SELECT payload FROM shadow_health ORDER BY seq DESC LIMIT 20")
    ]
    times = db.execute(
        "SELECT AVG(json_extract(payload_json,'$.runtime_milliseconds')),MAX(json_extract(payload_json,'$.runtime_milliseconds')) FROM decisions"
    ).fetchone()
    lags = [
        (
            datetime.fromisoformat(v["received_at"].replace("Z", "+00:00"))
            - datetime.fromisoformat(v["source_close_at"].replace("Z", "+00:00"))
        ).total_seconds()
        for v in latest_decisions
    ]
    return ShadowSnapshot.model_validate(
        {
            "mode": journal.pin.mode,
            "provider": journal.pin.provider,
            "generated_at": datetime.now(UTC),
            "consumer_state": state,
            "collector_state": "not_run; fixture replay"
            if journal.pin.mode == "fixture_replay"
            else "independent_collector_liveness_unverified",
            "permission_states": {
                k: (p.state_at(datetime.now(UTC)) + (";approved" if p.approved else ";unapproved"))
                for k, p in rights.permissions.items()
            },
            "rights_digest": rights.digest,
            "source_identity": journal.pin.identity,
            "versions": {
                "consumer": journal.pin.consumer_version,
                "source": journal.pin.source_version,
                "features": journal.config.feature_version,
                "strategy": journal.config.strategy_version,
            },
            "counts": counts,
            "strategy_states": strategy_states,
            "evaluation": evaluation_summary(journal),
            "recent_labels": recent_labels,
            "evaluation_protocol": journal.config.evaluation.model_dump(mode="json")
            if journal.config.reference_strategies
            else {},
            "directional_metrics": "owned_fixture_directional_mechanics_only"
            if journal.config.reference_strategies and journal.pin.mode == "fixture_replay"
            else "reference_direction_only_not_trade_win_rate"
            if journal.config.reference_strategies
            else "unavailable_no_eligible_directional_strategy_or_genuine_sample",
            "instruments": instruments,
            "latest_decisions": latest_decisions,
            "failures": failures,
            "quota": {
                "minute_limit": 8,
                "plan_daily_limit": 800,
                "application_daily_ceiling": journal.config.daily_credit_ceiling,
                "scheduled_M5_credits_per_day": 576,
                "application_headroom": 24,
                "reserved_other_usage_headroom": 200,
                "actual_account_usage": "unavailable; no genuine request in this study",
            },
            "latency": {
                "mean_strategy_ms": times[0],
                "maximum_strategy_ms": times[1],
                "mean_recent_publication_seconds": sum(lags) / len(lags) if lags else None,
            },
            "evidence_completeness": "atomic input/decision/checkpoint hashes verified; no continuous genuine availability measured",
        }
    )


def publish(
    journal: ShadowJournal, rights: DataRights, *, state: str = "stopped"
) -> ShadowSnapshot:
    journal.quota()
    value = snapshot(journal, rights, state=state)
    folder = journal.folder / "snapshots"
    path = folder / f"snapshot-{uuid4().hex}.json"
    atomic_write_json(path, value)
    atomic_write_json(folder / "current.json", {"file": path.name, "sha256": sha256_file(path)})
    return value
