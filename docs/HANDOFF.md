# Current handoff — P11b.1

Completed offline 2026-10-25 01:11 UTC on `codex/p11b-1-broker-quotes`; parent 15f9a80a16c843a5c3c95a286402f3846adbda49,
application baseline e537d563c151f548bdf983652cf25114172e5ac2/tag phase-P11b.0.1-done.
[Report](../reports/phases/P11b.1.md), [research](research/P11b.1-research.md),
[ADR0013](adr/0013-read-only-broker-quote-evidence.md), [how-to](how-to/broker-quote-research.md),
[journal](journal/P11b.1-journal.md). Independent review queued. **P11b.2 NO-GO; not implemented.**

- cTrader is an optional official JSON/WebSocket candidate behind BrokerQuoteSource. Fixed demo
  endpoint; returned SCOPE_VIEW, single pinned demo account/token/broker, exact symbol assets and
  documentary access/clock/rights required. No order/gateway/EA/account creation or paid service.
- No cTrader credential fields or suitable OANDA pair are configured. No new genuine provider call
  occurred. Actual account, OAuth scope, bid/ask, contracts, costs, resident/legal/Shariah status
  and funded minimum remain unverified independently for EURUSD/XAUUSD.
- Owned ten-event demo: 5 raw/4 quotes/4 observation links per symbol, zero execution state. Raw
  side clocks/receipt/values preserved; partial updates do not refresh the opposite side. All
  prices/minimum notional are labelled fixtures. Genuine reference alignment stays rights-blocked.
- Existing FeedStore, Bronze/Silver manifests, DecisionLedger and OS lease reused. Data/checkpoint/
  ledger append atomically with FULL sync and hash chain. Crash/duplicates/restart/source/rights/
  corruption tests pass; closed mock sources cannot reconnect into a real socket.
- Owned code digest 76169873c7ca996a04c4ecced6a6d5f3482c59dff92a11f5124ff39cff63b732.
  Study: `work/p11b1/owned-broker-study-76169873c7ca/`. Public pointer in ignored
  `reports/broker_quotes/fixture/current.json`; snapshot byte SHA256
  01809f0ecb6247d31b7ebaa3e41e45654a9d28a8fc14c711b76224944494dfd3. Old development studies
  remain separate; new source pin refuses existing genuine-store reuse, no silent migration.
- Fixture EURUSD 1000 units/ 1100.02000 USD and gold 1 unit / 2400.2 USD already exceed $100 before costs.
  These are illustrative owned values, not broker defaults/current prices. Actual cost totals,
  actual broker minimum capital, economic tick/product/profit/freeze/calendar facts remain unknown.
  Readiness states and legal/Shariah review stay independent; no simulator or risk approval.
- Active Twelve Data rights/risk/assets unchanged. New broker access/rights examples approve
  nothing; no active policy was installed. Documentary hashes/expiry/retention required; private
  display independent. No provider message, financial agreement, automatic deletion or 24/7 task.
- Full mandatory gates: 758 passed/3 optional live deselected/23 existing warnings in 133.02s;
  Ruff/376-file formatting/strict MyPy (148 sources) and existing default paper safety smoke pass.
  Baseline 685 passed in 199.86s. 73 new broker tests; all offline. Optional MT5 5.0.6231 was restored
  after default gates; final checks are recorded in the journal. No native initialization.
- Existing genuine M1 snapshot still c532e116087779fadd4ac3b0514c9b722042b91cd14ee38f5c99c5d06b95da78;
  all 16 prior genuine batches/files match hashes. Native MCP restrictions and original clock
  profiles remain unchanged/unverified. Locked 2025+ historical observations were not evaluated.
- Dashboard adds read-only broker readiness/alignment in Market Feed and Shadow Research.
  Three inspected PNGs in `reports/screenshots/P11b.1/`. No P&L or broker buttons.
- Next exact step: independent phase review; owner establishes genuine demo/app/accounts-only
  authorization and documented access/clock/usage/financial/eligibility facts. Then separately
  review any bounded read-only smoke. Do not automatically run it or start P11b.2/A1/A2.
- No push/PR. Original owner audit remains untracked and untouched. All broker clients/writers
  are closed; no scheduler or background collector. The temporary screenshot server was stopped.

Safe commands from repository root (PowerShell):

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.broker.cli status
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.broker.cli owned-demo
.\scripts\run-dashboard.ps1
```

Default uv sync/run omits the optional MT5 package; after required default gates, restore the
existing extra only with `uv sync --locked --extra mt5` and do not initialize a terminal. Genuine
broker smoke prerequisites/limits are in the how-to; there is no execution or 24/7 command.
