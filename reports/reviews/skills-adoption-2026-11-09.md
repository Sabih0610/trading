# Skills review: copy-trading, positioning and sentiment (2026-11-09)

Owner request: "find as many copy trader skills so we can have everything we need". Searched the Claude plugin
directory, the user's skill library and public skill indexes. Every candidate below was read before any decision.

## Searched and found

| Source | Result |
|---|---|
| Claude plugin directory | No copy-trading, positioning or COT plugin (only unrelated finance/messaging tools) |
| User skill library | No matching skills |
| [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) (MIT, commit `84fa6127`, actively maintained) | 70+ skills; the relevant ones are reviewed below. Our existing `backtest-expert`, `market-environment-analysis` and `market-news-analyst` came from here |
| [agiprolabs/claude-trading-skills](https://github.com/agiprolabs/claude-trading-skills) `copy-trading` | Solana DEX wallet copying: crypto leverage/memecoin context; out of scope and not halal-screened. Not adopted |
| HKUDS AI-Trader `copytrade` | Automatic position copying: executes trades, which project rules forbid. Not adopted |

## tradermonty skills relevant to "learn from other traders"

| Skill | What it does | Data it needs | Decision |
|---|---|---|---|
| `cot-contrarian-detector` | COT Index of large speculators; flags crowded long/short (90/10) | FMP **Premium+ (paid)** | **Method adopted** (COT Index, 156/26-week windows, 90/10 thresholds, "crowding is a precondition, not a signal") and reimplemented on free CFTC files in P12e. Scripts not installed. |
| `contrarian-setup-gate` | Gate that requires news-failure and price confirmation before a contrarian trade | FMP | Idea noted for the G1–G3 study design; not installed |
| `institutional-flow-tracker` | "Copy the smart money": quarter-over-quarter institutional ownership from SEC 13F filings | FMP (free tier limited) | **Best legal form of copy trading for stocks.** Planned on the free SEC Form 13F data sets (same SEC rights already registered). Its own guidance says 3–12-month horizon, so under the 10-day cap it is used as a **filter** (prefer stocks institutions are accumulating), not as a holding signal |
| `pead-screener` | Post-earnings drift with weekly red-candle pullback breakout | FMP | Method matches S4 family A; the weekly pullback-breakout variant is recorded as a candidate addition to the S4 draft |

## Why scripts are not installed

All four depend on Financial Modeling Prep keys. The COT endpoint needs a paid plan, which breaks the owner's
no-spend rule. We keep the ideas and rebuild them on free, rights-checked, point-in-time sources (CFTC, SEC),
inside our tested pipeline. MIT credit is kept in the code docstrings.

## Copy trading in a halal, long-only form

1. **Gold crowd positioning** (P12e, CFTC): buy spot gold only when the crowd is relatively short, or follow the
   speculators as a control.
2. **Smart-money stock filter** (next, SEC 13F): prefer screened stocks that big funds are accumulating.
3. Not adopted: copying a broker's live traders (CFD/leveraged, unverifiable and against the rules).
