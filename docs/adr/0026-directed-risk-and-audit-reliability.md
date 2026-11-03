# ADR 0026 — Directed risk arithmetic and bounded audit diagnostics

Accepted for J1 review, 2026-11-03 UTC. This is Wave 1 only and reads no genuine observations.
Risk defaults/ceilings, engine fill-price/priority code and labels remain unchanged. F/G's frozen research
identities retain their own semantics; this hardening does not relabel prior verdicts.

## Decision

Return a rejecting RiskDecision for noncanonical entry symbols and blank markets.
The latest owner prompt deliberately requires rejection, superseding the original
R-3 audit test's normalize-and-approve expectation. Preserve its no-exception guard
and strengthen its result to rejection. Canonical approved requests continue normally.

Use ROUND_DOWN in local Decimal contexts for every positive capacity division and
step ratio; preserve the floored step count's exact product so ambient precision
cannot move it off the lot grid or above the requested quantity. Reject an empty
fill after precision underflow. Without venue rules, retain Decimal precision with directed rounding;
do not invent a venue tick/lot filter or claim that a research quantity is executable.
Do not alter config or risk authority. Exact high-precision fixture checks prove
risk/cash/exposure remain bounded, including the original R-4 counterexample.

All legacy chart modes share the same UTC holdout check and actual timestamp
preflight, including rows after the visible page. A synthetic label is not provenance.
Owned dashboard fixtures already use 2024, so no date relabeling is needed.

Pin installers to the two existing audited commits, verify exact detached identity
and refuse dirty/mismatched caches. Listing/copying never executes third-party skills.
Index-only cleanup removes all tracked/ignored paths required by the existing S1
assertion. Keep every local file; no history rewrite or quality-content inspection.

Central missing-feature logs contain names and reasons only, once per process.
Configure CLI logging without reading private dotenv; actual dotenv availability is
reported only when load_settings is called. Console logs go to stderr so JSON stdout
remains parseable. Existing provider-specific disabled status reports remain intact.

Keep property assertions/example counts unchanged. Untimed module fixtures warm
native paths. Warm-up alone still measured 1.108s under concurrent Windows load;
only the two owner-named properties receive an explicit2s deadline. No global
Hypothesis relaxation. pytest faulthandler_timeout=600 dumps stacks without skipping
or failing a test. Add missing process/socket/thread bounds and document the audit.

## Alternatives and consequences

Floating skill HEAD, self-declared synthetic exemptions, half-even quantity division,
normalizing ambiguous entry symbols into approval, weakening causality assertions,
disabling timeouts or changing Wave 2 fill/label semantics are rejected.
The full gate must run in an isolated credential-free checkout. Local ignored kit
and quality files remain present in the original worktree after index cleanup;
new clean checkouts omit them by design. A missing kit zip may therefore yield the
existing explicit environmental skip in its old content-audit test.

See [research](../research/P11j-research.md), [journal](../journal/P11j-journal.md)
and [phase report](../../reports/phases/P11j.md).
