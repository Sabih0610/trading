# Current handoff — RC finding remediation

F-01–F-06 fixes are implemented in a separate credential-free checkout from sanitized
85f87ce, implementation-equivalent to candidate b669d43. The original review and all
protected worktrees remain preserved. Full offline validation passes: 992 tests/3 live deselected, all quality gates,
safety smoke and 14 deterministic studies.

Current owner scope supersedes the historical general push preference: no genuine
integration/provider use/OAuth, credentials, external orders, push or CI activation.
Use existing dependencies and `scripts/check-rc-remediation.ps1`; no sync is needed.
Do not reuse prior journals under new code or repair missing schema/lifetime pins.

[Report](../reports/phases/P11b-RC-remediation.md) ·
[Original review](../reports/reviews/P11b1a-independent-security-review.md) ·
[Research runbook](how-to/broker-independent-research.md) ·
[Codex-ready plan](specifications/P11b-broker-independent-research-plan.md) ·
[ADR](adr/0017-rc-permission-retention-and-recovery-boundaries.md).

Next: obtain independent human review of the patch/plan. Continue broker-independent
research using the plan and documented owned/licensed dataset admission rules.
Actual results and hashes are in the completion evidence. Independent human review remains pending.
No licensed market dataset has been admitted; research currently uses generated fixtures.
Genuine P11b.1a and P11b.2b remain NO-GO. Hosted CI stays inactive.
