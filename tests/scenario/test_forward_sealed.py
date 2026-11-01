"""One refusal per reader; only fictional inputs, never genuine sealed archive reads."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import polars as pl
import pytest

from tb.core.holdout import ForwardSealedError, read_unsealed_parquet, scan_unsealed_parquet

SEALED = {"holdout": "forward_sealed"}
NOW = datetime(2024, 1, 1, tzinfo=UTC)


def test_research_importer_refuses_sealed_path_before_open(tmp_path):
    from tb.research.importer import source_rows

    with pytest.raises(ForwardSealedError):
        next(source_rows(tmp_path / "forward_sealed/owned.parquet", None))


def test_research_runner_refuses_sealed_source_before_open(tmp_path):
    from tb.research.models import ResearchProtocol
    from tb.research.runner import run

    with pytest.raises(ForwardSealedError):
        run(tmp_path / "forward_sealed", "owned", ResearchProtocol(), clock=lambda: NOW)


def test_silver_reader_refuses_sealed_frame():
    from tb.silver.market import clean_minute_bars

    with pytest.raises(ForwardSealedError):
        clean_minute_bars(pl.DataFrame([SEALED]), market_kind="continuous")


def test_silver_pipeline_refuses_sealed_directory(tmp_path):
    from tb.silver.pipeline import build_silver

    with pytest.raises(ForwardSealedError):
        build_silver(tmp_path / "forward_sealed", tmp_path / "silver", tmp_path / "reports")


def test_gold_pipeline_refuses_sealed_directory(tmp_path):
    from tb.features.pipeline import build_gold

    with pytest.raises(ForwardSealedError):
        build_gold(tmp_path / "forward_sealed", tmp_path / "gold")


def test_shadow_replay_refuses_sealed_path(tmp_path):
    from tb.shadow.fixtures import read_replay

    with pytest.raises(ForwardSealedError):
        next(read_replay(tmp_path / "forward_sealed/manifest.json", None))


def test_gold_reader_refuses_sealed_frame():
    from tb.features.pipeline import build_feature_frame

    with pytest.raises(ForwardSealedError):
        build_feature_frame(pl.DataFrame([SEALED]), timeframe="1m")


def test_feature_engine_refuses_sealed_bar():
    from tb.features.engine import FeatureEngine

    with pytest.raises(ForwardSealedError):
        FeatureEngine().update(SEALED)


def test_backtester_refuses_sealed_inputs():
    from tb.backtest.engine import BacktestEngine

    with pytest.raises(ForwardSealedError):
        object.__new__(BacktestEngine).run([SEALED], [])


def test_ml_trainer_refuses_sealed_features():
    from tb.ml.models import fit_logistic_baseline

    with pytest.raises(ForwardSealedError):
        fit_logistic_baseline(pl.DataFrame([SEALED]), [])


def test_ml_labeler_refuses_sealed_inputs():
    from tb.ml.labeling import label_candidates

    with pytest.raises(ForwardSealedError):
        label_candidates([SimpleNamespace(holdout="forward_sealed")], [])


def test_arena_refuses_sealed_snapshot_before_ledger_or_provider():
    from tb.agents.arena import Arena

    with pytest.raises(ForwardSealedError):
        object.__new__(Arena).run(SEALED, questions=["owned"])


def test_shadow_reader_refuses_sealed_event():
    from tb.shadow.runtime import ShadowRuntime

    with pytest.raises(ForwardSealedError):
        object.__new__(ShadowRuntime).process(SEALED, NOW)


def test_paper_reducer_refuses_sealed_event():
    from tb.paper.offline.engine import PaperReducer

    with pytest.raises(ForwardSealedError):
        object.__new__(PaperReducer).apply(SEALED)


def test_contract_paper_engine_refuses_sealed_quote():
    from tb.paper.simulation import LocalPaperSimulator

    with pytest.raises(ForwardSealedError):
        object.__new__(LocalPaperSimulator).run([SEALED], [], [])


def test_dashboard_refuses_sealed_even_in_synthetic_mode(tmp_path):
    from tb.dashboard.readers import parquet_rows

    folder = tmp_path / "forward_sealed"
    folder.mkdir()
    (folder / "prices.parquet").touch()
    with pytest.raises(ForwardSealedError):
        parquet_rows(folder, "prices", "synthetic")


@pytest.mark.parametrize("reader", [read_unsealed_parquet, scan_unsealed_parquet])
def test_renamed_file_sidecar_and_list_path_cannot_bypass_seal(tmp_path, reader):
    path = tmp_path / "ordinary.parquet"
    path.with_suffix(".manifest.json").write_text(json.dumps(SEALED))
    with pytest.raises(ForwardSealedError):
        reader([str(path)])


def test_checksum_reader_cannot_open_sealed_payload(tmp_path):
    from tb.ingest.history.core import sha256_file

    with pytest.raises(ForwardSealedError):
        sha256_file(tmp_path / "forward_sealed/unopened.parquet")
