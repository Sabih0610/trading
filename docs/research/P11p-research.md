# P11p methodology research

2026-11-06 UTC. This note uses public methodology and merged source definitions,
not genuine market data or observed P results. The owner-fixed search and pass
bars govern; literature supplies cautions, not evidence this strategy works.

| Question | Options compared | Decision |
|---|---|---|
| Search bias | nominal Sharpe / trial-adjusted DSR | fixed243 trials; training-only null scale; disclose variance limitation |
| Causality | centred smoothing / trailing O kernel | trailing only, explicit availability and3/3 support delay |
| Dependence | iid trades / weekly blocks | whole weekly blocks plus preregistered2-week sensitivity for10-day holdings |
| Gold warm-up | splice XAU/PAXG / independent source history | cold-start PAXG without historical price stitching |
| Intraminute ordering | assume tick chronology / bounded orderings | stop-first and target-first minute bounds plus daily stop-first sensitivity |

Sources accessed2026-11-06:
- Bailey and Lopez de Prado, [Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf),
  2014 primary paper: trial count and nonnormality matter. No guarantee for correlated searches.
- Liu and Tsyvinski, [Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877),
  NBER24877: historical momentum hypothesis, not validation of this universe/protocol.
  Search metadata available; direct page returned403 on this check.
- [arch7.2.0 time-series bootstrap documentation](https://arch.readthedocs.io/en/stable/bootstrap/timeseries-bootstraps.html):
  distinguishes stationary/circular/moving blocks. We freeze weekly/calendar blocks
  rather than optimize block length after outcomes; no dependency upgrade.
- [Owner-approved swing research](../../reports/reviews/swing-research-2026-11-05.md)
  and merged [O definitions](../../src/tb/strategies/signals.py).

Risks: short development span, overlapping10-day holdings, incomplete reference
calendar, gold cold start, same-minute OHLC ambiguity and random baseline count
mismatch can make the result insufficient/nonpassing. No additional history,
post-data block choice, looser gate or permission change is a remedy.
