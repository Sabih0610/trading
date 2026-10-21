"""RSS/Atom and GDELT headline-only parser fixtures."""

import json
from datetime import UTC, datetime

import pytest
from defusedxml.common import DefusedXmlException

from tb.ingest.news.adapters import parse_gdelt_doc, parse_rss

FETCHED = datetime(2026, 10, 21, tzinfo=UTC)


def test_rss_and_atom_parse_only_headline_metadata() -> None:
    rss = b"""<?xml version="1.0"?><rss><channel><item>
      <title>Gold rises after Fed statement</title>
      <link>https://example.test/gold</link>
      <pubDate>Tue, 20 Oct 2026 14:30:00 -0400</pubDate>
      <description>Body must not be retained.</description>
    </item></channel></rss>"""
    atom = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>Bitcoin market update</title><link href="https://example.test/btc"/>
      <updated>2026-10-20T18:30:00Z</updated><summary>Do not retain.</summary>
    </entry></feed>"""

    rss_items = parse_rss(rss, source="fed", fetched_at=FETCHED)
    atom_items = parse_rss(atom, source="ecb", fetched_at=FETCHED)

    assert rss_items[0].published_utc == datetime(2026, 10, 20, 18, 30, tzinfo=UTC)
    assert "central_bank" in rss_items[0].topics
    assert atom_items[0].url == "https://example.test/btc"


def test_rss_schema_change_and_entity_expansion_fail_loudly() -> None:
    with pytest.raises(ValueError, match="missing"):
        parse_rss(
            b"<rss><channel><item><title>x</title></item></channel></rss>",
            source="x",
            fetched_at=FETCHED,
        )
    hostile = b'<!DOCTYPE x [<!ENTITY a "boom">]><rss><channel><item><title>&a;</title></item></channel></rss>'
    with pytest.raises(DefusedXmlException):
        parse_rss(hostile, source="x", fetched_at=FETCHED)


def test_gdelt_parser_handles_language_and_non_english() -> None:
    payload = json.dumps(
        {
            "articles": [
                {
                    "title": "El oro y la inflacion",
                    "url": "https://example.es/oro",
                    "domain": "example.es",
                    "seendate": "20261020T183000Z",
                    "language": "Spanish",
                }
            ]
        }
    ).encode()

    items = parse_gdelt_doc(payload, fetched_at=FETCHED)

    assert items[0].language == "es"
    assert items[0].source == "example.es"
