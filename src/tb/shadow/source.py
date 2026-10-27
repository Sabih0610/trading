"""Bounded read-only committed Silver events with exact source and file integrity."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from tb.ingest.history.core import sha256_file
from tb.ingest.mt5.models import Observation
from tb.ingest.mt5.storage import record_id
from tb.ingest.retention import require_lifetime
from tb.ingest.rights_review import check_review
from tb.shadow.journal import ShadowRefused
from tb.shadow.models import ShadowEvent, SourcePin


def read_committed(root: Path, commit_path: Path, pin: SourcePin) -> Iterator[ShadowEvent]:
    """A manifest assertion never substitutes for actual byte/source validation."""
    path, root = commit_path.resolve(), root.resolve()
    if not path.is_relative_to(root / "data/bronze/twelve_data") or path.stat().st_size > 131072:
        raise ShadowRefused("shadow_commit_path_or_size_refused")
    value = json.loads(path.read_text(encoding="utf-8"))
    retained = None
    if pin.mode == "genuine_shadow":
        rights = check_review(root, root / "config/data_rights.yaml", datetime.now(UTC))
        if rights.digest != pin.rights_digest or rights.account_fingerprint != pin.identity:
            raise ShadowRefused("shadow_current_source_rights_changed")
        retained = require_lifetime(rights, value.get("retention"), datetime.now(UTC))
    expected_origin = "synthetic" if pin.mode == "fixture_replay" else "twelve_data"
    if (
        value["origin"] != expected_origin
        or value["identity_fingerprint"] != pin.identity
        or value["code_version"] != pin.source_version
    ):
        raise ShadowRefused("shadow_commit_provider_identity_or_version_changed")
    if not 0 <= value["rows"] <= 10 or len(value["files"]) != 4:
        raise ShadowRefused("shadow_commit_row_or_file_bound_refused")
    silver: Path | None = None
    for name, checksum in value["files"].items():
        candidate = (root / name).resolve()
        if (
            not candidate.is_relative_to(root / "data")
            or candidate.stat().st_size > 1048576
            or sha256_file(candidate) != checksum
        ):
            raise ShadowRefused("shadow_committed_file_corrupt_or_missing")
        if (
            candidate.is_relative_to(root / "data/silver/twelve_data")
            and candidate.name == "observations.parquet"
        ):
            silver = candidate
    if silver is None:
        raise ShadowRefused("shadow_committed_silver_missing")
    records = pl.read_parquet(silver, n_rows=11).to_dicts()
    if len(records) > 10 or len(records) != value["rows"]:
        raise ShadowRefused("shadow_silver_row_bound_or_count_refused")
    for data in records:
        row = Observation.model_validate(
            {k: v for k, v in data.items() if k in Observation.model_fields}
        )
        if retained and row.received_at < retained.acquired_at:
            raise ShadowRefused("shadow_acquisition_clock_changed")
        if row.evidence != ("synthetic" if pin.mode == "fixture_replay" else "forward_observed"):
            continue
        yield ShadowEvent(
            retention=retained,
            pin=pin,
            observation=row,
            evidence_id=record_id(row, pin.identity),
            manifest_sha256=sha256_file(path),
            manifest_path=path.relative_to(root).as_posix(),
        )
