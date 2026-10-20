"""Properties for disk estimates and traversal-safe Bronze partitions."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tb.ingest.history.core import estimate_required_bytes, partition_directory


@given(
    partitions=st.integers(min_value=0, max_value=1_000_000),
    average_bytes=st.integers(min_value=0, max_value=10**9),
)
def test_estimate_never_understates_raw_product(partitions: int, average_bytes: int) -> None:
    assert estimate_required_bytes(partitions, average_bytes) >= partitions * average_bytes


@given(segment=st.sampled_from(["..", "../x", "x/y", "x\\y", "", ".hidden", " space"]))
def test_unsafe_source_segments_never_escape(segment: str) -> None:
    with pytest.raises(ValueError):
        partition_directory(
            Path("bronze"),
            segment,
            "BTCUSDT",
            "1m",
            datetime(2026, 1, 1, tzinfo=UTC),
        )
