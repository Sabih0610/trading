# Run the P09.5 offline simulation

This command demonstrates mechanics with synthetic fixtures and no API keys. It reuses the causal
feature engine, risk policy and append-only journal; it also exercises the existing Spot backtester.
Its prices, contracts, profits and losses are examples, not historical market evidence.

From the repository root with uv on PATH:

```powershell
uv sync --locked
.\scripts\run-alignment-smoke.ps1
```

For the local uv bootstrap installed during this phase:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.paper.smoke
```

Outputs are `reports/safety/P09.5/P09.5.json`, synthetic input JSON, a checksum manifest and ignored
SQLite journals. Rerunning appends journal rows; it does not mutate earlier evidence. Use a fresh
`--output-root 'work/fresh smoke'` to obtain a fresh journal. JSON summaries reproduce deterministically.

## Interpret the examples

- BTCUSDT with 100 USDT: a synthetic profitable Spot round trip.
- EURUSD with $10,000: a funded synthetic FX contract round trip.
- XAUUSD with $10,000: a severe synthetic gap, actual loss beyond the planned stop and a peak halt.
- XAUUSD/EURUSD with $100: minimum lot cannot be fully funded; no simulated entry.
- Legacy Spot replay: original backtester closes on a protective circuit breaker after a gap.

The all-in planned risk budget is 0.5%; a gap can exceed that planned loss. Liquidation equity
includes entry fees already deducted and estimated exit fees/slippage. Daily loss halts at 2%,
peak drawdown at 5%, one simultaneous position, and gross notional never uses borrowed funds.
Daily halts reset at UTC rollover; a peak halt remains latched. `SafetyState` can serialize that
latch for a future persistent runner. This bounded replay does not implement a continuous process.

## Missing data and permissions

The simulator requires explicit contract size, lot/tick/pip rules, costs, currencies, timestamps
and source. Contract metadata expires after 24 hours; quotes/conversions after 60 seconds against
the replay event clock. These are conservative research defaults, not verified broker settings.
Unfilled candidates expire after 60 seconds, so a gap in quote delivery cannot revive an old signal.
Invalid marks raise an error instead of pretending to liquidate at a stale price. A future live
reader must use its receipt clock and its own reviewed freshness policy.

Real 2025+ historical replay is refused by this runner. The existing guarded evaluation path
continues to require `--final-test` and an access log; this phase never invokes it. Fixture runs
are labelled synthetic and provide no empirical trial count. Binance XAUT cannot have pre-2025
history; see `config/research.yaml` and the P09.5 research assessment.

There is no external order gateway or independently certified instrument. XAUUSD/EURUSD remain
blocked by the original Spot guard. Their extra permission is limited to separate local research.
Paid AI providers remain disabled. No credentials are needed for this guide.
