# P03 journal — Calendar and news

P03 is researching and building multi-source, terms-aware economic-calendar and headline ingestion. Official schedules will remain authoritative for event timing; keyless live sources are preferred, while credentialed integrations remain disabled without keys.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 01:03 UTC | Context | Read P03, the P02 report, source seed list, state/handoff, and checked for review blockers. | `prompts/P03-calendar-and-news.md`, `reports/phases/P02.md` | P03 started; no blocking review exists. | — |
| 2026-10-21 01:08 UTC | Research | Audited official BLS/BEA/Fed/EIA/ECB schedules, structured calendar candidates, GDELT, and live RSS endpoints. | `docs/research/P03-research.md` | Official-time precedence, metadata-only news, and terms-gated sources selected. | D-0013–D-0015 |
| 2026-10-21 01:19 UTC | Build/test | Added strict calendar/news models, deterministic IDs, official-source reconciliation, BLS/ECB/Finance Calendar parsers, safe RSS/Atom parsing, and GDELT metadata parsing. | `src/tb/ingest/calendar/`, `src/tb/ingest/news/` | 11 focused tests pass; strict mypy clean across 36 source files. | D-0013–D-0015 |
| 2026-10-21 01:19 UTC | Build | Added immutable raw/snapshot storage, HTTP caching, gap/source-mix coverage reports, calendar/news CLIs, and PowerShell entry points. | `src/tb/ingest/content_store.py`, `coverage.py`, `http_cache.py`, both CLIs/scripts | Offline fallback, cache, resume, DST, schema drift, dedup, and missing-key scenarios pass. | D-0013–D-0015 |
| 2026-10-21 01:20 UTC | Live calendar | Downloaded the full target period from permitted BLS, ECB, and Finance Calendar sources, then reconciled and reported it. | `scripts/download-calendar.ps1 -From 2020-10-01 -To 2026-10-21 -Resume` | 522 events; all 73 target months covered; source mix BLS 384, ECB 47, Finance Calendar 103. | D-0013 |
| 2026-10-21 01:20 UTC | Live news | Pulled a bounded 2026-10-20 RSS/GDELT sample and deduplicated the permitted feeds. | `scripts/download-news.ps1 ...` | 56 unique headlines from CoinDesk, Cointelegraph, Decrypt, and ECB. GDELT returned HTTP 429 and was recorded as a source warning. | D-0014 |
| 2026-10-21 01:20 UTC | Final gate | Ran the complete offline gate and unified Bronze validation. | Ruff, format, mypy, pytest, Bronze validator | 106 tests passed, 3 live deselected; 41 source files type-clean; 125 Parquet files and 12,673,099 rows passed with zero issues. | — |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 01:20 UTC | Reconciled live calendar snapshot failed after source snapshots succeeded. | Polars inferred a null-only `actual` column from its first 100 rows, then encountered a later string. | Infer the schema across the complete bounded metadata snapshot; keep partition-at-a-time behavior for market data. | Added a 120-row late-non-null regression test. |
| 2026-10-21 01:20 UTC | Finance Calendar initially yielded only four usable events. | Some valid records had neither official `source_url` nor event-page `url`, and strict parsing rejected each affected response. | Retain the documented API attribution URL as the provenance fallback while preserving official URLs when present. | Parser fixture now covers null source links. |
| 2026-10-21 01:20 UTC | GDELT live sample exhausted bounded retries with HTTP 429. | The public DOC service throttled this host after research probes. | Kept five-second gating and fail-loud warnings; other independent RSS streams completed. Historical GDELT remains pending cooldown. | Existing 429 retry and source-fallback tests cover behavior. |
