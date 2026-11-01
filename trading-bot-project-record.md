# Shariah-Compliant AI Trading System — Complete Project Record

*Compiled from the planning conversation (October–November 2026). This document captures every topic discussed, the research findings, the decisions made, and the current state of the project.*

*Updated 2026-11-01 to match the repository ([github.com/Sabih0610/trading](https://github.com/Sabih0610/trading), `main` at `aa65e85`). Sections 1–21 keep the original planning record; where the repository has since changed direction, a **"Repo update"** note says what is now true. Section 22 is the current status, and section 24 lists every phase actually built. Repository files (`AGENTS.md`, `PROGRESS.md`, `docs/decisions/DECISIONS.md`) remain the source of truth if this record disagrees with them.*

---

## Contents

1. Project summary
2. How the plan evolved
3. Shariah compliance analysis
4. Final trading universe
5. Trading venue decision (Binance spot)
6. Money flow and safety (Pakistan)
7. Realistic expectations and how to judge the system
8. Trading strategies
9. Decision architecture
10. Machine-learning models and the learning loop
11. AI models: Jev, Grok, LLMs and public competitions
12. The AI arena (multi-model testing)
13. Data plan (six years, medallion architecture)
14. Economic calendar and news sources
15. System architecture and technology stack
16. Hardware and local setup
17. Claude skills for the project
18. Development workflow (Codex builds, Claude reviews)
19. The development kit (files and phases)
20. Codex configuration
21. Earlier prototype: TradingView Pine Script
22. Current status, open items and next steps
23. Sources referenced
24. Phases actually built (repository history)

---

## 1. Project summary

**Goal:** build an AI-assisted, intraday trading system that analyzes markets, selects trades, and eventually executes them — while staying Shariah-compliant, keeping costs low, and proving its edge before any real money is used.

**Final shape of the project:**

| Item | Decision |
|---|---|
| First traded asset | XAUT (Tether Gold, tokenized physical gold) |
| Later assets | BTC, then ETH and SOL; other utility tokens after individual screening |
| Quote currency | USDT (not traded for profit) |
| Data-only instruments | XAUUSD (real gold), FX pairs (synthetic DXY), oil, US yields |
| Venue | Binance spot (backup: OKX) |
| Style | Intraday, long-only, no leverage, flat by end of day |
| Decision model | Tested rules → ML filter → AI agents (veto/size-down only) → deterministic risk manager |
| Build tools | Codex (GPT-5.6 Sol) builds; Claude reviews, debugs, stress-tests |
| Location | Local PC, folder `E:\trading bot` |
| Testing | 6 years of historical data, backtests, then ≥30 days paper/demo trading |
| Scholar approval | User confirmed scholar approved the USDT pairing and intraday XAUT trading |

> **Repo update (P09.5, 2026-10-22, decision D-0024 / ADR 0004).** The owner redirected the project to **one modular research and paper platform** whose primary research targets are **XAUUSD and EURUSD**, simulated locally as fully funded contracts. Binance spot (XAUT, BTC, ETH, SOL) stays as a secondary research track, and all existing spot-only / long-only guards remain in code. Reasons: authentic Binance XAUT history only starts on 2026-03-26, which is inside the locked 2025+ final-test window, so XAUT strategies cannot be researched on pre-2025 data (D-0021, D-0026).
>
> | Item | Current repository state |
> |---|---|
> | Primary research instruments | XAUUSD, EURUSD (local contract simulation; `role: data_only` in `config/assets.yaml`) |
> | Secondary track | Binance spot XAUT/BTC/ETH/SOL (`role: tradable`, `shariah_status: approved` by project policy) |
> | External orders | **Disabled everywhere** — no demo or live order path exists (`src/tb/execution/` is empty) |
> | Data feeds explored | MT5 (read-only), Twelve Data Basic, OANDA and cTrader (read-only quote research, OAuth prepared but not completed) |
> | Risk defaults | Tightened: 0.5% risk per trade, 2% daily loss, 5% peak drawdown, 1 position, 1.0× exposure |
> | Shariah note | The repository states that contract simulations are "not owned physical gold/FX or Shariah certification." Any move toward trading XAUUSD/EURUSD through a broker needs a fresh scholar ruling, because section 3.1 rejected CFDs. |
> | Build tool | Codex builds; the user publishes reviewed branches to GitHub (PRs #1 and #2 merged into `main`) |

---

## 2. How the plan evolved

| Stage | Original idea | What changed and why |
|---|---|---|
| Markets | Gold (XAUUSD) and oil (WTI/Brent) CFDs | Gold kept (as XAUT); oil moved to data-only because no Shariah-compliant oil instrument was found |
| Broker | Exness or XM with MT5 | Moved to Binance spot because CFDs give no ownership of the asset |
| Platform | MT5, then TradingView | Neither needed for trading; the bot connects directly to the exchange API. MT5 optional as a free gold data feed |
| Capital test | $10 → $20–30 in a month | Replaced with backtest + demo testing judged on expectancy, drawdown and consistency |
| AI role | AI analyzes, decides and executes | AI filters and challenges only; tested rules find trades; fixed risk manager decides |
| Scope | Gold and oil only | Multi-asset, one at a time, each through a Shariah gate and the same tests |
| Infrastructure | Cloud services | Lean local setup on the user's PC, near-zero cost |
| Primary research target (repo, P09.5) | XAUT on Binance spot | XAUUSD/EURUSD local contract simulation; Binance spot secondary. Binance XAUT history starts 2026-03-26, inside the locked final-test window |
| Data feeds (repo, P11a–P11b) | Dukascopy + Binance archives only | Added read-only MT5, Twelve Data, OANDA and cTrader quote research; each feed must prove timestamps, rights and contract metadata before use |
| Real data (repo, P11c.0) | Six years downloaded and cleaned | Research engine runs only on generated fixtures; genuine historical evaluation is blocked until a licensed dataset is formally admitted |
| Collaboration (repo, 2026-10-27) | Local folder only | Published to GitHub; task branches and PRs, hosted CI kept inactive (`[skip ci]`) |

---

## 3. Shariah compliance analysis

### 3.1 Why swap-free CFDs were rejected (majority view)

- **AAOIFI Shariah Standard No. 57 (gold)**, developed with the World Gold Council (2016), permits gold investment when the rules on possession are met — gold must be exchanged spot, with actual or constructive possession.
- **CFDs** never give ownership of the asset; profit/loss is settled only on price difference. Most contemporary fatwa bodies hold that a "swap-free" or "Islamic" account does not fix this, because the core objection is ownership and possession, not only interest.
- **Exness confirmed** to a trader that neither side owns any gold in their gold CFD — profit and loss come purely from price movement.
- **Short selling** CFDs means selling gold one does not own — a separate problem.
- **Minority view:** some scholars (e.g. answers on the Ask Ghamidi forum) permit CFDs on halal assets with no interest. This was noted but not adopted.
- **Vantage FX** claimed a Shariah board certification (Sheikh Hasan Qamra), but even sympathetic observers noted it needed more transparency.
- **Past trading on XM:** discussed with care; done in good faith because brokers market these as "Islamic accounts." Questions about purification of past profits were left to the user's scholar.

### 3.2 Compliant gold options found

| Option | Status | Fit for automated intraday trading |
|---|---|---|
| Physically backed gold ETCs (Invesco Physical Gold, Royal Mint, iShares IGLN, TradePlus Shariah Gold Tracker) | Shariah-certified / screened | Possible but limited exchange hours, long-only, settlement-timing question |
| Meezan Gold Fund (Pakistan) | Shariah-compliant | Daily NAV — holding only |
| Digital gold apps (O Gold, Gold Souq) | Certified | No API — not suitable |
| **XAUT (Tether Gold)** | **Certified Shariah-compliant by Amanah Advisors**; each token = 1 troy oz of physical gold in Swiss vaults | **Chosen** — spot ownership, 24/7, real order book, API |
| PAXG (Pax Gold) | Similar structure; no formal certification found | Not chosen |

### 3.3 Oil

No certified retail instrument for direct oil exposure was found. Options: use oil prices as a signal only (chosen now), Shariah-screened oil & gas stocks later (e.g. PSX KMI-30 constituents like OGDC, PPL, Mari, PSO — current list to be checked), or a certified oil token if one appears.

### 3.4 Crypto

- No final AAOIFI standard on cryptocurrency as of 2026; scholars differ.
- **Permissive (conditional) view:** Mufti Faraz Adam (Amanah Advisors), Shariah Review Bureau (Bahrain) and others. Screeners following it rate **BTC, ETH, SOL as halal**; stablecoins and meme coins as doubtful; lending/derivatives tokens (e.g. Aave) as not halal.
- **Restrictive view:** Mufti Muhammad Taqi Usmani considers crypto trading impermissible in its current speculative form; Egypt's Dar al-Ifta prohibited Bitcoin dealings in 2017.
- **Intent matters:** even permissive sources caution against pure price gambling.
- **User's scholar approved** the USDT pairing and intraday XAUT trading.

### 3.5 Crypto categories adopted

| Category | Examples | Use |
|---|---|---|
| Established utility networks | BTC, ETH, SOL | Yes |
| Tokenized gold | XAUT | Yes — first asset |
| Other utility tokens | Case by case | After individual screening, recorded in the asset registry |
| Stablecoins | USDT, USDC | Quote currency only |
| Lending/interest DeFi | e.g. Aave | No |
| Meme coins | — | No |
| Futures, perpetuals, margin, earn/lending | — | No |
| Staking | — | Set aside for now |

---

## 4. Final trading universe

| Asset | Role | Phase |
|---|---|---|
| XAUT/USDT | Traded | 1 |
| BTC/USDT | Traded | 2 |
| ETH/USDT, SOL/USDT | Traded | 3 |
| Other utility tokens | Traded after screening | Later |
| USDT | Quote currency only | Throughout |
| XAUUSD | Data only (history + live reference) | Throughout |
| FX pairs (EUR, JPY, GBP, CAD, SEK, CHF) | Data only (synthetic DXY) | Throughout |
| Oil (WTI/Brent), US yields | Data only | Throughout |
| Shariah-screened oil & gas stocks | Possible later phase | Later |

**Rules for all assets:** spot only, long-only, no leverage, no futures/margin/lending/earn products, no staking for now, flat by end of day, no XAUT entries on weekends (underlying gold market closed).

> **Repo update.** `config/assets.yaml` matches this table, with two changes: XAUUSD and EURUSD now carry `instrument_type: gold_contract` / `fx_contract` and an explicit eligibility block (reference data, historical research, local simulation) while remaining `role: data_only`. XAUT has a stricter per-asset override of 0.25% risk per trade and 2 trades per day. The synthetic DXY is gated (D-0016) until permission from ICE is confirmed, because ICE reserves the index formula.

---

## 5. Trading venue decision (Binance spot)

### 5.1 Venue comparison

| Venue | Order book | Shariah (majority) | Verdict |
|---|---|---|---|
| XM / MT5 CFDs | No | Fails | Data feed only |
| Futures exchanges (COMEX/NYMEX) | Deepest | Fails | No |
| Gold ETCs on stock exchanges | Yes | Certified | Possible later |
| **Binance spot** | **Yes** | **Certified/screened assets** | **Chosen** |

### 5.2 Why Binance

- **Deepest XAUT market:** ~US$19M/day XAUT/USDT volume; ±2% depth about $2.4M bids / $3.0M asks (vs Bitget, OKX, Bybit lower).
- **Deepest BTC/ETH/SOL** markets (~38.7% of top-ten exchange spot volume in Q2 2026).
- **Pakistan:** PVARA granted Binance and HTX No Objection Certificates in December 2025 (not an operating license). Largest PKR P2P merchant base.
- **Tooling:** Spot Testnet, WebSocket order book and trade streams, OCO orders, User Data Stream (via WebSocket API — old listenKey method deprecated), sub-accounts, trade-only API keys with IP whitelisting, python-binance and CCXT support, regular API updates.
- **Fees:** about 0.1% per trade (lower with BNB; BNB fee payment left as a minor scholar question).
- **XAUT listed on Binance on 26 March 2026** — so Binance has only ~7 months of XAUT history.
- **Backup:** OKX (second-best XAUT depth, ~0.08% maker / 0.1% taker).

### 5.3 TradingView and MT5

- XM connects directly to TradingView; Exness does not. This was relevant only during the CFD phase.
- TradingView is not needed in the final system (optional for viewing charts).
- MT5 cannot trade spot XAUT/BTC; it stays only as an optional free data feed (Windows-only Python library).

---

## 6. Money flow and safety (Pakistan)

**Profit = (sell price − buy price) × quantity − fees − spread.** No interest earned or paid.

**Flow:**
1. **Deposit:** PKR → USDT via Binance P2P (Easypaisa, JazzCash, Raast, bank transfer; escrow-protected).
2. **Trade:** the agent trades XAUT/USDT via API; profits accumulate in USDT.
3. **Withdraw:** USDT → PKR via P2P.

**Regulatory status:** PVARA created July 2025; Virtual Assets Act 2026 classifies crypto as property; no exchange fully licensed as of September 2026. Licensed providers will later route rupees through Pakistani banks with segregated client accounts.

**Safety rules:**
- P2P only with verified merchants; pay and receive only in own-name accounts; never accept third-party payments; keep records.
- API key: trade-only, withdrawals disabled, IP-restricted.
- Two-factor authentication; a separate sub-account holding only the agent's capital.
- Taxes: keep the full journal; confirm filing obligations with a tax advisor.
- Ask scholar about zakat on holdings.
- Claude cannot hold, move, or trade money; all deposits, withdrawals and approvals stay with the user.

---

## 7. Realistic expectations and how to judge the system

**Why the "$10 → $20–30 in a month" test was dropped:**
- $10 cannot trade gold without heavy leverage (0.01 lot = 1 oz, worth thousands of dollars).
- Doubling in a month signals excessive risk, not skill.
- One month of ~20–40 trades is mostly noise.

**How to judge instead:**

| Metric | Healthy sign |
|---|---|
| Expectancy per trade after costs | Positive and stable |
| Profit factor | Above ~1.3 |
| Maximum drawdown | Under ~10–15% |
| Live vs backtest | Live roughly matches backtest |

A realistic good result is a few percent per month with small drawdowns.

**Testing stages:** backtest on years of data → demo/paper for at least 30 days → small live amount large enough to size trades properly.

---

## 8. Trading strategies

All long-only and intraday; bearish signals mean "exit" or "don't enter."

### 8.1 XAUT (gold)

| # | Strategy | Idea |
|---|---|---|
| A | London sweep → structure shift → FVG | Price sweeps the Asian-session low during the London open (07:00–10:00 London), reclaims it, shifts structure upward; buy the pullback into the fair value gap; stop below the sweep; target 2R; flat by end of day |
| B | XAUT catch-up (lead-lag) | Real gold moves first; thin XAUT sometimes lags. When XAUUSD jumps and XAUT hasn't followed, buy XAUT. Considered possibly the most realistic edge (market structure, not prediction) |
| C | Trend pullback to VWAP | In an up-trending session, buy a pullback to session VWAP that holds |

### 8.2 BTC, ETH, SOL (later)

| # | Strategy | Idea |
|---|---|---|
| D | Volatility breakout | Buy breakouts from quiet compression with rising volume |
| E | Time-series momentum | Buy when short and medium trends align upward |
| F | Order-book confirmed entries | Enter only when bids outweigh asks and aggressive buying dominates |

### 8.3 Market drivers discussed

**Gold — bullish:** weaker dollar, falling real yields / rate-cut expectations, inflation surprises with dovish Fed, geopolitical risk, central-bank buying, weak US data. **Bearish:** the opposite.

**Oil — bullish:** inventory draws, OPEC+ cuts, supply disruptions, strong demand, weaker dollar. **Bearish:** the opposite.

Intraday, these matter mainly around release times; otherwise sessions, liquidity and structure dominate.

### 8.4 Concepts that had to be codified

Smart Money Concepts are discretionary, so each needs exact definitions: swing points (fractal/pivot with confirmation delay), BOS, CHoCH/MSS, liquidity sweep (break + reclaim within N bars), FVG (three-candle gap with minimum size vs ATR), sessions and news windows.

---

## 9. Decision architecture

```
Rules detect setup
   → ML models score it (P(win), forecast, uncertainty)
   → Jev / AI agents: proposer builds the case, challenger tries to kill it
   → Judge (fixed rules): take / reduce size / skip
   → Risk manager (final authority, deterministic)
   → Execution (Binance API, trade-only key)
   → Journal / decision ledger
```

**Risk manager rules:** ≤1% risk per trade, exposure ≤1.0× equity, daily loss limit (default 3%), max trades per day, flat by end of day, no XAUT weekend entries, kill switch.

> **Repo update (D-0007, D-0025).** Hard ceilings are compiled into Python and config may only make them stricter. The configured research/paper defaults (`config/risk.yaml`) are: **0.5%** all-in planned risk per trade (costs included), **2%** daily loss measured on marked liquidation equity, **5%** peak-drawdown halt that latches across days, **1** open position, **1.0×** fully funded exposure, 3 trades per day per asset, flat by end of day, no XAUT weekend entries. Risk is rechecked at actual fills to catch gaps. Note: `AGENTS.md` §2 still lists the older 1%/3% ceilings while §1 lists the new defaults.

**AI limits:** AI may classify, score, veto, or reduce size — never create trades, enlarge them, move stops away, or access keys.

**Human role:** defined powers like another agent — pause, veto, reduce size, approve flagged trades; cannot open trades or widen stops. Every intervention logged and measured via shadow tracking.

**Tweaking discipline:** every change versioned with a reason, tested on unseen data (walk-forward), run in shadow before replacing, limited number of changes per month.

**Example snapshot sent to agents:** asset/session info, H4 trend, H1 structure, Asian range in ATR, sweep depth, FVG size, spread vs average, DXY change, minutes to next high-impact event, trades today, R:R to target.

---

## 10. Machine-learning models and the learning loop

### 10.1 Principle

ML does not predict prices from scratch. It filters and sizes trades the rules already found. Every model must beat simple baselines.

### 10.2 Models

| Model | Role |
|---|---|
| Logistic / ridge / linear regression | Baseline every model must beat; interpretable |
| LightGBM / XGBoost (meta-labeling) | Core filter: probability a setup wins |
| Triple-barrier labeling | Labels: target, stop, or time limit hit first |
| Isotonic / Platt calibration | Makes confidence match reality |
| Gaussian Process Regression | Forecast with uncertainty band — size larger when confident, skip when uncertain; best fit for XAUT–gold gap (Strategy B) and short-term volatility; use sparse/rolling windows due to O(n³) scaling |
| Kalman filter / online ridge (RLS with forgetting) | Track the changing fair XAUT–gold relationship |
| HMM / clustering | Market regime (trending, ranging, chaotic) |
| GARCH / HAR-RV | Volatility forecasts for sizing and stops |
| Order-book models (logistic / small GBM) | Short-horizon entry timing (later) |
| Online tree models (River) | Optional incremental learning |
| Contextual bandits (Thompson sampling) | Choose strategy/variant per regime with controlled exploration |
| Drift detectors (ADWIN, Page-Hinkley, PSI) | Alert when market stops resembling training data |

**Avoided at the start:** deep learning on price (LSTMs/Transformers) and reinforcement learning — data-hungry, overfit-prone, hard to validate.

### 10.3 Validation

Walk-forward testing; purged k-fold cross-validation with embargo; train on real gold, validate on XAUT; shadow tracking of every filter; baselines: do nothing, buy-and-hold, "yesterday's trend continues."

### 10.4 Learning loop (automation)

```
Collect → Label → Train → Validate → Shadow → Promote → Monitor → (back to Collect)
```

- **Schedule:** continuous collection; nightly labeling and drift checks; weekly retraining; monthly human review.
- **Learning from losses correctly:** label every candidate setup (taken, skipped, vetoed) to avoid selection bias; classify loss reasons (bad setup / bad timing / execution / normal loss — normal losses are not "fixed").
- **SHAP** values explain decisions and reveal loss patterns.
- **Guardrails:** automation never changes risk limits; champion vs challenger in shadow; human approval to promote; all models versioned (MLflow); minimum new samples (e.g. 50+) before retraining.

---

## 11. AI models: Jev, Grok, LLMs and public competitions

### 11.1 Jev (TypeSafe AI)

- Released 15 September 2026; built for structured decisions in software — returns choices, scores or probabilities from a state plus typed questions, no prose.
- Fast: decision loops around 10 times per second (vs several seconds for LLMs).
- Limits found: weaker on multi-step calculation; behind GPT-5.6 and Claude Sonnet 5 on a stance-detection benchmark; robustness and answer-order effects under study.
- Calibration: TypeSafe says its RLCD training aligns confidence with accuracy, but methodology is unpublished; its own Jev 1.13 notes call Score outputs "weak in numerical calibration"; calibration can drift.
- TradeRank found Jev's direction calls statistically indistinguishable from "yesterday's drift continues" and its 80% confidence band held only 68% of the time.
- **Role decided:** fast filter/classifier (news, regime, proposer/challenger questions) — never a direction predictor; never in the math or risk path; calibration measured on our own trades; evaluated only on forward data (historical contamination risk). API access to be added later.

### 11.2 The "HFT with Jev" Instagram reel — assessment

- The method described (Avellaneda–Stoikov reservation price, posting/cancelling quotes) is **market making**, which needs a real exchange order book — not applicable to CFD brokers.
- 100 ms decisions don't make a retail setup HFT; network hops dominate, and M5-bar strategies don't benefit from sub-second speed.
- "Confidence correlates with real market probability" was overstated.
- "Comment HFT" is a lead-generation hook.
- Useful part kept: summarize market state into a compact snapshot, ask typed questions in parallel, keep prices/limits in deterministic code.

### 11.3 Grok

- "Grok bots" online are mostly ready-made programs where Grok makes decisions, often on perpetual futures (non-compliant), often untested; plus an active scam industry using the Grok name.
- **SuperGrok subscription (~$30) does not include API credits**; the xAI API is billed separately (new accounts typically get ~$25 promotional credits; API is OpenAI-compatible).
- **Grok Bot** (xAI product, beta from August 2026): persistent AI teammates on a shared cloud computer with skills, routines (up to 50 per bot), plugins (including Jev). Access via SuperGrok Heavy/Plus, a limited trial, or linking certain subscriptions to Cursor.
- **Decision:** Grok Bot is fine as a research/operations teammate with read-only access and no exchange keys; it should not run live trading (IP whitelisting impossible on shared cloud, beta reliability, LLM in execution path). Note: in July 2026 xAI's coding CLI uploaded working directories regardless of privacy settings (later fixed) — never run such tools in folders with keys.
- User later chose to set Grok aside.

### 11.4 Open-source frameworks considered

- TradeMind-style bot (Grok + Binance + FastAPI + Postgres + risk + backtest): closest fit to fork.
- TradingAgents: multi-agent design ideas; too slow/LLM-centered as a base.
- Clawd Grok / OpenClawd: built around Solana perpetuals — poor fit.
- If forking: keep infrastructure (exchange client, scheduler, DB, dashboard, Telegram), replace the decision layer; audit code, licenses, key handling, hidden token promotions.

### 11.5 Alpha Arena (Nof1)

**Season 1 (Oct–Nov 2025, crypto perpetuals on Hyperliquid, $10,000 each, 17 days):**

| Rank | Model | Ending balance |
|---|---|---|
| 1 | Qwen 3 Max | ~$12,231 |
| 2 | DeepSeek | ~$10,489 |
| 3 | Claude Sonnet 4.5 | ~$5,799 |
| 4 | Gemini 2.5 Pro | ~$5,445 |
| 5 | Grok 4 | ~$4,208 |
| 6 | GPT-5 | ~$4,126 |

Grok was briefly up ~$3,000 (the source of viral claims) before ending down ~58%; DeepSeek peaked above $13,000.

**Season 1.5 (US stocks):** Grok 4.20 won with ~12% average return over two weeks.

**Season 2:** announced with upgrades but no public results as of August 2026.

### 11.6 TradeRank.ai (main 2026 arena)

- Season 10 started 10 October 2026: 22 models, $10,000 simulated each, daily decisions (not day trading).
- Standings on 20 October: GPT-6.1 Sol Pro +1.34%, Muse Spark 1.3 +0.73%, Jev +0.56%, Claude Opus 5.5 +0.19%, Grok 4.7 0.00%; only 4 of 22 in profit.
- All-time across 10 seasons: Gemini 3.8 Flash +21.2% vs S&P 500 buy-and-hold +18.5%; Grok −13.6% (≈ BTC hold −14.1%); Claude Opus 5.5 −26.2%.
- Findings: herding (151 of 156 opens were longs into a falling market in one season; only contrarian agents finished positive), structural short bias, discipline beat intelligence.

### 11.7 Lessons applied

Risk discipline beats intelligence; leverage caused the big losses; short tests are noise; LLMs carry stable biases; never choose a model from a leaderboard — test in our own system.

---

## 12. The AI arena (multi-model testing)

**Participants:** local models via Ollama (Qwen, DeepSeek, Llama, Mistral — sized to hardware), API models (Grok, OpenAI, DeepSeek, Qwen, Claude), Jev, and baselines (rules-only, trend-continues, always-skip).

**Three rounds per setup:**
1. **Independent decisions** on a masked snapshot (no asset name, date or raw price) in fixed JSON: take/skip, confidence, reason, key risk.
2. **Cross-review:** each model sees others' anonymized answers once; record mind changes and whether they helped.
3. **Hypotheses:** models propose patterns in a fixed format → hypothesis queue → automatic backtest → results credited per model; nothing changes live behavior without passing tests and human approval.

**Scoring:** per-model paper portfolio, Brier score/log loss, shadow veto value, hypothesis hit rate, error correlation (herding), cost and speed per useful decision. **Ensemble:** multiplicative-weights updating; poor models benched, still scored in shadow.

**Storage:** one central append-only decision ledger (SQLite → Postgres later), nightly backups; each model reads anonymized past outcomes but keeps its own notes (to avoid herding). A truly distributed database was judged unnecessary.

**Safety:** during testing no model's decision executes; only market snapshots go to external APIs; per-provider budget caps, timeouts, caching.

### 12.1 AI budget (~$20/month)

Estimate for the demo month: ~150 candidate setups, 2 calls per setup per model, ~4,000 input + ~400 output tokens per setup per model → ~600K input + ~60K output tokens per model per month.

| Role | Model type | Usage | Budget |
|---|---|---|---|
| Voter 1 | Low-cost API (e.g. DeepSeek) | Every setup | ~$2 |
| Voter 2 | Low-cost API (e.g. Qwen) | Every setup | ~$2 |
| Voter 3 | Mid-tier (e.g. Grok/OpenAI) | Every setup | ~$5 |
| Senior reviewer | Premium | Cross-review on filtered setups only | ~$6 |
| Reserve | — | Spikes, hypothesis reviews | ~$5 |
| Free | Local models | News tagging, regimes, extra votes | $0 |

**Cost controls:** monthly and daily caps per provider; response cache; provider prompt caching; short JSON outputs; compact snapshots; batch APIs (~50% discount) for non-urgent work; local models for frequent tasks. **Trap avoided:** don't run API models on all six years of history — use local models on full history and API models on a sample via batch.

---

## 13. Data plan (six years, medallion architecture)

### 13.1 Sources

| Data | Source | Six years? |
|---|---|---|
| XAUUSD 1-minute/tick | Dukascopy (free) | Yes |
| FX pairs for DXY | Dukascopy | Yes |
| US yields | FRED (keyless CSV; API key later) | Yes |
| Oil (signal) | Dukascopy | Yes |
| BTC, ETH, SOL | Binance public archive | Yes (SOL since 2020) |
| XAUT | Binance since 2026-03-26 + thinner earlier venues | Partial |
| Economic calendar | Official schedules + calendar sources | Yes, needs sourcing |
| Order-book history | Not free (vendors like Tardis.dev) | Collect live from now |

### 13.2 Training split

- **Train:** 2020-10 → 2023-12 (walk-forward inside)
- **Validation:** 2024
- **Final test:** 2025-01 → today — **locked, used once**

### 13.3 Which models train on what

London sweep, VWAP, regime and meta-label models → six years of real gold; XAUT catch-up and GPR gap model → all XAUT history; costs → Binance XAUT data; order-book features → collected live; crypto strategies → six years of Binance data in their own phase.

### 13.4 Medallion layers

| Layer | Contents |
|---|---|
| Bronze | Raw downloads exactly as received, immutable, with manifests |
| Silver | Cleaned, validated, UTC, deduplicated, gaps/spikes flagged, session-tagged, aligned |
| Gold | Features, labeled setups (triple-barrier), trade journal, decision ledger |

**AI-ready extras:** a plain-language data dictionary, masked snapshots for LLM evaluation, data-quality checks on every load.

**Start immediately:** the live XAUT order-book collector, since order-book history can't be downloaded free later.

> **Repo update.** What actually happened with data:
> - **Six-year download not run (D-0012).** The estimate was ~779 GB against ~118 GB free, so only a verified seven-day sample was kept. `data/` holds about 190 MB of Bronze, 9 MB Silver, 9 MB Gold (git-ignored).
> - **FRED paused (D-0011)** until its terms on AI/software use are resolved.
> - **News stores headlines and links only (D-0014)**; Fair Economy and Nasdaq are excluded from automated storage until their terms are verified (D-0015).
> - **XAUT history cannot exist before 2026-03-26**, so strategies A/B/C are marked "not evaluable" rather than tested on substituted data (D-0021, D-0026).
> - **P11c.0 research pipeline** (registry → import → frozen evaluation → replay → dashboard) works end-to-end on generated sample data. Genuine evaluation is **BLOCKED — DATASET NOT AUTHORIZED** until one licensed local EURUSD file (then XAUUSD separately) passes owner + independent-reviewer rights checks.
> - The live XAUT order-book collector was not built.

---

## 14. Economic calendar and news sources

**Calendar:**
- Official schedules (BLS, BEA, Federal Reserve FOMC, EIA, ECB) as ground truth for release times.
- ForexFactory / Fair Economy weekly JSON feed — current week only; forecast/previous but no actuals.
- ForexFactory calendar pages by date range, Nasdaq calendar (check terms, rate-limit politely).
- FRED/ALFRED release dates (key later).

**News:**
- GDELT 2.0 DOC API — free, keyless, ~1 request per 5 seconds, rolling recent window only.
- GDELT 2.0 bulk 15-minute files — full history, stream-filtered by topic.
- RSS feeds (Fed, metals, FX/macro, CoinDesk, Cointelegraph, Decrypt, The Block).
- Free crypto news archives (verify licence/quality).
- Keyed later: Finnhub, CryptoPanic, NewsData.io.

**Approach:** download with PowerShell from multiple streams, reconcile across sources (official schedule wins on times), deduplicate headlines, store raw in Bronze.

---

## 15. System architecture and technology stack

### 15.1 Language

| Language | Verdict |
|---|---|
| Python | Main language (ML ecosystem, exchange libraries; speed sufficient for 1–5 min bars) |
| Rust | Only if order-book processing ever bottlenecks (Polars already gives Rust speed) |
| C++, Java, C | Not needed |

### 15.2 Components

```
Data sources → Collectors → Message bus → Storage + Feature engine + Hot state
  → Strategy engine → Decision layer (ML + agents, cached) → Risk manager
  → Execution service (only holder of keys) → Binance
Training pipeline (scheduler + MLflow) feeds models; Monitoring (dashboard, Telegram, kill switch)
```

### 15.3 Full vs lean stack

| Component | Full version | Lean version (chosen to start) |
|---|---|---|
| Hosting | Cloud VPS near Binance (AWS Tokyo region) | Local PC |
| Storage | Postgres + TimescaleDB + Parquet | Parquet + DuckDB; SQLite |
| Bus / cache | Redis Streams / Redis | In-process cache or diskcache |
| Scheduling | Prefect / Airflow | Cron / Windows Task Scheduler |
| Tracking | MLflow server | MLflow local |
| Dashboard | Grafana + Prometheus | Streamlit |
| Alerts | Full monitoring | Telegram bot |

**Key principles:** the same feature code for backtest and live (no train/serve skew); the risk manager as a separate simple process; the execution service as the only component holding keys; an event-driven backtester reusing live code.

### 15.4 Caching (to protect AI budget and rate limits)

| Item | Key | Expiry |
|---|---|---|
| News classification | Hash of headline + model version | Hours–days |
| Jev/LLM answers | Hash of snapshot + question set + model version | One bar |
| Regime label | Asset + bar time | Until next bar |
| LLM journal summaries | Trade ID | Permanent |
| Market state | Symbol | Live |
| Rate-limit counters | API key | Rolling |

Rules: never cache risk decisions or order states; version everything in keys; on AI timeout (~300 ms) fall back to skip or rules-only at reduced size; log every AI call for audit and replay.

### 15.5 Execution adapter

Execution sits behind an exchange adapter (Binance now, OKX as a second adapter, MT5 adapter possible), so strategies and risk code don't change if the venue changes.

---

## 16. Hardware and local setup

| Item | Value |
|---|---|
| GPU | NVIDIA GTX 1650 Ti, 4 GB VRAM |
| RAM | 16 GB |
| Disk | 1 TB SSD |
| OS | Windows (PowerShell 7) |
| Project folder | `E:\trading bot` (path contains a space — always quote it) |

**Implications:** local LLMs limited to ~3–4B parameters, 4-bit quantized, via Ollama; don't run LLM inference and training at the same time; process data in chunks (never load six years of ticks into memory); LightGBM on CPU; GPR with sparse/rolling windows; MT5 Python library works on Windows if used.

**Low-cost demo plan:** paper trading engine on live Binance data simulating fills against the real order book (more realistic than Testnet, which may not list XAUT), plus Testnet only to verify order mechanics.

---

## 17. Claude skills for the project

| Source | Skills to use | Avoid |
|---|---|---|
| Binance Skills Hub (official) | spot, sub-account, assets, algo, p2p | all derivatives-trading-*, margin-trading, simple-earn, vip-loan, meme-rush |
| tradermonty/claude-trading-skills | backtest-expert, market-news-analyst, market-environment-analysis | Equity-only parts (adapt or skip) |
| quant-analyst | Strategy dev, time series, pairs-style statistics, sensitivity analysis | — |
| backtesting-trading-strategies | Systematic backtesting workflow | — |
| Alpaca skills library | Design reference for structured backtest outputs | US-stock specifics |
| **Our project skill: trading-bot-rules** | Filters every other skill through project rules | — |

**Use of skills:** speed up development (each component mapped to helping skills); convert skill methods into deterministic, testable Python; run them through a scenario library and stress tests; store results in the ledger; keep per-scenario robustness scorecards.

**Scenario library:** COVID crash (2020-03), rate hikes (2022), banking stress (2023-03), strong trend (2024–26 rally — validation only up to 2024), quiet ranges, CPI/NFP/FOMC days, thin liquidity. Stress tests: doubled spreads, slippage, delayed/missing data, input noise, shuffled answer order for LLM methods.

**Cautions:** review skills before installing; never give skills live keys with withdrawal rights; skills support building, not the 24/7 core.

---

## 18. Development workflow (Codex builds, Claude reviews)

- **Codex (GPT-5.6 Sol)** builds the application and infrastructure in `E:\trading bot`.
- **Claude** reviews, debugs, and stress-tests, writing independent tests and scenario tests.
- **Shared specification:** `AGENTS.md` (Codex) and `CLAUDE.md` (Claude, pointing to AGENTS.md) plus the project skill.
- **Tests are the contract;** small components one at a time; user approves merges.
- **APIs added later:** every integration optional; missing key ⇒ feature disabled, mocks in tests.
- **Secrets only in `.env`;** `.env.example` holds names only.
- **Claude desktop (Claude Code)** recommended for folder-scoped review of `E:\trading bot`, since the web chat cannot access local folders.

---

## 19. The development kit (files and phases)

### 19.1 Files

| File | Purpose |
|---|---|
| `AGENTS.md` | Rules, stack, architecture, data splits, documentation rules |
| `CLAUDE.md` | Claude's reviewer role |
| `.agents/skills/trading-bot-rules/SKILL.md` | Project skill |
| `prompts/_PROTOCOL.md` | Research → plan → build → self-test → verify → report |
| `prompts/RUN_ALL.md` | Master prompt: runs all phases automatically, resumable |
| `prompts/P00 … P14` | Phase prompts |
| `prompts/REVIEW_CLAUDE.md` | Claude review prompt |
| `scripts/install-skills.ps1` | Clones skill repos for review; installs only approved skills to `.agents/skills` and `.claude/skills` |
| `docs/research/SOURCES_SEED.md` | Data sources for Codex to verify |
| `docs/DOCUMENTATION_STANDARD.md`, `docs/templates/` | Documentation rules and templates |
| `.env.example`, `.gitignore` | Key names only; `.env` never committed |

### 19.2 Phases

| Phase | Topic | Keys needed |
|---|---|---|
| P00 | Bootstrap, tooling, skills | none |
| P01 | Asset registry, Shariah gate, risk config | none |
| P02 | Six years of market data → Bronze | none |
| P03 | Calendar + news research and downloaders | none (keyed sources disabled) |
| P04 | Silver cleaning, validation, data dictionary | none |
| P05 | Feature engine (backtest = live) | none |
| P06 | Backtester + risk manager | none — **human gate** |
| P07 | Strategies A/B/C + scenario library | none |
| P08 | ML models | none |
| P09 | Decision ledger + AI arena | none (mock + Ollama) — **human gate** |
| P10 | Streamlit dashboard | none |
| P11 | Live data + paper trading | none (public streams) |
| P12 | Binance Testnet execution | Testnet keys — **human gate** |
| P13 | Learning loop | none |
| P14 | Demo month runbook, go/no-go | none |

> **Repo update.** P00–P11 were built, with extra phases inserted (P09.5, P11a–P11a.3, P11b.0–P11b.2a.1, P11b.1a, P11c.0). P11 became read-only feed qualification and offline paper trading instead of live Binance paper trading. P12–P14 were redefined in `PROGRESS.md` as: P12 separately reviewed demo-only gateways (optional stock paper), P13 controlled offline learning and AI value evaluation, P14 30+ day forward paper/demo evaluation. None of P12–P14 has started. The human gates after P06 and P09 were passed by explicit owner direction with the Claude review recorded as "deferred" (D-0020). See section 24 for the full list.

### 19.3 Automation and documentation

- **One prompt:** `Read prompts/RUN_ALL.md and execute it.` Re-send the same prompt to resume.
- **Stops:** human gates (after P06, P09, P12), missing keys (continues other phases), long downloads (background jobs), unfixable failures, context limits (writes HANDOFF.md), any attempt to violate AGENTS.md.
- **Living files:** `PROGRESS.md`, `docs/state/progress.json`, `docs/HANDOFF.md`, `CHANGELOG.md`, `docs/decisions/DECISIONS.md`, `docs/pending.md`, `docs/review_queue.md`.
- **Per phase:** live journal (`docs/journal/`), research note with sources (`docs/research/`), ADRs (`docs/adr/`), phase report (`reports/phases/`), how-to guides (`docs/how-to/`).

### 19.4 Dashboard pages (P10)

Overview · Trades (with annotated charts) · Decisions · Shadow tracking · Arena · Models · Risk & health · Data quality · Controls (pause/approve; cannot change risk limits).

### 19.5 Demo go/no-go criteria (P14)

Paper results within the backtest's expected range; enough setups observed; slippage/fees within the cost model; every AI/ML filter shows non-negative shadow value or is switched off; AI spend within budget; zero reconciliation incidents; human signs the go decision; live starts with a small capital cap.

---

## 20. Codex configuration

- Web search is on by default in **cached** mode; **live** mode fetches current results.
- Project file `E:\trading bot\.codex\config.toml` containing exactly:

```toml
web_search = "live"

[sandbox_workspace_write]
network_access = true
```

- The file must contain only those lines and be named exactly `config.toml` (not `.txt`); the project must be marked **trusted** or Codex ignores it.
- Verified: Codex live search returned uv v0.13.4 (20 October 2026) from Astral's GitHub releases.

---

## 21. Earlier prototype: TradingView Pine Script

A Pine Script v6 strategy (`gold_london_sweep_fvg.pine`) was written during the XM/TradingView stage to sanity-check Strategy A:
- Asian range (00:00–07:00 London), sweep with reclaim within 3 bars during 07:00–10:00, structure shift via pivot break, FVG ≥ 0.15×ATR, limit entry at FVG edge/midpoint, stop beyond sweep − 0.1×ATR, 2R target.
- One trade per day, 1:1 exposure cap, 1% risk, spread modeled on entries and exits, cancel unfilled at London end, close all at 20:00.
- Long/short toggles (shorts disabled under the final long-only rules).
- Superseded by the Python backtester in P06/P07, but useful as a visual reference.

---

## 22. Current status, open items and next steps

*As of 2026-11-01, repository `main` at `aa65e85`.*

| Item | Status |
|---|---|
| Scholar ruling on USDT pairing and intraday XAUT | Approved (per user) |
| Scholar ruling on XAUUSD/EURUSD contract research direction | **Needed before any broker step** — repository says simulations are not Shariah certification |
| Development kit extracted into `E:\trading bot` | Done |
| Codex config (live search + network access) | Done; live search verified |
| Run `RUN_ALL.md` | Done through P11c.0 (see section 24) |
| Published to GitHub | Done — `Sabih0610/trading`, PRs #1 and #2 merged to `main`; hosted CI inactive |
| Full project audit | Done 2026-11-01 — `reports/reviews/FULL-AUDIT.md`: APPROVED WITH FIXES, no blockers, 5 major (same-bar limit-fill optimism, weak forbidden-endpoint guard, MLflow telemetry, `.env` file permissions, XAUT weekend flag unused) |
| Per-phase independent reviews | Mostly queued or deferred (P06 and P09 gates passed by owner direction) |
| Licensed historical dataset (EURUSD first, then XAUUSD) | **Blocking** — needs owner + independent reviewer rights approval before P11c.1 |
| P11c.1 genuine historical qualification | Not started |
| cTrader OAuth (P11b.1a) | Prepared offline; app approval pending; consent not performed |
| Genuine broker integration (P11b.2b) | NO-GO / not started |
| P12–P14 | Not started |
| Binance account, identity verification, sub-account | Pending |
| FRED (terms), news, AI provider, Jev, Telegram keys | Later; FRED paused on terms |
| Six-year bulk download | Deferred — needs ~779 GB free disk |
| PVARA licensing status | Monitor |
| Tax obligations | Confirm with advisor |

**Immediate sequence (current):** independent review of P11c.0 and the six RC remediation fixes → obtain and approve one licensed local EURUSD dataset → P11c.1 frozen evaluation on it (no tuning, no 2025+ access) → separately qualify XAUUSD → only then consider P12 demo gateways, P13 learning loop and the ≥30-day P14 paper run → go/no-go → small live.

---

## 23. Sources referenced

*Paraphrased findings from these sources appear above.*

- AAOIFI Shariah Standard No. 57 on gold (via Islamic finance coverage)
- Islamic Finance Guru forum and screening articles on CFDs, swap-free accounts, crypto and tokenized gold
- Ask Ghamidi forum (minority view on CFDs)
- Amanah Advisors certification of Tether Gold (XAUT)
- Amanie Advisors certifications of physical gold ETCs; Musaffa screening of iShares IGLN
- Meezan Gold Fund materials; SECP/PSX Shariah settlement discussion
- PVARA, Virtual Assets Act 2026 and Binance NOC coverage (Pakistan)
- CoinGecko exchange data for XAUT liquidity; Binance listing coverage (XAUT, 26 March 2026)
- Binance developer documentation (Spot API, WebSocket API, Testnet, changelog); Binance Skills Hub
- python-binance documentation
- TypeSafe AI / Jev coverage and documentation notes
- Nof1 Alpha Arena coverage (ForkLog, GN Crypto and others)
- TradeRank.ai live leaderboard (October 2026)
- xAI Grok pricing and Grok Bot coverage (diyai, The Rundown, Flavio Copes, unified.to, amplifying.ai)
- GitHub: tradermonty/claude-trading-skills, sickn33 quant-analyst, jeremylongshore backtesting skill, Alpaca skills library, TradingAgents, TradeMind, Clawd Grok
- Apify listings describing ForexFactory and GDELT access limits; cryptocurrency.cv
- OpenAI Codex configuration documentation (web search modes, project config)
- BrokerChooser (XM–TradingView integration), Exness help pages

---

## 24. Phases actually built (repository history)

From `PROGRESS.md` and `docs/decisions/DECISIONS.md`. "Review" is the independent-review status recorded in the repository.

| Phase | What was built | Outcome | Review |
|---|---|---|---|
| P00 | uv project, `src/tb` package, logging with secret redaction, audited skills | Done | Queued |
| P01 | Asset registry, Shariah gate, risk config with compiled hard ceilings | Done | Queued |
| P02 | Bronze ingestion (Binance archives, Dukascopy BI5) | Done on a 7-day sample; full download deferred for disk space | Queued |
| P03 | Calendar (official schedules authoritative) and headline-only news | Done; some sources gated on terms | Queued |
| P04 | Silver cleaning with checksum lineage | Done; DXY replica gated | Queued |
| P05 | One causal bar-by-bar feature engine shared by backtest and live | Done | Queued |
| P06 | Pessimistic event-driven backtester + deterministic risk manager | Done | Deferred by owner |
| P07 | Strategies A/B/C + scenario library | Built; **not evaluable** (no pre-2025 XAUT history) | Queued |
| P08 | ML with purged/embargoed CV, calibration, size-reduction only | Built; empirical data blocked | Queued |
| P09 | Append-only decision ledger and AI arena (veto / multiplier ≤ 1 only) | Done | Deferred by owner |
| P09.5 | Pivot to XAUUSD/EURUSD local contract research; tighter risk defaults | Done | Queued |
| P10 | Read-only Streamlit evidence dashboard | Done | Queued |
| P11a–P11a.3 | Read-only MT5 feed, clock profiles, Twelve Data Basic M1 reference feed | MT5 not data-qualified (≈UTC+3 clocks); Twelve Data qualified for bounded M1 EURUSD/XAUUSD reference only | Queued |
| P11b.0–P11b.0.1 | Rights-gated shadow research and two price-only hypotheses (EMA/channel) | Done offline; genuine rights blocked | Queued |
| P11b.1 | Read-only cTrader broker quote readiness | Done offline; genuine unverified | Queued |
| P11b.2a, P11b.2a.1 | Offline paper lab (persistent accounting, recovery), independent validation, gated Windows CI | Done offline; hosted CI inactive | Queued |
| P11b.1a-Prep / RC / remediation | Owner-assisted cTrader OAuth prepared offline; release review; six security/accounting fixes | Offline only; genuine OAuth not done | Remediation review pending |
| P11c.0 | Broker-independent local market research MVP (registry, import, evaluation, replay, dashboard) | Done on sample data; 1,084 tests reported passing | Pending (merged to `main` via PR #2) |
| P12–P14 | Demo gateways, learning loop, 30+ day forward evaluation | Not started | — |
