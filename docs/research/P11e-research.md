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

The required original Vision PDF is larger than the existing text-document bound.
Retain the generic 128 KiB limit and add a narrow 1 MiB PDF path only for the exact
closed Vision terms URL/name, with PDF header, digest and bounded 64 KiB scanning.
All owner/reviewer, fake-evidence, lifetime and other-document checks stay intact.
Nineteen existing/new Vision integration cases pass, including non-PDF/wrong-name
refusal and the hard PDF bound.

## Download flow confirmed

HistData's public HTML form submits its six provider fields to `/get.php` with the
metadata page as Referer, same session, no API key or script execution. Archived past
years expose annual ZIPs named `DAT_ASCII_<SYMBOL>_M1_<YEAR>.zip` with the corresponding
CSV member; archived monthly forms can have empty tokens. Use annual cadence only
when the whole nominal fixed-EST archive fits the approved UTC window. Do not retry
unavailable monthly forms indefinitely. The dated homepage and FAQ snapshots have no
terms/license/legal link; this is the review's medium-confidence terms-absence evidence,
not a claim that the provider has granted unrestricted rights.

Provider sources accessed 2026-11-01:
[ASCII format](https://www.histdata.com/f-a-q/data-files-detailed-specification/),
[annual archive form](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd/2021),
[homepage](https://www.histdata.com/) and [FAQ](https://www.histdata.com/f-a-q/).

A constant UTC−5 annual file extends five hours past the nominal year. The approved
2024 whole-file boundary is unsafe; the 2020 annual file begins before approval.
Refuse both before network access, record precise private reasons, and leave missing
bars absent. Source calendars exclude weekend/rollover from coverage penalties.
Source-specific quality paths avoid collisions when backup and primary coexist.
See [ADR 0021](../adr/0021-approved-forex-history.md).

Admission is rechecked around every bounded FX transport attempt and before partial
original persistence. Retention expiry is an authorization refusal, not a provider
technical failure: it must stop without producing a technical report or invoking
backup. Owned tests advance the clock during a response and assert no raw write.
