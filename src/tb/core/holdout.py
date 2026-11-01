"""Forward-sealed observations have no read/evaluation bypass before separately authorized P14."""

from __future__ import annotations

import glob
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import polars as pl

SEALED = "forward_sealed"


class ForwardSealedError(ValueError):
    """Capture is permitted; analytical access and unsealing are outside this phase."""


def require_unsealed(value: Any) -> None:
    """Refuse sealed paths, metadata, frames or typed input objects before processing."""
    if isinstance(value, Path):
        if any(part.casefold() in {SEALED, "sealed_forward"} for part in value.resolve().parts):
            raise ForwardSealedError(
                "forward_sealed: locked until the single authorized P14 forward test"
            )
        if glob.has_magic(str(value)):
            for matched in glob.iglob(str(value), recursive=True):
                require_unsealed(Path(matched))
        for manifest in (
            value.with_suffix(value.suffix + ".manifest.json"),
            value.with_suffix(".manifest.json"),
            value.with_name(value.stem + "_manifest.json"),
        ):
            if manifest.is_file():
                if manifest.stat().st_size > 524288:
                    raise ForwardSealedError("Manifest exceeds the safe seal-check limit")
                require_unsealed(json.loads(manifest.read_text(encoding="utf-8")))
        return
    if isinstance(value, pl.DataFrame | pl.LazyFrame):
        schema = value.collect_schema()
        if "holdout" in schema:
            column = value.select(pl.col("holdout").cast(pl.String).eq(SEALED).any())
            if isinstance(column, pl.LazyFrame):
                column = column.collect()
            if column.item():
                raise ForwardSealedError("forward_sealed: analytical frame access refused")
        return
    if isinstance(value, Mapping):
        marker = value.get("holdout")
        if isinstance(marker, str) and marker.casefold() == SEALED:
            raise ForwardSealedError("forward_sealed: metadata/input access refused")
        for key in ("metadata", "provenance"):
            if key in value:
                require_unsealed(value[key])
        return
    if isinstance(value, list | tuple):
        for item in value:
            require_unsealed(item)
        return
    marker = getattr(value, "holdout", None)
    if marker == SEALED:
        raise ForwardSealedError("forward_sealed: typed input access refused")


def read_unsealed_parquet(source: Any, **kwargs: Any) -> pl.DataFrame:
    """File/sidecar seal is checked before Polars can open any price-bearing bytes."""
    if isinstance(source, list | tuple):
        for item in source:
            require_unsealed(Path(item) if isinstance(item, str) else item)
    else:
        require_unsealed(Path(source) if isinstance(source, str) else source)
    frame = pl.read_parquet(source, **kwargs)
    require_unsealed(frame)
    return frame


def scan_unsealed_parquet(source: Any, **kwargs: Any) -> pl.LazyFrame:
    """Refuse a sealed scan before schema/footer access, even in synthetic mode."""
    if isinstance(source, list | tuple):
        for item in source:
            require_unsealed(Path(item) if isinstance(item, str) else item)
    else:
        require_unsealed(Path(source) if isinstance(source, str) else source)
    frame = pl.scan_parquet(source, **kwargs)
    require_unsealed(frame)
    return frame
