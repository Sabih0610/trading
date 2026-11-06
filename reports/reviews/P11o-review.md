# P11o review: causal chart-signal library

| Field | Value |
|---|---|
| Date | 2026-11-06 |
| Reviewer | Claude (MASTER-2026-12) |
| Scope | `codex/p11o-chart-signals` at `644bc43` |
| Verdict | **APPROVED**, merged. |

## Checks

| Item | Result |
|---|---|
| Fixtures only | No genuine data read or committed. |
| Pattern smoother | `causal_kernel`: Gaussian weights over `values[index - lag]` for `lag in range(window)`, so **one-sided** (current and past bars only), with `None` during warm-up. The two-sided Lo-Mamaysky-Wang smoother is not used. |
| Swing lows | `confirmed_swing_lows` first restricts to bars available at `as_of` (`_history`), and the confirmation time is the latest `available_at` in the window, so it is causal. |
| Triggers | Breakout: close above the prior N-day high (signal bar excluded). Pullback and pattern triggers on completed bars. No candlestick triggers. |
| Cost rule | `COST_MOVE_MULTIPLE = 5`: the expected move must be ≥ 5× the round-trip cost. |
| Long-only | Stops below entry; no short path. |

## Gates (`644bc43`, clean worktree, run alone)

pytest **1,833 passed**, 2 skipped, 3 deselected, 0 failed. Ruff clean (642 files), strict mypy clean (215 sources).
