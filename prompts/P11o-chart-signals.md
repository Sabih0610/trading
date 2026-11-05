# P11o: Causal chart-signal library (daily/weekly)

Follow `prompts/_PROTOCOL.md` and the rules in `prompts/MASTER-2026-12.md`. Branch `codex/p11o-chart-signals`.
Evidence basis: [swing research note](../reports/reviews/swing-research-2026-11-05.md). Fixtures only; **no genuine data
in this track.**

## Build (`tb.strategies.signals`, pure functions over completed bars)
1. **Trend filter:** weekly close above its N-week SMA **and** that SMA rising over M weeks; optional daily
   confirmation (close above the 50- or 100-day SMA).
2. **Breakout trigger:** daily close above the prior N-day high (N excludes the signal bar).
3. **Pullback trigger:** within an up-trend, the daily low touches or crosses the 20- or 50-day SMA (or the last
   confirmed swing-low zone), then a daily close back above it.
4. **Pattern trigger (one family):** bullish double-bottom and bull-flag detection by **one-sided** kernel
   smoothing (Lo-Mamaysky-Wang style, but the window ends at the confirmation bar; the original two-sided
   smoother looks ahead and is forbidden). Confirmation means a close above the pattern's neckline or flag high.
5. **Exits:** initial stop = last confirmed swing low − k×ATR14 (or entry − k×ATR14); optional trailing stop
   (chandelier: highest close − k×ATR14); target = R multiple or none; `max_holding_days` ≤ 10 (P11m).
6. **Cost filter (the project's own rule):** take a trade only if the expected move (the distance to target, or
   2×ATR14 when there is no target) is **≥ 5× the round-trip cost**.
7. No candlestick triggers (evidence: no value). News and calendar are a veto only (existing gate).

## Tests
- Property: future bars cannot change any past signal; the pattern smoother is one-sided (a test that injects
  a future spike must not alter earlier detections).
- Unit: a hand-built fixture for each trigger fires exactly where intended.
- The cost filter rejects small-move setups; stops are always below entry; long-only only.

## Done
Gates green; ADR (signal definitions); how-to; phase report `reports/phases/P11o.md`.
