# P12e: gold crowd-positioning data (CFTC COT) and side-study design

Authority: owner chat 2026-11-09 ("do the side study on gold ... make things proper for our analysis").
Builder/self-reviewer: Claude. Data-only positioning; no orders, no accounts, no money. 2025+ stays locked.

## Why this source

The owner asked to learn from copy traders. Broker copy-trading records are not freely available with rights
(OANDA ended historical position books in 2024; IG/DailyFX sentiment has no free history). The legally clean,
free and long-history version of "what the crowd is doing in gold" is the **CFTC Commitments of Traders**
report for COMEX gold (code 088691). It is US-government public domain ("may be freely distributed and copied",
cftc.gov Web Policy). It gives weekly positions of:

- **Non-commercial / managed money:** hedge funds and CTAs (the "large speculators" a copy trader would copy).
- **Non-reportable:** small traders below reporting size (the retail crowd).
- **Commercial / producers / swap dealers:** hedgers (not a sentiment signal).

## Data pipeline (built in P12e)

- Closed allowlist: legacy `deacot{2016..2024}.zip` and disaggregated `fut_disagg_txt_{2016..2024}.zip`.
- Gold rows only; both reports joined on the Tuesday; open interest must agree.
- `known_at` = report Tuesday **+ 6 days**, 23:59:59 New York (Friday release plus 3 days' holiday slack).
  Reports whose `known_at` would fall in 2025 are dropped and counted.
- Rights-checked registry, immutable Bronze, Silver weekly table, quality report.
- COT Index = (net − min) / (max − min) × 100 over the last N reports (method credited to
  tradermonty/claude-trading-skills `cot-contrarian-detector`, MIT, reimplemented on free data).

## Side-study design (DRAFT; registered only after this pipeline is built and frozen)

Instrument: long-only spot gold. Prices: the existing rights-checked swing-v1 gold daily bars (XAUUSD
2021–2023 as the development proxy for XAUT; PAXG for 2024), same as P11p. Costs: the existing XAUT cost
model. Risk: unchanged RiskManager (0.25% XAUT risk override, ≤ 10-day holds, no weekend entries).

Signal check each Monday after `known_at`; entry at the next session open; stop 2 × ATR(14); time exit h.

| Family | Hypothesis | Rule | Trials |
|---|---|---|---|
| G1 | Fade the speculators (Shapiro) | non-commercial COT Index ≤ L | L ∈ {10, 20} × lookback ∈ {156, 26} × h ∈ {5, 10} = 8 |
| G2 | Fade the hedge funds | managed-money COT Index (156) ≤ L | L ∈ {10, 20} × h = 4 |
| G3 | Fade the retail crowd | non-reportable COT Index (156) ≤ L | L ∈ {10, 20} × h = 4 |
| G4 | Follow the speculators (Wang 2001: speculators as trend followers; control) | non-commercial index (156) ≥ 90 and up week-over-week | h = 2 |

18 trials; the deflated-Sharpe count adds them to every earlier registered trial. Selector ≥ 20 training trades.
Development 2021–2023, validation 2024 once, 2025+ locked. Benchmarks: random weekly entry (same holds and
stops) and buy-and-hold gold.

**Honest prior:** extremes are rare (a few weeks a year), so trade counts may fall short of 20, and the verdict
may again be "insufficient evidence". Crowding is described by its own advocates as a precondition, not a
signal on its own.
