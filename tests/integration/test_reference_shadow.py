"""Six-decision atomic research, frozen evaluation, crash recovery and read-only safety."""

import json
from datetime import datetime, timedelta

import pytest

from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.mt5.storage import record_id
from tb.risk.config import load_asset_registry
from tb.shadow.evaluation import evaluate_event
from tb.shadow.fixtures import FIXTURE_START, fixture_pin, fixture_rights, scenario_events
from tb.shadow.journal import ShadowJournal
from tb.shadow.models import ShadowConfig
from tb.shadow.reporting import snapshot
from tb.shadow.runtime import ShadowRuntime
from tb.strategies.reference import ReferenceStrategyConfig


def configuration():
    return ShadowConfig(
        version="2.0.0",
        strategy_version="price-only-strategies-1.0.0",
        feature_version="shared-price-only-2.0.0",
        reference_strategies=ReferenceStrategyConfig(),
    )


@pytest.fixture
def reference_context(tmp_path):
    config = configuration()
    pin = fixture_pin(config, "test")
    rights = fixture_rights()
    journal = ShadowJournal(tmp_path / "research path", pin, config, create=True)
    runtime = ShadowRuntime(journal, rights, load_asset_registry(), started_at=FIXTURE_START)
    yield journal, runtime, list(scenario_events(pin, "false_breakout", 96))
    journal.close()


def process(runtime, event, **kwargs):
    return runtime.process(
        event, event.observation.received_at + timedelta(milliseconds=1), **kwargs
    )


def frozen(db):
    return list(db.execute("SELECT id,payload_json FROM decisions ORDER BY id"))


def test_six_atomic_decisions_and_frozen_available_outcomes(reference_context):
    j, r, events = reference_context
    pending_checked = False
    for event in events:
        process(r, event)
        if (
            not pending_checked
            and j.db.execute(
                "SELECT 1 FROM decisions WHERE json_extract(payload_json,'$.signal')!='WAIT' LIMIT 1"
            ).fetchone()
        ):
            early = snapshot(j, fixture_rights())
            assert sum(v["not_yet_available"] for v in early.evaluation) > 0
            pending_checked = True
    assert pending_checked
    assert j.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == len(events) * 6
    labels = [json.loads(v[0]) for v in j.db.execute("SELECT payload FROM shadow_labels")]
    assert labels and {v["horizon_m5"] for v in labels} == {1, 3, 6}
    assert all(v["signal"] != "WAIT" for v in labels)
    assert any(not v["correct"] for v in labels)
    assert all(v["not_trade_profitability"] for v in labels)
    before = frozen(j.db)
    label_count = len(labels)
    for event in events:
        assert process(r, event) == "duplicate"
    assert frozen(j.db) == before
    assert j.db.execute("SELECT COUNT(*) FROM shadow_labels").fetchone()[0] == label_count
    view = snapshot(j, fixture_rights())
    assert view.evaluation and view.recent_labels and len(view.strategy_states) == 12
    assert all(
        v["available"] + v["missing_outcomes"] + v["not_yet_available"]
        == v["directional_decisions"]
        for v in view.evaluation
    )
    assert not view.fills_created and not view.positions_created
    assert all(v["always_WAIT_scored"] == 0 for v in view.evaluation)


def test_new_strategy_restart_reconstructs_state_without_repeating_transition(reference_context):
    j, r, events = reference_context
    for e in events[:130]:
        process(r, e)
    before = frozen(j.db)
    folder, pin, config = j.folder, j.pin, j.config
    j.close()
    reopened = ShadowJournal(folder, pin, config)
    rr = ShadowRuntime(reopened, fixture_rights(), load_asset_registry(), started_at=FIXTURE_START)
    try:
        for e in events[130:]:
            process(rr, e)
        assert dict(frozen(reopened.db)).items() >= dict(before).items()
        first = frozen(reopened.db)
        for e in events:
            process(rr, e)
        assert frozen(reopened.db) == first
        reopened.verify()
    finally:
        reopened.close()


def test_new_partial_transaction_is_not_a_completed_signal(reference_context):
    j, r, events = reference_context

    def crash():
        raise RuntimeError("owned crash")

    with pytest.raises(RuntimeError):
        process(r, events[0], before_commit=crash)
    assert j.db.execute("SELECT COUNT(*) FROM shadow_events").fetchone()[0] == 0
    assert j.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    with pytest.raises(FeedUnavailable):
        process(r, events[0])


def test_new_revision_and_future_label_cannot_modify_decisions(reference_context):
    j, r, events = reference_context
    e = events[0]
    process(r, e)
    before = frozen(j.db)
    changed = e.observation.model_copy(update={"close": e.observation.high})
    revision = e.model_copy(
        update={"observation": changed, "evidence_id": record_id(changed, e.pin.identity)}
    )
    assert process(r, revision) == "revision_frozen_interval"
    with pytest.raises(FeedUnavailable, match="future"):
        evaluate_event(j, fixture_rights(), e, e.observation.received_at - timedelta(seconds=1))
    assert frozen(j.db) == before


def test_horizon_gap_is_missing_not_a_losing_label(reference_context):
    j, r, _ = reference_context
    events = list(scenario_events(j.pin, "gaps", 128))
    for e in events:
        process(r, e)
    value = snapshot(j, fixture_rights())
    assert value.counts["data_gaps"] == 2
    assert any(v["missing_outcomes"] > 0 for v in value.evaluation)
    assert all(
        v["available"] + v["missing_outcomes"] + v["not_yet_available"]
        == v["directional_decisions"]
        for v in value.evaluation
    )


def test_overlapping_reference_windows_are_not_independent(tmp_path):
    # Disable the spike filter only in this declared overlap test, not in production config.
    config = configuration().model_copy(
        update={"reference_strategies": ReferenceStrategyConfig(maximum_range_atr=100)}
    )
    pin = fixture_pin(config, "overlap-test")
    journal = ShadowJournal(tmp_path / "overlap", pin, config, create=True)
    runtime = ShadowRuntime(
        journal, fixture_rights(), load_asset_registry(), started_at=FIXTURE_START
    )
    try:
        for e in scenario_events(pin, "false_breakout", 96):
            process(runtime, e)
        value = snapshot(journal, fixture_rights())
        assert any(
            v["overlapping"] > 0 and v["nonoverlapping"] < v["available"] for v in value.evaluation
        )
    finally:
        journal.close()


@pytest.mark.parametrize("lag", [-1, 31, 900])
def test_new_strategy_receipt_window_is_not_bypassed(reference_context, lag):
    journal, runtime, events = reference_context
    event = events[0]
    with pytest.raises(FeedUnavailable, match="receipt_stale_or_catchup"):
        runtime.process(event, event.observation.received_at + timedelta(seconds=lag))
    assert journal.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


def test_new_incomplete_candle_and_unauthorized_execution_remain_refused(reference_context):
    journal, runtime, events = reference_context
    event = events[0]
    row = event.observation.model_copy(
        update={"interval_complete": False, "received_at": event.closes_at - timedelta(seconds=1)}
    )
    incomplete = event.model_copy(
        update={"observation": row, "evidence_id": record_id(row, event.pin.identity)}
    )
    with pytest.raises(FeedUnavailable, match="unfinished"):
        process(runtime, incomplete)
    process(runtime, event)
    decisions = [json.loads(v[0]) for v in journal.db.execute("SELECT payload_json FROM decisions")]
    assert all(
        d["execution_eligible"] is False
        and datetime.fromisoformat(d["decision_at"]) >= datetime.fromisoformat(d["received_at"])
        for d in decisions
    )
    assert all("unavailable" in d["risk_sizing"] and "disabled" in d["advisory"] for d in decisions)
    tables = {v[0] for v in journal.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not tables.intersection({"orders", "fills", "positions", "balances"})


def test_legacy_scoring_cannot_override_new_frozen_protocol(reference_context):
    from tb.shadow.evaluation import append_directional_label
    from tb.shadow.models import ShadowSnapshot

    journal, runtime, events = reference_context
    process(runtime, events[0])
    with pytest.raises(FeedUnavailable, match="legacy_label_protocol"):
        append_directional_label(
            journal, fixture_rights(), "unknown", events[0], events[0].observation.received_at
        )
    value = snapshot(journal, fixture_rights()).model_dump(mode="json")
    value["strategy_states"][0]["raw_price"] = 1234
    with pytest.raises(ValueError, match="price/account"):
        ShadowSnapshot.model_validate(value)


def test_reference_names_do_not_authorize_an_execution_strategy():
    from tb.strategies.base import require_strategy_allowed
    from tb.strategies.reference import REFERENCE_STRATEGIES

    for symbol in ("EURUSD", "XAUUSD"):
        for name in REFERENCE_STRATEGIES:
            with pytest.raises(ValueError):
                require_strategy_allowed(symbol, name)
