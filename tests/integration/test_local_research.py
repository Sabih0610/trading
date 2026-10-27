"""Owned offline research, independent causal oracles and adversarial admission/recovery."""

import ast
import csv
import io
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from streamlit.testing.v1 import AppTest

from tb.core.config import repo_root
from tb.features.engine import FeatureEngine
from tb.ingest.history.core import sha256_file
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.research import importer, registry, runner
from tb.research.cli import status
from tb.research.fixtures import generate, rows
from tb.research.models import DatasetPolicy, ResearchProtocol, ResearchRefused
from tb.strategies.reference import REFERENCE_STRATEGIES, ReferenceStrategyConfig

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


@pytest.fixture
def owned(tmp_path):
    generate(tmp_path, "owned", NOW, bars=160)
    return tmp_path, registry.load(tmp_path, "owned", NOW)


def proposal(root, policy):
    path = root / f"work/research/proposals/{policy.dataset_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(policy.model_dump_json(), encoding="utf-8")
    return path.relative_to(root).as_posix()


def licensed(root, source_policy, data, **changes):
    """Fictional provider permission ONLY for tests; source remains owned arithmetic data."""
    evidence = root / "work/rights/fictional.txt"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("FICTIONAL OWNED TEST DATA APPROVAL; NOT REAL PROVIDER RIGHTS")
    grant = Permission(
        status="confirmed",
        approved=True,
        approved_by="test-reviewer",
        evidence="Fictional approval of owned test rows only",
        evidence_kind="provider_terms",
        evidence_artifact="work/rights/fictional.txt",
        evidence_sha256=sha256_file(evidence),
        expires_at=NOW + timedelta(days=30),
        permitted_retention_seconds=30 * 86400,
    )
    rights = source_policy.rights.model_copy(
        update={
            "provider": "fictional-test-provider",
            "dataset_id": "licensed",
            "reviewer": "test-reviewer",
            "owner_approved_by": "test-owner",
            "personal_research": grant,
            "research_reports": grant,
            "permissions": {k: grant for k in source_policy.rights.permissions},
        }
    )
    values = source_policy.model_dump()
    values.update(
        dataset_id="licensed",
        provider=rights.provider,
        source_class="licensed_historical",
        original_source="fictional test source",
        source_file="work/research/sources/licensed.csv",
        owned_generation=None,
        rights=rights,
        retention=lifetime(rights, NOW),
    )
    values.update(changes)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(data)
    content = stream.getvalue().encode()
    values["source_sha256"] = registry.digest_bytes(content)
    p = DatasetPolicy.model_validate(values)
    path = root / p.source_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    proposal(root, p)
    return p


def admitted(owned):
    root, p = owned
    importer.import_dataset(root, p.dataset_id, clock=lambda: NOW)
    result = runner.run(root, p.dataset_id, ResearchProtocol(), clock=lambda: NOW)
    return root, p, result


def ledger(root, result, table):
    path = root / f"data/gold/research/{result['run_id']}/journal.sqlite"
    with sqlite3.connect(path) as db:
        return [
            json.loads(r[0]) for r in db.execute(f"SELECT payload_json FROM {table} ORDER BY rowid")
        ]


def deny_price_reads(monkeypatch, root):
    original = Path.open

    def guarded(path, *args, **kwargs):
        relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else ""
        if relative.startswith(("data/", "work/research/sources/", "work/research/staging/")):
            # Price-free plans are deliberately allowed to establish current policy.
            if path.name not in {"plan.json", "schema.json", "result.manifest.json"}:
                raise AssertionError("price-bearing file was opened before authorization")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(pl, "read_parquet", lambda *a, **k: pytest.fail("expired parquet read"))
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: pytest.fail("expired ledger read"))


def test_metadata_check_never_reads_source_and_creates_no_approval(owned, monkeypatch):
    root, p = owned
    deny_price_reads(monkeypatch, root)
    assert registry.check(root, f"work/research/proposals/{p.dataset_id}.json", NOW) == p
    assert not (root / "data").exists()


@pytest.mark.parametrize(
    "change", ["owner", "reviewer", "revoked", "missing", "wrong_scope", "expired"]
)
def test_bad_rights_refused_before_source_open(owned, monkeypatch, change):
    root, p = owned
    value = p.model_dump(mode="json")
    if change == "owner":
        value["rights"]["owner_approved"] = False
    elif change == "reviewer":
        value["rights"]["reviewer"] = None
    elif change == "revoked":
        value["rights"]["permissions"]["raw_cache"]["status"] = "prohibited"
    elif change == "missing":
        del value["rights"]["permissions"]["historical_storage"]
    elif change == "wrong_scope":
        value["rights"]["instruments"] = ["EURUSD"]
    else:
        value["retention"]["expires_at"] = NOW.isoformat()
    (root / "work/research/proposals/owned.json").write_text(json.dumps(value))
    deny_price_reads(monkeypatch, root)
    with pytest.raises(ValueError):
        registry.check(root, "work/research/proposals/owned.json", NOW)


def test_fake_licensed_approval_requires_test_environment(owned, monkeypatch):
    root, p = owned
    p = licensed(root, p, rows(p))
    monkeypatch.delenv("TB_OFFLINE_VALIDATION", raising=False)
    with pytest.raises(ResearchRefused, match="test_only"):
        registry.register(root, proposal(root, p), NOW)


@pytest.mark.parametrize("change", ["same_reviewer", "no_document", "wrong_hash", "no_approval"])
def test_documentary_evidence_is_not_automatic_approval(owned, monkeypatch, change):
    root, p = owned
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    p = licensed(root, p, rows(p))
    values = p.model_dump()
    if change == "same_reviewer":
        values["rights"]["reviewer"] = "test-owner"
    elif change == "no_document":
        (root / "work/rights/fictional.txt").unlink()
    elif change == "wrong_hash":
        (root / "work/rights/fictional.txt").write_text("Changed evidence")
    else:
        values["rights"]["owner_approved"] = False
    # Recompute scope pin only to isolate the independent approval/document check.
    from tb.research.models import DatasetRights

    rights = DatasetRights.model_validate(values["rights"])
    values.update(rights=rights, retention=lifetime(rights, NOW))
    p = DatasetPolicy.model_validate(values)
    with pytest.raises(ValueError):
        registry.register(root, proposal(root, p), NOW)


def test_generated_provenance_cannot_be_laundered_or_manually_registered(owned):
    root, p = owned
    with pytest.raises(ResearchRefused, match="generator"):
        registry.register(root, proposal(root, p), NOW)
    value = p.model_dump()
    value["source_sha256"] = "f" * 64
    changed = DatasetPolicy.model_validate(value)
    with pytest.raises(ResearchRefused, match="generation_proof"):
        registry.check(root, proposal(root, changed), NOW)
    value["source_class"] = "licensed_historical"
    with pytest.raises(ValueError):
        DatasetPolicy.model_validate(value)


@pytest.mark.parametrize(
    "relative",
    ["../escape", "C:/private", "/absolute", "work/../secret", "work\\file", "work/file:ads"],
)
def test_path_traversal_refused(tmp_path, relative):
    with pytest.raises(ResearchRefused):
        registry.safe(tmp_path, relative)


def test_symlink_refused(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        # Windows without symbolic-link privilege still has native directory junctions.
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
        )
        assert result.returncode == 0
    with pytest.raises(ResearchRefused, match="symlink_or_junction"):
        registry.safe(tmp_path, "link/file.csv")


@pytest.mark.parametrize(
    "field,value",
    [
        ("units", {"EURUSD": "EUR_per_USD", "XAUUSD": "USD_per_troy_ounce"}),
        ("coverage_end", datetime(2025, 1, 1, tzinfo=UTC)),
        ("acquired_at", datetime(2024, 1, 1, tzinfo=UTC)),
        ("source_symbols", {"EUR/USD": "XAUUSD"}),
    ],
)
def test_scope_units_holdout_and_acquisition_refused(owned, field, value):
    _, p = owned
    data = p.model_dump()
    data[field] = value
    with pytest.raises(ValueError):
        DatasetPolicy.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("close", "NaN"),
        ("open", "Infinity"),
        ("low", "-1"),
        ("open", "0"),
        ("high", "0.1"),
        ("low", "10"),
        ("complete", "false"),
        ("complete", 1),
        ("timestamp", "2024-06-03T08:00:00"),
        ("available_at", "2024-06-03T08:00:00+00:00"),
        ("local_available_at", "2026-10-27T11:00:00+00:00"),
        ("symbol", "USD/EUR"),
        ("timestamp", "2025-01-01T00:00:00+00:00"),
    ],
)
def test_invalid_row_refused(owned, field, value):
    _, p = owned
    row = rows(p)[0]
    row[field] = value
    with pytest.raises((ValueError, KeyError, ArithmeticError)):
        importer.parse(row, p)


@pytest.mark.parametrize("stamp", ["2024-03-10T02:30:00", "2024-11-03T01:30:00"])
def test_dst_ambiguous_or_nonexistent_refused(owned, stamp):
    _, p = owned
    with pytest.raises(ResearchRefused, match="DST"):
        importer.at(stamp, p.model_copy(update={"source_timezone": "America/New_York"}))


def test_timestamp_conversion_is_explicit_and_keeps_timezone_provenance(owned):
    _, p = owned
    local = p.model_copy(update={"source_timezone": "America/New_York"})
    assert importer.at("2024-06-03T04:00:00", local) == p.coverage_start
    epoch = p.model_copy(update={"timestamp_format": "epoch_ms"})
    assert importer.at(str(int(p.coverage_start.timestamp() * 1000)), epoch) == p.coverage_start
    with pytest.raises(ResearchRefused, match="epoch_units"):
        importer.at(str(int(p.coverage_start.timestamp())), epoch)
    with pytest.raises(ResearchRefused, match="contradiction"):
        importer.at("2024-06-03T08:00:00-04:00", p)


def test_midpoint_cannot_gain_bid_ask_sides(owned):
    _, p = owned
    row = rows(p)[0]
    row["ask_close"] = "1.2"
    with pytest.raises(ResearchRefused, match="manufacture_sides"):
        importer.parse(row, p)


@pytest.mark.parametrize("fmt,timeframe", [("csv", "M5"), ("parquet", "M1"), ("parquet", "M5")])
def test_csv_parquet_original_bytes_and_bounded_silver(tmp_path, fmt, timeframe):
    generate(tmp_path, "owned", NOW, file_format=fmt, timeframe=timeframe, bars=80)
    p = registry.load(tmp_path, "owned", NOW)
    value = importer.import_dataset(tmp_path, "owned", clock=lambda: NOW)
    assert value["counts"]["valid"] == 160
    assert value["counts"]["M5_rows"] == (32 if timeframe == "M1" else 160)
    assert sha256_file(tmp_path / value["bronze"]) == p.source_sha256
    assert importer.import_dataset(tmp_path, "owned", clock=lambda: NOW) == value
    normalized = list(importer.bars(tmp_path, "owned", clock=lambda: NOW))
    assert len(normalized) == value["counts"]["M5_rows"]
    assert all(b.timeframe == "M5" and b.ask_close is None for b in normalized)


def test_bid_ask_retained_without_execution_claims(tmp_path):
    generate(tmp_path, "owned", NOW, price_type="bid_ask", bars=64)
    value = importer.import_dataset(tmp_path, "owned", clock=lambda: NOW)
    normalized = list(importer.bars(tmp_path, "owned", clock=lambda: NOW))
    assert value["price_type"] == "bid_ask"
    assert all(b.ask_close > b.close for b in normalized)


def test_source_checksum_truncation_refused(owned):
    root, p = owned
    (root / p.source_file).write_bytes(b"truncated")
    with pytest.raises(ResearchRefused, match="checksum"):
        importer.import_dataset(root, "owned", clock=lambda: NOW)


@pytest.mark.parametrize(
    "kind", ["missing_columns", "oversized_field", "truncated_record", "parquet_corrupt"]
)
def test_malformed_bounded_parsers(owned, kind):
    root, p = owned
    path = root / "bad.csv"
    if kind == "missing_columns":
        path.write_text("symbol,open\nEUR/USD,1\n")
    elif kind == "oversized_field":
        source = rows(p)[0]
        source["close"] = "1" * 2050
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=list(source))
        writer.writeheader()
        writer.writerow(source)
        path.write_text(text.getvalue())
    elif kind == "truncated_record":
        source = rows(p)[0]
        path.write_text(",".join(source) + "\nEUR/USD,2024\n")
    else:
        path.write_bytes(b"broken parquet")
        p = p.model_copy(update={"file_format": "parquet"})
    with pytest.raises((ValueError, pl.exceptions.PolarsError)):
        list(importer.source_rows(path, p))


def test_file_size_bound_before_hashing(owned, monkeypatch):
    root, _ = owned
    original = Path.stat

    def stat(path, *a, **k):
        result = original(path, *a, **k)
        if path.name == "owned.csv":
            from types import SimpleNamespace

            return SimpleNamespace(st_size=65 * 1024 * 1024, st_mode=result.st_mode)
        return result

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(importer, "sha256_file", lambda _: pytest.fail("oversized hash read"))
    with pytest.raises(ResearchRefused, match="size"):
        importer.import_dataset(root, "owned", clock=lambda: NOW)


def test_duplicates_revisions_order_gaps_and_rejections_are_explicit(owned, monkeypatch):
    root, base = owned
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    data = rows(base)
    revised = {**data[10], "close": data[10]["open"]}
    invalid = {**data[12], "close": "NaN"}
    # Remove one interval, reverse source order, add a duplicate, one revision and bad price.
    data = [r for i, r in enumerate(data) if i != 20]
    data.reverse()
    data += [data[0], revised, invalid]
    p = licensed(root, base, data)
    registry.register(root, proposal(root, p), NOW)
    value = importer.import_dataset(root, "licensed", clock=lambda: NOW)
    c = value["counts"]
    assert c["duplicates"] == c["revisions_rejected"] == 1
    assert c["rejected"] == 2 and c["out_of_order"] > 0 and c["missing_M5_intervals"] == 1
    assert c["observations"] == c["valid"] + c["duplicates"] + c["rejected"]
    normalized = list(importer.bars(root, "licensed", clock=lambda: NOW))
    assert normalized == sorted(normalized, key=lambda b: (b.symbol, b.source_at))


def test_m1_gap_prevents_completed_m5(owned):
    _, p = owned
    p = p.model_copy(update={"timeframe": "M1"})
    base = rows(p)[:10:2]
    group = [importer.parse(r, p) for r in base]
    assert importer.m5_group(group) is not None
    assert importer.m5_group(group[:2] + group[3:]) is None


def test_holdout_row_aborts_entire_import_and_leaves_inventory(owned, monkeypatch):
    root, p = owned
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    data = rows(p)
    data.append({**data[-1], "timestamp": "2025-01-01T00:00:00+00:00"})
    p = licensed(root, p, data)
    registry.register(root, proposal(root, p), NOW)
    with pytest.raises(ResearchRefused, match="holdout"):
        importer.import_dataset(root, "licensed", clock=lambda: NOW)
    inv = registry.inventory(root, NOW)
    assert any("cache" in item["kinds"] and item["exists"] for item in inv["objects"])
    assert (
        not list((root / "data/silver").rglob("manifest.json"))
        if (root / "data/silver").exists()
        else True
    )


@pytest.mark.parametrize("target", ["bronze", "silver", "manifest_scope"])
def test_import_integrity_and_provider_scope_refused(owned, target):
    root, _ = owned
    value = importer.import_dataset(root, "owned", clock=lambda: NOW)
    if target == "bronze":
        (root / value["bronze"]).write_bytes(b"changed")
    elif target == "silver":
        (root / value["files"][0]["path"]).write_bytes(b"changed")
    else:
        value["provider"] = "unrelated-provider"
        p = registry.load(root, "owned", NOW)
        with pytest.raises(ResearchRefused, match="identity"):
            importer.verify_import(root, p, value, NOW)
        return
    with pytest.raises(ResearchRefused, match="checksum"):
        list(importer.bars(root, "owned", clock=lambda: NOW))


def test_import_crash_recovery_keeps_atomic_manifest_and_original_deadline(owned):
    root, p = owned

    def fail(stage):
        if stage == "before_manifest":
            raise RuntimeError("owned simulated crash")

    with pytest.raises(RuntimeError):
        importer.import_dataset(root, "owned", clock=lambda: NOW, fault=fail)
    assert not list((root / "data/silver").rglob("manifest.json"))
    value = importer.import_dataset(root, "owned", clock=lambda: NOW + timedelta(days=1))
    assert value["retention"] == p.retention.model_dump(mode="json")
    assert all(
        o["retention"] == value["retention"] for o in registry.inventory(root, NOW)["objects"]
    )


def test_shared_features_signals_warmup_causal_labels_and_baseline_oracle(owned):
    root, _, result = admitted(owned)
    decisions = ledger(root, result, "decisions")
    labels = ledger(root, result, "outcomes")
    source = list(importer.bars(root, "owned", clock=lambda: NOW))
    engines, plugins, by_id = {}, {}, {}
    for b in source:
        engine = engines.setdefault(
            b.symbol,
            FeatureEngine(
                timeframe=timedelta(minutes=5), reference_periods=ReferenceStrategyConfig().periods
            ),
        )
        features = engine.update(
            {
                "timestamp_utc": b.source_at,
                **{k: float(getattr(b, k)) for k in ("open", "high", "low", "close")},
            },
            reference_only=True,
        )
        features["timestamp_utc"] = b.source_at.isoformat()
        for name, cls in REFERENCE_STRATEGIES.items():
            plugin = plugins.setdefault((b.symbol, name), cls(b.symbol, ReferenceStrategyConfig()))
            d = next(
                d
                for d in decisions
                if d["symbol"] == b.symbol
                and d["strategy"] == name
                and datetime.fromisoformat(d["source_open_at"]) == b.source_at
            )
            expected = plugin.evaluate(b.symbol, features)
            assert d["features"] == features
            assert d["signal"] == expected.signal and d["reasons"] == list(expected.reasons)
            by_id[d["id"]] = d
    assert all(d["signal"] == "WAIT" for d in decisions[:51])
    assert any(d["signal"] in {"BUY", "SELL"} for d in decisions)
    for label in labels:
        d = by_id[label["decision_id"]]
        start = datetime.fromisoformat(label["start"])
        assert start >= datetime.fromisoformat(d["decision_at"])
        bars = [
            b
            for b in source
            if b.symbol == d["symbol"]
            and start <= b.source_at < datetime.fromisoformat(label["end"])
        ]
        change = bars[-1].close - bars[0].open
        assert label["label"] == ("UP" if change > 0 else "DOWN" if change < 0 else "FLAT")
    for group in result["results"]:
        selected = [
            v
            for v in labels
            if v["symbol"] == group["symbol"]
            and v["strategy"] == group["strategy"]
            and v["horizon_M5"] == group["horizon_M5"]
        ]
        matched = [v for v in selected if v["nonoverlapping"] and v["previous_movement"] != "WAIT"]
        assert group["matched_n"] == len(matched)
        assert group["matched_always_UP_correct"] == sum(v["label"] == "UP" for v in matched)
        assert group["matched_previous_movement_correct"] == sum(
            v["label"] == v["previous_movement"] for v in matched
        )
        assert group["labels"] == group["correct"] + group["incorrect"] + group["FLAT"]
        assert (
            group["wilson95_descriptive"] is None and group["serial_dependence_resolved"] is False
        )
    # These smooth fixtures have sparse regime transitions: overlap/tail cases have separate oracles.
    assert all(g["nonoverlapping"] <= g["labels"] for g in result["results"])
    assert (
        result["label"] == "SOFTWARE TEST ONLY"
        and "BLOCKED" in result["genuine_historical_evaluation"]
    )


@pytest.mark.parametrize("stage", ["before_input_commit", "before_report_commit"])
def test_atomic_journal_crash_restart_replay_and_append_only(owned, stage):
    root, _ = owned
    importer.import_dataset(root, "owned", clock=lambda: NOW)
    calls = 0

    def fail(actual):
        nonlocal calls
        if actual == stage:
            calls += 1
            if calls == (15 if stage == "before_input_commit" else 1):
                raise RuntimeError("owned crash")

    with pytest.raises(RuntimeError):
        runner.run(root, "owned", ResearchProtocol(), clock=lambda: NOW, fault=fail)
    result = runner.run(root, "owned", ResearchProtocol(), clock=lambda: NOW)
    assert runner.replay(root, result["run_id"], clock=lambda: NOW)["identical"]
    assert len(ledger(root, result, "decisions")) == 640
    path = root / f"data/gold/research/{result['run_id']}/journal.sqlite"
    with sqlite3.connect(path) as db, pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("UPDATE research_inputs SET payload_sha='changed'")


def test_report_checksum_tampering_is_refused(owned):
    root, _, result = admitted(owned)
    path = root / f"data/gold/research/{result['run_id']}/result.json"
    changed = json.loads(path.read_text())
    changed["results"][0]["matched_correct"] = 999999
    path.write_text(json.dumps(changed))
    with pytest.raises(ResearchRefused, match="checksum"):
        runner.read_result(root, result["run_id"], now=NOW)


def test_schema_corruption_refused_without_repair(owned):
    root, _, result = admitted(owned)
    path = root / f"data/gold/research/{result['run_id']}/journal.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER research_inputs_no_UPDATE")
    before = sha256_file(path)
    with pytest.raises(ResearchRefused, match="schema_corruption"):
        runner.run(root, "owned", ResearchProtocol(), clock=lambda: NOW)
    assert sha256_file(path) == before


@pytest.mark.parametrize(
    "action", ["import", "run", "read", "replay", "inventory", "status", "display"]
)
@pytest.mark.parametrize("reason", ["expired", "revoked"])
def test_every_reuse_boundary_checks_current_rights_before_price_open(
    owned, monkeypatch, action, reason
):
    root, p, result = admitted(owned)
    now = p.retention.expires_at if reason == "expired" else NOW
    if reason == "revoked":
        data = p.model_dump(mode="json")
        data["rights"]["owner_approved"] = False
        (root / "work/research/proposals/owned.json").write_text(json.dumps(data))
    deny_price_reads(monkeypatch, root)
    if action == "inventory":
        inv = registry.inventory(root, now)
        assert inv["deletions"] == 0 and inv["objects"]
        assert len({o["path"] for o in inv["objects"]}) == len(inv["objects"])
        assert all(o["content_opened"] is False and not o["current_access"] for o in inv["objects"])
        return
    if action == "status":
        assert "BLOCKED" in status(root, now)["datasets"][0]["status"]
        return
    with pytest.raises(ValueError):
        if action == "import":
            importer.import_dataset(root, "owned", clock=lambda: now)
        elif action == "run":
            runner.run(root, "owned", ResearchProtocol(), clock=lambda: now)
        elif action == "read":
            runner.read_result(root, result["run_id"], now=now)
        elif action == "replay":
            runner.replay(root, result["run_id"], clock=lambda: now)
        else:
            registry.load(root, "owned", now, display=True)


def test_training_and_validation_are_separate_without_cross_split_warmup(owned):
    root, _ = owned
    importer.import_dataset(root, "owned", clock=lambda: NOW)
    result = runner.run(root, "owned", ResearchProtocol(split="research"), clock=lambda: NOW)
    assert result["observations_analyzed"] == 0
    assert not ledger(root, result, "decisions") and not result["results"]


def test_protocol_parameters_and_wilson_oracle():
    with pytest.raises(ValueError):
        ResearchProtocol(horizons=(1,))
    assert runner.wilson(10, 29) is None
    assert runner.wilson(50, 100) == pytest.approx([0.4038315, 0.5961685], abs=1e-7)


def test_dashboard_read_only_default_and_revocation(owned, monkeypatch):
    root, p, result = admitted(owned)

    # Use a future-safe frozen clock independent of the wall date.
    class Clock:
        @staticmethod
        def now(_zone):
            return NOW

    import tb.dashboard.research as view

    monkeypatch.setattr(view, "datetime", Clock)
    script = (
        "from pathlib import Path\nfrom tb.dashboard.research import research_view\nresearch_view(Path("
        + repr(str(root))
        + "))"
    )
    app = AppTest.from_string(script, default_timeout=30).run()
    assert not app.exception and not app.button
    assert any("SOFTWARE TEST ONLY" in w.value for w in app.warning)
    assert len(app.dataframe) == 2
    app.checkbox[0].check().run()
    assert not app.exception and len(app.dataframe) == 3
    value = p.model_dump(mode="json")
    value["rights"]["owner_approved"] = False
    (root / "work/research/proposals/owned.json").write_text(json.dumps(value))
    app.run()
    assert not app.exception and not app.checkbox and len(app.dataframe) == 1
    assert any("No currently authorized" in i.value for i in app.info)
    assert result["external_orders"] == 0


def test_offline_cli_and_no_provider_or_order_dependencies(tmp_path):
    completed = subprocess.run(
        [sys.executable, "-m", "tb.research.cli", "--root", str(tmp_path), "status"],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(completed.stdout)
    assert result["provider_connections"] == result["external_orders"] == 0
    assert "BLOCKED" in result["genuine_historical_evaluation"]
    for path in (repo_root() / "src/tb/research").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [n.name for n in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                assert not any(
                    any(
                        x in name.lower()
                        for x in (
                            "requests",
                            "httpx",
                            "socket",
                            "ctrader",
                            "oanda",
                            "twelve",
                            "metatrader",
                            "mcp",
                        )
                    )
                    for name in names
                )
    (tmp_path / ".env").touch()  # Presence only; never read secret values.
    failed = subprocess.run(
        [sys.executable, "-m", "tb.research.cli", "--root", str(tmp_path), "status"],
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 2 and "credential-free" in failed.stderr


def test_repaired_source_manifest_has_all_six_fixes():
    root = repo_root()
    value = json.loads(
        (root / "reports/validation/P11b-RC-remediation/regression-map.json").read_text()
    )
    assert value["total"] == 55 and set(value["counts"]) == {f"F-0{i}" for i in range(1, 7)}
    for cases in value["tests"].values():
        for item in cases:
            assert "def " + item["test"] + "(" in (root / item["file"]).read_text()


def test_extension_of_future_fixture_does_not_change_past_decisions(tmp_path):
    decisions = []
    for count in (80, 128):
        root = tmp_path / str(count)
        generate(root, "owned", NOW, bars=count)
        importer.import_dataset(root, "owned", clock=lambda: NOW)
        value = runner.run(root, "owned", ResearchProtocol(), clock=lambda: NOW)
        decisions.append(ledger(root, value, "decisions"))
    # Source/run identifiers legitimately change with coverage. Compare actual frozen information.
    old = {(d["symbol"], d["strategy"], d["source_open_at"]): d for d in decisions[0]}
    new = {(d["symbol"], d["strategy"], d["source_open_at"]): d for d in decisions[1]}
    for key, before in old.items():
        after = new[key]
        assert all(
            before[k] == after[k]
            for k in ("features", "features_sha256", "signal", "reasons", "decision_at")
        )


def test_split_boundary_cannot_supply_warmup_or_outcome_from_other_partition(owned, monkeypatch):
    root, original = owned
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    data = rows(original)
    start = datetime(2023, 12, 31, 20, tzinfo=UTC)
    for index, row in enumerate(data):
        stamp = start + timedelta(minutes=5 * (index // 2))
        row["timestamp"] = stamp.isoformat()
        row["available_at"] = (stamp + timedelta(minutes=5, seconds=1)).isoformat()
    p = licensed(root, original, data, coverage_start=start, coverage_end=stamp)
    registry.register(root, proposal(root, p), NOW)
    importer.import_dataset(root, "licensed", clock=lambda: NOW)
    for split, expected in (("research", 96), ("validation", 224)):
        value = runner.run(root, "licensed", ResearchProtocol(split=split), clock=lambda: NOW)
        ds = ledger(root, value, "decisions")
        assert value["observations_analyzed"] == expected
        for symbol in ("EURUSD", "XAUUSD"):
            for strategy in REFERENCE_STRATEGIES:
                subset = [d for d in ds if d["symbol"] == symbol and d["strategy"] == strategy]
                assert all(d["signal"] == "WAIT" for d in subset[:51])
        for outcome in ledger(root, value, "outcomes"):
            assert datetime.fromisoformat(outcome["end"]).year == (
                2023 if split == "research" else 2024
            )


def test_missing_future_intervals_are_never_interpolated(owned, monkeypatch):
    root, p = owned
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    data = [r for i, r in enumerate(rows(p)) if i not in (110, 111)]
    p = licensed(root, p, data)
    registry.register(root, proposal(root, p), NOW)
    importer.import_dataset(root, "licensed", clock=lambda: NOW)
    result = runner.run(root, "licensed", ResearchProtocol(), clock=lambda: NOW)
    assert any(g["missing"] > 0 for g in result["results"])
    known = {importer.at(r["timestamp"], p) for r in data}
    for label in ledger(root, result, "outcomes"):
        start = datetime.fromisoformat(label["start"])
        assert all(start + timedelta(minutes=5 * i) in known for i in range(label["horizon_M5"]))


def test_display_and_training_require_separate_current_grants(owned, monkeypatch):
    root, p = owned
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    # A distinct test file, not the already registered owned hash.
    p = licensed(root, p, list(reversed(rows(p))))
    rights = p.rights.model_copy(
        update={
            "permissions": {k: v for k, v in p.rights.permissions.items() if k != "private_display"}
        }
    )
    p = p.model_copy(update={"rights": rights, "retention": lifetime(rights, NOW)})
    registry.register(root, proposal(root, p), NOW)
    assert registry.load(root, "licensed", NOW) == p
    with pytest.raises(ResearchRefused, match="permission_missing"):
        registry.load(root, "licensed", NOW, display=True)
    with pytest.raises(ResearchRefused, match="permission_missing"):
        registry.authorize(root, p, NOW, training=True)


def test_row_count_bound_and_cache_accountability(owned, monkeypatch):
    root, _ = owned
    monkeypatch.setattr(importer, "MAX_ROWS", 10)
    with pytest.raises(ResearchRefused, match="row_limit"):
        importer.import_dataset(root, "owned", clock=lambda: NOW)
    inv = registry.inventory(root, NOW)
    assert any("cache" in o["kinds"] and o["exists"] for o in inv["objects"])


def test_silver_chunk_boundary_uses_bounded_parts(tmp_path):
    generate(tmp_path, "owned", NOW, bars=600)
    value = importer.import_dataset(tmp_path, "owned", clock=lambda: NOW)
    assert [p["rows"] for p in value["files"]] == [1000, 200]


def test_pending_tail_and_matched_overlap_denominators(tmp_path):
    from tb.shadow.models import ResearchDecision

    generate(tmp_path, "owned", NOW, bars=80)
    importer.import_dataset(tmp_path, "owned", clock=lambda: NOW)
    result = runner.run(tmp_path, "owned", ResearchProtocol(), clock=lambda: NOW)
    assert any(g["pending"] > 0 for g in result["results"])
    ds = [ResearchDecision.model_validate(v) for v in ledger(tmp_path, result, "decisions")]
    prototype = next(d for d in ds if d.signal == "BUY")
    # Hand-counted labels verify overlapping observations never inflate the primary n.
    labels = [
        {
            "symbol": prototype.symbol,
            "strategy": prototype.strategy,
            "horizon_M5": 1,
            "decision_id": prototype.id,
            "label": direction,
            "correct": correct,
            "nonoverlapping": nonoverlap,
            "previous_movement": previous,
        }
        for direction, correct, nonoverlap, previous in [
            ("UP", True, True, "UP"),
            ("DOWN", False, False, "DOWN"),
            ("FLAT", False, True, "DOWN"),
            ("UP", True, True, "WAIT"),
        ]
    ]
    summaries = runner._summary(
        ds,
        labels,
        list(importer.bars(tmp_path, "owned", clock=lambda: NOW)),
        "owned_synthetic",
        ResearchProtocol(),
    )
    group = next(
        g
        for g in summaries
        if g["symbol"] == prototype.symbol
        and g["strategy"] == prototype.strategy
        and g["horizon_M5"] == 1
    )
    assert group["labels"] == 4 and group["nonoverlapping"] == 3 and group["overlapping"] == 1
    assert group["matched_n"] == 2 and group["matched_correct"] == 1
    assert group["matched_always_UP_correct"] == group["matched_previous_movement_correct"] == 1
    assert (
        group["directional_accuracy"] == 0.5
        and group["sample_size_status"] == "INSUFFICIENT EVIDENCE"
    )


def test_independent_runs_have_identical_frozen_hashes(tmp_path):
    runs = []
    for name in ("first", "independent"):
        root = tmp_path / name
        generate(root, "owned", NOW, bars=80)
        importer.import_dataset(root, "owned", clock=lambda: NOW)
        runs.append(runner.run(root, "owned", ResearchProtocol(), clock=lambda: NOW))
    assert runs[0] == runs[1]


@pytest.mark.parametrize("error_kind", ["csv", "parquet"])
def test_cli_parser_errors_are_static_and_price_free(owned, monkeypatch, capsys, error_kind):
    import tb.research.cli as cli

    root, _ = owned
    error = (
        csv.Error("PRIVATE-SOURCE-CONTENT")
        if error_kind == "csv"
        else pl.exceptions.ComputeError("PRIVATE-SOURCE-CONTENT")
    )

    def fail(*a, **k):
        raise error

    monkeypatch.setattr(cli, "import_dataset", fail)
    monkeypatch.setattr(sys, "argv", ["research", "--root", str(root), "import", "owned"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
    output = capsys.readouterr()
    assert "PRIVATE-SOURCE-CONTENT" not in output.err and "Research refused" in output.err
