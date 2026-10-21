# P05 research — deterministic causal feature engine

Research date: 2026-10-21 UTC. Installed runtime: Python 3.12 and Polars 2.0.0.

## Questions

1. How can batch and streaming paths be made exactly equal rather than merely similar?
2. When does a swing or structure event become knowable without future leakage?
3. Which operational definitions make BOS, CHoCH/MSS, sweeps, gaps, and order-block proxies testable?
4. Which order-book quantities can be reconstructed safely from Binance Spot inputs?
5. How should unavailable DXY, yields, and historical book inputs appear in Gold?

## Evidence and choices

| Topic | Evidence / alternatives | Decision |
|---|---|---|
| Rolling causality | Polars row windows include the current row and preceding rows by default; centered windows use later rows and are therefore unsuitable. Native expressions are faster, but a separately implemented batch graph can drift from streaming. | Make one bar-by-bar state machine authoritative. The batch API accepts/returns Polars frames but feeds rows through that same state. Never use centered windows. |
| Online statistics | Welford's recurrence is a stable one-pass mean/variance method. Fixed-window indicators additionally need bounded queues and deterministic removal. | Use explicit bounded state and recurrence formulas; retain a reference recomputation test where removal is involved. |
| Swings | TradingView defines a pivot high/low using lower highs/higher lows on both sides. A right-side requirement means the point is unknowable until those later bars arrive. | Default `left=3`, `right=3`; publish a pivot for bar `t-3` only at bar `t`, with `confirmation_delay=3`. No retroactive value is exposed on earlier rows. |
| Structure vocabulary | BOS/CHoCH/MSS and order blocks do not have one scientific standard; online descriptions disagree about wick versus close and motive. Treating narrative intent as fact is unsafe. | Freeze project definitions: a close beyond the latest confirmed swing is a break; same-direction continuation is BOS, first opposite break is CHoCH/MSS. The last opposite-color candle before the break is explicitly labeled an approximation, not institutional intent. |
| Sweep | At the instant a level is exceeded, a sweep and a sustained break are indistinguishable. A reclaim observation is required. | Candidate when wick exceeds a confirmed swing; confirm only if close re-enters within 3 completed bars. Store direction and lag. |
| Three-bar gap | A commonly used operational definition is non-overlap between candle 1 and candle 3 wicks. Claims about unfilled institutional orders are not observable from bars. | Bullish when current low exceeds high two bars earlier; bearish vice versa. Require size at least 0.25 of the prior known ATR. Track subsequent partial/full fill causally. Call it an FVG-shaped price gap, not proof of hidden orders. |
| ATR / EMA | Wilder ATR uses true range and recursive smoothing after an initial window. EMA is also recursive, but libraries differ on seeds and adjustment. | Specify seeds exactly: ATR-14 starts after 14 true ranges with their mean, then Wilder recurrence; EMA starts at first close with `alpha=2/(n+1)`. |
| VWAP / sessions | Session measures are cumulative until the relevant window closes. Using the final session range earlier in that session leaks information. | VWAP is cumulative typical-price × volume divided by volume per UTC trading-day ID. Asia high/low are running values during Asia and frozen only afterward; London/NY opens appear on their first observed bar. |
| Book features | Binance Spot depth updates include update IDs and require a snapshot plus buffered replay to maintain a local book. Queue imbalance research supports explicit bid/ask-size ratios; a simple size-weighted quote is not the full model-estimated Stoikov microprice. | Define spread, depth within ±bps, top-level imbalance, weighted quote, and trade-flow imbalance. Name the weighted quote accurately. Historical bar partitions expose nullable fields plus `book_available=false`; no invented values. |
| Macro inputs | D-0016 blocks an exact DXY replica; D-0011 blocks current FRED use. | Emit nullable `usd_index_change` and `yield_change` with availability flags. Do not substitute a generic basket under a protected name. |
| Event proximity | A future calendar schedule may be used only if the schedule itself was already known. | At bar `t`, consider only high-impact rows with `known_at <= t` and `timestamp_utc >= t`; return nonnegative minutes or null. |

## Initial feature contract

Every `FeatureSpec` declares a stable name, version, required columns, lookback bars, confirmation
delay, native timeframe, and whether missing live-only input is allowed. Version changes are part of
the Gold manifest, so a definition change invalidates dependent partitions.

The first implementation will use completed OHLCV bars only and produce: true range/ATR-14,
realized log-return volatility, EMA-20/50 and normalized slopes, confirmed swings, BOS/CHoCH,
sweep/reclaim state, ATR-filtered three-bar gaps and fill state, cumulative session VWAP and session
levels, event proximity, basis rolling z-score, nullable macro changes, and nullable book fields.

## Risks and mitigations

- **Warmup ambiguity:** encode null until each definition's stated minimum history is satisfied.
- **Gap contamination:** reset continuity-dependent state after a timestamp gap larger than one
  native interval; keep slower structural history only when the contract explicitly allows it.
- **Floating drift:** batch is a wrapper over streaming state, and tests compare null masks plus
  values at tight tolerance.
- **Subjective names:** documentation states project definitions and never presents a bar pattern as
  proof of participant intent.
- **Performance:** process one Gold partition at a time, carry only declared bounded state, and
  avoid materializing the full six-year universe on the 16 GB host.

## Sources

- [Polars expression reference](https://docs.pola.rs/api/python/stable/reference/expressions/) — rolling-window inclusion, `min_samples`, centered behavior, and native expression guidance; accessed 2026-10-21.
- [Polars rolling-window guide](https://docs.pola.rs/user-guide/transformations/time-series/rolling/) — time-window boundary semantics; accessed 2026-10-21.
- [TradingView Pivot Points High Low](https://www.tradingview.com/support/solutions/43000589195-pivot-points-high-low/) — left/right-bar pivot definition; accessed 2026-10-21.
- [Binance Spot WebSocket streams](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams) — depth streams, update IDs, book ticker, aggregate trades, and local-book synchronization; accessed 2026-10-21.
- [Welford, Note on a Method for Calculating Corrected Sums of Squares](https://doi.org/10.1080/00401706.1962.10490022) — one-pass variance recurrence; accessed 2026-10-21.
- [Gould and Bonart, Queue Imbalance as a One-Tick-Ahead Price Predictor](https://arxiv.org/abs/1512.03492) — explicit bid/ask queue imbalance and next-move evidence; accessed 2026-10-21.
- [Cont, Kukanov, and Stoikov, The Price Impact of Order Book Events](https://arxiv.org/abs/1011.6402) — order-flow imbalance construction and depth relationship; accessed 2026-10-21.
- [Liquidity Sweep Trading, fair value gap definition](https://liquiditysweeptrading.com/learn/fair-value-gap/) — representative three-candle wick non-overlap definition plus explicit warning that a chart cannot prove unfilled orders; accessed 2026-10-21.
- [P04 research and D-0016](P04-research.md) — exact DXY licensing boundary and point-in-time alignment; accessed 2026-10-21.
