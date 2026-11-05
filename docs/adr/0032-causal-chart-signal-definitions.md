# ADR 0032: explicit causal chart-signal definitions

Date: 2026-11-05. Status: fixture implementation; independent review pending.
The owner authorized a daily/weekly swing-signal library, not a strategy or genuine trial. Every condition is deterministic and long-only. No registry permission, RiskManager rule or asset allowlist changes.

## Availability and inputs

`CompletedBar` has one symbol, 1d/1w timeframe, UTC midnight open and exclusive end, positive finite Decimal OHLC, coherent bounds, completeness and optional delayed `known_at`. Weeks open Monday UTC. A value cannot be known before its end. Each call has an explicit UTC `as_of`; availability is filtered before visible-history validation. Visible bars must be strictly ordered, duplicate-free and single-symbol/timeframe.

A visible `HistoryGap` or incomplete `CompletedBar` resets usable history. `HistoryGap` has clocks and positive expected-minute metadata but **no OHLC**, so an all-missing expected-open day needs no fabricated prices. Expected-zero calendar closures must be omitted, never passed as a gap. Future/delayed barriers are unavailable before their own known-at clock; a delayed known barrier also floors subsequent condition availability. Swing support preceding the barrier is excluded from a new pullback. Required windows must warm up again after a barrier. No prices or missing bars are filled. Daily lookbacks count completed trading-day observations supplied by the session-aware medallion; weekly lookbacks additionally require consecutive Monday windows. Warm-up cannot be shortened silently. A signal has stable `(kind, symbol, bar_opened_at)` identity: later queries of the same latest bar are the same observation, never a new entry. A caller must process only newly completed IDs, consume each once, and never retimestamp a result to the query time. P must adapt N's timestamp_utc/bar_end_utc and preserve its source/price-side provenance outside this pure numeric type.

## Exact conditions

- **Trend:** last completed weekly close > the N-week mean including that close; that mean > the same N-week mean M weeks earlier. Defaults N=20, M=4. Optional daily confirmation is last close > 50- or 100-observation SMA, with full warm-up.
- **Breakout:** last completed daily close > maximum raw high of exactly N prior daily observations, excluding the signal bar. Equality does not fire.
- **Pullback:** explicit Boolean up-trend required. The current daily low <= support < current close. Support is the completed 20/50-day SMA including current close, or the latest known confirmed swing low. A swing confirmed after the signal bar was available cannot retrospectively support that bar. This is an end-of-day observation, never an intraday fill at the earlier low.
- **Confirmed low:** strict low against N bars on each side, emitted only after N later bars complete; ties are not unique pivots. Confirmation timestamp is the latest availability in the local window.
- **Smoothing:** Gaussian endpoint weights `exp(-lag²/(2 bandwidth²))`, only the fixed trailing kernel window. Earlier endpoints are never refitted from later prices. Initial kernel outputs are unavailable until the full window exists. This is a causal adaptation, not the original retrospective LMW smoother.
- **Double bottom:** the last two strict smoothed troughs, each confirmed by one later completed endpoint, separated by at least the fixed minimum and within relative bottom tolerance. Neckline is the highest raw high strictly between troughs. Previous close<=neckline<current close is required, so only its first close-cross fires.
- **Bull flag:** positive raw pole gain at least the fixed fraction, smoothed pole rising, then a negative least-squares slope over smoothed flag observations. The flag high cannot exceed the pole high; positive retracement is bounded by a fixed fraction of pole gain. Confirmation is the first daily close above the raw flag high.
- **One pattern family:** fixed double-bottom-before-bull-flag precedence if both are present. No discretion, fitted shape search or candlestick trigger. Pattern defaults and all future searched parameters must be disclosed in P's registration; no genuine search occurs here.

## Exit and cost levels

Initial long stop is latest already-confirmed low minus k*ATR14, or entry minus k*ATR14 if no low is known. It must be positive and strictly below entry. Optional target is entry+R(entry-stop), strictly above entry. Holding duration is a strict integer 1..10; the caller must still obey any tighter RiskManager/config duration.

Chandelier candidate is highest close minus k*ATR14; return max(previous stop,candidate), never loosen. Profitable trailing stops may rise above the original entry. `chandelier_exit` compares with the executable current mark: if mark<=stop it reports a close-only condition rather than lowering the stop to fit a gap. Execution price/accounting and final authority remain with the engine/RiskManager; the library creates no fill or order.

The price-unit round trip uses `entry*(2*fee_bps+full_quoted_spread_bps+2*slippage_bps)/10000`, multiplied by at least 1 for registered stresses. Full quote spread is halved per fill, not charged twice as a full spread. Target distance, or 2*ATR when no target, must be at least **5 times** the round trip; equality is accepted. This hurdle is the owner's fixed project rule, not a paper-derived profitability result.

## Alternatives and limits

Two-sided smoothing, incomplete-window interpolation, retrospective pivot timestamps, mutable stops, current-bar breakout highs and discretionary pattern selection were rejected because they alter timing or permit lookahead. Pure functions need no new dependency and can be reused unchanged by research and any later authorized runtime. They do not establish empirical validity, position sizing, news entry triggers or execution permission. News/calendar remain veto-only outside this library.

[Research](../research/P11o-research.md) · [runbook](../how-to/chart-signals.md) · [phase](../../reports/phases/P11o.md).
