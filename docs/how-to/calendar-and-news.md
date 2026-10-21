# Calendar and news ingestion

P03 stores permitted economic-calendar payloads and headline metadata in immutable Bronze, then writes normalized manifested snapshots and coverage reports. Official agency schedules own event times; publisher article bodies are never downloaded or stored.

## Calendar history and live refresh

From the repository root:

```powershell
Set-Location -LiteralPath "E:\trading bot"
pwsh -NoProfile -File .\scripts\download-calendar.ps1 `
  -Sources bls,ecb,finance_calendar `
  -From 2020-10-01 `
  -To 2026-10-21 `
  -Resume
```

The command caches HTTP responses, preserves exact HTML/JSON payloads, normalizes Eastern and Europe/Berlin schedules to UTC, reconciles equivalent events, and writes `reports/data-quality/P03-calendar-coverage.json`. A non-null official time always wins a conflict; conflicting source times remain recorded on the event.

Finance Calendar requires visible attribution if its data is displayed: link to [financecalendar.com](https://www.financecalendar.com). It is a breadth/value cross-check, not the authoritative clock.

## Recent and historical headline metadata

Recent multi-feed sample:

```powershell
pwsh -NoProfile -File .\scripts\download-news.ps1 `
  -Sources gdelt,federal_reserve,ecb,coindesk,cointelegraph,decrypt `
  -From 2026-10-20 `
  -To 2026-10-20 `
  -Resume
```

Full GDELT metadata history after the public service cooldown:

```powershell
pwsh -NoProfile -File .\scripts\download-news.ps1 `
  -Sources gdelt `
  -From 2020-10-01 `
  -To 2026-10-21 `
  -Resume
```

GDELT uses one UTC-day window at a time and waits at least five seconds between uncached calls. Expect roughly three hours for 2,212 daily windows before retries. A 250-result day is marked saturated in the output; it is not silently called complete. GDELT use/display must cite and link to [The GDELT Project](https://www.gdeltproject.org/).

## Outputs

```text
data/bronze/_raw/calendar/<source>/year=YYYY/month=MM/*
data/bronze/calendar/<SOURCE>/event/year=YYYY/month=MM/*.parquet
data/bronze/_raw/news/<source>/year=YYYY/month=MM/*
data/bronze/news/<SOURCE>/headline/year=YYYY/month=MM/*.parquet
reports/data-quality/P03-*-coverage.json
```

Raw payloads are content-addressed and never edited. Normalized snapshots include standard P02 manifests. Repeated unchanged responses are cached/skipped; a parser change produces a new immutable normalized snapshot rather than overwriting evidence.

## Disabled sources

- `finnhub`, `cryptopanic`, and `newsdata` report `disabled_missing_key` and make no request when their environment key is absent.
- Fair Economy live storage is disabled under D-0015 until automated-use/reuse terms are verified.
- Live FRED remains disabled under D-0011.

## Troubleshooting

- GDELT HTTP 429: wait for cooldown and rerun the same command with `-Resume`; do not shorten the five-second gate.
- A feed format error: the affected source fails independently; inspect its preserved raw payload and update fixtures/parser before accepting it.
- Missing calendar month: inspect the coverage report and source warnings. Do not synthesize an event.
- Duplicate headlines: identity is based on normalized headline text; the earliest deterministic publisher/link record is retained in the reconciled snapshot.
