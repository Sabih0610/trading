"""News orchestration deduplicates feeds and survives one source outage."""

from pathlib import Path

import httpx

from tb.ingest.news.cli import run_news_download


def test_news_cli_uses_available_rss_and_deduplicates(tmp_path: Path, monkeypatch) -> None:
    feed = b"""<rss><channel><item>
      <title>Gold rises after Fed statement</title>
      <link>https://example.test/gold</link>
      <pubDate>Tue, 20 Oct 2026 18:30:00 +0000</pubDate>
    </item></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.federalreserve.gov":
            return httpx.Response(200, content=feed, request=request)
        return httpx.Response(404, request=request)

    monkeypatch.setattr("tb.ingest.news.cli.repo_root", lambda: tmp_path)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run_news_download(
            sources="federal_reserve,ecb",
            from_value="2026-10-20",
            to_value="2026-10-20",
            resume=True,
            bronze_root=tmp_path / "bronze",
            client=client,
            pause=lambda _: None,
        )

    report = tmp_path / "reports" / "data-quality" / "P03-news-coverage.json"
    assert report.is_file()
    assert next((tmp_path / "bronze").rglob("*.parquet")).is_file()


def test_keyed_source_without_key_is_disabled_without_network(tmp_path: Path, monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected network request: {request.url}")

    monkeypatch.setattr("tb.ingest.news.cli.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "tb.ingest.news.cli.features_enabled",
        lambda settings: {
            "finnhub": False,
            "cryptopanic": False,
            "newsdata": False,
        },
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run_news_download(
            sources="finnhub",
            from_value="2026-10-20",
            to_value="2026-10-20",
            resume=True,
            bronze_root=tmp_path / "bronze",
            client=client,
            pause=lambda _: None,
        )
