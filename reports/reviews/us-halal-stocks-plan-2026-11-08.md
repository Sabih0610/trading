# US halal stocks: feasibility and plan (2026-11-08)

The owner chose US Shariah-compliant stocks as the first halal expansion after 243 Stage 3 crypto/gold trials
found no edge. This file checks whether the route is open, then proposes a build. **Nothing here is approved yet.
No rule, venue, account, data or trial changes are made until the owner says yes.**

## 1. Can it be done? (blockers checked)

| Question | Finding | Confidence | Source |
|---|---|---|---|
| Will a US broker with an API accept a Pakistan resident? | Interactive Brokers (IBKR) accepts residents of all countries except OFAC-prohibited ones; Pakistan is not prohibited. Opening needs CNIC + proof of address, 24–72 h review. Has a full trading API and a free paper account. | Medium (IBKR docs + aggregators) | [IBKR registration docs](https://www.interactivebrokers.com/docs/web-api/account-management/client-registration/data-for-client-registration), [BrokerRank](https://brokerrank.net/broker/interactive-brokers/pakistan), [ElevatePay guide](https://www.elevatepay.co/blog/open-ibkr-account-pakistan-elevate-pay) |
| Alpaca (commission-free API)? | Pakistan not named in any supported-country list found. | Unverified, likely no | [Alpaca about](https://alpaca.markets/about) |
| May a Pakistan resident send money abroad to buy shares? | SBP FE Manual Ch. 20 Para 13: a resident individual may invest **up to USD 25,000 a year** in listed foreign shares **through a bank**. Ch. 20 was re-consolidated 2025-09-11; no newer individual limit found. | Medium (SBP FAQ; date unclear) | [SBP FAQ](https://www.sbp.org.pk/epd/pdf/FAQs.pdf), [Ch. 20](https://www.sbp.org.pk/assets/document/Chapter-20-foreign-exchange-manual.pdf), [SBP 2025 circular](https://www.sbp.org.pk/epd/2025/FECL9.htm), [SBP 2021 release](https://www.sbp.org.pk/press/2021/Pr1-10-Feb-21.pdf) |
| US day-trading rule ($25k PDT)? | **Removed.** SEC approved FINRA Rule 4210 amendments 2026-04-14, effective 2026-06-04; brokers phase in until about 2027-10. Irrelevant anyway for a **cash** account (we never use margin). Cash accounts must trade with **settled** funds (T+1). | High | [Federal Register 2026-04-17](https://www.govinfo.gov/content/pkg/FR-2026-04-17/html/2026-07485.htm), [E*TRADE](https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change) |
| Shariah screening data? | Musaffa (AAOIFI, scholar-certified) and Zoya offer APIs at **custom (sales-quoted) prices**. Neither gives a *historical, point-in-time* status, which a backtest needs. | Medium | [Musaffa methodology](https://uat2.musaffa.com/screening-methodology/), [HalalTerminal comparison](https://www.halalterminal.com/blog/posts/best-islamic-finance-apis-2026) |
| Price history with clear rights? | No free source with confirmed terms. Alpaca free = IEX venue only; Tiingo/EODHD are paid with personal-use licences (fine: we publish aggregates only). | Low; must read each licence | [Qveris comparison](https://api.qveris.ai/guides/stock-api-free-comparison), [Geekflare](https://geekflare.com/guides/best-stock-market-api/) |

**Verdict: the route looks open**, with two items only the owner can confirm: the bank's outward-remittance process
under Para 13, and the IBKR application itself. Claude never opens accounts or enters credentials.

### Fallback broker: XM "Shares" account (owner decision 2026-11-08: list it as the fallback)

**Owner decision 2026-11-08 (later):** the owner will not deposit the USD 10,000 XM minimum until a strategy
has been tested successfully on a real account. XM is therefore **deferred**; the build targets IBKR only.

If IBKR refuses the application, the fallback is XM's **Shares** account, not any MT5 CFD account.

| Point | XM Shares account | XM swap-free (Islamic) CFD accounts |
|---|---|---|
| What you hold | Real shares, unleveraged (reviews say about 1,150 stocks) | A CFD price contract; no ownership |
| Shariah | Acceptable after screening, as with IBKR | **Rejected** (AAOIFI Std 57; project record §3.1). "Swap-free" only removes overnight interest; reviews mention admin fees and revocable status |
| Minimum deposit | About **USD 10,000** (above the USD 1,000 budget) | n/a |
| Commission | About **USD 1 per US-share order** (≈ 3× IBKR's minimum) | n/a |
| Regulation | Offshore (Belize FSC): weaker client protection | n/a |
| Automation | MT5, controllable from Python (MetaTrader5 package) | n/a |

The same SBP Para 13 bank remittance applies to any foreign broker. All XM facts come from third-party reviews
and must be checked against XM's own account terms before use:
[InvestingLive](https://www.investinglive.com/brokers/xm-group/review/),
[InvestinGoal](https://investingoal.com/xm-account-types),
[DailyForex](https://www.dailyforex.com/forex-brokers/xm-review/islamic-account),
[Tradersunion](https://tradersunion.com/brokers/forex/view/xm_group/halal-or-haram/).
The rule "no CFDs on any platform" stands for every MT5 broker.

## 2. Shariah conditions that change the build

1. **Cash account only.** Margin is riba; the cash account also avoids all day-trading rules.
2. **Opt out of IBKR interest on idle cash and of the stock-yield (securities-lending) programme**, or purify any
   interest received.
3. **Dividend purification:** donate the non-compliant-income share of each dividend (AAOIFI). The bot records it.
4. **Screen = AAOIFI Std 21:** no prohibited core business; interest-bearing debt < 30% of market cap;
   interest-bearing deposits < 30%; non-compliant income < 5%. Re-screened every quarter; a stock that fails is sold.
5. Long-only, spot (real shares), no options, no shorting: unchanged.

## 3. The point-in-time problem and its fix

Backtesting today's halal list over 2015–2024 is **lookahead and survivorship bias**: it keeps only firms that
passed *later*. The fix is to compute AAOIFI ratios ourselves from **SEC EDGAR XBRL filings**, which are US
government public data, free, and carry the **filing date** (so a ratio is used only after it was public).
Business screening uses SIC codes plus a hand-kept exclusion list. Musaffa/Zoya are then used only to
**cross-check** current status, not to build history. EDGAR asks automated clients to identify themselves with a
contact address: **the owner must choose what to put there.**

## 4. Costs: the small-account trap

US large caps trade at about 0.01–0.03% spread, but IBKR Pro charges about **USD 0.35 minimum per order**.

| Position size | Commission per side | Round trip with spread |
|---|---|---|
| USD 200 | 0.175% | ~0.37% (same as crypto) |
| USD 500 | 0.07% | ~0.16% |
| USD 1,000 | 0.035% | ~0.09% |

With USD 1,000, the cheap-cost advantage appears only with **one or two positions at a time**, so breadth in
*selection* (many stocks screened) is high but breadth in *holdings* is low. The cost model will include the
minimum commission; this is the main reason a USD 1,000 account cannot run a 20-stock portfolio profitably.

## 5. Strategy design (quant)

Fundamental law: IR ≈ IC × √Breadth. Crypto gave 4 assets; a screened US large-cap universe gives roughly
150–300 names, so the same weak skill (IC) is worth about **6–9× more** in breadth terms.

Candidate families, all long-only, daily bars, rebalanced weekly, each with documented evidence in US equities:

| Family | Rule sketch | Evidence |
|---|---|---|
| A. Time-series trend + vol targeting | Hold the halal ETF (SPUS/HLAL) or top names only when above their 100/200-day average | Moskowitz-Ooi-Pedersen 2012; Moreira-Muir 2017 |
| B. Cross-sectional momentum | Buy the 1–2 strongest 6–12-month names among the screened universe, skip last month | Jegadeesh-Titman 1993, decades of replication |
| C. Short-term reversal in up-trends | Buy a large cap after a 1-week drop while its 200-day trend is up; hold ≤ 10 days | Lehmann 1990; weaker after costs (must be tested) |
| D. Post-earnings drift | Buy after a positive earnings surprise filed on EDGAR | Bernard-Thomas 1989; decaying in large caps |

The families are weakly correlated, so an equal-risk ensemble improves Sharpe by about √(N/(1+(N−1)ρ)).
All trials are pre-registered and counted on top of the existing 243 for the deflated Sharpe. 2025+ stays locked.

**Honest expectation:** a good long-only equity system makes 10–20% a year. On USD 1,000 that is about
**USD 8–17 a month**, not USD 300. The benchmark to beat is simply holding SPUS/HLAL (a halal S&P-type ETF).

## 6. Build stages (after approval)

| Stage | Work | Needs from owner |
|---|---|---|
| S0 | AGENTS.md + skill: add asset class "US equities, AAOIFI-screened, cash account, IBKR"; keep all risk limits | **Approve the venue/asset-class change (reopens O-6)** |
| S1 | EDGAR ingest → point-in-time AAOIFI screen (Bronze/Silver/Gold, rights record) | Contact string for EDGAR's User-Agent |
| S2 | Daily price history ingest with a rights record, including delisted names | Choose/pay a data source (≈ USD 10–30/month) or wait for IBKR account data |
| S3 | Cost model with minimum commission; T+1 settled-cash rule; dividend purification ledger | none |
| S4 | Pre-register families A–D; one evaluation; aggregates only published | none |
| S5 | IBKR **paper** account trading through the API (fallback: XM Shares account through MT5) | Owner opens the broker account and paper login themselves |

Real money stays prohibited until a strategy passes and the owner separately authorizes it.

## 7. Decisions for the owner

1. Approve US AAOIFI-screened stocks as a new asset class/venue (IBKR, cash account)?
2. Will you confirm with your bank that a Para 13 outward remittance (≤ USD 25,000/yr) is available to you?
3. Data: pay for a daily price source now, or wait until the IBKR account exists?
4. ~~The contact text for EDGAR requests.~~ Answered 2026-11-08 (kept in the private root, not in the repository).
5. Earlier open items still stand: candidate 1 rules, XAUT recorder task fix.

## Gaps

- IBKR minimum commission and Pakistan eligibility should be confirmed on IBKR's own pricing/application pages.
- US–Pakistan tax treaty dividend withholding rate not verified (default 30% for non-residents via W-8BEN).
- No licence text for any price vendor has been read yet.
