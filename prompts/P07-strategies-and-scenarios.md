# P07 — Strategies A/B/C, scenario library and stress tests

Follow `prompts/_PROTOCOL.md`.

## Goal
Implement the first strategies as plug-ins, test them on 2020-10 → 2023-12 (train) and 2024
(validation) using XAUUSD history (and XAUT where available), and build the reusable scenario library.

## Strategies (long-only)
- **A — London sweep → MSS → FVG:** Asian range (00:00–07:00 London), sweep of the Asian LOW reclaimed
  within N bars during 07:00–10:00, bullish structure shift, limit entry at FVG edge/mid, stop
  beyond sweep − buffer×ATR, target R-multiple, flat by end of day.
- **B — XAUT catch-up (lead-lag):** when XAUUSD moves up by > k×σ over a short window and the
  XAUT basis z-score shows XAUT lagging, buy XAUT; exit on basis normalization, time stop, or stop.
  Research lead-lag measurement (cross-correlation at lags, Hayashi-Yoshida for asynchronous data).
- **C — Trend pullback to session VWAP:** in an up-trend regime, buy a pullback to VWAP that holds.
Each strategy has a small number of parameters with documented defaults and ranges.

## Scenario library (`config/scenarios.yaml`)
Crash (2020-03), rate-hike pressure (2022), banking stress (2023-03), strong trend (2024–2025 gold
rally, validation only), quiet ranges (auto-selected low-vol windows), news days (CPI/NFP/FOMC),
thin liquidity (holidays, Asian session). Note: anything from 2025-01 onward belongs to the locked
final test and is excluded here.

## Stress tests
Costs ×2/×3 · slippage +n ticks · 1-bar entry delay · parameter perturbation ±20% (robustness
surface, not optimization) · Monte Carlo reshuffle of trade order (drawdown distribution) ·
remove best 5% of trades.

## Build and report
Run all strategies vs all baselines; write `reports/strategies/P07.md` with per-scenario tables and
a clear verdict per strategy: KEEP / REWORK / DROP. Do not tune on validation repeatedly; log every
configuration tried (count of trials is reported).

## Acceptance
Strategies pass unit tests on synthetic patterns that should and should not trigger; results
reproducible from a single command; report written.
