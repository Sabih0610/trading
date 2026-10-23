# Current handoff — P11a.2

P11a.2 is complete as software/research/diagnostic work, NOT DATA-QUALIFIED.
Branch codex/p11a-2-clock-profiles; parent35cf719; local tag phase-P11a.2-done.
EURUSD NO-GO; XAUUSD NO-GO. Stop: P11b unstarted. No orders/EA/paid AI/funding/accounts.

- Final quality:523 passed,3 optional live deselected,23 existing warnings in60.62s; Ruff/format clean, strict MyPy113 source files, paper safety smoke passed. uv sync --locked removed optional SDK for tests; SDK5.0.6231 restored afterward with uv sync --locked --extra mt5.
- Configured MetaQuotes-Demo profile is UNVERIFIED with no offset/DST rule. Clock framework includes exact source/build/instrument scope, authoritative evidence/reviewer, repeated UTC validation, effective periods/history range, DST gap/fold rejection and expiry. Revalidates unchecked-copy state changes before normalization. No automatic profile promotion.
- Normalized observations preserve raw representation/time plus UTC/profile digest/rule/public identity. Old files untouched; raw-based dedup prevents profile-version replay. Existing collector/store/checkpoint/manifest/health are reused, with independent instrument masks and provider namespaces.
- Actual diagnostic2026-10-23 16:51:02–16:51:47 UTC, Build6281/SDK5.0.6231, MetaQuotes-Demo/USD/fingerprint2699de315a80. Native trading false, shell absent, same four MCP tools. EURUSD five raw changing quotes, all+~10800s rejected, zero qualified. XAUUSD selected=true/visible=false, zero raw quotes/five missing attempts. Ten M1 bars per instrument raw-only backfill; no valid M5/continuous coverage or genuine restart reliability proof.
- Microsoft external UTC agrees (+.236522s); Cloudflare unavailable this run; W32Time service/sync unverified. No automatic clock/service edits. SDK/native wall components agree within sequential precision; no authoritative exact-server UTC/DST mapping, controlled build or seasonal test. Do not apply another broker's schedule.
- Optional OANDA Practice GET-only adapter is offline-tested, not genuinely connected. Credentials absent; current Pakistan/division/API/metals/no-funding/storage rights unverified. v20 excludes Global Markets/TMS. Genuine construction requires independent approval evidence and genuine clock proof; fixture transport remains synthetic. No extra dependency.
- Conditional next provider verification candidate: separate Pepperstone MT5 demo, because of published seasonal server-clock and dated official Pakistan affiliate material. Current demo/data-only region/entity/SDK/storage approval, exact server/time contract, rates and coverage remain unverified. No registration/contact/funding was automated.
- Read-only dashboard at http://127.0.0.1:8501 → Market Feed, genuine/synthetic separate. Shows recorded clock state/raw-vs-normalized diagnostics and per-instrument NO-GO; zero invalid price rows. Alternative selection only for actually indexed configured data. Collector stopped. Screenshots reports/screenshots/P11a.2/.
- Costs/pip/session/holidays/stop/conversion and XAUUSD tick-value consistency remain incomplete. EUR minimum funded notional indicatively$1119.58 from rejected ask; current gold price unavailable, prior indicative notional>$100. No sizing or strategy approval;1x/risk/eligibility unchanged.
- Every prior test retained. Existing 2025+ holdout protected; provider forward namespaces excluded from historical readers. Original supplied audit untouched/untracked. Independent review queued; no push/PR.

Read reports/phases/P11a.2.md; docs/research/P11a.2-research.md; docs/adr/0009-versioned-source-clock-profiles.md; docs/how-to/source-clock-profiles.md; docs/P11b-proposal.md. Genuine evidence: reports/mt5/P11a.2-20261023T165147Z-64c15adb.json, including public working-source/config hash and immutable raw/checksum facts.

From repository root in PowerShell:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked pytest -q
& '.\work\tooling\Scripts\uv.exe' run --locked --extra mt5 python -m tb.ingest.assessment --samples 5
.\scripts\run-dashboard.ps1
```

Assessment success means a diagnostic report, not qualification. Smallest external action: provider-authoritative exact-server SDK UTC/DST evidence, or current no-funding regional data-only demo/API/storage confirmation from a candidate provider. Owner may manually show exact XAUUSD again if quote inspection wanted. No new development or P11b until separately requested.
