# ADR0033: swing preregistration and genuine-data firewall

Date2026-11-06. Status: proposed for Claude review (not approved).
Context: merged M/N/O enable multi-day daily/weekly research, but genuine P access
requires a separately reviewed ex-ante protocol.

Decision: register three portfolio families/nine cells each and preserve216prior
trials in243-trial correction. Freeze exact clocks, source-specific gold warm-up,
risk overrides, terminal cutoff and ambiguity bounds before any genuine registry
or quality inspection. Publish all PartB implementation/config before its one
registered run. P11p-prereg-review.md on main is the only review unlock.

Alternatives: reuse the shorter intraday hold/purge (reject: changed horizon);
splice XAU and PAXG (reject: changes information/price identity);
infer minute tick order (reject: unknowable); tune after inspection (reject).
The [registration](../../reports/stage3/P11p-preregistration.md) controls details.

Consequences: insufficient data/benchmark frequencies are honest nonpasses.
A pass supports an owner decision; no providers, paper operation, execution
allowlist, orders, holdout access or automatic merge are enabled.
