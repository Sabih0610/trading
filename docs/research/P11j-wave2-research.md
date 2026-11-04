# P11j Wave 2 research

D-3 and D-4 correct pessimistic replay and label semantics after both Stage 3 batches
were reviewed and merged. Research on 2026-11-04 used primary documentation only;
no provider prices, dataset metadata or historical strategy run was opened.
Project trading rules and the owner's exact Wave 2 direction control this change.

## Questions and options

| Question | Options | Decision and reason |
|---|---|---|
| Does a bar merely touching a buy limit establish a fill? | Touch fill, probabilistic queue model, strict trade-through | Require low < limit in the default engine, as the audit and owner require. OHLC has no queue-position evidence; no new probability or tuning parameter. |
| Can the former research boolean weaken that default? | Keep false override, ignore false, remove switch | Remove the switch. A private subclass inside the preflighted historical gold adapter retains its already registered touch diagnostic, without exporting bars or an engine. |
| What is a gap-through stop label's loss price? | Stop, inferred close, actual bar opening price when lower | Require open and use min(open, stop), preserving adverse same-bar priority. Missing opens fail closed. |
| Should earlier research be rebuilt? | Rerun/relabel, preserve immutable evidence | Preserve F/G exactly. C/D/E/G enter MARKET, so D-3 does not change them; D-4 concerns labels only. A's approved G-1 sensitivity already disclosed strict fills. |

## Sources (accessed 2026-11-04)

- [QuantConnect latest-price fill model](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/supported-models/latest-price-model):
  primary engineering reference for explicit bar-based fill assumptions and avoiding
  same-timestamp lookahead. The exact strict predicate here comes from our audit
  and owner direction, not a claim that this model reconstructs a real queue.
- [SEC Investor.gov stop-order bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-15),
  updated 2026-08-18: stop-trigger and execution prices can differ materially.
  The conservative gap treatment applies that limitation to existing labels;
  it introduces no execution, venue, order authorization or investment advice.
- [FULL-AUDIT D-3/D-4](../../reports/reviews/FULL-AUDIT.md) and
  [Wave 2 prompt](../../prompts/P11j-audit-minors-and-test-reliability.md).

## Risks and limits

Trade-through is a deterministic conservative bar rule, not a measured fill
probability or liquidity guarantee. Required opening prices break callers that
previously supplied high/low/close only; every in-repository constructor is audited
and missing values are refused. Labels remain gross price returns with no newly
introduced fee model. This is a repair to existing label utilities, not Stage 4.
No genuine labels, parameters, provider data, holdout or forward archive is rebuilt.
