"""Metadata HTTP caching avoids repeated requests and rejects stale entries."""

import os
import time
from pathlib import Path

import httpx

from tb.ingest.http_cache import cached_download


def test_cached_download_reuses_immutable_response(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"payload", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = cached_download(
            client,
            "https://example.test/data",
            tmp_path,
            resume=True,
            max_age_seconds=None,
        )
        second = cached_download(
            client,
            "https://example.test/data",
            tmp_path,
            resume=True,
            max_age_seconds=None,
        )

    assert not first.from_cache
    assert second.from_cache
    assert calls == 1


def test_stale_cache_is_refetched(tmp_path: Path) -> None:
    responses = iter((b"old", b"new"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(responses), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        cached_download(
            client,
            "https://example.test/data",
            tmp_path,
            resume=True,
            max_age_seconds=60,
        )
        path = next(tmp_path.glob("*.bin"))
        stale = time.time() - 120
        os.utime(path, (stale, stale))
        result = cached_download(
            client,
            "https://example.test/data",
            tmp_path,
            resume=True,
            max_age_seconds=60,
        )

    assert result.payload == b"new"
    assert not result.from_cache
