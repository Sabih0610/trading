# Current handoff — P11a.3

P11a.3 is complete. Twelve Data Basic EUR/USD and XAU/USD each qualified four prospective
completed M1 midpoint candles. This is bounded source-data qualification only. No executable
bid/ask, realistic paper fills, permanent archive/display license or 24h reliability is qualified.
P11b remains unstarted; no external orders, EA, paid upgrade, new MT5 account or MCP expansion.

- Branch codex/p11a-3-twelve-data, parent44a4c4d, local completion tag phase-P11a.3-done.
- Baseline523 tests preserved. Final582 passed,3 live deselected,23 existing warnings in63.03s.
  Ruff/313 formatted files/strict MyPy119 source files clean; paper safety smoke passed.
- Actual Basic access confirmed independently for EUR/USD Physical Currency and XAU/USD
  Precious Metal. No paid upgrade. Forex metadata omitted exchange_timezone; preserve null,
  explicit UTC request and raw bar-open strings. No offset/profile promotion.
- Bounded run2026-10-23 18:13:23-18:18:46 UTC, six polls, now stopped. Each symbol18 parsed
  rows,10 duplicates,8 unique:4 original backfill and4 newly completed forward M1 openings
  18:14-18:17 UTC. Publication/receipt lag41.879-102.683s after end. Finality/revisions unknown.
- Initial exchange_rate timestamps were~114-116s old and rejected as point observations.
  No executable bid/ask, spread, commission, volume or broker sizing facts manufactured.
- Final Cloudflare/Microsoft UTC checks passed. Closing official usage18:20:51 UTC reported
  Basic 8/minute,800/day; current_usage1,daily_usage20. Local conservative reservations21.
- Optional SecretStr TWELVE_DATA_API_KEY exists ONLY in ignored root .env with current-user
  ACL. Do not print it. No key in URLs/logs/reports; no price data in committed docs.
- New GET-only client allows only fixed-host usage, timestamped reference-rate and bounded
  M1 time-series shapes for two exact symbols. Persistent credits/cache/cooldown survive
  restart; no inline retries, redirects, inherited proxy, scheduler, or write endpoint.
- Existing FeedStore/classifier/lease/manifests/atomic recovery reused. New coverage per run;
  dedup resumes. Incomplete intervals labeled/backfill, missing volume stays unavailable.
  Legacy IDs and old files untouched. Source-specific copies revalidated before storing.
- Dashboard localhost8501 -> Market Feed -> Genuine market observations -> Twelve Data Basic
  (reference). Price field withheld under Basic non-display policy; UTC/freshness/counts/status
  shown independently from account P&L. Restart Streamlit after schema changes if hot reload
  retains old classes. Current dashboard restarted; collector remains stopped.
- Original MT5/OANDA config and MetaQuotes-Demo UNVERIFIED profile unchanged. Default locked
  sync removed optional MT5 SDK for offline checks; SDK5.0.6231 restored afterward with the
  existing locked extra (uv sync --locked --extra mt5), preserving baseline MT5 availability.
  Historical2025+ holdout stays locked; no history evaluation or model training occurred.
- Remaining: independent review; confirm raw retention, private display and any commercial/ML
  data rights. Basic cannot support two M1 calls/minute continuously (2880/day >800).
  Future reference M5 budgeting could fit576/day plus checks, but is not implemented.
- Recommended next authorized step: supervised reference shadow consumer of committed Silver
  events with causal features/risk veto logging and durable failure/restart tests. No fills/P&L
  until licensed broker bid/ask and contract/cost/session/funded eligibility are established.
  Do not begin P11b without a new owner request. No push/PR; original audit remains untracked.

Read reports/phases/P11a.3.md; docs/research/P11a.3-research.md;
docs/adr/0010-reference-market-data-boundary.md; docs/how-to/twelve-data-feed.md;
docs/journal/P11a.3-journal.md; docs/P11b-proposal.md.

Genuine evidence remains ignored/local: reports/market_feed/twelve_data/
snapshot-3a2b0458a507481491eeff47a34ac1dd.json, SHA256
c532e116087779fadd4ac3b0514c9b722042b91cd14ee38f5c99c5d06b95da78.
Raw/checkpoint/credits under data/*/twelve_data; no public redistribution permission inferred.

From repository root in PowerShell:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked pytest -q
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.twelve_data.collect --polls 6
.\scripts\run-dashboard.ps1
```

Collection consumes credits and starts new forward coverage; downloading history cannot
recreate this sample's qualification. Missing key cleanly disables the component. Stop here.
