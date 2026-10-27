# Offline Paper Lab — operator guide

Run finite software tests on owned synthetic quotes and frozen reference decisions.
The $100 intended account and $10,000 engineering account are separate in every scenario.
No broker credentials, genuine feed, external orders or empirical performance evidence are involved.
P11b.1a remains unfinished in its original checkout; this milestone does not authorize genuine input.

## Run from this checkout root in PowerShell

```powershell
& '.\.venv\Scripts\python.exe' -m tb.paper.offline.cli status
& '.\.venv\Scripts\python.exe' -m tb.paper.offline.cli demo
& '.\.venv\Scripts\python.exe' -m tb.paper.offline.cli demo
```

Status performs no collection or account writes. Demo is finite and uses only the built-in owned
package factory. The second command invocation reconstructs/reconciles prior state and suppresses
all duplicate inputs. No deposit/reset, genuine provider, broker sender or file-to-feed gateway exists.
`--provider` accepts only `owned_fixture`. The optional `--output-root 'work/my owned lab'` selects a
separate owned output root; it does not allow supplying external market data. Such alternate roots
are CLI evidence only; the dashboard reads the default checkout export.

Each of 14 named studies has two accounts. Cases cover rising/declining/sideways markets, EMA and
channel entries, gold reversal, owned-long SELL/target/stop exits, adverse gaps and daily/peak halts,
missed fills/expiry, stale or partial sides and unavailable sessions. Additional automated acceptance
cases cover invalid financial facts, cancellation, risk counts, crashes and competing processes.
These price paths and amounts were designed to exercise branches, not to select profitable settings.

## Inspect the read-only view

```powershell
& '.\.venv\Scripts\python.exe' -m streamlit run '.\src\tb\dashboard\app.py' --server.address=127.0.0.1 --server.port=8502 --server.headless=true --browser.gatherUsageStats=false
```

Open the local dashboard and choose **Offline Paper Lab**, a scenario and a virtual account.
Inspect cash, reserved funds, marked equity, realized/unrealized P&L, fees, adverse adjustment,
positions, intention transition reasons, hypothetical fills and integrity/recovery evidence.
Missing valid exit-side marks display **Unavailable**, not a guessed current valuation. Synthetic
prices and results stay separate from genuine feed, shadow-only and broker diagnostic pages.

The view has no trading, funding, risk editing or reset controls. Changing selectors only changes
what is displayed. Stop this temporary dashboard with Ctrl+C in its own terminal when finished.

## Storage and recovery

Generated owned packages, checksummed input manifests, frozen shared-strategy journal and persistent
paper accounts live under `work/offline_paper/<code-digest-prefix>/<scenario>/`. This folder is ignored
by Git. Raw source timestamps and receipt times are explicit; no historical dataset is opened.
`paper.manifest.json` pins package/contracts, risk configuration and code. `paper.sqlite` reuses
DecisionLedger and commits each input, all account/fill/risk effects and immutable checkpoint in one
FULL-sync transaction. Recovery records are append-only and content-identified. An OS lease allows
one writer per account study. No stale PID bypass or automatic corruption repair exists.

Derived content-addressed snapshots and `current.json` live under ignored `reports/offline_paper/`.
Export follows commit. If export fails, rerun the same command: committed fills cannot be duplicated.
The UI opens SQLite read-only, checks hashes/ledger/checkpoints and independently sums fill cash flows.

If interrupted, close the failed process and rerun the same command. A failed writer is poisoned and
must reopen/reconcile. Do not edit balances, delete checkpoints, clear latches, replace manifests or
copy a database from another source/version. Preserve mismatched/corrupt evidence for review.
Source-code changes choose a separate owned study directory; earlier studies remain archived.
Bounds: at most 2,048 input events per default study, 128 MiB per study, bounded snapshot/input sizes
and minimum free space. Exhaustion refuses progress before a new transaction.

## Execution and accounting assumptions

- BUY can become a funded long intention after the shared risk check; SELL can close owned inventory
  and cannot create an uncovered sale. WAIT has no entry. One pending entry reserves funds.
- Entry uses a fresh subsequent ASK plus configured adverse ticks, exits use BID minus ticks and
  explicit fees. Both sides' source and receipt availability must follow the intention. No same-tick
  or previous midpoint fill. Risk and cash are checked again; changed eligible size is rejected.
- All fills are all-or-none. Synthetic missed-fill flags and 30-second intention expiration are
  explicit. Standing protective rules are established on entry; later quotes trigger stops, targets,
  risk or end-of-day exits. Targets receive no favorable gap improvement. Stops can lose more than
  planned when price gaps past them. Unavailable sessions/quotes cannot guarantee flatness.
- Full principal is debited once; exit proceeds less fees are credited once. Net liquidation equity
  includes exit fees/adverse prices. Spread/adverse-adjustment diagnostics are already embedded in
  prices and are not deducted twice. The Decimal account identity is equity minus initial cash
  equals realized plus unrealized P&L whenever a valid mark exists.
- Fixture EURUSD-style minimum is 1,000 units; gold-style minimum is one unit. They illustrate owned
  contract mechanics, not any actual broker specification or capital recommendation. The $100
  account correctly refuses them. Account B exists only for engineering, not a real funding target.
- Keep current 0.5% planned risk, 2% daily loss, 5% peak drawdown, full funding, position/trade counts
  and stricter instrument limits. Daily rollover is explicit; restart cannot reset either latch.

There is no validated depth, queue position, market impact, real latency or partial-fill model.
No Sharpe, empirical win rate or real-world profitability is inferred. Legal/independent Shariah
eligibility and actual broker costs remain unverified. No strategy optimization or model training.

See [report](../../reports/phases/P11b.2a.md), [research](../research/P11b.2a-research.md),
[ADR0014](../adr/0014-owned-persistent-paper-accounting.md) and [journal](../journal/P11b.2a-journal.md).
