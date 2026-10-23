# Current handoff

P11a is complete on codex/p11a-mt5-read-only from verified P10 a553490.
Local phase tag: phase-P11a-done. Stop here: P11b is not started; proposal only.

- Final gates: exact uv sync --locked passed and removed optional MT5 SDK. Full tests without it:
  **445 passed, 3 live deselected, 23 existing warnings, 62.39s**. Ruff/format clean (279 files),
  strict MyPy clean (106 source files), P09.5 smoke passed. Optional SDK 5.0.6231 restored afterward.
- Native Terminal MCP Build 6281 and MetaQuotes demo identity verified. 107 captured native input
  schemas, sanitized diagnostic JSON and phase report are in reports/mt5/ and reports/phases/P11a.md.
  MetaEditor not listening; hosted Market Data returned unauthenticated HTTP 401. Their authenticated
  tools remain unverified. Do not reuse the terminal token for a different endpoint.
- Installed ignored .codex/config.toml exposes exactly four reads through fixed stdio proxy.
  Restart Codex to attach; current chat catalog is not hot-reloaded. Real proxy tool list/time
  read passed. Token, demo pins and executable path only in ignored .env, current-user ACL.
- Native MT5 MCP trading permission is still true. The proxy cannot forward trading/shell/account
  changes; owner should also disable native AI/MCP Trading and dangerous shell operations in MT5.
  No native setting, account, symbol visibility or order was changed during this phase.
- Genuine EURUSD metadata is verified, but source epoch is about +3h relative to receipt UTC.
  Quotes are rejected/raw-only quarantined, not shifted. XAUUSD metadata identifies a real XAU/USD
  contract but hidden quotes are unavailable. GOLD is stock on this server. Zero qualified forward
  quotes/candles; no price reliability or strategy performance claim.
- Data-only collector is finite and stopped. Read-only dashboard runs at http://127.0.0.1:8501;
  select Market Feed, then genuine or explicitly synthetic evidence. Account P&L stays separate.
- Read docs/how-to/mt5-market-feed.md and docs/P11b-proposal.md before future work. Reuse shared
  features/risk only after source clock, metadata/cost/session/eligibility and review gaps resolve.
  Historical 2025+ protections remain unchanged; forward namespace is isolated from old ingestion.
- Current acquisition commands from repo root:
  uv run --locked python -m tb.ingest.mt5.smoke
  .\scripts\collect-mt5.ps1 -Polls 2
  .\scripts\collect-mt5.ps1 -Offline -Polls 2
  .\scripts\run-dashboard.ps1
- No 24/7 job or P11b paper runtime installed. Capacity/retention and native-call hang supervision
  need measured review before a separately authorized soak. No external orders or paid AI calls.
- Original supplied audit remains untouched/untracked. P11a independent review is queued;
  previous reviews/deferrals are not broker-routing approval. No push or PR was requested.
