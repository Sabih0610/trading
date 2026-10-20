# P05 — Feature engine (shared by backtest and live) → Gold features

Follow `prompts/_PROTOCOL.md`.

## Goal
One deterministic feature library computing all strategy and model inputs, identical in batch
(backtest) and streaming (live/paper) modes, with proven absence of lookahead.

## Research first
- Precise, testable definitions of swing points (fractal/pivot with confirmation delay), BOS,
  CHoCH/MSS, liquidity sweeps, fair value gaps, order-block approximations.
- Incremental/streaming indicator implementation patterns that match batch results exactly.
- Order-book features (imbalance, microprice, spread, depth at ±x bps, trade-flow imbalance).

## Build
1. `src/tb/features/` modules: volatility (ATR, realized vol), trend (EMAs, slopes, HTF structure),
   structure (swings with confirmation lag, BOS, CHoCH/MSS), sessions (Asian range high/low,
   London/NY opens), liquidity (sweep detection with reclaim window), gaps (FVG with ATR-relative
   size, fill status), VWAP (session-anchored), macro (synthetic DXY change, yields change),
   event proximity (minutes to next high-impact event), basis (XAUT vs XAUUSD gap z-score),
   order-book features (live only; placeholders in history).
2. Every feature declares: inputs, lookback, confirmation delay, timeframe, version.
3. A batch API (Polars over Silver) and a streaming API (bar-by-bar state machine). A test asserts
   they produce identical values on the same data.
4. Gold feature tables partitioned by asset/timeframe/month + feature manifest (versions).

## Scenarios to self-test
"Future poisoning" test: append random future bars and confirm past features do not change ·
batch vs streaming equality on 3 months of data · gaps in input · first bars of history.

## Acceptance
All features documented in the data dictionary; equality and no-lookahead tests green; report written.
