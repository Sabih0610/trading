# P03 — Economic calendar and news: intensive research + PowerShell multi-source downloaders

Follow `prompts/_PROTOCOL.md`. This phase is research-heavy: spend real effort comparing sources.

## Goal
(a) A history of high-impact US/global events for 2020-10 → today with scheduled times in UTC,
(b) a live weekly calendar feed, (c) a news headline archive plus live feeds for gold, macro and
crypto — all downloaded by PowerShell scripts from MULTIPLE independent streams, deduplicated,
and stored in Bronze. Keyless sources first; keyed sources are wired but disabled until keys exist.

## Candidate sources to research, verify and compare (terms of use, robots.txt, history depth,
## timezone handling, reliability). Seed list in `docs/research/SOURCES_SEED.md`.
Calendar:
- Official schedules: BLS (CPI, NFP), BEA (GDP, PCE), Federal Reserve FOMC calendar and statements,
  EIA weekly petroleum report schedule, ECB press releases. These are the ground truth for times.
- ForexFactory/Fair Economy weekly JSON feed (current week only; no actual values in the free feed).
- ForexFactory calendar pages by date range (public pages; check terms; polite rate limits).
- Nasdaq economic calendar (date-range history), FRED/ALFRED release dates (key later).
News:
- GDELT 2.0: DOC API (rolling ~3 months, 1 request per 5 s) for recent; GKG/event 15-minute files
  for history — stream-filter by themes/keywords (gold, Fed, inflation, oil, bitcoin) and discard the rest.
- RSS: central banks (Fed press releases), gold/metals outlets, FX/macro outlets, crypto outlets
  (CoinDesk, Cointelegraph, Decrypt, The Block). Verify each feed URL works.
- Free crypto news aggregators with archives (verify quality and licence before use).
- Keyed later (disabled now): Finnhub, CryptoPanic, NewsData.io.

## Build
1. `docs/research/P03-research.md`: comparison table (source, type, history, latency, limits,
   timezone, terms, reliability, cost), the chosen primary + backup per need, and why.
2. `scripts/download-calendar.ps1` and `scripts/download-news.ps1` (parameters -From -To -Sources
   -Resume), calling Python modules in `src/tb/ingest/calendar/` and `src/tb/ingest/news/`.
3. Normalized schemas: CalendarEvent(event_id, name, country, currency, importance, scheduled_utc,
   actual, forecast, previous, source, source_url, fetched_at) and NewsItem(id, headline, source,
   url, published_utc, fetched_at, topics, language, raw_hash). Keep raw payloads in Bronze.
4. Cross-source reconciliation: the same event from several sources is merged; time conflicts are
   flagged and the official schedule wins. Headlines deduplicated by normalized text hash.
5. Respect robots/terms; identify with a clear User-Agent; cache responses; never hammer sites.

## Scenarios to self-test
Source down → backup used · conflicting times between sources · DST transitions (US vs UK) ·
feed format changes (schema validation fails loudly) · duplicate headlines across outlets ·
GDELT rate limit · non-English headlines · historical gaps reported in a coverage report.

## Acceptance
Coverage report for 2020-10 → today (events per month, missing months, source mix); live feeds
pulled successfully once; offline tests with fixtures; report written.
