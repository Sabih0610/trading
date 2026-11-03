# P11f Part A review: Stage 3 crypto pre-registration

| Field | Value |
|---|---|
| Date | 2026-11-02 |
| Reviewer | Claude (reviewer role per `CLAUDE.md`, template `prompts/REVIEW_CLAUDE.md`) |
| Scope | [PR #5](https://github.com/Sabih0610/trading/pull/5), `6a0cbb9` → `3141380` (3 commits, 25 files, +1,517 / −8): strategies D/E, `reports/stage3/P11f-preregistration.md` (162 trials) |
| Verdict | **APPROVED WITH ONE REQUIRED AMENDMENT (P11f-1)** before Part B. Amending the registration is allowed because no genuine data has been read. |

## 1. Rules audit

| Check | Result |
|---|---|
| Long-only / spot / no orders | D and E only propose long entries with a stop below entry; E's trend loss proposes a close only and never sells unowned inventory. No order or execution code. |
| Config change | Only `allowed_strategies` for BTC/ETH/SOL gains `volatility_breakout` and `ts_momentum`, as owner-approved. Costs, risk and other assets are unchanged. `StrategyBar` gains an optional `volume` field. |
| Risk manager | Unchanged: 0.5% / 2% / 5%, one position, 3 trades per day per asset, flat at UTC end of day. Each strategy proposes at most once a day, which is stricter. |
| Holdout | 2025+ refused before file access; `--final-test` never used. Part A read no genuine data, not even the registry. |
| Public repo | Only verdicts and aggregate metrics may be published; trades, equity and bootstraps stay private. |

## 2. Causality (code read)

- **D** (`volatility_breakout.py`): decides before appending the signal bar, so the baseline,
  compression window, percentile and range high all come strictly from prior bars. The signal
  bar's own ATR is not used. The stop is the compression low minus 0.1×ATR of the last prior bar.
- **E** (`ts_momentum.py`): the N-bar return compares with `prior[-N]` before the current bar is
  appended. EMA, slope and ATR are the shared completed-bar features.
- **Shared state** (`crypto.py`): strictly increasing timestamps, the symbol is checked before any
  mutation, and any timeframe gap clears the lookback (no bridging). The daily proposal cap survives gaps.
- Fills happen at the next bar open (engine), so the signal bar's close is never the fill price.

## 3. Pre-registration assessment

Stronger than the prompt in several places, all in the conservative direction:
- **Trials:** the timeframe choice is part of the search, giving 162 trials, which are counted for DSR.
- **DSR:** uses the expected maximum Sharpe of 162 null trials, from the cross-cell variance of training Sharpes, rather than a zero benchmark.
- **Random entry:** the candidate must beat the **95th percentile** of 100 seeded runs, not just their average.
- **Costs:** the registry spread is read as a per-side cost, about twice the usual half-spread reading. This is conservative and accepted.
- **Drawdown:** the larger of daily and intrabar drawdown is used, and the 2024 batch is run once and immutable.
- **Sample size:** "insufficient evidence" is never a pass, and failed families are dropped.

## 4. Findings

| ID | Severity | Where | Description | Required change |
|---|---|---|---|---|
| P11f-1 | **major (fix before Part B)** | Pre-registration, "fixed training selector" | The selector picks the cell with the highest **mean net R/trade**, and any cell with at least one training trade is eligible. A cell with 1–5 lucky trades can win; the tie-break toward fewer trades makes it worse. Evaluation stays out of sample, so this cannot create a false pass. But it can waste the one-shot test by carrying noise parameters into 2024, especially in the 2021 fold, which trains on 2020-Q4 alone. | A cell is eligible only if it has **≥ 20 completed training trades** in that fold. If none qualifies, the fold is "insufficient evidence", as already specified. Keep 162 as the trial count. Re-record the amended file's SHA-256 in the journal before Part B. |
| P11f-2 | minor (report only) | Risk / pass bar | The engine's 5% peak-drawdown circuit halts a strategy for the rest of the fold, so the 15% drawdown bar rarely binds. A halted strategy's later flat days count as zero return, which is correct. | Report circuit trips and halted days per fold and strategy-symbol in the verdict table. Do not change the circuit or the bar. |
| P11f-3 | note | Pre-registration, 2021 fold | Training for 2021 is only 2020-10 → 2020-12. D at 1h needs 168 contiguous bars before its first signal. Expect "insufficient evidence" in some 2021 cells. Pass needs 2 of 3 development years. | No change; state it in the Part B report as a known limitation. |

## 5. Gates (rerun independently on `3141380` in a clean credential-free worktree)

| Gate | Result |
|---|---|
| `pytest` (default) | **1,412 passed**, 1 skipped (S-5 environmental), 3 live deselected, 5 xfailed (unchanged audit minors); 10 m 38 s. Matches Codex's report. |
| `ruff check` / `ruff format --check` | Clean / 517 files formatted |
| `mypy src` (strict) | Clean, 192 source files |

## 6. Decision

Part B may start once P11f-1 is applied to the pre-registration on the same PR, with its new SHA-256 recorded and no genuine data read before then. Report P11f-2 in Part B.

## Part B (2026-11-03)

**APPROVED**: see [P11f-partB-review.md](P11f-partB-review.md). No crypto candidate passes; PR #5 merged.
