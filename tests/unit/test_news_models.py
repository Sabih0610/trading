"""News headline identity, topic tagging, and deduplication."""

from datetime import UTC, datetime, timedelta

from tb.ingest.news.models import build_news_item, deduplicate_news, headline_id


def _item(headline: str, source: str, minutes: int = 0):
    return build_news_item(
        headline=headline,
        source=source,
        url=f"https://example.test/{source}",
        published_utc=datetime(2026, 10, 20, tzinfo=UTC) + timedelta(minutes=minutes),
        fetched_at=datetime(2026, 10, 20, 1, tzinfo=UTC),
        language="EN",
        raw_record=f"{headline}|{source}".encode(),
    )


def test_headline_identity_normalizes_unicode_case_and_punctuation() -> None:
    assert headline_id("Fed\u2019s GOLD outlook") == headline_id("FED'S gold outlook!")


def test_deduplication_keeps_earliest_deterministic_record_and_topics() -> None:
    later = _item("Bitcoin rises as Fed watches inflation", "zeta", 5)
    earlier = _item("Bitcoin rises as Fed watches inflation!", "alpha")

    result = deduplicate_news([later, earlier])

    assert len(result) == 1
    assert result[0].source == "alpha"
    assert result[0].topics == ("central_bank", "inflation", "crypto")
