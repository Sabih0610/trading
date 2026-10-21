"""Small content-addressed HTTP cache for polite public metadata retrieval."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from tb.ingest.history.core import RetryPolicy, atomic_write_bytes, download_bytes


class CachedResponse(BaseModel):
    """Public response bytes plus whether network access was avoided."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: bytes
    from_cache: bool


def cached_download(
    client: httpx.Client,
    url: str,
    cache_root: Path,
    *,
    resume: bool,
    max_age_seconds: int | None,
    policy: RetryPolicy | None = None,
) -> CachedResponse:
    """Fetch public bytes, reusing a fresh or explicitly immutable cached response."""

    if max_age_seconds is not None and max_age_seconds < 0:
        raise ValueError("Cache age cannot be negative")
    key = hashlib.sha256(url.encode()).hexdigest()
    path = cache_root / f"{key}.bin"
    if resume and path.is_file():
        age = max(0.0, time.time() - path.stat().st_mtime)
        if max_age_seconds is None or age <= max_age_seconds:
            return CachedResponse(payload=path.read_bytes(), from_cache=True)
    payload = download_bytes(client, url, policy=policy)
    atomic_write_bytes(path, payload)
    return CachedResponse(payload=payload, from_cache=False)
