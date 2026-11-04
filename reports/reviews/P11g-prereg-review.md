# P11g pre-registration review: gold development test

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher; reviewer role per `CLAUDE.md`) |
| Scope | `codex/p11g-stage3-gold-dev` at `d92e120`: `reports/stage3/P11g-preregistration.md`, `session_orb`, the gold proxy adapter and the quality gate |
| Verdict | **APPROVED, conditional on amendments G-1 and G-2 below, applied verbatim** before any genuine input. Record the amended file's SHA-256 in the journal. No further pre-registration review is needed; I will verify the amendment text and its SHA in the Part B review. |

## 1. What is sound

- **Boundary:** XAUUSD stays data-only (only XAUTUSDT gains `session_orb`). The proxy adapter refuses paper, simulation, Testnet, live and execution purposes before reading input. 2024+ is refused before registry or price access, including bars whose `known_at` would cross into 2024.
- **Causality:** completed bars only, `bar_end` as the availability clock, fills on the next eligible bar, and parent context by backward as-of join only.
- **Search:** 54 trials (3 strategies × 9 configurations × 2 timeframes), the ≥ 20-training-trade selector from P11f, and the final 2021–2023 selector frozen for 2024. A null choice can never be promoted.
- **Verdict logic:** reject, promising or insufficient; "never a validated pass"; both orderings must be promising; any reject bound means reject.
- **Honesty about the data:** C needs volume-backed VWAP, which HistData cannot supply, so C will wait and may be insufficient. Its 18 cells still count. Approved as written.
- **Risk:** the unchanged RiskManager with the stricter XAUT override (0.25% risk, 2 trades/day), flat at UTC end of day, and no weekend entries.

## 2. Required amendments (pre-data)

| ID | Severity | Amendment |
|---|---|---|
| **G-1** | major | **Limit fills (audit D-3) for A.** A enters with a LIMIT at the FVG midpoint, and the current engine fills a limit when the bar low only *touches* it. That inflates a pullback strategy. Add a registered **trade-through fill path** in which a LIMIT fills only if a later eligible bar trades strictly through it (`low < limit`); a touch is unfilled and the proposal expires as normal. A can be **Promising only if it is promising under the trade-through path as well**, in both stop-first and target-first orderings. Any reject on that path means reject. MARKET-entry strategies (C, G) are unaffected. Use the path only inside this research replay; do not change the engine default (that is J2's D-3). |
| **G-2** | major | **Cost interpretation.** Use XAUTUSDT's registry costs with their **registry meaning**: `spread_bps_default = 8` is the full quoted spread, halved at each fill by the existing `CostAssumptions` (4 bps per side). Fee is 10 bps and slippage 5 bps per side, with stress at 1×, 1.5× and 2× on all components and both sides, unchanged. Treat the HistData bid proxy as the mid (the XAUUSD bid–mid gap is under 1 bp, which is immaterial next to these costs). Remove the doubled "effective spread_bps = 16". The doubling came from my prompt's "per side" wording, not from the registry; correcting it before data is legitimate. Note in the journal that P11f kept the stricter reading; its verdicts are unaffected because pre-cost expectancy was about zero for every crypto candidate (P11f Part B review §3). |

## 3. Accepted assumptions and notes

- **Counterfactual execution capacity:** approved as registered (10 × 10,000 USDT / prior bid close, so participation 0.1 caps notional at about the 10,000 USDT account). It is never provider volume and is never searched. **Real XAUT order-book liquidity remains unverified** and is a paper-trading gate.
- **G anchors:** London 08:00 and New York 09:30 (cash-equity open), fixed before data. The 08:20 COMEX open was not chosen; it would put the 08:30 US data releases inside the opening range. Accepted.
- **Quality gate:** the wall-clock minute grid counts the daily rollover and weekend minutes as missing, so C's 50-period windows will often be vetoed. That is accepted and must be reported. A (London-midnight window) and G (≥ 15-minute window) are barely affected.
- **Cost scale:** at base cost a round trip is about 0.38% of price, large against gold's intraday stops. A reject driven by costs is a genuine finding about XAUT intraday trading, not a defect.

## 4. Decision

Apply G-1 and G-2 to `reports/stage3/P11g-preregistration.md` (and the matching fixture tests), record the new SHA-256, freeze the code and config identities, then run Part B once. Do not merge `main`; the Part B PR is reviewed as normal.
