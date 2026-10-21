"""Official and structured calendar parser fixtures."""

import json
from datetime import UTC, datetime

import pytest

from tb.ingest.calendar.adapters import (
    FairEconomyTermsReviewRequired,
    parse_bls_schedule,
    parse_ecb_webcasts,
    parse_finance_calendar,
    require_fair_economy_terms_approval,
)

FETCHED = datetime(2026, 10, 21, tzinfo=UTC)


def test_bls_parser_handles_us_dst_and_filters_non_target_releases() -> None:
    html = b"""
    <table class="release-list"><tbody>
      <tr><td class="date-cell"><p>Friday, March 06, 2020</p></td>
          <td class="time-cell"><p>08:30 AM</p></td>
          <td class="desc-cell"><p><strong>Employment Situation</strong> for February</p></td></tr>
      <tr><td class="date-cell"><p>Tuesday, July 14, 2020</p></td>
          <td class="time-cell"><p>08:30 AM</p></td>
          <td class="desc-cell"><p><strong>Consumer Price Index</strong> for June</p></td></tr>
      <tr><td class="date-cell"><p>Wednesday, July 15, 2020</p></td>
          <td class="time-cell"><p>10:00 AM</p></td>
          <td class="desc-cell"><p><strong>Minor Survey</strong></p></td></tr>
    </tbody></table>
    """

    events = parse_bls_schedule(
        html,
        year=2020,
        source_url="https://www.bls.gov/schedule/2020/home.htm",
        fetched_at=FETCHED,
    )

    assert [event.scheduled_utc.hour for event in events] == [13, 12]
    assert [event.name for event in events] == ["US Employment Situation", "US CPI"]


def test_ecb_parser_handles_european_dst() -> None:
    html = b"<dl><dt>23 January 2020</dt><dd>Frankfurt</dd><dt>16 July 2020</dt></dl>"

    events = parse_ecb_webcasts(
        html,
        source_url="https://www.ecb.europa.eu/press/tvservices/webcast/html/index.en.html",
        fetched_at=FETCHED,
        start_year=2020,
    )

    assert [event.scheduled_utc.hour for event in events] == [13, 12]


def test_finance_calendar_parser_preserves_values_and_rejects_schema_change() -> None:
    payload = json.dumps(
        {
            "events": [
                {
                    "name": "US CPI",
                    "country": "US",
                    "impact": "high",
                    "release_at_utc": "2026-10-14T12:30:00+00:00",
                    "all_day": False,
                    "actual": "3.4%",
                    "consensus": "3.1%",
                    "prior": "3.0%",
                    "source_url": "https://www.bls.gov/cpi/",
                }
            ]
        }
    ).encode()

    events = parse_finance_calendar(payload, fetched_at=FETCHED)

    assert events[0].actual == "3.4%"
    assert events[0].currency == "USD"
    with pytest.raises(ValueError, match="events list"):
        parse_finance_calendar(b"{}", fetched_at=FETCHED)


def test_fair_economy_live_use_is_terms_gated() -> None:
    with pytest.raises(FairEconomyTermsReviewRequired, match="D-0015"):
        require_fair_economy_terms_approval()
