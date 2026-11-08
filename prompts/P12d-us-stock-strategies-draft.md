# P12d (DRAFT): US halal stock strategies, Stage 3 pre-registration (stage S4)

Status: **draft, not registered.** It becomes a registration only after S2 price data exists, the code is frozen,
and its SHA is recorded before any price is read. Authority: owner-approved US halal stocks plan, plus the owner's
2026-11-08 decision to **keep the 10-day holding cap** for stocks. Builder/self-reviewer: Claude.

## Fixed constraints (unchanged rules)

- Long-only, real shares, IBKR cash account, settled cash only (P12b), whole shares only.
- Simulated account **USD 1,000**. RiskManager defaults: 0.5% planned risk per trade, 2% daily loss, 5% peak
  drawdown, one position, exposure ≤ 1×, holding ≤ **10 calendar days** (compiled ceiling).
- Costs at the **actual order size** through `tb.backtest.us_equity_costs` (Tiered plan). Typical sizes are
  USD 125–250, so a round trip costs about **0.4–0.7%**. The existing cost rule applies: expected move ≥ 5× cost.
- Decisions on a completed daily bar; fills at the next session's open; stops intraday from the next session.

## Universe at each decision date t (point-in-time)

1. AAOIFI pass from P12a `components_at(t)` with market cap = close(t) × latest shares outstanding known at t
   (`dei:EntityCommonStockSharesOutstanding`, to be added in S2), and `debt_reported` required.
2. Price ≥ USD 10; 20-day median dollar volume ≥ USD 50 m; at least 260 trading days of history.
3. Companies delisted later stay in the universe until their last bar (S2 must carry delisted history).

## Strategy families (16 trials; DSR counts 243 + 16 = 259)

Each family is short-horizon by design and has documented evidence in US stocks.

| # | Family | Signal at close t | Exit | Trials |
|---|---|---|---|---|
| A | **Earnings-filing drift** (PEAD) | 10-Q/10-K filed (known by t) with standardized unexpected EPS (diluted EPS change vs same quarter last year ÷ its 8-quarter std) in the top q of the universe that quarter; stock above its 50-day average | hold h days | q ∈ {10%, 5%} × h ∈ {5, 10} = 4 |
| B | **Filing-day gap continuation** | Open-to-close return on the first session after a 10-Q/10-K filing ≥ g, close in the top quarter of the day's range | hold h | g ∈ {3%, 5%} × h ∈ {5, 10} = 4 |
| C | **New-high breakout** (George-Hwang 52-week-high momentum, short form) | Close at a new N-day high; 200-day trend up | hold h | N ∈ {126, 252} × h ∈ {5, 10} = 4 |
| D | **Pullback in an up-trend** (short-term reversal, low prior; control) | 5-day return ≤ −d; close above its 200-day average | hold h | d ∈ {5%, 8%} × h ∈ {3, 5} = 4 |

Common rules: stop = 2 × ATR(14) below the fill (sets size through the 0.5% risk rule); time exit at h sessions
or the 10-day ceiling, whichever is first. With one position at a time, the candidate with the strongest
signal (A: highest SUE; B: largest gap; C: largest 20-day dollar volume; D: deepest pullback) is taken, and ties
break by CIK. No re-entry into the same stock within 10 days of an exit.

## Evaluation (same discipline as P11f/P11p)

- Development folds: 2021, 2022, 2023 (walk-forward; each year evaluated with parameters chosen on prior years
  only). Validation: **2024, evaluated once** for the frozen selection. **2025+ stays locked.**
- Selector: ≥ 20 training trades per cell, best mean net R after costs.
- Pass bar: positive mean net R on 2024 with weekly block-bootstrap 95% CI above 0; DSR with N = 259 above the
  benchmark; beat the random-entry benchmark (same universe, holds and stops; 95th percentile of 30 seeds);
  report against buy-and-hold **SPUS** (halal S&P ETF) on return and drawdown.
- Report expectancy per trade, break-even win rate, cost share of gross profit, trades per month and turnover.

## Honest priors

- Large-cap PEAD and reversal have weakened since 2000s; costs of 0.4–0.7% per round trip are high for
  10-day trades. A likely outcome is "no pass". That is still useful: it stops real money being risked.
- A pass would justify only paper trading (S5), never real money.

## Needed before registration

S2 prices (free Tiingo key from the owner), shares outstanding and diluted EPS tags added to the SEC Silver,
CIK-to-ticker mapping including delisted names (limitations disclosed), and this draft frozen with a SHA.
