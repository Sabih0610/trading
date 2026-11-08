# P12b: US stock cost, settlement and purification model (stage S3)

Authority: owner-approved US halal stocks plan (stage S3 needs no owner input) and AGENTS.md (cash account,
settled cash only, purification, IBKR). Builder/self-reviewer: Claude. No data, prices, orders or trials.

## Commission (IBKR Pro, official page retrieved 2026-11-08)

| Plan | Per share | Minimum per order | Maximum per order | Extra fees |
|---|---|---|---|---|
| Tiered (≤ 300k shares/month) | USD 0.0035 | USD 0.35 | 1% of trade value | exchange (model: USD 0.0030/share, pessimistic remove-liquidity), clearing USD 0.00020/share |
| Fixed | USD 0.005 | USD 1.00 | 1% of trade value | none beyond regulatory |

Rule: commission = min(max(rate × shares, minimum), 1% × value); when the 1% cap is below the minimum, the
cap applies (IBKR's own example). Fractional trades: same rates, floor USD 0.01. Regulatory on sells only:
SEC fee 0.0000278 × sale value (the highest rate in force 2020–2026; the 2026 page shows 0.0000206), FINRA
TAF USD 0.000195/share sold (capped USD 9.79; pessimistic), CAT USD 0.000003/share on every fill. IBKR Lite is US-residents-only, so it is not modelled.

## Execution (pessimistic)

Half-spread + slippage per fill: 0.06% for names with 20-day median dollar volume ≥ USD 50 m (S2 filter);
anything less liquid is not tradable. Fills at the next session's open (no same-bar lookahead).

## Settlement (cash account)

Settlement date = trade date + 2 settlement days for trades before 2024-05-28, + 1 from 2024-05-28 onward.
A settlement day is a trading day (taken from the price calendar) that is not Columbus Day (second Monday of
October) or Veterans Day (11 November; Sunday → Monday; Saturday → not observed). Buys use settled cash
only; sale proceeds become spendable on their settlement date. No margin, no free-riding.

## Purification and interest

Dividend purification = dividend × (interest income / revenue) from the point-in-time AAOIFI components;
unknown ratio ⇒ purify 5% (the AAOIFI ceiling). Deducted from equity on the pay date. Interest on idle cash = 0
(opted out). Both recorded in a ledger.

## Tests

Commission edge cases (min, cap below min, per-share above min, fractional floor); sell-side fees only on sells;
round-trip cost on a USD 500 order; T+2 → T+1 switch on 2024-05-28; holiday and Columbus/Veterans gaps;
weekend; settled-cash refusal; proceeds unusable before settlement; purification with known/unknown ratio;
no negative or NaN inputs.
