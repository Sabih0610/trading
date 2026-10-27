"""Frozen historical orchestration of the existing feature/strategy/evaluation components."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from tb.core.leases import writer_lease
from tb.features.engine import FeatureEngine
from tb.ingest.history.core import atomic_write_bytes, sha256_file
from tb.ledger.store import DecisionLedger, LedgerVersions
from tb.paper.offline.integrity import ledger_matches, schema_digest
from tb.research.importer import bars, imported
from tb.research.models import (
    HOLDOUT,
    VALIDATION_START,
    VERSION,
    HistoricalBar,
    ResearchProtocol,
    ResearchRefused,
    digest,
)
from tb.research.registry import (
    artifact,
    declare_artifact,
    immutable_json,
    load,
    read_metadata,
    safe,
)
from tb.shadow.evaluation import future_start, price_direction
from tb.shadow.models import ResearchDecision
from tb.strategies.reference import (
    REFERENCE_FEATURE_VERSION,
    REFERENCE_STRATEGIES,
    REFERENCE_STRATEGY_VERSION,
    PriceOnlyStrategy,
)

VERSIONS = LedgerVersions(
    model_version=REFERENCE_STRATEGY_VERSION,
    prompt_version="none",
    question_set_version=VERSION,
    features_version=REFERENCE_FEATURE_VERSION,
)


def code_digest() -> str:
    base = Path(__file__).resolve().parents[1]
    paths = list((base / "research").glob("*.py")) + list((base / "features").glob("*.py"))
    paths += [
        base / p
        for p in (
            "strategies/reference.py",
            "shadow/evaluation.py",
            "shadow/models.py",
            "ingest/retention.py",
            "ledger/store.py",
            "paper/offline/integrity.py",
            "silver/market.py",
        )
    ]
    return digest({p.relative_to(base).as_posix(): sha256_file(p) for p in sorted(paths)})


def wilson(successes: int, total: int) -> list[float] | None:
    """Descriptive binomial interval; not proof of independent market samples or strategy skill."""
    if total < 30:
        return None
    z = 1.959963984540054
    p = successes / total
    den = 1 + z * z / total
    middle = (p + z * z / (2 * total)) / den
    width = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return [middle - width, middle + width]


def _append(
    ledger: DecisionLedger,
    db: sqlite3.Connection,
    table: Literal["decisions", "outcomes"],
    identifier: str,
    payload: dict[str, Any],
    when: datetime,
    *,
    decision_id: str | None = None,
) -> None:
    if table not in {"decisions", "outcomes"}:
        raise ResearchRefused("research_ledger_table_refused")
    old = db.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
    expected = {
        "id": identifier,
        "created_at_utc": when.isoformat().replace("+00:00", "Z"),
        "decision_id": decision_id,
        "payload": payload,
        **VERSIONS.model_dump(),
    }
    if old:
        if not ledger_matches(old, expected):
            raise ResearchRefused("research_immutable_ledger_changed")
    else:
        ledger._append(
            table,
            payload,
            VERSIONS,
            row_id=identifier,
            created_at=when,
            decision_id=decision_id,
            connection=db,
        )


def _summary(
    decisions: list[ResearchDecision],
    labels: list[dict[str, Any]],
    rows: list[HistoricalBar],
    policy_class: str,
    protocol: ResearchProtocol,
) -> list[dict[str, Any]]:
    results = []
    for symbol in sorted({b.symbol for b in rows}):
        known = {b.source_at: b for b in rows if b.symbol == symbol}
        last_open = max(known) if known else None
        for strategy in REFERENCE_STRATEGIES:
            ds = [d for d in decisions if d.symbol == symbol and d.strategy == strategy]
            signals = Counter(d.signal for d in ds)
            reasons = Counter(reason for d in ds for reason in d.reasons)
            for horizon in protocol.horizons:
                ls = [
                    label_row
                    for label_row in labels
                    if label_row["symbol"] == symbol
                    and label_row["strategy"] == strategy
                    and label_row["horizon_M5"] == horizon
                ]
                nonoverlap = [label_row for label_row in ls if label_row["nonoverlapping"]]
                matched = [
                    label_row
                    for label_row in nonoverlap
                    if label_row["previous_movement"] != "WAIT"
                ]
                correct = sum(label_row["correct"] for label_row in ls)
                flat = sum(label_row["label"] == "FLAT" for label_row in ls)
                primary_correct = sum(label_row["correct"] for label_row in matched)
                available = {label_row["decision_id"] for label_row in ls}
                pending = missing = 0
                for d in ds:
                    if d.signal == "WAIT" or d.id in available:
                        continue
                    end = future_start(d.decision_at) + timedelta(minutes=5 * (horizon - 1))
                    if last_open is None or end > last_open:
                        pending += 1
                    else:
                        missing += 1
                n = len(matched)
                owned = policy_class == "owned_synthetic"
                results.append(
                    {
                        "symbol": symbol,
                        "strategy": strategy,
                        "horizon_M5": horizon,
                        "observations": len(ds),
                        "BUY": signals["BUY"],
                        "SELL": signals["SELL"],
                        "WAIT": signals["WAIT"],
                        "signal_coverage": (signals["BUY"] + signals["SELL"]) / len(ds)
                        if ds
                        else 0,
                        "labels": len(ls),
                        "UP": sum(label_row["label"] == "UP" for label_row in ls),
                        "DOWN": sum(label_row["label"] == "DOWN" for label_row in ls),
                        "FLAT": flat,
                        "correct": correct,
                        "incorrect": len(ls) - correct - flat,
                        "pending": pending,
                        "missing": missing,
                        "nonoverlapping": len(nonoverlap),
                        "overlapping": len(ls) - len(nonoverlap),
                        "matched_n": n,
                        "matched_correct": primary_correct,
                        "matched_always_UP_correct": sum(
                            label_row["label"] == "UP" for label_row in matched
                        ),
                        "matched_previous_movement_correct": sum(
                            label_row["label"] == label_row["previous_movement"]
                            for label_row in matched
                        ),
                        "directional_accuracy": primary_correct / n if n else None,
                        "always_UP_accuracy": sum(
                            label_row["label"] == "UP" for label_row in matched
                        )
                        / n
                        if n
                        else None,
                        "previous_movement_accuracy": sum(
                            label_row["label"] == label_row["previous_movement"]
                            for label_row in matched
                        )
                        / n
                        if n
                        else None,
                        "wilson95_descriptive": None if owned else wilson(primary_correct, n),
                        "serial_dependence_resolved": False,
                        "status": "SOFTWARE TEST ONLY"
                        if owned
                        else "INSUFFICIENT EVIDENCE"
                        if n < 30
                        else "DESCRIPTIVE HISTORICAL EVIDENCE — DEPENDENCE UNRESOLVED",
                        "sample_size_status": "INSUFFICIENT EVIDENCE"
                        if n < 30
                        else "minimum_count_met_not_proof_of_independence",
                        "suppression_reasons": dict(reasons),
                    }
                )
    return results


def run(
    root: Path,
    dataset_id: str,
    protocol: ResearchProtocol,
    *,
    clock: Callable[[], datetime],
    fault: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    policy, source = imported(root, dataset_id, clock())
    source_hash = digest(source)
    plan = {
        "version": VERSION,
        "dataset_id": dataset_id,
        "policy_digest": policy.digest,
        "source_sha256": policy.source_sha256,
        "source_class": policy.source_class,
        "provider": policy.provider,
        "price_type": policy.price_type,
        "import_sha256": source_hash,
        "code_digest": code_digest(),
        "protocol": protocol.model_dump(mode="json"),
        "retention": policy.retention.model_dump(mode="json"),
    }
    identifier = digest(plan)
    folder = safe(root, f"data/gold/research/{identifier}")
    with writer_lease(safe(root, f"work/research/locks/run-{identifier}.lock")):
        immutable_json(folder / "plan.json", plan)
        db_path = folder / "journal.sqlite"
        dependencies = [p["path"] for p in source["files"]]
        declare_artifact(root, policy, db_path, ["features", "decisions", "labels"], dependencies)
        for suffix in ("-wal", "-shm", "-journal"):
            declare_artifact(
                root,
                policy,
                Path(str(db_path) + suffix),
                ["cache"],
                [db_path.relative_to(root).as_posix()],
            )
        for name in ("result.json", "report.md"):
            declare_artifact(
                root,
                policy,
                folder / name,
                ["reports", "dashboard"],
                [db_path.relative_to(root).as_posix()],
            )
        schema_path = folder / "schema.json"
        if db_path.exists() != schema_path.exists():
            raise ResearchRefused("research_partial_journal_initialization_refused")
        existed = db_path.exists()
        if existed:
            check = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
            try:
                expected = read_metadata(root, schema_path.relative_to(root).as_posix())
                if (
                    check.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                    or schema_digest(check) != expected["sha256"]
                ):
                    raise ResearchRefused("research_schema_corruption_refused_without_repair")
            finally:
                check.close()
        ledger = DecisionLedger(db_path, initialize=not existed)
        db = ledger.connect()
        try:
            db.execute("PRAGMA synchronous=FULL")
            if not existed:
                db.execute(
                    "CREATE TABLE research_inputs(id TEXT PRIMARY KEY,seq INTEGER UNIQUE,payload_sha TEXT NOT NULL)"
                )
                for action in ("UPDATE", "DELETE"):
                    db.execute(
                        f"CREATE TRIGGER research_inputs_no_{action} BEFORE {action} ON research_inputs BEGIN SELECT RAISE(ABORT,'append-only research'); END"
                    )
                db.commit()
                immutable_json(schema_path, {"sha256": schema_digest(db)})
            observations = [
                b
                for b in bars(root, dataset_id, clock=clock)
                if (
                    b.source_at < VALIDATION_START
                    if protocol.split == "research"
                    else VALIDATION_START <= b.source_at < HOLDOUT
                )
            ]
            observations.sort(key=lambda bar: (bar.available_at, bar.symbol, bar.source_at))
            if len(observations) > 50000:
                raise ResearchRefused("research_row_bound_exceeded")
            engines: dict[str, FeatureEngine] = {}
            plugins: dict[str, dict[str, PriceOnlyStrategy]] = {}
            decisions = []
            for index, bar in enumerate(observations, 1):
                if index % CHUNK_SIZE == 1:
                    load(root, dataset_id, clock())
                engine = engines.setdefault(
                    bar.symbol,
                    FeatureEngine(
                        timeframe=timedelta(minutes=5),
                        reference_periods=protocol.strategies.periods,
                    ),
                )
                if bar.symbol not in plugins:
                    plugins[bar.symbol] = {
                        name: cls(bar.symbol, protocol.strategies)
                        for name, cls in REFERENCE_STRATEGIES.items()
                    }
                features = engine.update(
                    {
                        "timestamp_utc": bar.source_at,
                        **{k: float(getattr(bar, k)) for k in ("open", "high", "low", "close")},
                    },
                    reference_only=True,
                )
                features["timestamp_utc"] = bar.source_at.isoformat()
                event_id = digest(bar.model_dump(mode="json"))
                event_decisions = []
                for name, plugin in plugins[bar.symbol].items():
                    signal = plugin.evaluate(bar.symbol, features)
                    d = ResearchDecision(
                        id=digest([identifier, event_id, name]),
                        event_id=event_id,
                        evidence_id=event_id,
                        mode="fixture_replay"
                        if policy.source_class == "owned_synthetic"
                        else "historical_research",
                        provider="owned_fixture"
                        if policy.source_class == "owned_synthetic"
                        else "licensed_local",
                        symbol=bar.symbol,
                        strategy=name,
                        strategy_version=REFERENCE_STRATEGY_VERSION,
                        feature_version=REFERENCE_FEATURE_VERSION,
                        source_open_at=bar.source_at,
                        source_close_at=bar.source_at + timedelta(minutes=5),
                        received_at=bar.available_at,
                        information_available_at=bar.available_at,
                        decision_at=bar.available_at,
                        signal=signal.signal,
                        status=signal.state,
                        reasons=signal.reasons,
                        features=features,
                        features_sha256=digest(features),
                        strategy_config=protocol.strategies.model_dump(mode="json"),
                        strategy_config_sha256=digest(protocol.strategies.model_dump(mode="json")),
                        rights_digest=policy.rights.digest,
                        source_version=policy.source_sha256,
                        consumer_version=VERSION,
                        runtime_milliseconds=0,
                    )
                    event_decisions.append(d)
                    decisions.append(d)
                payload_sha = digest([d.model_dump(mode="json") for d in event_decisions])
                old = db.execute(
                    "SELECT seq,payload_sha FROM research_inputs WHERE id=?", (event_id,)
                ).fetchone()
                if old and tuple(old) != (index, payload_sha):
                    raise ResearchRefused("research_checkpoint_changed")
                with db:
                    for d in event_decisions:
                        if (
                            old
                            and not db.execute(
                                "SELECT 1 FROM decisions WHERE id=?", (d.id,)
                            ).fetchone()
                        ):
                            raise ResearchRefused("research_atomic_decision_missing")
                        _append(
                            ledger, db, "decisions", d.id, d.model_dump(mode="json"), d.decision_at
                        )
                    if not old:
                        db.execute(
                            "INSERT INTO research_inputs VALUES(?,?,?)",
                            (event_id, index, payload_sha),
                        )
                    if fault:
                        fault("before_input_commit")
            if db.execute("SELECT count(*) FROM research_inputs").fetchone()[0] != len(
                observations
            ) or db.execute("SELECT count(*) FROM decisions").fetchone()[0] != len(decisions):
                raise ResearchRefused("research_unmatched_checkpoint_or_decision")
            by_symbol = {
                symbol: {b.source_at: b for b in observations if b.symbol == symbol}
                for symbol in policy.instruments
            }
            labels = []
            last_end: dict[tuple[str, str, int], datetime] = {}
            for d in decisions:
                if d.signal == "WAIT":
                    continue
                for horizon in protocol.horizons:
                    start = future_start(d.decision_at)
                    window = [
                        by_symbol[d.symbol].get(start + timedelta(minutes=5 * i))
                        for i in range(horizon)
                    ]
                    if any(b is None for b in window):
                        continue
                    complete = [b for b in window if b is not None]
                    if any(b.source_at < d.decision_at for b in complete):
                        raise ResearchRefused("research_label_lookahead")
                    label = price_direction(
                        complete[0].open, complete[-1].close, protocol.flat_threshold_bps
                    )
                    end = complete[-1].source_at + timedelta(minutes=5)
                    key = (d.symbol, d.strategy, horizon)
                    nonoverlap = key not in last_end or start >= last_end[key]
                    if nonoverlap:
                        last_end[key] = end
                    move = d.features.get("log_return")
                    prediction = (
                        "UP" if move and move > 0 else "DOWN" if move and move < 0 else "WAIT"
                    )
                    payload = {
                        "decision_id": d.id,
                        "symbol": d.symbol,
                        "strategy": d.strategy,
                        "horizon_M5": horizon,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "available_at": max(b.available_at for b in complete).isoformat(),
                        "label": label,
                        "correct": label == ("UP" if d.signal == "BUY" else "DOWN"),
                        "previous_movement": prediction,
                        "nonoverlapping": nonoverlap,
                        "evidence_ids": [digest(b.model_dump(mode="json")) for b in complete],
                        "not_trade_profitability": True,
                    }
                    with db:
                        _append(
                            ledger,
                            db,
                            "outcomes",
                            digest([d.id, horizon]),
                            payload,
                            max(b.available_at for b in complete),
                            decision_id=d.id,
                        )
                    labels.append(payload)
            if db.execute("SELECT count(*) FROM outcomes").fetchone()[0] != len(labels):
                raise ResearchRefused("research_unmatched_labels")
            load(root, dataset_id, clock())
            for table in ("model_calls", "hypotheses", "interventions"):
                if db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]:
                    raise ResearchRefused("research_unexpected_ledger_table")
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            value = {
                **plan,
                "run_id": identifier,
                "schema_version": 1,
                "observations_analyzed": len(observations),
                "evidence_status": "INSUFFICIENT EVIDENCE"
                if not observations
                else "SOFTWARE TEST ONLY"
                if policy.source_class == "owned_synthetic"
                else "SEE_INSTRUMENT_STRATEGY_HORIZON_SAMPLE_COUNTS",
                "quality": source["counts"],
                "label": "SOFTWARE TEST ONLY"
                if policy.source_class == "owned_synthetic"
                else "AUTHORIZED HISTORICAL DIRECTIONAL RESEARCH",
                "genuine_historical_evaluation": "BLOCKED — DATASET NOT AUTHORIZED"
                if policy.source_class == "owned_synthetic"
                else "AUTHORIZED_FOR_SCOPED_LOCAL_RESEARCH_ONLY",
                "decision_sha256": digest([d.model_dump(mode="json") for d in decisions]),
                "labels_sha256": digest(labels),
                "results": _summary(decisions, labels, observations, policy.source_class, protocol),
                "source_availability": "historical market-availability clock; actual acquisition retained separately; not forward observations",
                "execution_PnL": "UNAVAILABLE — no executable fills/contracts/costs inferred",
                "external_orders": 0,
                "report_time": policy.acquired_at.isoformat(),
                "retention": policy.retention.model_dump(mode="json"),
            }
            if fault:
                fault("before_report_commit")
            immutable_json(folder / "result.json", value)
            immutable_json(
                folder / "result.manifest.json",
                {"run_id": identifier, "sha256": sha256_file(folder / "result.json")},
            )
        finally:
            db.close()
        artifact(
            root,
            policy,
            db_path,
            ["features", "decisions", "labels"],
            [p["path"] for p in source["files"]],
            clock(),
        )
        artifact(
            root,
            policy,
            folder / "result.json",
            ["reports", "dashboard"],
            [db_path.relative_to(root).as_posix()],
            clock(),
        )
        report = markdown(value)
        target = folder / "report.md"
        if target.exists() and target.read_text(encoding="utf-8") != report:
            raise ResearchRefused("research_report_replay_changed")
        if not target.exists():
            atomic_write_bytes(target, report.encode())
        artifact(
            root,
            policy,
            target,
            ["reports"],
            ["data/gold/research/" + identifier + "/result.json"],
            clock(),
        )
        atomic_write_bytes(
            safe(root, "work/research/current.json"),
            (json.dumps({"dataset_id": dataset_id, "run_id": identifier}) + "\n").encode(),
        )
        return value


CHUNK_SIZE = 1000


def read_result(root: Path, run_id: str, *, now: datetime) -> dict[str, Any]:
    plan = read_metadata(root, f"data/gold/research/{run_id}/plan.json", base="data/gold/research")
    policy = load(root, plan["dataset_id"], now)
    if (
        digest(plan) != run_id
        or plan["policy_digest"] != policy.digest
        or plan["code_digest"] != code_digest()
    ):
        raise ResearchRefused("research_run_identity_or_code_changed")
    value = read_metadata(
        root, f"data/gold/research/{run_id}/result.json", base="data/gold/research"
    )
    manifest = read_metadata(
        root, f"data/gold/research/{run_id}/result.manifest.json", base="data/gold/research"
    )
    if manifest != {
        "run_id": run_id,
        "sha256": sha256_file(safe(root, f"data/gold/research/{run_id}/result.json")),
    }:
        raise ResearchRefused("research_result_checksum_changed")
    if value["run_id"] != run_id or any(value.get(k) != v for k, v in plan.items()):
        raise ResearchRefused("research_result_identity_changed")
    return value


def replay(root: Path, run_id: str, *, clock: Callable[[], datetime]) -> dict[str, Any]:
    old = read_result(root, run_id, now=clock())
    actual = run(
        root, old["dataset_id"], ResearchProtocol.model_validate(old["protocol"]), clock=clock
    )
    if actual != old:
        raise ResearchRefused("research_replay_mismatch")
    return {
        "run_id": run_id,
        "identical": True,
        "decision_sha256": old["decision_sha256"],
        "labels_sha256": old["labels_sha256"],
    }


def markdown(value: dict[str, Any]) -> str:
    rows = [
        "# Frozen local market research",
        "",
        value["label"],
        "",
        "Genuine evaluation: " + value["genuine_historical_evaluation"],
        "",
        "Dataset: `" + value["dataset_id"] + "`; run: `" + value["run_id"] + "`.",
        "Price semantics: `"
        + value["price_type"]
        + "`. Acquisition: "
        + value["retention"]["acquired_at"]
        + "; deadline: "
        + value["retention"]["expires_at"],
        "",
        "52 contiguous M5 bars warm up existing EMA12/26, ATR14 and channel20. Parameters are frozen.",
        "Outcomes start at the first full M5 bar after decision availability. Missing intervals are not filled.",
        "Primary comparisons use the same non-overlapping windows where the previous-movement baseline can predict.",
        "Non-overlap does not prove independence; any Wilson interval is descriptive and conditional, not evidence of alpha.",
        "",
        "| Instrument | Strategy | Horizon | BUY/SELL/WAIT | Labels | Missing/pending | Non-overlap | Matched n | Correct / always-UP / previous | Status |",
        "|---|---|---:|---|---:|---|---:|---:|---|---|",
    ]
    for g in value["results"]:
        rows.append(
            f"| {g['symbol']} | {g['strategy']} | {g['horizon_M5']} | {g['BUY']}/{g['SELL']}/{g['WAIT']} | {g['labels']} | {g['missing']}/{g['pending']} | {g['nonoverlapping']} | {g['matched_n']} | {g['matched_correct']}/{g['matched_always_UP_correct']}/{g['matched_previous_movement_correct']} | {g['sample_size_status']} |"
        )
    rows += [
        "",
        "No Sharpe ratio, execution win rate, account return or monetary profitability is calculated.",
        "The reference or bid series is a directional research input, not executable-side fill evidence.",
        "Full counts, rejections, reasons, uncertainty and hashes are in the permission-gated JSON result and append-only ledger.",
        "",
    ]
    return "\n".join(rows)
