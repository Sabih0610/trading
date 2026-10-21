"""Calendar orchestration uses an available source when another source is down."""

from pathlib import Path

import httpx

from tb.ingest.calendar.cli import run_calendar_download


def test_calendar_cli_uses_bls_when_ecb_is_down(tmp_path: Path, monkeypatch) -> None:
    html = b"""<table class="release-list"><tbody><tr>
    <td class="date-cell">Wednesday, October 14, 2026</td>
    <td class="time-cell">08:30 AM</td>
    <td class="desc-cell"><strong>Consumer Price Index</strong> for September</td>
    </tr></tbody></table>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.bls.gov":
            return httpx.Response(200, content=html, request=request)
        return httpx.Response(404, request=request)

    monkeypatch.setattr("tb.ingest.calendar.cli.repo_root", lambda: tmp_path)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run_calendar_download(
            sources="bls,ecb",
            from_value="2026-10-01",
            to_value="2026-10-31",
            resume=True,
            bronze_root=tmp_path / "bronze",
            client=client,
        )

    assert next((tmp_path / "bronze").rglob("*.parquet")).is_file()
    report = tmp_path / "reports" / "data-quality" / "P03-calendar-coverage.json"
    assert report.is_file()
