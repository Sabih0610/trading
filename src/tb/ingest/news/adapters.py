"""Strict headline-only parsers for RSS and GDELT DOC metadata."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from tb.ingest.news.models import NewsItem, build_news_item


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(item: Element, names: tuple[str, ...]) -> str | None:
    for child in item:
        if _local_name(child.tag) in names and child.text and child.text.strip():
            return child.text.strip()
    return None


def _link(item: Element) -> str | None:
    for child in item:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href.strip()
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _published(value: str) -> datetime:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("RSS publication timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def parse_rss(
    payload: bytes,
    *,
    source: str,
    fetched_at: datetime,
    language: str = "en",
) -> list[NewsItem]:
    """Parse RSS 2.0 or Atom entries without retaining summaries or article bodies."""

    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid RSS/Atom XML") from exc
    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    items: list[NewsItem] = []
    for entry in entries:
        title = _text(entry, ("title",))
        url = _link(entry)
        published_text = _text(entry, ("pubDate", "published", "updated", "date"))
        if not title or not url or not published_text:
            raise ValueError("RSS/Atom entry is missing title, link, or publication time")
        raw_record = ElementTree.tostring(entry, encoding="utf-8")
        items.append(
            build_news_item(
                headline=title,
                source=source,
                url=url,
                published_utc=_published(published_text),
                fetched_at=fetched_at,
                language=language,
                raw_record=raw_record,
            )
        )
    if not items:
        raise ValueError("RSS/Atom feed contains no entries")
    return items


_LANGUAGE_CODES = {"English": "en", "Spanish": "es", "French": "fr", "German": "de"}


def parse_gdelt_doc(payload: bytes, *, fetched_at: datetime) -> list[NewsItem]:
    """Parse GDELT DOC article-list JSON into headline/link metadata."""

    raw = json.loads(payload)
    if not isinstance(raw, dict) or not isinstance(raw.get("articles"), list):
        raise ValueError("GDELT DOC response must contain an articles list")
    items: list[NewsItem] = []
    for article in raw["articles"]:
        if not isinstance(article, dict):
            raise ValueError("GDELT article must be an object")
        headline = article.get("title")
        url = article.get("url")
        seen = article.get("seendate")
        if not all(isinstance(value, str) and value.strip() for value in (headline, url, seen)):
            raise ValueError("GDELT article is missing title, URL, or seen date")
        assert isinstance(url, str)
        domain = str(article.get("domain") or urlparse(url).netloc).strip()
        if not domain:
            raise ValueError("GDELT article is missing a source domain")
        seen_at = datetime.strptime(str(seen), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        language = _LANGUAGE_CODES.get(str(article.get("language")), "und")
        raw_record = json.dumps(article, sort_keys=True, ensure_ascii=False).encode()
        items.append(
            build_news_item(
                headline=str(headline),
                source=domain,
                url=url,
                published_utc=seen_at,
                fetched_at=fetched_at,
                language=language,
                raw_record=raw_record,
            )
        )
    return items
