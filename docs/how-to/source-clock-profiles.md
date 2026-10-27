# Source-clock profiles and read-only feed assessment

P11a.2 can inspect current sources without fixing their times or placing orders.
MetaQuotes-Demo's configured clock profile is UNVERIFIED; no three-hour correction is installed.
The optional OANDA Practice reader is offline-tested; actual access is unverified and disabled.
Both instruments remain NO-GO for P11b.

From the repository root in PowerShell:

```powershell
& '.\work\tooling\Scripts\uv.exe' sync --locked
& '.\work\tooling\Scripts\uv.exe' run --locked pytest -q
& '.\work\tooling\Scripts\uv.exe' run --locked --extra mt5 python -m tb.ingest.assessment --samples 5
.\scripts\run-dashboard.ps1
```

Assessment permits one to five explicit diagnostic attempts per instrument; no extended collection option or orders. It uses the already running, authenticated, pinned demo terminal and existing four-tool MCP proxy. It writes a unique `reports/mt5/P11a.2-*.json` with a public source/config fingerprint and reuses Bronze/SQLite/checksums for raw quarantine. A new immutable dashboard snapshot adds clock status/raw-vs-normalized diagnostics and per-instrument NO-GO. Prior phase reports and observations are unchanged. Exit success means reporting, not qualification. No MT5/keys: clear unavailable report; use offline tests instead.

`config/source_clocks.yaml` contains public profiles. A reviewed profile needs exact provider/broker/server/environment/build/instrument scope, semantics, effective dates, verified conversion/DST rule and authoritative evidence hashes. VERIFIED additionally needs a reviewer, at least three independently checked samples spanning ten seconds, two UTC references, at most two seconds residual, supported data kinds and refresh/expiry conditions. Changing a status field or measuring a stable offset cannot supply missing evidence. Do not edit risk/eligibility to clear a data gate.

Normalization preserves the raw clock and attaches normalized UTC/profile digest. Overlapping UTC rule periods, ambiguous local folds, missing spring intervals, dates outside verified coverage, expiry, identity/build/instrument mismatch or unexpected source shifts are refused. A new profile does not rewrite old files or reset dedup. Backfills remain historical, and existing 2025+ locks remain enforced.

The generic collector now evaluates instrument admission independently. A valid EURUSD may be collected while XAUUSD is unavailable; common host UTC, identity or security failure blocks both. Extended observation remains bounded by existing finite duration/poll/storage limits. Polling never proves complete tick coverage. A verified profile is one prerequisite, not P11b or strategy approval.

OANDA variables are optional names only: `OANDA_PRACTICE_TOKEN`, `OANDA_PRACTICE_ACCOUNT_ID`, stored only in ignored root `.env`. Do not paste credentials into chat, commands or reports. No genuine alternative credentials were present. The adapter also requires provider-confirmed Pakistan demo/API access without funding, reviewed storage rights, unexpired authorization and a genuinely verified clock profile. These conditions are not inferred from credentials. Only GET summary/instruments/pricing/bounded completed bid candles are implemented; host is fixed, redirects/environment proxies disabled. Its contract method always refuses sizing until independent costs/constraints exist. There is no auto-registration or subscription path.

Smallest external unblock: obtain authoritative MetaQuotes-Demo SDK tick/candle timezone/DST semantics for the exact server/build, or ask a candidate provider to confirm current Pakistan data-only demo access, no funding and storage/API rights. Do not send messages or create accounts automatically. Current XAUUSD is selected but hidden again; owner may manually show exact XAUUSD if quotes are wanted (Ctrl+U → inspect Gold vs US Dollar → Show). GOLD stock is not a substitute. Visibility alone cannot fix the clock-profile blocker.

After evidence review, a separately supervised qualification should measure valid quotes, unique updates/spreads, manifests/recovery and two completed M5 intervals where possible; sustained duration and interval gaps must be explicit. No P11b runtime, EA or external order functionality is part of this guide.
