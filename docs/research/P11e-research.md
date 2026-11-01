# P11e acquisition research

Primary sources accessed 2026-11-01. Scope and approvals are the owner's P11e prompt
and [independent rights review](../../reports/reviews/dataset-rights-review-2026-11-01.md).
No consent file was found at the specified owner path; HistData is the approved backup.

| Question | Choice / reason | Source |
|---|---|---|
| Vision evidence | Save the exact v1.0, 2026-08-26 PDF; pin SHA-256, existing private scope and finite retention. | [Terms PDF](https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf) |
| HistData format | Generic ASCII M1, original archives retained; source/side always explicit. | [Download](https://www.histdata.com/download-free-forex-data/) |
| Clock, side and volume | Fixed UTC−5 without DST, bid OHLC; volume unreliable. Use constant +5 hours and no invented ask/spread. | [FAQ](https://www.histdata.com/f-a-q/) |
| Missing consent | Do not contact Dukascopy; preserve legacy samples as not for evaluation and use backup. | P11e B0 and rights review §2a |
| Publication | Keep genuine prices and quality artifacts ignored. Public report links to a private per-symbol/year table. | P11e hard rule and acceptance |

Open checks: exact download form/nonce flow; dated homepage/FAQ terms-absence evidence;
fixed-offset month boundaries (December 2024 can nominally extend into UTC 2025);
calendar-aware expected grids and source-specific rollover flags; bounded acquisition
and yearly shared feature runtime. Unsafe partitions must be refused before network,
with precise private gap reasons rather than reading holdout observations.
