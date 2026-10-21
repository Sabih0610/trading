# P03 research — Economic calendar and news ingestion

P03 needs time-correct event history and a useful headline stream without turning fragile websites into undocumented APIs. The selected design makes official agency schedules authoritative, uses attribution-friendly structured feeds for breadth, stores headline metadata rather than article bodies, and records coverage gaps instead of inventing events.

## Questions asked

- Which sources expose a stable keyless contract, and how far back does it actually reach?
- Which source owns the event time when calendars disagree?
- How should US/EU daylight-saving transitions be converted to UTC?
- Can news metadata be stored and analyzed without copying publisher article text?
- Which apparently public pages disallow or fail to document automated reuse?
- How can six years of GDELT coverage be bounded on a 16 GB machine and limited disk?

## Comparison

| Source | Type | History / latency | Limits and timezone | Terms / reliability | Decision |
|---|---|---|---|---|---|
| BLS yearly schedules + ICS | Official calendar | Year pages verified for 2020–2026; ICS is forward-looking and normally refreshed weekly | Times are US Eastern; PFEI releases are normally 08:30 ET | US government source; stable archived year pages | Primary for US CPI, employment, PPI and selected high-impact labor releases |
| BEA full schedule | Official calendar | Current full-year GDP/PCE/trade schedule; releases link to archives | Times are US Eastern | BEA states its website information is public domain unless noted | Primary for current GDP/PCE; historical archive support remains a coverage task |
| Federal Reserve FOMC calendars / RSS | Official calendar + news | Current page covers 2021–2027; a separate 2020 historical page exists; press RSS is live | Regular decisions are Eastern time; RSS timestamps are explicit | First-party and stable; unscheduled decisions need press-release timestamps | Primary for FOMC schedule and monetary-policy headlines |
| EIA WPSR schedule | Official calendar | Current schedule plus listed holiday exceptions | Normally Wednesday 10:30 ET; exceptions explicit | First-party; narrow scope | Primary for petroleum inventory release times |
| ECB webcast / governing-calendar / RSS | Official calendar + news | Webcast index exposes monetary-policy press conferences back through the target period; RSS is live | Europe/Berlin local time; current decisions 14:15 and conference 14:30 | First-party; stable archives | Primary EU monetary-policy events and headlines |
| Finance Calendar | Structured aggregator | Full file covers 12 months back and 400 days forward; `/history` empirically returned only 12 events for US CPI despite a 2020 start | Keyless 2,000 requests/day/IP; UTC and source timezone included | Free commercial use with visible attribution; cache/storage allowed | Live/global breadth and cross-check only; never overrides official time |
| Fair Economy weekly JSON | Structured aggregator | Current Monday–Sunday only; live endpoint verified | Embedded numeric offsets; no historical contract | Feed is public but governing automated-use/reuse terms could not be verified | Parser fixtures only; no automated stored live use until terms are resolved |
| Nasdaq calendar | Web application | Current page returned no data during the check | Undocumented backing interface | Data terms are licensing/order-form oriented | Excluded from automated ingestion |
| GDELT DOC 2.0 | Open news metadata API | Search supports bounded date windows; article lists return at most 250 per request | Rate-limited; empirical back-to-back calls triggered non-JSON throttling; minimum 5-second gate | GDELT permits unrestricted use/redistribution with attribution | Primary headline archive/live discovery; store metadata and links only |
| GDELT GKG/event files | Open 15-minute bulk data | GDELT 2.0 from 2015; every 15 minutes | Raw archive is extremely large (GDELT reports over 2.5 TB for one recent year) | Same GDELT attribution requirement | Not bulk-downloaded on current disk; DOC windows first, future streaming job only on adequate storage |
| Fed and ECB RSS | Official RSS | Recent live items | Poll slowly with conditional caching | Explicitly published syndication feeds | Primary macro/central-bank live news |
| CoinDesk headline RSS | Publisher RSS | Recent live items; official site advertises the feed | Headline/link syndication; no full article copy | Publisher media kit distinguishes free headline-link feed from licensed full text | Crypto live headline source; headline/link only |
| Cointelegraph and Decrypt RSS | Publisher RSS | Endpoints returned valid XML during the live technical check | Recent feed only | Treat as publisher syndication; retain links, not bodies | Independent crypto live backups |
| Finnhub, CryptoPanic, NewsData.io | Keyed APIs | Provider dependent | Keys/quotas required | Provider terms apply | Wired as disabled capabilities until their environment keys exist |

## Chosen design

1. Official schedules win event-time conflicts. Reconciliation may fill missing forecast/previous/actual values from an aggregator, but it must never replace a non-null official schedule time.
2. Normalize local timestamps with IANA zones (`America/New_York`, `Europe/Berlin`) before UTC conversion. Fixed `EST`, `EDT`, `CET`, or numeric-offset assumptions are not allowed for schedule pages.
3. Keep each fetched payload unchanged under Bronze and write normalized Parquet separately with a manifest. A parser contract change fails loudly and preserves the raw evidence.
4. Calendar identity is a stable hash of normalized event family, country/currency, and scheduled date. Reconciliation allows a bounded time disagreement and records every conflicting source time.
5. News identity is the SHA-256 of Unicode-normalized, whitespace-collapsed, case-folded headline text. Store headline, canonical link, publisher, published/fetched UTC, language, topics, and raw-record hash; never fetch/store article bodies.
6. GDELT requests use date-window pagination with one global request at least every five seconds. Result caps are coverage warnings, never silently interpreted as exhaustive history.
7. Cache and conditional-fetch RSS. Keyed providers report `disabled_missing_key` and make no network request.

## Source contracts verified

### Official calendars

BLS publishes archived schedule pages for every target year and explicitly labels all displayed times as Eastern. Its current dissemination policy says the seven principal federal indicators are scheduled for 08:30 ET and most other national releases for 10:00 ET. BEA's current full schedule includes exact times for GDP and Personal Income and Outlays, and BEA says website material is public domain unless marked otherwise.

The Federal Reserve main calendar currently includes meeting schedules and statement/minutes links for 2021–2027, while the 2020 historical page remains reachable. The Fed publishes first-party RSS feeds including a monetary-policy feed. ECB's webcast index provides monetary-policy press-conference dates throughout the target period, and its governing-council policy page says decisions are published at 14:15 CET and meeting accounts four weeks later. EIA documents the usual Wednesday 10:30 ET WPSR schedule plus holiday exceptions.

### Structured calendars

The live Finance Calendar documentation states 14-country coverage, over 50 release/decision series, a 92-day range limit per calendar call, explicit UTC/source-zone timestamps, 2,000 keyless calls per day, caching permission, and required visible attribution. Its hourly full file covers only the trailing 12 months, not the six-year target, so it is a live/breadth cross-check rather than the historical authority.

The Fair Economy current-week JSON endpoint was reachable and returned offset-aware events with title, currency-like country, impact, forecast, and previous fields. However, the governing terms/robots material was not reliably retrievable during research. A reachable endpoint alone is not sufficient authorization for a stored automated dataset, so only an offline parser boundary will be built until terms are resolved.

### News

GDELT describes its datasets as free for unrestricted academic/commercial/government use and allows redistribution with attribution. DOC article-list output is capped and the service rate-limits load; it is appropriate for a bounded headline/link archive with explicit saturation reporting, not a claim of exhaustive news coverage. GKG is richer but far too large for the current volume.

The Fed and ECB explicitly publish RSS. CoinDesk advertises a headline feed and distinguishes it from licensed full-text feeds. Cointelegraph and Decrypt feed URLs returned XML in the live check. P03 will ingest only syndicated metadata and links; publisher prose/content is out of scope.

## Risks and unknowns

- BEA does not honor a simple `year=` query for historical schedules; older GDP/PCE event coverage needs archive-page extraction or a documented gap.
- Unscheduled central-bank decisions do not fit a regular-calendar parser and must come from official press RSS/archive timestamps.
- GDELT article-list caps can undercount high-volume windows. Coverage reports must mark capped windows and narrow them on rerun.
- RSS formats and namespace choices vary; strict fixture tests and per-feed failure isolation are required.
- Headline language labels are publisher/GDELT metadata, not a locally inferred fact. Unknown must remain `und`.
- Fair Economy and Nasdaq are excluded from live automated storage unless their access terms are clarified.

## Sources

Accessed 2026-10-21 UTC.

- [BLS iCalendar subscription](https://www.bls.gov/help/hlpiCAL.htm) — official ICS URL and update behavior.
- [BLS dissemination policy](https://www.bls.gov/about-bls/dissemination.htm) — official release-time conventions.
- [BLS 2026 release schedule](https://www.bls.gov/schedule/2026/home.htm) — year-page format and Eastern-time declaration.
- [BEA release schedule](https://www.bea.gov/news/schedule/full) — current GDP/PCE schedule and exact times.
- [BEA public-domain FAQ](https://www.bea.gov/help/faq/147) — reuse status and requested attribution.
- [Federal Reserve FOMC calendars](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) — meetings, statements, and minutes for 2021 onward.
- [Federal Reserve RSS feeds](https://www.federalreserve.gov/feeds/feeds.htm) — official syndication catalogue.
- [EIA WPSR schedule](https://www.eia.gov/petroleum/supply/weekly/schedule.php) — standard time and holiday exceptions.
- [ECB Governing Council decisions](https://www.ecb.europa.eu/press/govcdec/html/index.en.html) — publication timing and policy cadence.
- [ECB press-conference webcasts](https://www.ecb.europa.eu/press/tvservices/webcast/html/index.en.html) — historical meeting-date archive.
- [Finance Calendar API](https://www.financecalendar.com/api/) — keyless contract, history horizon, rate limits, attribution, and caching rights.
- [GDELT terms](https://www.gdeltproject.org/about.html) — unrestricted use and attribution requirement.
- [GDELT data access](https://www.gdeltproject.org/data.html) — 15-minute datasets and scale.
- [GDELT DOC 2.0 documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) — query, date, format, and result-limit contract.
- [GDELT rate-limiting note](https://blog.gdeltproject.org/ukraine-api-rate-limiting-web-ngrams-3-0/) — rate behavior and bulk alternative.
- [CoinDesk RSS announcement](https://www.coindesk.com/coindesk-news/2021/09/17/coindesk-rss) — official headline feed.
