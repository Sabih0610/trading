# P11o research: causal daily/weekly signals

The library defines deterministic chart conditions on completed fictional bars. These are signal definitions, not evidence of an edge or permission to trade. P's separately reviewed registration decides any future genuine experiment.

| Question | Options | Decision / reason |
|---|---|---|
| Pattern smoothing | Two-sided retrospective fit; one-sided endpoint kernel | Trailing Gaussian kernel at each historical endpoint, never refit using later observations. Extrema require later *already completed* confirmation bars. |
| Trend / breakout | Current moving windows including an unclosed bar; explicit availability cutoff | UTC open/end and known-at stamps, bounded completed windows; breakout excludes its signal bar from the prior high. |
| Missing/incomplete bars | Interpolate, silently drop, or refuse the affected window | Keep completeness metadata; no signal when an affected required window is incomplete. No prices filled. |
| Numbers and time | Binary-float thresholds/naive timestamps; Decimal/awareUTC | Positive finite Decimal and explicit UTC boundaries avoid ambiguous costs and clocks. |
| Exits and cost hurdle | Mutable discretionary stops; deterministic long-only levels | Initial stop below entry, trailing stop never lower,1..10days; move>=5x full quoted-spread/fees/slippage round trip. RiskManager remains final authority. |

Primary sources accessed2026-11-05:

- [Lo, Mamaysky and Wang, author-hosted paper](https://www.mit.edu/~wangj/pap/LoMamayskyWang00.pdf), Journal of Finance2000; [NBER abstract](https://www.nber.org/papers/w7613). Their systematic kernel-pattern study finds incremental information in some patterns, not proof of this library's profitability. This project deliberately changes the retrospective smoother into a one-sided causal definition; it is not a replication of their empirical result. Original NBER PDF endpoint returned403, so the author-hosted version was used.
- [Python3.12 Decimal](https://docs.python.org/3.12/library/decimal.html): decimal quantities/thresholds can be represented directly and finite values must be checked.
- [Python3.12 datetime](https://docs.python.org/3.12/library/datetime.html): aware timestamps identify an unambiguous instant; all signal clocks here must be UTC.
- [Owner/reviewer swing evidence](../../reports/reviews/swing-research-2026-11-05.md) and [P11o prompt](../../prompts/P11o-chart-signals.md): restrict this track to long-only causal definitions and fixtures, no candlestick triggers or genuine evaluation.

Pinned environment remains Python3.12, pytest9.1.1, Hypothesis6.170.5 and strict mypy2.4.0. No dependency changes. The historical paper is used as the explicitly requested methodology source, not represented as recent evidence.
