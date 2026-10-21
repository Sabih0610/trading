"""Reusable integrity and content validation for immutable Bronze Parquet partitions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from tb.ingest.history.core import BronzeManifest, sha256_file


class BronzeValidationReport(BaseModel):
    """Aggregate result for a bounded, streaming-friendly Bronze validation pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    files: int = Field(ge=0)
    rows: int = Field(ge=0)
    bytes: int = Field(ge=0)
    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return true when every discovered partition passes all checks."""

        return not self.issues


def _manifest_path(data_path: Path) -> Path:
    return data_path.with_name(f"{data_path.stem}_manifest.json")


def _timestamp_column(frame: pl.LazyFrame) -> str:
    names = frame.collect_schema().names()
    for candidate in ("timestamp_ns", "open_time_ns"):
        if candidate in names:
            return candidate
    raise ValueError("no supported nanosecond timestamp column")


def validate_bronze(root: Path) -> BronzeValidationReport:
    """Validate checksums, row counts, time ordering, and exact row uniqueness."""

    issues: list[str] = []
    files = 0
    rows = 0
    byte_count = 0
    for data_path in sorted(root.rglob("*.parquet")):
        files += 1
        relative = data_path.relative_to(root)
        byte_count += data_path.stat().st_size
        manifest_path = _manifest_path(data_path)
        if not manifest_path.is_file():
            issues.append(f"{relative}: missing manifest")
            continue
        try:
            manifest = BronzeManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            issues.append(f"{relative}: invalid manifest ({exc})")
            continue
        if manifest.byte_count != data_path.stat().st_size:
            issues.append(f"{relative}: manifest byte count does not match")
        if manifest.parquet_sha256 != sha256_file(data_path):
            issues.append(f"{relative}: manifest checksum does not match")
        try:
            frame = pl.scan_parquet(data_path)
            timestamp_column = _timestamp_column(frame)
            summary = frame.select(
                pl.len().alias("rows"),
                pl.col(timestamp_column).is_sorted().alias("sorted"),
            ).collect()
            partition_rows = int(summary["rows"][0])
            rows += partition_rows
            if manifest.rows != partition_rows:
                issues.append(f"{relative}: manifest row count does not match")
            if not bool(summary["sorted"][0]):
                issues.append(f"{relative}: timestamp_ns is not sorted")
            duplicate_count = int(
                frame.select(
                    pl.struct(pl.all()).is_duplicated().sum().alias("duplicates")
                ).collect()["duplicates"][0]
            )
            if duplicate_count:
                issues.append(f"{relative}: {duplicate_count} exact duplicate rows")
        except (OSError, ValueError, pl.exceptions.PolarsError) as exc:
            issues.append(f"{relative}: unreadable Parquet ({exc})")
    return BronzeValidationReport(
        files=files,
        rows=rows,
        bytes=byte_count,
        issues=tuple(issues),
    )


def main() -> None:
    """Validate a Bronze tree and return a nonzero process status on any issue."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Bronze root to validate")
    arguments = parser.parse_args()
    report = validate_bronze(arguments.root.resolve())
    print(json.dumps(report.model_dump(), indent=2))
    if not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
