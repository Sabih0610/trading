# Causal daily/weekly chart conditions

`tb.strategies.signals` is a fixture-tested pure numeric library. It does not load a dataset, select a tradable asset, size a position or send an order. Genuine strategy evaluation remains behind P's separate registration/review.

From a credential-free checkout root (coordinate the test slot when working in parallel):

```powershell
uv sync --locked
uv run --locked pytest -q './tests/unit/test_chart_signals.py' './tests/property/test_chart_signals.py'
```

Create `CompletedBar` values with positive finite Decimal OHLC, UTC midnight boundaries and an exclusive next-day/Monday-week end. Set `complete=False` for insufficient upstream coverage. Use `known_at` if the completed value was published later; every function requires explicit `as_of`. Map N's `timestamp_utc` to `opened_at` and `bar_end_utc` to `closed_at`; preserve source and price-side labels in the adapter. No current incomplete weekly bar may enter a trend condition. For an ended expected-open row without OHLC, construct `HistoryGap` using its UTC boundaries, positive expected minutes and coverage-known-at timestamp. It has no price fields and resets the warm-up prefix. Incomplete positive-OHLC bars also reset history. Expected-zero closed weekends/holidays are omitted and do not reset history. Never silently omit an expected-open all-missing day. N supplies `coverage_available_at` and `history_barrier` for this mapping.

- `trend_filter` returns Boolean weekly trend with optional 50/100-day confirmation.
- `breakout_signal`, `pullback_signal` and `pattern_signal` return a frozen long-only `ChartSignal` or None. There is no quantity or permission field. Its stable `identity` is `(kind, symbol, bar_opened_at)`; consume only a newly completed ID once. Querying later without a new bar returns the same observation and cannot authorize a repeated entry.
- `confirmed_swing_lows` delays each pivot until the specified later bars complete. External confirmed-low inputs need actual confirmation clocks, not pivot clocks.
- `causal_kernel` gives trailing endpoint estimates; future appended values cannot revise an earlier estimate.
- `initial_exit_plan` supplies long stop/optional R target and 1..10-day duration. These are candidate levels; the unchanged RiskManager enforces its own tighter limits.
- `chandelier_stop` only tightens. `chandelier_exit` also reports `close_required=True` when the current executable mark has crossed that stop; do not loosen it to fit a gap. The engine decides actual closing price and risk accounting.
- `round_trip_cost` charges two fees, one full quoted spread and two slippages at a common reference price. Use actual registry inputs and registered stress multipliers, never invented zero costs. `passes_cost_filter` fixes the expected-move hurdle at 5x.

No signal authorizes a fill at the already observed daily low/neckline or at a past price. A later separately authorized caller must wait until confirmation, use the actual next executable observation, retain calendar/news vetoes, and pass deterministic permissions/risk checks.

Troubleshooting: insufficient warm-up, incomplete required windows and nonconsecutive weekly windows return no condition. Invalid UTC clocks, OHLC bounds, duplicate/out-of-order visible bars, mixed symbols or unsupported parameters raise ValueError. Future data is ignored before visible-history checks. Daily calendar completeness belongs to the upstream medallion, not guessed from missing observations here.

Exact definitions/defaults and limitations are in [ADR 0032](../adr/0032-causal-chart-signal-definitions.md); [research](../research/P11o-research.md), [phase report](../../reports/phases/P11o.md).
