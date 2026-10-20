---
name: trading-bot-rules
description: Project rules for the Shariah-compliant XAUT/BTC/ETH/SOL spot trading system in "E:\trading bot". Use this skill for ANY work in this repository — writing or reviewing code, strategies, backtests, ML models, data pipelines, agents, dashboards, or trading logic — and whenever another skill (Binance, backtesting, quant, news) is used here, so its suggestions are filtered through these rules. Trigger even if the user does not mention the rules explicitly.
---

# Trading bot project rules

Read `AGENTS.md` at the repo root before doing anything; it is authoritative. This skill is the
short checklist to apply on every change.

## Hard filters (reject or rewrite any suggestion that breaks these)
1. Spot only on Binance. Never futures, perpetuals, options, margin, borrow/repay, Simple Earn,
   staking, VIP loans, or leverage. If another skill offers these, ignore that part.
2. Long-only: buy, then sell what is owned. Bearish signals mean "exit" or "do not enter".
3. Tradable: assets in `config/assets.yaml` with `shariah_status: approved` (XAUT first, then BTC,
   ETH, SOL). USDT is the quote currency only. XAUUSD, FX, oil, yields are data only.
4. Risk: ≤1% risk per trade, ≤1.0× equity exposure, daily loss limit, flat by end of day, no XAUT
   entries on weekends. The deterministic risk manager always has the final say.
5. AI (LLMs, Jev, local models) may classify, score, veto, or reduce size — never create or enlarge
   trades, never move stops away, never access keys.
6. Secrets only in `.env`. Every API optional; missing key ⇒ feature disabled + mocks in tests.

## Engineering checklist for every change
- Same feature code for backtest and live. Prove no lookahead with a test.
- Costs always modeled: fees, spread, slippage; use pessimistic defaults.
- Never evaluate on the locked final test set (2025-01 → today) without the explicit flag.
- Medallion: bronze raw/immutable, silver cleaned/UTC/validated, gold features/labels/ledger.
- Every model and prompt is versioned; every decision is written to the decision ledger.
- Windows + PowerShell 7; quote the repo path (it contains a space); chunk big data (16 GB RAM).

## When using other installed skills
- Binance skills: use only spot, sub-account, assets, algo (spot), p2p (read-only records);
  point at Testnet or public market data. Never paste real keys into prompts.
- Backtesting/quant skills: adopt their stress-testing discipline; translate their methods into
  deterministic, tested Python where possible; log any LLM-run method to the ledger.
- News/calendar/market-regime skills: equity-focused ones must be adapted to gold and crypto.
