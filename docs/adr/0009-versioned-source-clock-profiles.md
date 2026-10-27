# ADR 0009 — Versioned source clocks and independent instrument admission

Date: 2026-10-23. Status: accepted for P11a.2.
Broker wall time is not automatically UTC even when encoded as an epoch-like integer.
No conversion for MetaQuotes-Demo is verified; its profile remains UNVERIFIED.
Alternative provider access is independently evidence-gated; mocks never establish connectivity.

Use public, frozen, extra-forbid clock profiles scoped to provider, broker, exact server, demo/practice environment, build and instruments. Profiles include issued/verified/expiry dates, effective source periods, authoritative references with content hashes, reviewer, validation sample/residual evidence and refresh conditions. Only VERIFIED permits normalization; expiry and source-scope changes refuse acquisition. VERIFIED requires at least three validation samples over ten seconds, two distinct UTC references and maximum residual at most two seconds. These are minimum clock checks, not a substitute for sustained qualification or independent review.

Keep UNVERIFIED/PROVISIONAL/VERIFIED/EXPIRED/INVALID states separate. Stable observed displacement never creates an authoritative rule. A provider-specific fixed-period schedule or documented IANA zone is accepted only after review; UTC periods may not overlap. Round-trip conversion rejects uncovered spring gaps and ambiguous autumn folds. Historical applicability is bounded independently of profile freshness. Unexpected source/receipt steps and out-of-order quotes refuse acceptance.

Record original representation, raw interpretation, normalized UTC, exact profile ID/content digest, rule and public identity fingerprint per new normalized observation. Do not edit old Bronze/Silver files or retroactively change old timestamps. Dedup uses original source identity/clock rather than a mutable normalization profile, preventing a new profile version from making the same fact newly observed. Explicit reprocessing would need its own reviewed derived dataset, never in-place mutation.

Reuse ReadOnlyMarketFeed through an acquisition protocol and the existing finite collector/store/checkpoint/manifest/dashboard. Provider namespaces separate OANDA Practice from MT5 and existing historical readers. New genuine MT5 reads require a profile; fixtures retain explicit synthetic provenance. Admission preserves host/native safety checks and masks instruments independently. One failed symbol does not block a passing sibling; global identity/security/host-clock failures still stop all.

OANDA reader accepts only fixed GET operations against the Practice host, pinned existing identity and bounded responses. No generic URL/method, mutation, account creation or broker sender. Real construction requires separate region/API/no-funding/storage approval evidence and genuinely validated clock evidence; credentials alone do not authorize use. Fixture transport is explicit and produces only synthetic evidence.

No configured source meets genuine qualification now. See [research/comparison](../research/P11a.2-research.md), [guide](../how-to/source-clock-profiles.md), [report](../../reports/phases/P11a.2.md). P11b is NO-GO and unstarted.
