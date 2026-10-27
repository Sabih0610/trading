# Current handoff — P11c.0 local market research

Dedicated local branch `codex/p11c-0-research-mvp` directly integrates repaired
`978aad2`. Original credential-owning checkout and existing worktrees remain
preserved. Owned CSV/Parquet registry→import→existing strategies→labels→report→replay
and read-only dashboard are implemented; full completion results are in
[P11c.0](../reports/phases/P11c.0.md).
All quality gates pass: 1,084 tests, 3 optional live deselected, 23 existing warnings;
all 55 remediation regressions, smoke and 14 identical paper states pass. Both owned
CSV/Parquet runs replay identically. No actual licensed dataset has been admitted.

Start review with [ADR0018](adr/0018-permission-gated-local-market-research.md),
[dataset/protocol contract](specifications/local-market-research.md),
[runbook](how-to/local-market-research.md) and
[source candidates](research/P11c.0-research.md). With an existing pinned Python 3.12
environment, `scripts/research.ps1 -Python <python.exe> -ResearchArguments @('demo')`
demonstrates owned software only. No dependency installation is needed.

Next exact action: independent review of this local phase and six repairs; select
one actual licensed local EURUSD dataset with distinct owner/reviewer approvals,
then separately authorize P11c.1 qualification. XAUUSD needs its own evidence.
Genuine evaluation is BLOCKED — DATASET NOT AUTHORIZED. Do not change the frozen
protocol, extend old retention, access 2025+ data or promote midpoint outcomes into
broker execution performance. cTrader OAuth remains unfinished and untouched.
Owner follow-up authorizes task-branch publication and the README quick start.
Main merge, hosted CI, provider requests, real authorization and external orders
remain unauthorized. P11c.1 is unstarted. Earlier general Git instructions and
historical status below do not override this phase's explicit restrictions.

## Previous remediation checkpoint

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
