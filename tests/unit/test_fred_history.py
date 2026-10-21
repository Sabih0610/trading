"""Offline FRED CSV contract tests; live use remains explicitly gated."""

import pytest

from tb.ingest.history.fred import (
    FredTermsReviewRequired,
    graph_csv_url,
    parse_graph_csv,
    require_live_terms_approval,
)


def test_keyless_url_is_allowlisted() -> None:
    assert graph_csv_url("dgs10") == "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    with pytest.raises(ValueError, match="Unsupported"):
        graph_csv_url("UNREVIEWED")


def test_csv_parser_preserves_missing_values() -> None:
    payload = b"observation_date,DGS10\r\n2026-01-01,.\r\n2026-01-02,4.25\r\n"

    frame = parse_graph_csv(payload, "DGS10")

    assert frame["DGS10"].to_list() == [".", "4.25"]
    assert frame["value"].to_list() == [None, 4.25]


def test_csv_parser_rejects_duplicates_and_wrong_columns() -> None:
    duplicate = b"observation_date,DGS10\n2026-01-01,4\n2026-01-01,5\n"
    with pytest.raises(ValueError, match="duplicate"):
        parse_graph_csv(duplicate, "DGS10")
    with pytest.raises(ValueError, match="Expected FRED columns"):
        parse_graph_csv(b"date,DGS10\n2026-01-01,4\n", "DGS10")


def test_live_fred_use_fails_closed_pending_terms_review() -> None:
    with pytest.raises(FredTermsReviewRequired, match="D-0011"):
        require_live_terms_approval()
