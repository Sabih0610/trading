"""Owned fictional Silver inputs only; admission/causality/checkpoint contracts."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import polars as pl
import pytest

import tb.research.gold_development_data as module
from tb.ingest.history.core import sha256_file
from tb.ingest.history.histdata_clock import CLOCK_MODEL
from tb.research.gold_development_data import DATASET_ID, GoldSource, PrivateStore
from tb.research.gold_proxy import GoldResearchDecisions, SessionQuality
from tb.research.models import ResearchRefused
from tb.silver.market import clean_minute_bars
from tb.strategies.gold_stage3 import gold_trials

NOW = datetime(2026, 11, 4, tzinfo=UTC)
START = datetime(2021, 1, 4, tzinfo=UTC)


def trial(strategy="session_orb", minutes=5):
    return next(
        t
        for t in gold_trials()
        if t.strategy == strategy and t.timeframe == timedelta(minutes=minutes)
    )


def silver(start=START, count=720, *, removed=()):
    return clean_minute_bars(
        pl.DataFrame(
            [
                dict(
                    timestamp_ns=int((start + timedelta(minutes=i)).timestamp()) * 10**9,
                    symbol="XAUUSD",
                    source="histdata",
                    price_side="bid",
                    volume=0.0,
                    open=100.0 + (i % 31) * 0.01,
                    high=101.0 + (i % 31) * 0.01,
                    low=99.0 + (i % 31) * 0.01,
                    close=100.1 + (i % 31) * 0.01,
                )
                for i in range(count)
                if i not in removed
            ]
        ),
        market_kind="weekday",
    ).frame


@pytest.fixture
def source(tmp_path, monkeypatch):
    retention = {"delete_at": "2028-11-01T00:00:00Z"}
    plan = SimpleNamespace(
        dataset_id=DATASET_ID,
        provider="histdata",
        price_side="bid",
        instruments=("XAUUSD", "EURUSD"),
        digest="a" * 64,
        retention=SimpleNamespace(model_dump=lambda **kwargs: retention),
    )
    monkeypatch.setattr(module, "load_forex_plan", lambda *a: plan)
    monkeypatch.setattr(module, "authorize", lambda *a, **k: None)
    monkeypatch.setattr(module, "declare_artifact", lambda *a, **k: None)
    active = GoldSource(tmp_path, lambda: NOW)

    def write(year, frame=None, *, modify=None):
        generation = "b" * 64
        outputs = {}
        if frame is not None:
            relative = f"data/silver/histdata/{DATASET_ID}/XAUUSD/1m/{generation}/{year}.parquet"
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.write_parquet(path)
            outputs = {
                "silver/1m": dict(path=relative, sha256=sha256_file(path), rows=frame.height)
            }
        quality = dict(
            symbol="XAUUSD",
            year=year,
            source="histdata",
            price_side="bid",
            clock_model=CLOCK_MODEL,
            generation=generation,
            quarantined_days=[],
            week_open_checks=[],
        )
        value = dict(
            dataset_id=DATASET_ID,
            symbol="XAUUSD",
            year=year,
            source="histdata",
            price_side="bid",
            generation=generation,
            policy_digest=plan.digest,
            retention=retention,
            outputs=outputs,
            status="complete" if outputs else "missing",
            quality=quality,
        )
        if modify:
            modify(value)
        path = tmp_path / f"data/manifests/histdata/{DATASET_ID}/XAUUSD-{year}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return value

    for year in (2021, 2022, 2023):
        write(year)
    return active, write


@pytest.mark.parametrize("year", (2020, 2024, 2025))
def test_partition_scope_refuses_before_metadata(source, monkeypatch, year):
    active, _ = source
    monkeypatch.setattr(module, "load_forex_plan", lambda *a: pytest.fail("registry touched"))
    with pytest.raises(ResearchRefused, match="before_access"):
        active.scan(year)


@pytest.mark.parametrize(
    "stop",
    (
        datetime(2020, 12, 31, tzinfo=UTC),
        datetime(2024, 1, 1, 0, 1, tzinfo=UTC),
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2023, 1, 1),
    ),
)
def test_request_scope_refuses_before_metadata(source, monkeypatch, stop):
    active, _ = source
    monkeypatch.setattr(module, "load_forex_plan", lambda *a: pytest.fail("registry touched"))
    with pytest.raises(ResearchRefused, match="request_scope"):
        active.load(trial(), stop)


def test_unknown_cell_refuses_before_metadata(source, monkeypatch):
    active, _ = source
    from dataclasses import replace

    forged = replace(trial(), timeframe=timedelta(minutes=1))
    monkeypatch.setattr(module, "load_forex_plan", lambda *a: pytest.fail("registry touched"))
    with pytest.raises(ResearchRefused, match="request_scope"):
        active.load(forged, START + timedelta(days=1))


@pytest.mark.parametrize(
    "change,reason",
    [
        (lambda m: m.update(source="other"), "manifest_identity"),
        (lambda m: m.update(price_side="mid"), "manifest_identity"),
        (lambda m: m.update(policy_digest="c" * 64), "manifest_identity"),
        (lambda m: m["quality"].update(clock_model="obsolete"), "quality_identity"),
        (lambda m: m["quality"].pop("quarantined_days"), "quality_identity"),
        (lambda m: m["outputs"]["silver/1m"].update(path="data/silver/2024.parquet"), "namespace"),
        (lambda m: m["outputs"]["silver/1m"].update(sha256="c" * 64), "checksum"),
        (lambda m: m["outputs"]["silver/1m"].update(rows=9999), "row_bound"),
    ],
)
def test_identity_checksum_and_quality_refusal(source, change, reason):
    active, write = source
    write(2021, silver(count=60), modify=change)
    with pytest.raises(ResearchRefused, match=reason):
        active.scan(2021)


def test_partition_timestamp_cannot_hide_2024(source):
    active, write = source
    write(2023, silver(datetime(2024, 1, 1, tzinfo=UTC), 60))
    with pytest.raises(ResearchRefused, match="clock_refused"):
        active.scan(2023)


def test_fresh_features_complete_native_bars_and_no_volume(source):
    active, write = source
    write(2021, silver(count=720, removed=(2,)))
    result = active.load(trial(), START + timedelta(days=1))
    assert result.timestamps[0] == START + timedelta(minutes=5)
    assert result.coverage(START, START + timedelta(minutes=20)) == (20, 19)
    assert result.has_scored_bars(START, START + timedelta(hours=1))
    assert not result.has_scored_bars(START + timedelta(days=2), START + timedelta(days=3))
    features = active._features[START + timedelta(days=1)][0]["5m"]
    assert features[0].ema20 == features[0].close
    assert all(b.volume == 0 and b.session_vwap is None for b in features)
    assert len(result.timestamps) == 143


def test_no_2020_warmup_or_existing_gold_read(source, monkeypatch):
    active, write = source
    write(2021, silver(count=120))
    original = module.read_metadata
    touched = []

    def checked(root, relative, **kwargs):
        touched.append(relative)
        assert "2020" not in relative.rsplit("/", 1)[-1]
        assert "2024" not in relative.rsplit("/", 1)[-1]
        assert "/gold/" not in relative
        return original(root, relative, **kwargs)

    monkeypatch.setattr(module, "read_metadata", checked)
    active.load(trial(), START + timedelta(days=1))
    assert touched


def test_completed_parent_context_and_prefix_invariance(source):
    active, write = source
    write(2021, silver(count=720))
    short_stop = START + timedelta(hours=6)
    long_stop = START + timedelta(hours=12)
    selected = trial("trend_vwap_pullback", 15)
    active.load(selected, short_stop)
    prefix = active._features[short_stop][0]["15m"]
    active.load(selected, long_stop)
    full = active._features[long_stop][0]["15m"]
    assert full[: len(prefix)] == prefix
    assert prefix[0].htf_structure_direction is None
    assert prefix[4].htf_structure_direction == 0


def test_feature_state_survives_year_boundary(source):
    active, write = source
    left = datetime(2021, 12, 31, 23, tzinfo=UTC)
    write(2021, silver(left, 60))
    write(2022, silver(left + timedelta(hours=1), 60).with_columns(pl.col("close") + 0.05))
    stop = left + timedelta(hours=2)
    active.load(trial(), stop)
    bars = active._features[stop][0]["5m"]
    assert len(bars) == 24
    assert bars[12].ema20 != bars[12].close
    assert bars[12].ema50_slope is not None


def test_provider_volume_or_wrong_side_is_not_relabelled(source):
    active, write = source
    write(2021, silver(count=60).with_columns(pl.lit(12.0).alias("volume")))
    with pytest.raises(ResearchRefused, match="minute_identity"):
        active.load(trial(), START + timedelta(days=1))
    write(2021, silver(count=60).with_columns(pl.lit("ask").alias("price_side")))
    with pytest.raises(ResearchRefused, match="minute_identity"):
        active.load(trial(), START + timedelta(days=1))


def test_quality_five_percent_and_overlapping_reasons(source):
    active, write = source
    write(
        2021,
        silver(count=720),
        modify=lambda m: m["quality"].update(quarantined_days=[{"source_date": "2021-01-04"}]),
    )
    data = active.load(trial(), START + timedelta(days=1))
    assert any(q.quarantined_day for q in data.qualities)
    five = SessionQuality(known_at=START, expected_minutes=20, present_minutes=19)
    assert five.reasons(START) == ()
    assert SessionQuality(known_at=START, expected_minutes=20, present_minutes=18).reasons(START)
    stamp = START + timedelta(hours=9)
    counts = data.quality_counts(
        START,
        START + timedelta(days=1),
        GoldResearchDecisions("proxy", (), (), ((stamp, ("quarantined_day", "late_week_open")),)),
    )
    assert counts["candidate_calendar_sessions"] == 2
    assert counts["unique_proposal_sessions_vetoed"] == 1
    assert counts["proposal_sessions_vetoed_by_reason"] == {
        "late_week_open": 1,
        "quarantined_day": 1,
    }


def test_empty_years_are_flat_quality_diagnostics(source):
    active, _ = source
    data = active.load(trial(), START + timedelta(days=1))
    assert not data.has_scored_bars(START, START + timedelta(days=1))
    counts = data.quality_counts(
        START, START + timedelta(days=1), GoldResearchDecisions("proxy", (), (), ())
    )
    assert counts["sessions_with_no_eligible_bars"] == 2


def test_checkpoint_immutable_status_mutable_checksum_and_revocation(source, monkeypatch):
    active, _ = source
    store = PrivateStore(active, "owned-fixture")
    store.write("choice.json", {"identity": "x", "selection": None})
    assert store.read("choice.json") == {"identity": "x", "selection": None}
    with pytest.raises(ResearchRefused, match="checkpoint_changed"):
        store.write("choice.json", {"identity": "y"})
    store.status({"stage": "a"})
    store.status({"stage": "b"})
    assert store.read("status.json") == {"stage": "b"}
    path = active.root / store.base / "choice.json"
    value = json.loads(path.read_text())
    value["result"]["identity"] = "changed"
    path.write_text(json.dumps(value))
    with pytest.raises(ResearchRefused, match="checkpoint_identity"):
        store.read("choice.json")
    monkeypatch.setattr(
        module, "load_forex_plan", lambda *a: (_ for _ in ()).throw(ResearchRefused("revoked"))
    )
    with pytest.raises(ResearchRefused, match="revoked"):
        store.read("status.json")


@pytest.mark.parametrize("name", ("../escape", "UPPER", ""))
def test_invalid_private_run_id(source, name):
    active, _ = source
    with pytest.raises(ResearchRefused, match="run_id"):
        PrivateStore(active, name)


def test_quality_diagnostics_require_vwap_and_full_opening_range(source):
    active, write = source
    write(2021, silver(count=720, removed=(481,)))
    stop = START + timedelta(days=1)
    empty_decisions = GoldResearchDecisions("proxy", (), (), ())
    c = active.load(trial("trend_vwap_pullback", 15), stop)
    assert c.quality_counts(START, stop, empty_decisions)["sessions_with_complete_inputs"] == 0
    g = active.load(trial(), stop)
    counts = g.quality_counts(START, stop, empty_decisions)
    assert counts["sessions_with_complete_inputs"] == 0
    assert counts["sessions_with_no_eligible_bars"] == 1  # New York window not observed


def test_zero_width_gap_is_absent_not_an_invalid_price_gap(source):
    active, write = source
    frame = silver(count=120).with_columns(
        pl.lit(100.0).alias(k) for k in ("open", "high", "low", "close")
    )
    write(2021, frame)
    stop = START + timedelta(days=1)
    active.load(trial(), stop)
    bars = active._features[stop][0]["5m"]
    assert all(
        b.atr14 is None and b.fvg_direction is None and b.fvg_lower is None and b.fvg_upper is None
        for b in bars
    )


def test_invalid_minute_prices_cannot_count_as_presence(source):
    active, write = source
    frame = silver(count=60).with_columns(
        pl.when(pl.arange(0, pl.len()) == 2).then(-1.0).otherwise(pl.col("low")).alias("low")
    )
    write(2021, frame)
    with pytest.raises(ResearchRefused, match="invalid_silver_prices"):
        active.load(trial(), START + timedelta(days=1))


def test_cache_preserves_selected_session_window_and_missing_partition_flags(source):
    active, write = source
    write(2021, silver(count=720))
    write(
        2022, modify=lambda m: m["quality"].update(quarantined_days=[{"source_date": "2022-01-03"}])
    )
    stop = datetime(2023, 1, 1, tzinfo=UTC)
    first = active.load(trial(), stop)
    later = next(
        t
        for t in gold_trials()
        if t.strategy == "session_orb"
        and t.timeframe == timedelta(minutes=5)
        and t.config.entry_window_minutes == 180
    )
    cached = active.load(later, stop)
    assert cached.trial == later
    assert cached.batch is first.batch
    assert datetime(2022, 1, 3, tzinfo=UTC).date() in active._features[stop][2]


def test_actual_source_and_registered_batch_compose_without_inventing_evidence(source, monkeypatch):
    """Real reader/replay/store compose on two fictional days and absent OOS years."""
    from pathlib import Path

    import tb.backtest.gold_development as development
    from tb.backtest.gold_development import GoldBatch

    active, write = source
    write(2021, silver(count=2 * 24 * 60))
    # The uncertainty diagnostic is informational and expensive; core source,
    # selection, replay, quality, rights/checksum paths and checkpoint I/O stay real.
    monkeypatch.setattr(development, "weekly_bootstrap", lambda *args: None)
    repo = Path(__file__).resolve().parents[2]
    batch = GoldBatch(repo, active)
    later = next(
        t
        for t in gold_trials()
        if t.strategy == "session_orb"
        and t.timeframe == timedelta(minutes=5)
        and t.config.entry_window_minutes == 180
    )
    stop = START + timedelta(days=2)
    initial = batch.prepared(trial(), stop)
    configured = batch.prepared(later, stop)
    assert configured.trial == later
    assert configured.batch is initial.batch

    result = batch.run()
    assert result["identity"]["n_trials"] == 54
    assert result["identity"]["data_manifest_sha256"] == active.identity()
    assert len(result["verdicts"]) == 3
    for row in result["verdicts"]:
        assert row["verdict"] == "insufficient evidence"
        assert row["missing_training_folds"] == [2022, 2023]
        assert row["final_training_ineligible"]
        for path in row["metrics"].values():
            assert path["aggregate"]["trade_count"] == 0
            for fold in path["folds"]:
                assert fold["metrics"]["trade_count"] == 0
                assert fold["circuit_trips"] == fold["halted_days"] == 0
        for quality in row["quality_gate"]:
            for timeframe in quality["timeframes"]:
                counts = timeframe["counts"]
                assert counts["sessions_with_complete_inputs"] == 0
                assert (
                    counts["sessions_with_no_eligible_bars"]
                    == counts["candidate_calendar_sessions"]
                )

    frozen = result["frozen_parameters"]
    assert frozen["n_trials"] == 54
    assert all(
        item["config"] is None and item["timeframe_seconds"] is None
        for item in frozen["strategies"].values()
    )
    assert not any(
        f'"{key}"' in json.dumps(frozen)
        for key in ("open", "high", "low", "close", "volume", "price", "prices", "trades")
    )
    for label in ("2022", "2023", "final-2021-2023"):
        selection = batch.store.read(f"training/{label}/selection.json")
        assert len(selection["cells"]) == 54
        assert all(value is None for value in selection["selected"].values())
        assert all(cell["trade_count"] == 0 for cell in selection["cells"])
    assert batch.store.read("status.json")["stage"] == "complete"
    monkeypatch.setattr(
        active, "load", lambda *args: pytest.fail("Finished checkpoint reran replay")
    )
    assert batch.run() == result
