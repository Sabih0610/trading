# P11g research before genuine input

Source/code research only,2026-11-03. No gold registry, quality table or observations
were opened. Exact hypotheses and every small grid precede data.

|Question|Alternatives|Decision|
|---|---|---|
|Session timing|Fixed UTC / separate local clocks|London08:00 and NewYork09:30 market-centre cash-opening anchors; IANA DST independently, not claimed Spot venue opening times.|
|Stop|Range midpoint / low|Fixed range LOW, no stop-position grid;2R target.|
|Search|Large calendar/filter search / small Cartesian grid|Nine configs each A/C/G, two TF each,54trials; quality five-percent fixed.|
|Bid and VWAP|Infer ask/volume / preserve provenance|Pay full registry per-side spread/slippage; preserve absent volume/VWAP, C waits.|
|Proxy routing|Relabel executable source / research-only capability|XAU stays data-only; explicit historical purpose, no runtime iteration or export.|
|Quality window|Arbitrary previous-night span / actual setup lookback|A London midnight→proposal; C50native periods; G14periods. Wall-clock gaps conservatively exclude closures.|

Primary sources accessed2026-11-03:
- [LSE official hours](https://www.londonstockexchange.com/en/resources/faqs/personal-investing): local London anchor08:00.
- [NYSE official trading information](https://www.nyse.com/trade/trading-information): local NewYork anchor09:30. These are timing hypotheses for a gold proxy, not equity data/strategies.
- [Python3.12 zoneinfo](https://docs.python.org/3.12/library/zoneinfo.html): distinct IANA rules for UK/US mismatch weeks; installed tzdata remains pinned.
- [Polars joins](https://docs.pola.rs/user-guide/transformations/joins/): backward known-at joins, never unfinished parent context.
- [DSR original paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf): reuse F probability/units, substitute registered54null trials, informational not validation.

Source inspection (not data): A uses LIMIT midpoint and retains frozen F touch
semantics; J2 must not silently alter this run. HistData bid Gold cannot manufacture
real volume. Scheduled/holiday gaps may remove sessions under the fixed grid;
counts are reported after approval rather than used to tune the threshold.

Execution-capacity decision: retaining provider zero volume as engine capacity
would prove only absent fills. Instead the proposed registration declares a fixed
counterfactual initial-funded-notional capacity, confined to internal historical
engine bars. Provider Gold/StrategyBar volume and VWAP remain unchanged; no liquidity
claim or runtime export. Gap/cost checks prove cash/risk still bind. This exact
assumption is conditional on Claude pre-registration approval, never tuned on data.
