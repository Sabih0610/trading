# Current handoff — P11b.1a-Prep complete offline

2026-10-27 10:11 UTC. Branch codex/p11b-1a-prep from b56cfb1 / phase-P11b.2a.1-done.
Checkpoint ref phase-P11b.1a-prep-done. Stop for independent review and exact owner external actions.
P11b.1a genuine is pending/uncompleted; P11b.2b remains NO-GO/unstarted. Hosted CI inactive.

[Report](../reports/phases/P11b.1a-prep.md), [owner guide](how-to/ctrader-oauth-after-approval.md),
[integration plan](specifications/P11b.1a-prep-integration-plan.md), [security](security/ctrader-oauth-prep.md),
[ADR0016](adr/0016-private-owner-assisted-ctrader-onboarding.md), [journal](journal/P11b.1a-prep-journal.md).

- Baseline 853 pass/3 live deselected/23 warnings, 175.44s. Final 937/3/23, 234.20s: locked sync,
  Ruff/format, strict MyPy (167 sources), safety smoke, 14 owned paper scenarios and fake local OAuth pass.
  84 new tests; all previous tests and restrictions retained.
- Optional onboarding package adds one-use exact owner-registered loopback callback, local code/
  redirect binding, typed token/account enums, single-demo/broker pin and hidden owner confirmation.
  Actual portal callback acceptance/state/PKCE support are unverified; no undocumented convenience.
- Private root .env only; owner/SYSTEM ACL before staged secret write, full-pair atomic replace,
  writer/session leases, bounded/sanitized fixed TLS exchange, explicit manual refresh only.
  Callback parser errors never reflect the request/code; default status is inert; no quotes/paper startup.
- Genuine auth additionally needs two private human flags and explicit after-approval command.
  CI refuses real transport. Owned tests mock all real edges or use a fake loopback provider.
  No genuine code/token/scope/account/quote was obtained; no actual browser consent opened.
- Original OAuth checkout stays cc5a4ea with progress changes, untracked journal/owner audit and
  private .env unchanged. Completed paper/validation worktrees remain 47e74fc/b56cfb1. No secret copy.
  Original .env ACL metadata verifies owner/SYSTEM-only; exact private-value artifact scan passes.
- Existing broker facade/models/allowlist, rights, risk, ledger, paper and dashboard source unchanged.
  Paper source digest f1205049a3c14643552f6861443a34018ce7a7aa221bb6ec18b0af136140aea5 remains.
  New protocol operations are only four existing auth/identity kinds; no order/execution imports.
- No risk relaxation, genuine providers, external orders, holdout reads, AI promotion, paid service,
  merge/rebase/stash/reset/push or hosted activation. No new SDK/runtime dependency.
- Structured owned summaries: reports/validation/P11b.1a-prep; fresh safety summary:
  reports/safety/P11b.1a-prep/legacy-paper-smoke.json. No real private values in artifacts.

Next owner actions, ALL NOT YET EXECUTED: actual app approval; independently eligible broker/demo
and terms; reviewed integration into credential-owning checkout without copying .env; prepare/register
exact fresh private callback; separately authorize accounts-only single-demo consent and confirmation.
Only after real permission/rights/UTC/contract/cost/retention evidence and separate approval may the
existing bounded read-only quote diagnostic be considered. No genuine-to-paper integration authorized.

Re-run only offline checks/rehearsal now in this credential-free worktree:

```powershell
pwsh -NoProfile -File './scripts/check-offline.ps1'
uv run --locked python -m tb.ingest.broker.onboarding.cli status
uv run --locked python -m tb.ingest.broker.onboarding.cli rehearsal
```

Use git worktree list to locate originals. Preserve original uncommitted files before any future
owner-authorized integration; follow the written conflict plan. No independent human approval claimed.
