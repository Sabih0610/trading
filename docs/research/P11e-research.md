# P11e acquisition research

Primary sources accessed 2026-11-01. Scope and approvals are the owner's P11e prompt
and [independent rights review](../../reports/reviews/dataset-rights-review-2026-11-01.md).
No consent file was found at the specified owner path; HistData is the approved backup.

| Question | Choice / reason | Source |
|---|---|---|
| Vision evidence | Save the exact v1.0, 2026-08-26 PDF; pin SHA-256, existing private scope and finite retention. | [Terms PDF](https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf) |
| HistData format | Generic ASCII M1, original archives retained; source/side always explicit. | [Download](https://www.histdata.com/download-free-forex-data/) |
| Clock, side and volume | Provider FAQ says fixed UTC−5, but reviewed original files contradict it. Use the reviewed EU-week clock, verify the autumn provider duplicate, bid OHLC and unreliable volume; no invented ask/spread. | [FAQ](https://www.histdata.com/f-a-q/) |
| Missing consent | Do not contact Dukascopy; preserve legacy samples as not for evaluation and use backup. | P11e B0 and rights review §2a |
| Publication | Keep genuine prices and quality artifacts ignored. Public report links to a private per-symbol/year table. | P11e hard rule and acceptance |

Open checks: exact download form/nonce flow; dated homepage/FAQ terms-absence evidence;
reviewed source-clock month boundaries (December 2024 can nominally extend into UTC 2025);
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
when the whole nominal source-clock archive fits the approved UTC window. Do not retry
unavailable monthly forms indefinitely. The dated homepage and FAQ snapshots have no
terms/license/legal link; this is the review's medium-confidence terms-absence evidence,
not a claim that the provider has granted unrestricted rights.

Provider sources accessed 2026-11-01:
[ASCII format](https://www.histdata.com/f-a-q/data-files-detailed-specification/),
[annual archive form](https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd/2021),
[homepage](https://www.histdata.com/) and [FAQ](https://www.histdata.com/f-a-q/).

January is UTC−5, so a nominal annual file extends five hours past the nominal year. The approved
2024 whole-file boundary is unsafe; the 2020 annual file begins before approval.
Refuse both before network access, record precise private reasons, and leave missing
bars absent. Source calendars exclude weekend/rollover from coverage penalties.
Source-specific quality paths avoid collisions when backup and primary coexist.
See [ADR 0021](../adr/0021-approved-forex-history.md).

Admission is rechecked around every bounded FX transport attempt and before partial
original persistence. Retention expiry is an authorization refusal, not a provider
technical failure: it must stop without producing a technical report or invoking
backup. Owned tests advance the clock during a response and assert no raw write.


## Fix round research — 2026-11-01

The reviewer checked the original pre-2025 files and corrected the source clock
specification. This observed contract supersedes the FAQ's fixed-EST claim.

| Question | Alternatives | Decision |
|---|---|---|
| Seasonal mapping | Fixed +5, New York DST, London trading-week state | +4 during weeks whose Sunday noon London is BST, +5 otherwise. Keep US/EU mismatch weeks. |
| Autumn repeated hour | Treat as two hours, arbitrary dedupe, verify exact source bytes | Owner checked all three dates and corrected the review: one +5 h offset for the whole week. Keep the first hour; drop the second only if all 60 timestamps/OHLCV fields are byte-identical. Otherwise quarantine the whole day and flag it. |
| Existing wrong Bronze conversion | Rewrite Bronze, shift its deduplicated timestamps, reparse original CSV | Verify original CSV hash and bounded size and re-decode in Silver. Preserve every original/legacy Bronze byte and original policy/retention identity. |
| Fixture admission | Private HTTPX attribute, explicit injected mock client | A dedicated client accepts only MockTransport, plus the existing offline flag and explicit fixture opt-in. No network-capable client qualifies. |
| Rate limits | Ignore header, unlimited retries, bounded delay or stop | Retry-After seconds/HTTP-date capped at 60 s, maximum three attempts; missing/invalid header stops on first 429. |

The owner clarified the repeated-hour bytes after the initial review. The interim
ordered-fold interpretation was stopped before any new generation was published.
A verified duplicate is recorded as `provider_duplicate_hour`. A differing or
incomplete repeated block quarantines the day, preserving original evidence but
publishing no bars from that day. Genuine contradictions require stopping and
asking the owner. Weekly open flags never cause timestamps to be shifted.
Expected EURUSD opens are 17:00 New York; XAUUSD 18:00. The rollover flag is the
17:00–18:00 New York convention expressed in the same source clock, separately
excluded from missing-open coverage, not asserted as a full instrument closure.

Primary engineering sources accessed 2026-11-01:
[Python 3.12 zoneinfo](https://docs.python.org/3.12/library/zoneinfo.html),
[PEP 495 ordered folds](https://peps.python.org/pep-0495/),
[HTTPX injected transports](https://www.python-httpx.org/advanced/transports/),
[RFC 9110 §10.2.3 Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after).
ZoneInfo supplies UK/US calendar state; the provider's byte-identical duplicate is not a real timezone fold. Dependencies remain pinned.
