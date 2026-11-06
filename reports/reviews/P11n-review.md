# P11n review: causal daily and weekly bars with intrabar paths

| Field | Value |
|---|---|
| Date | 2026-11-06 |
| Reviewer | Claude (MASTER-2026-12) |
| Scope | `codex/p11n-daily-weekly` at `5ab5236` |
| Verdict | **APPROVED**, merged. |

## Checks

| Item | Result |
|---|---|
| Data rights | Only the three approved private datasets (Vision crypto, HistData XAUUSD, PAXG); no new downloads. |
| Bars | 1d (UTC day) and 1w (Monday 00:00 UTC) with observed-vs-expected source-minute counts. Incomplete bars are flagged, never filled. Calendar in `config/swing-calendar.json`. |
| Swing points | `features/swing.py`: confirmed only at the confirmation bar's exclusive end ("event available only at confirmation bar exclusive end"), so they are causal. |
| Intrabar accessor | `backtest/intrabar.py`: bound to one UTC date at construction; refuses any other day **before IO**; refuses until the day has completed (`as_of >= day end`); refuses ≥ 2025 and out-of-scope days; checks for a ≤ 1,440 unique minute path with no cross-day points; verifies identity. It is a fill-ordering aid only, not a signal API. |
| Holdout | 2025+ is refused. Nothing genuine is committed (manifests/health are metadata only). |

## Gates (`5ab5236`, clean worktree, run alone)

pytest **1,795 passed**, 2 skipped, 3 deselected, 0 failed. Ruff clean (649 files), strict mypy clean (221 sources).
