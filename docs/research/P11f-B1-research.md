# P11f-B1 — explicit deny-all strategy policy

Claude's approved P11f Part B review drops C/D/E for BTC/ETH/SOL. An empty
allowlist is the explicit deny-all representation. The prior schema required at
least one strategy for a tradable asset, which cannot represent the reviewed
restriction and prevents the whole registry loading. Remove only that minimum
requirement; retain all actual permission checks and structural/risk constraints.

| Option | Decision |
|---|---|
| Empty allowlist with unchanged membership guard | Chosen: all strategy constructors refuse; current-policy regressions cover all nine combinations and 162 frozen catalogue cells |
| Fake/sentinel allowed strategy | Rejected: invents a permission name instead of representing no approved candidate |
| Reclassify crypto as data-only | Rejected: changes unrelated instrument/eligibility semantics and is unnecessary for removing strategy permission |
| Bypass constructor guard in old tests | Rejected: explicit historical fixture uses the real guard and validated prior allowlists; all mechanics assertions stay unchanged |

Primary source verified by the coordinating root on 2026-11-03 UTC:
[OWASP Authorization Cheat Sheet — Deny by Default](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html#deny-by-default).
Its explicit default-denial and authorization-regression guidance supports this
representation and the separate unpatched production refusal tests. It grants no
new project permission. Authority remains the
[approved review](../../reports/reviews/P11f-partB-review.md), not the reference.
No genuine data, frozen evaluator or F result is revisited.
