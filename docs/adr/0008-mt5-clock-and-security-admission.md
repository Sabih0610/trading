# ADR 0008 — Fresh security and UTC evidence for genuine acquisition

Date: 2026-10-23. Status: accepted for P11a.1.
The source feed connects but emits epochs about three hours ahead of verified receipt UTC.
Keep those facts immutable and disallow prospective use until the convention is resolved.
Native safety closure is necessary but does not establish data qualification.

Retain the four-tool proxy and Python data whitelist. Require a fresh, demo-fingerprint-bound admission at startup and before each genuine collection poll: explicit native trading false, absence of a shell tool, recent independent UTC, native UTC agreement, exact visible instruments and fresh quotes. Unknown state refuses collection. Missing keys/network disable genuine acquisition clearly; offline fixtures remain usable.

Owner manually disabled native trading/dangerous shell and showed exact XAUUSD. Native trading false and shell-tool absence were measured. The API does not expose the shell checkbox independently; record owner confirmation plus catalogue observation.

Parse integer epochs without local timezone or floating-point milliseconds. Require paired fields to agree; refuse naive textual clocks as UTC. Compare read wall time with monotonic duration. Do not infer a broker offset or edit system time. Two HTTPS references support this session's UTC comparison; they do not establish disciplined NTP synchronization.

Diagnostics are finite and raw-only. Extended collection defaults to 1,800 seconds, maximum 2,700, checked between polls as well as finite poll counts. Native blocking calls may delay a boundary check; hard process-supervisor timeout remains future acceptance work.

FeedStore returns actual normalized unique rows in an ephemeral receipt. Exports consume that receipt, preventing duplicate or out-of-order downgraded rows from acquiring a forward label through display. Quote counters are separate from candle provenance. Sampled polling does not prove complete tick coverage.

Current genuine acquisition is blocked. Risk, eligibility and historical holdout rules are unchanged. A provider-supported UTC/DST contract with tests, or a separately reviewed UTC-explicit data-only Practice source, is needed before qualification. P11b remains unstarted. See [research](../research/P11a.1-research.md) and [report](../../reports/phases/P11a.1.md).
