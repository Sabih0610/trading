"""Strict normalized news-headline contracts."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

_NON_WORD = re.compile(r"[\W_]+", flags=re.UNICODE)
_TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "gold": ("gold", "bullion", "xau"),
    "central_bank": ("federal reserve", "fed ", "fomc", "ecb", "central bank"),
    "inflation": ("inflation", "cpi", "pce"),
    "oil": ("oil", "crude", "opec", "brent", "wti"),
    "crypto": ("bitcoin", "btc", "ethereum", "ether", "crypto", "solana"),
}


def normalize_headline(value: str) -> str:
    """Normalize Unicode, punctuation, case, and whitespace for headline identity."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return _NON_WORD.sub(" ", normalized).strip()


def headline_id(headline: str) -> str:
    """Return the deterministic normalized-text SHA-256 identifier."""

    normalized = normalize_headline(headline)
    if not normalized:
        raise ValueError("Headline must contain letters or numbers")
    return hashlib.sha256(normalized.encode()).hexdigest()


def classify_topics(headline: str) -> tuple[str, ...]:
    """Apply transparent keyword tags without creating trading decisions."""

    normalized = f" {normalize_headline(headline)} "
    return tuple(
        topic for topic, terms in _TOPIC_TERMS.items() if any(term in normalized for term in terms)
    )


class NewsItem(BaseModel):
    """One publisher/GDELT headline metadata record; article bodies are excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: str = Field(pattern=r"^[0-9a-f]{64}$")
    headline: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=4096)
    published_utc: AwareDatetime
    fetched_at: AwareDatetime
    topics: tuple[str, ...]
    language: str = Field(pattern=r"^[a-z]{2,3}$")
    raw_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("published_utc", "fetched_at", mode="after")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


def build_news_item(
    *,
    headline: str,
    source: str,
    url: str,
    published_utc: datetime,
    fetched_at: datetime,
    language: str,
    raw_record: bytes,
) -> NewsItem:
    """Build one normalized item and hash its exact source record."""

    return NewsItem(
        id=headline_id(headline),
        headline=headline,
        source=source,
        url=url,
        published_utc=published_utc,
        fetched_at=fetched_at,
        topics=classify_topics(headline),
        language=language.casefold(),
        raw_hash=hashlib.sha256(raw_record).hexdigest(),
    )


def deduplicate_news(items: list[NewsItem]) -> list[NewsItem]:
    """Keep one deterministic record per normalized headline hash."""

    chosen: dict[str, NewsItem] = {}
    for item in items:
        current = chosen.get(item.id)
        if current is None or (item.published_utc, item.source, item.url) < (
            current.published_utc,
            current.source,
            current.url,
        ):
            chosen[item.id] = item
    return sorted(chosen.values(), key=lambda item: (item.published_utc, item.id))
