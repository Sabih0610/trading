"""Fixture-backed FRED graph CSV parsing with live use gated on terms review."""

from __future__ import annotations

from io import BytesIO

import polars as pl

FRED_GRAPH_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ALLOWED_SERIES = frozenset({"DGS10", "DFII10", "DTWEXBGS"})


class FredTermsReviewRequired(RuntimeError):
    """Raised because current FRED terms require an owner/legal scope decision."""


def graph_csv_url(series: str) -> str:
    """Return the keyless graph CSV URL for an explicitly allowlisted series."""

    normalized = series.strip().upper()
    if normalized not in ALLOWED_SERIES:
        raise ValueError(f"Unsupported FRED series: {normalized}")
    return f"{FRED_GRAPH_BASE_URL}?id={normalized}"


def require_live_terms_approval() -> None:
    """Fail closed until the owner records a lawful live-use decision."""

    raise FredTermsReviewRequired(
        "Live FRED ingestion is paused pending the terms decision recorded as D-0011"
    )


def parse_graph_csv(payload: bytes, series: str) -> pl.DataFrame:
    """Parse an offline FRED CSV fixture, preserving the published date/value columns."""

    normalized = series.strip().upper()
    if normalized not in ALLOWED_SERIES:
        raise ValueError(f"Unsupported FRED series: {normalized}")
    frame = pl.read_csv(
        BytesIO(payload),
        schema_overrides={"observation_date": pl.String, normalized: pl.String},
        raise_if_empty=True,
    )
    if frame.columns != ["observation_date", normalized]:
        raise ValueError(
            f"Expected FRED columns ['observation_date', '{normalized}'], got {frame.columns}"
        )
    parsed = frame.with_columns(
        pl.col("observation_date").str.to_date("%Y-%m-%d", strict=True).alias("date"),
        pl.when(pl.col(normalized) == ".")
        .then(None)
        .otherwise(pl.col(normalized).cast(pl.Float64, strict=True))
        .alias("value"),
    )
    if parsed["date"].is_duplicated().any():
        raise ValueError("FRED CSV contains duplicate observation dates")
    if not parsed["date"].is_sorted():
        raise ValueError("FRED CSV observation dates must be sorted")
    return parsed
