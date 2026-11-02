# P11g: Stage 3 gold, development test on the XAUUSD data we have (2021–2023)

Follow `prompts/_PROTOCOL.md`. Run **after P11f Part A is approved** and reuse its evaluator,
pre-registration format and Backtest Lab. Branch `codex/p11g-stage3-gold-dev` from current `main`,
credential-free checkout, private data from `E:\trading-p11e` via `load_forex_plan`.
Authority: owner approval in chat (2026-11-02), `docs/ROADMAP.md` Stage 3, P11e review.

## Goal
Test the gold strategies now on the HistData XAUUSD history we already have (2021–2023), as a
**development verdict** for XAUT. **2024 is not available yet and stays untouched.** It becomes the
validation year later, from Dukascopy, using parameters frozen by this phase. So this phase can
**reject** strategies or mark them **promising**; it cannot pass them.

## Hard rules
- All P11f hard rules apply: no 2025+ data, no `--final-test`, risk manager unchanged,
  pre-registration before any genuine-data run, no re-tuning, and nothing genuine committed
  (verdict summary and aggregate metrics only).
- **XAUUSD stays data-only.** Do not change its `role`, eligibility or `allowed_strategies`.
  Add a **research-only proxy-bar adapter**: XAUUSD Silver/Gold bars are fed to strategies
  configured for `XAUTUSDT`. Every result is labelled `proxy: XAUUSD(histdata, bid) → XAUTUSDT`.
  The adapter must refuse paper, simulation and any execution path (test it).
- **Costs:** use **XAUTUSDT's registry costs** (10 bps fee + 8 bps spread + 5 bps slippage per
  side), since XAUT is what would actually be traded. Also report 1.5× and 2×. HistData is
  bid-only, so long entries fill at bid **plus** the spread above; never infer a spread from bid bars.
- **No 2024 data of any kind** may be read in this phase, including XAUUSD from other sources.

## Part A: build and pre-register, then STOP for review
1. Implement **strategy G, session opening-range breakout** (`session_orb`, ROADMAP Stage 3):
   London and New York opens, a 15-minute opening range, entry on the first completed bar
   closing above the range high, stop at the range midpoint or low (pre-register one), 2R
   target, flat by end of day. Add it to XAUTUSDT's `allowed_strategies` (owner-approved).
2. Strategies in scope: **A** `london_sweep_mss_fvg`, **C** `trend_vwap_pullback`, **G** `session_orb`.
   **B** `xaut_catch_up` is excluded because it needs simultaneous XAUT prices, which only
   exist from 2026-03 (forward only). Comparisons: do nothing, buy-and-hold, random entry.
3. **Data-quality gate** (pre-registered): no trade in a session that has a quarantined day, a
   flagged late week open, or more than a set % of missing minutes in the strategy's lookback
   window. 2023 has heavy HistData gaps (February to July); report how many sessions the gate
   removes per year.
4. Write `reports/stage3/P11g-preregistration.md` in the P11f format: rules, timeframes, a small
   grid (at most 3 values per parameter, at most 27 combinations), the trial count, the protocol
   and verdict rules below, and the file's SHA-256 in the journal.
5. Gates green on fixtures, push and open a PR, **stop** for Claude's review.

## Part B: after approval
1. Walk-forward: train 2021 → evaluate 2022; train 2021–2022 → evaluate 2023. Parameters are
   chosen on training data only, with the purge and embargo as in P11f.
2. **Freeze** the selected parameters (trained on 2021–2023) into
   `reports/stage3/P11g-frozen-params.json` (no prices) for the future 2024 Dukascopy validation.
3. Same-bar ambiguity bounds and cost sensitivity as in P11f.
4. **Verdict per strategy:**
   - **Reject:** expectancy ≤ 0 after costs in either development year, **or** profit factor
     < 1.1 on the aggregate, **or** not positive at 1.5× costs. Drop it with no re-tuning.
   - **Promising:** positive in both years, profit factor ≥ 1.3 on the aggregate, max drawdown
     ≤ 15%, at least 60 trades on the aggregate, beats do-nothing and random entry, and survives
     1.5× costs and the ambiguity bound. Goes on to 2024 validation.
   - **Insufficient evidence:** anything else (e.g. too few trades after the quality gate).
   - Report DSR with the trial count; at this sample size it is informative, not a gate.
5. Backtest Lab shows the gold results labelled **"development only: not validated"**, with a
   proxy badge and the quality-gate counts.

## Scenarios to self-test
Proxy adapter used from a paper or simulation path → refused · any 2024 timestamp → refused ·
quarantined day → no trade · bid-only fill pays the XAUT spread on entry · DST mismatch week
→ the London/NY open lands at the correct UTC time · frozen-parameter file has no prices ·
a strategy failing in 2022 alone → reject.

## Acceptance
- Part A: PR with G, the proxy adapter (with refusal tests), the quality gate and the
  pre-registration; gates green; stopped for review.
- Part B: `reports/phases/P11g.md` with the verdict table, quality-gate counts, cost and ambiguity
  sensitivity, frozen parameters committed (no prices), and an honest note that **no gold strategy
  is validated** until 2024 runs. Push to the PR and do not merge `main`.
