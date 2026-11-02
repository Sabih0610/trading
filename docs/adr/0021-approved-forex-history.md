# ADR 0021 — Approved, source-separated FX history

Accepted for P11e on 2026-11-01. Historical acquisition is private and pre-2025;
this decision does not enable strategy evaluation or orders. The source's clock,
price side, documentary approval and retention accompany each generation.

## Decision

Use a closed `ForexDatasetPlan` alongside the existing Vision registry. The same
owner, distinct reviewer, permissions, original evidence hash and finite lifetime
checks run before requests and reads. Dukascopy requires registered nonempty written
consent: hash it without inspecting its text. Legacy unregistered downloads refuse;
owned replay additionally requires offline validation and `httpx.MockTransport`.

HistData Generic ASCII M1 is the approved backup. Preserve original ZIP and CSV
bytes, verify immutable artifacts on resume, commit a Bronze manifest last, and
publish one atomic yearly Silver/Gold generation through the existing shared engine.
HistData timestamps use the reviewed EU-week clock (+4/+5 h) and verified autumn provider duplicate; see the correction below. OHLC is bid only;
volume is unreliable. Dukascopy retains BID/ASK, derived mid and spread at every
Gold timeframe. Provider namespaces and explicit side fields prevent silent mixing.
Each FX dataset gets a separate private quality path.

Archived HistData years use consolidated yearly ZIPs. Nominal whole-file UTC bounds
must fit the registered scope before requesting even the download form. Refuse any
archive extending before the approved start or into the locked holdout; do not
request it and then filter. Record the withheld file and exact reason privately.
Calendar closures and rollover windows are separately flagged, excluded from the
missing-open-session score. No synthetic bars fill gaps.

Dukascopy technical failure stops after bounded retries/backoff, retains originals,
writes price-free endpoint/time/error diagnostics and triggers the approved backup.
A partly delivered primary year may require a whole backup year because that is the
provider's archive granularity; the sources remain separate and are never merged.
Completed primary years suppress the corresponding backup archive.

## Alternatives and consequences

Unregistered public downloads omit rights evidence. Using New York DST directly to decode
HistData mislabels US/EU mismatch weeks. Download-then-filter can access locked data.
Monthly requests to unavailable archived forms cannot provide the annual data.
These alternatives are rejected. Some boundary history can remain unavailable until
a safe source is supplied; this is reported instead of widening approval.

The asset registry's configured spread is exposed as the Stage 3 long-entry floor.
A missing/nonpositive floor is explicitly unqualified and requires owner cost review;
never derive spread from bid-only bars or change risk/config defaults in acquisition.
Actual per-symbol/year quality tables remain ignored/private because the public
repository may contain no genuine quality artifacts. Public reports link their local
location and include only a blank template.

See [research](../research/P11e-research.md), [runbook](../how-to/forex-history.md),
and [rights review](../../reports/reviews/dataset-rights-review-2026-11-01.md).


## Bounded quality metadata

Yearly quality details can exceed the existing metadata reader bound. Preserve the
complete private report in an immutable hashed artifact with the same retention;
keep scores, counters, monthly heat strips and explicitly labeled bounded list
samples in the manifest/health summary. Record full list lengths and the detail
pointer/hash. Do not widen the generic reader limit or discard quality evidence.
This changes no Bronze bytes, bar data, quality formula or canonical Gold hashes.


## Clock correction after independent review

The real pre-2025 files contradict the FAQ's fixed-EST specification. Choose +4 h
when the trading week's Sunday noon in Europe/London is BST, otherwise +5 h.
The owner verified that the repeated autumn Sunday hour is a byte-identical provider
duplicate, correcting the review's initial two-hour claim. Apply +5 h to the entire
fall-back week. Keep the first copy and remove the second only when both complete
60-minute blocks have identical source timestamps and every OHLCV field has exactly
the same ASCII bytes. Record `provider_duplicate_hour`; include its 60 minutes in
`duplicates_removed`. Any differing or incomplete repeated block quarantines the
whole day with a quality flag; original bytes remain intact. Stop and ask the owner
if genuine source data contradicts this rule. No shifted hours or automatic open
correction is allowed. This supersedes the interim fold interpretation, which was
stopped before publishing derived generations.

Silver verifies and re-decodes bounded original CSV bytes, leaving old Bronze
Parquet conversions, manifests, ZIP and CSV unchanged. New generations record
`histdata-eu-week-provider-duplicate-v2`, original CSV input hashes and code version. Existing
immutable approved plans retain their declared `source_timezone: UTC-05:00` as
historical documentary metadata; the corrected derived clock is explicit. No
approval digest or retention deadline is rewritten. January/holdout boundaries
are unchanged, and unsafe whole files are still refused before any HTTP request.

The expected grid expresses US session boundaries in the same EU-week source
clock, including mismatch weeks and the single-offset autumn week. Quality includes each full
in-scope week's expected/observed UTC open, signed minute offset, status and counts.
These diagnostic flags do not tune prices, costs or strategies. P11e-3 stays an
owner Stage 3 cost gate; asset spreads remain unchanged.
