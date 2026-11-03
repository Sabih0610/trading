# P11f Part B review: Stage 3 crypto verdicts

| Field | Value |
|---|---|
| Date | 2026-11-03 |
| Reviewer | Claude (MASTER-2026-11 watcher; reviewer role per `CLAUDE.md`) |
| Scope | [PR #5](https://github.com/Sabih0610/trading/pull/5) `3141380` → `83c67f8` (Part B: evaluator, runner, Backtest Lab, verdicts) plus the private run `work/stage3/P11f/registered-162-v1` in `E:\trading-p11e` |
| Verdict | **APPROVED.** The test was run as registered, and its conclusion holds: **no crypto candidate passes**. |

## 1. Integrity of the one-shot test

| Check | Result |
|---|---|
| Registration frozen before data | `reports/stage3/P11f-preregistration.md` is byte-identical from the amendment `05cd0f1` to the head (SHA-256 `f7109e15…`), and the same digest is in the run's `identity`. |
| Code frozen before data | No `src/`, `scripts/` or `config/` change after the frozen source `d58cd8f`. The run records implementation SHA-256 `8c690d28…` and `n_trials = 162`. |
| Single batch | `status.json` shows `stage = complete`, 9 experiments, runtime about 2.8 h, peak RSS about 0.9 GB. No relabelled or repeated run. |
| Engine change | `backtest/engine.py` is additive and opt-in: `research_target_first` (default off) changes only same-bar stop/target ordering, and a gap-through-stop open still exits at the open. `ReplayAudit` only observes (initial risk, conservative intrabar equity bounds, circuit latch time) and never feeds risk decisions. Default behaviour is unchanged. |
| Rules | Long-only and spot-only; the risk manager is unchanged; no 2025+ access; no orders or keys; living docs untouched (MASTER conflict rule); config differs from `main` only by the reviewed `allowed_strategies` entries. |
| Public data | `reports/stage3/P11f-verdicts.json` holds only permitted aggregates (PF, expectancy in R, max DD %, trade count, Sharpe, DSR, circuit trips, halted days, ambiguity counts). I scanned it: there are no prices, returns, equity curves or trades, and the only large numbers are years, runtime and RSS. |

## 2. Results (from the private run and the public projection)

7 × **fail**, 2 × **insufficient evidence** (C on BTC and D on ETH, both under 30 trades in 2024 and losing). Development profit factors are 0.61–0.87 for 8 of the 9, and 1.03 for D on SOL. All are far below the 1.3 bar.

## 3. Independent checks

1. **Pre-cost edge.** I extrapolated expectancy linearly from the 1×, 1.5× and 2× cost paths back to zero cost. The development pre-cost expectancy is **−0.12R to +0.12R** for every candidate. The strategies have essentially no predictive edge, so the failure is not just a cost artefact. D on BTC and SOL shows a small gross edge (+0.03R / +0.12R) that costs consume.
2. **5% circuit.** In most folds the peak-drawdown circuit latched and halted the strategy for 57–330 days, which truncates the evidence. The verdict is still robust:
   - The pre-cost edge is near zero.
   - The candidates that ran whole years without a halt still fail: D on BTC and SOL in 2022–2024, and E on ETH in 2021–2022.
   - Codex reported the halts as required (P11f-2) and did not add an unregistered circuit-off rerun. That was correct; such a rerun would be exploratory only and could not change a verdict.
3. **Same-bar ambiguity.** 0 ambiguous bars. This is plausible on 15m/1h/4h bars with 1–2 ATR stops and 2R targets.
4. **Comparators.** The random-entry 95th percentile is negative (development −8%), consistent with costs dominating random trading. No candidate beats it.

## 4. Gates (rerun on `83c67f8`, clean credential-free worktree)

pytest **1,455 passed**, 1 skipped (S-5 environmental), 3 live deselected, 5 xfailed (unchanged audit minors), 11 m 37 s. Ruff clean, 526 files formatted, strict mypy clean on 197 source files. Merges cleanly into `main`.

## 5. Follow-ups (non-blocking; for the living-docs PR)

| ID | Severity | Action |
|---|---|---|
| P11f-B1 | minor | Per "fail = drop", remove `volatility_breakout`, `ts_momentum` **and** `trend_vwap_pullback` from BTCUSDT/ETHUSDT/SOLUSDT `allowed_strategies` (more restrictive). XAUTUSDT is unchanged pending the gold test. |
| P11f-B2 | note | Record in `docs/pending.md`: crypto Stage 3 found no tradable edge. Stage 4/5 do not start for these candidates. Any new crypto idea needs a new pre-registration, and its trials add to the multiple-testing record. |

## 6. Decision

Merge PR #5. The owner decision after gold (P11g): new pre-registered ideas, a different approach, or stop.
