# Installed project skills

Five reviewed skills are installed in both `.agents/skills` and `.claude/skills`. Every retained file was inventoried and scanned for external I/O, credential handling, destructive commands, prompt injection, and prohibited trading behavior on 2026-10-20 UTC. Third-party scripts were read but not executed.

All third-party guidance is subordinate to `AGENTS.md` and `trading-bot-rules`: Binance spot only, long-only, approved assets only, deterministic risk controls, optional keys, no live writes, and no access to the locked final-test period without the explicit gate.

## Retained skills

| Skill | Folder | Purpose here | Mandatory filters / ignored content | Audit result |
|---|---|---|---|---|
| `trading-bot-rules` | `.agents/skills/trading-bot-rules` | Authoritative project safety overlay for every repository task. | None; `AGENTS.md` remains authoritative. | Retained, 1 file. |
| `backtest-expert` | `.agents/skills/backtest-expert` | Pessimistic costs, parameter sensitivity, walk-forward validation, bias checks, and failure-oriented review. | Ignore its generic 50% drawdown ceiling and any short-selling example; project risk limits are much stricter. Never accept its `Deploy` label as authority over deterministic project gates or the locked final test. | Retained, 7 files. Its evaluator performs local calculations/report writes only. |
| `market-news-analyst` | `.agents/skills/market-news-analyst` | Source-quality and market-impact research patterns for later news/calendar work. | Equity, earnings, options, futures, and margin-call material is context only. Adapt analysis to gold/crypto; it may classify or veto but never create/enlarge a trade. | Retained, 5 documentation files; no scripts. |
| `market-environment-analysis` | `.agents/skills/market-environment-analysis` | Timezone/calendar discipline and risk-on/risk-off reporting patterns. | Equity venue schedules, VIX, futures, FX, oil, yields, and options are data-only. Never turn bearish analysis into a short. Do not use its scripts as production feature code. | Retained, 6 files. Scripts have no network calls or credential access. |
| `quant-analyst` | `.agents/skills/quant-analyst` | General data-quality, transaction-cost, out-of-sample, and sensitivity-analysis checklist. | Ignore options pricing, statistical-arbitrage/pairs-trading, portfolio leverage, shorting, and its pandas-first implementation suggestion where Polars/DuckDB are required. | Retained, 1 documentation file; no scripts. |

The `.claude/skills` tree mirrors these same reviewed copies for the later Claude review workflow.

## Rejected or unavailable skills

| Skill | Disposition | Reason |
|---|---|---|
| `backtesting-trading-strategies` | Quarantined under ignored `.cache/rejected-skills` and removed from future installer runs. | Its executable engine, strategies, and tests open and account for short positions. It also fetches from unapproved sources directly and is not the project’s shared feature engine. |
| `p2p` | Quarantined under ignored `.cache/rejected-skills` and removed from future installer runs. | It includes production authenticated writes, advertisement management, evidence uploads, partial API-key display, and irreversible appeal cancellation. The project permits P2P context only as read-only records. |
| Binance `spot`, `sub-account`, `assets`, `algo` | Not installed. | The reviewed upstream revision no longer contains these named folders. No broad Binance replacement was substituted because it could include forbidden products or permissions. |

## Source provenance

The ignored `.cache/skill-sources` clones were reviewed at these revisions:

| Source | Commit | Result |
|---|---|---|
| `tradermonty/claude-trading-skills` | `cb0f3aadffed6d1089db4b224162c964368baa46` | Three skills retained with filters above. |
| `sickn33/antigravity-awesome-skills` | `32b8ad933cfb84065a4ce5304c2557c9e39b25fa` | `quant-analyst` retained with filters above. |
| `binance/binance-skills-hub` | `43cc38ef5ca4ec3bd62b7d82ac35f1a8e5003166` | Requested spot folders unavailable; installed P2P copy rejected. |
| `jeremylongshore/claude-code-plugins-plus-skills` | `49811a252469a93bb74afb8f6b005edf305598f3` | Installed backtesting copy rejected for executable short paths. |

## Re-audit and update

Run from the repository root after reviewing changes in the source repositories:

```powershell
pwsh -ExecutionPolicy Bypass -NoProfile -File ".\scripts\install-skills.ps1" -ListOnly
```

Do not run the non-list installer after an upstream update until the requested skill directories and every copied file have been audited again. The installer intentionally excludes both rejected skill names.
