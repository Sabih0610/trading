from pathlib import Path

import mlflow
import pytest

from tb.ml.tracking import assign_human_registry_role, local_tracking_uri, log_local_run


class _FakeRegistryClient:
    def __init__(self) -> None:
        self.aliases: list[tuple[str, str, str]] = []
        self.tags: list[tuple[str, str, str, str]] = []

    def set_registered_model_alias(self, name: str, alias: str, version: str) -> None:
        self.aliases.append((name, alias, version))

    def set_model_version_tag(self, name: str, version: str, key: str, value: str) -> None:
        self.tags.append((name, version, key, value))


def test_local_run_records_params_metrics_tags_and_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.txt"
    artifact.write_text("offline evidence\n", encoding="utf-8")
    previous = mlflow.get_tracking_uri()

    result = log_local_run(
        tmp_path / "tracking store with space",
        experiment_name="P08-test",
        run_name="synthetic",
        parameters={"data_version": "fixture-v1", "feature_version": "1.0.0"},
        metrics={"brier": 0.2},
        tags={"evidence": "synthetic", "final_test": "false"},
        artifacts=[artifact],
    )

    assert result.run_id
    assert result.tracking_uri == local_tracking_uri(tmp_path / "tracking store with space")
    assert (tmp_path / "tracking store with space" / "mlflow.db").is_file()
    assert mlflow.get_tracking_uri() == previous


def test_registry_roles_require_named_human_and_disable_auto_deployment() -> None:
    client = _FakeRegistryClient()

    assign_human_registry_role(
        client,
        model_name="xaut-meta",
        version="3",
        role="challenger",
        approved_by="owner",
    )

    assert client.aliases == [("xaut-meta", "challenger", "3")]
    assert ("xaut-meta", "3", "automatic_deployment", "disabled") in client.tags
    with pytest.raises(ValueError, match="approver"):
        assign_human_registry_role(
            client,
            model_name="xaut-meta",
            version="3",
            role="champion",
            approved_by="",
        )
    with pytest.raises(ValueError, match="role"):
        assign_human_registry_role(
            client,
            model_name="xaut-meta",
            version="3",
            role="production",
            approved_by="owner",
        )


def test_tracking_inputs_fail_before_writes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        log_local_run(
            tmp_path,
            experiment_name="",
            run_name="run",
            parameters={},
            metrics={},
            tags={},
        )
    with pytest.raises(FileNotFoundError):
        log_local_run(
            tmp_path,
            experiment_name="experiment",
            run_name="run",
            parameters={},
            metrics={},
            tags={},
            artifacts=[tmp_path / "missing.txt"],
        )
