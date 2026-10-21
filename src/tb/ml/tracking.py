"""Local MLflow tracking and explicitly human-controlled registry aliases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

import mlflow
from pydantic import BaseModel, ConfigDict


class TrackingRun(BaseModel):
    """Identifiers and local stores created for one experiment run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    experiment_id: str
    tracking_uri: str
    artifact_uri: str


class RegistryAliasClient(Protocol):
    """Minimal MLflow client surface used by the human promotion boundary."""

    def set_registered_model_alias(self, name: str, alias: str, version: str) -> None: ...

    def set_model_version_tag(self, name: str, version: str, key: str, value: str) -> None: ...


def local_tracking_uri(root: Path) -> str:
    """Return a platform-safe absolute SQLite URI below the selected local root."""

    database = (root.resolve() / "mlflow.db").as_posix()
    return f"sqlite:///{database}"


def log_local_run(
    root: Path,
    *,
    experiment_name: str,
    run_name: str,
    parameters: Mapping[str, str | int | float | bool],
    metrics: Mapping[str, float],
    tags: Mapping[str, str],
    artifacts: Sequence[Path] = (),
) -> TrackingRun:
    """Log complete local evidence and restore the caller's tracking URI afterward."""

    if not experiment_name.strip() or not run_name.strip():
        raise ValueError("experiment_name and run_name must be non-empty")
    if any(not key.strip() for key in (*parameters, *metrics, *tags)):
        raise ValueError("tracking keys must be non-empty")
    missing = [path for path in artifacts if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Tracking artifact does not exist: {missing[0]}")
    root.mkdir(parents=True, exist_ok=True)
    previous_uri = mlflow.get_tracking_uri()
    uri = local_tracking_uri(root)
    try:
        mlflow.set_tracking_uri(uri)
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            experiment_id = mlflow.create_experiment(
                experiment_name,
                artifact_location=(root.resolve() / "mlruns").as_uri(),
            )
            experiment = mlflow.get_experiment(experiment_id)
        mlflow.set_experiment(experiment_id=experiment.experiment_id)
        with mlflow.start_run(run_name=run_name) as active:
            mlflow.log_params(dict(parameters))
            mlflow.log_metrics(dict(metrics))
            mlflow.set_tags(dict(tags))
            for artifact in artifacts:
                mlflow.log_artifact(str(artifact.resolve()))
            return TrackingRun(
                run_id=active.info.run_id,
                experiment_id=experiment.experiment_id,
                tracking_uri=uri,
                artifact_uri=mlflow.get_artifact_uri(),
            )
    finally:
        mlflow.set_tracking_uri(previous_uri)


def assign_human_registry_role(
    client: RegistryAliasClient,
    *,
    model_name: str,
    version: str,
    role: str,
    approved_by: str,
) -> None:
    """Assign champion/challenger only with a named human approval audit tag."""

    normalized = role.strip().lower()
    if normalized not in {"champion", "challenger"}:
        raise ValueError("role must be champion or challenger")
    if not model_name.strip() or not version.strip() or not approved_by.strip():
        raise ValueError("model, version, and human approver must be non-empty")
    client.set_registered_model_alias(model_name, normalized, version)
    client.set_model_version_tag(model_name, version, "role", normalized)
    client.set_model_version_tag(model_name, version, "human_approved_by", approved_by.strip())
    client.set_model_version_tag(model_name, version, "automatic_deployment", "disabled")
