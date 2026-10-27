# Release candidate — owner checklist

Candidate source is b669d43 / phase-P11b.1a-prep-done. It already contains paper validation and
OAuth preparation. RC review changes documentation/evidence only; no new implementation commit/tag.
Real authorization, quote collection and genuine paper integration are not activated by this checklist.

| Category | Action / present status |
|---|---|
| Possible now | Inspect RC/prep reports and source; run credential-free local checks and owned rehearsals below. Preserve original uncommitted files/private .env. |
| Requires independent code review | Callback/code/session binding and reflection handling; scope/account enum separation; private ACL/atomic state; current branch compatibility and any redirect redesign. Automated validation is not human review. |
| Requires explicit owner authorization | Incorporate reviewed candidate into the credential-owning checkout; any genuine consent/renewal or later bounded quote diagnostic; GitHub push/hosted CI activation. None done here. |
| Requires cTrader approval | Owner verifies approved status, exact one-demo identity and broker eligibility, prepares/registers fresh private callback and approves accounts-only consent. All NOT YET EXECUTED. |
| Requires independent data-rights evidence | Actual broker/provider retrieval/storage/retention/display terms, UTC/source/receipt semantics, contract/cost/conversion/session metadata and legal/independent Shariah eligibility. OAuth success does not supply these. |
| Must remain prohibited | Real/demo broker orders, live/trading-scope authorization, leverage/risk relaxation, secret sharing, callback-security downgrade, holdout bypass, model promotion and automatic P11b.2b/CI activation. |

## Safe commands now — credential-free review checkout

Run from the repository root. If uv is outside PATH, use the existing guide's quoted -Uv path.

```powershell
git worktree list
git status --short
uv sync --locked
pwsh -NoProfile -File './scripts/check-offline.ps1'
uv run --locked python -m tb.ingest.broker.onboarding.cli status
uv run --locked python -m tb.ingest.broker.onboarding.cli rehearsal
```

Quality checks refuse a private root .env. Rehearsal uses owned generated credentials and a fake
loopback provider in disposable private storage. Do not copy original credentials into this checkout.

## Future approved credential-owning checkout — NOT YET EXECUTED

First obtain independent review and owner integration approval; preserve original non-secret work and
private .env in place following the [integration plan](../specifications/P11b.1a-prep-integration-plan.md).
Confirm actual app approval, broker/demo eligibility and exact private pins. Only then may the owner
enable the two private human flags described in the [OAuth guide](ctrader-oauth-after-approval.md).

```powershell
uv run --locked python -m tb.ingest.broker.onboarding.cli prepare
```

Privately register the exact new URI before the next command. Do not print/paste it into chat or
screenshots. Acceptance of the proposed loopback URI is UNVERIFIED; if rejected, stop and follow
the [contingency review](../security/ctrader-redirect-contingency.md). Every attempt needs a fresh URI.

```powershell
uv run --locked python -m tb.ingest.broker.onboarding.cli authorize --after-approval
uv run --locked python -m tb.ingest.broker.onboarding.cli status
```

Choose only the expected demo account and accounts/view-only scope; privately re-enter its ID when
prompted. Stored status booleans are not current server verification, especially after expiry/revocation.
No quote session starts. Renew only if separately authorized; it is never automatic:

```powershell
uv run --locked python -m tb.ingest.broker.onboarding.cli refresh --after-approval
```

For revocation, use the owner-controlled cTrader ID authorization interface, disable the local enable
flag and clear invalid token values privately. Do not auto-repair/recover uncertain token state.

## Later quote diagnosis — separate approval and rights evidence required

The following existing bounded command remains **NOT AUTHORIZED NOW / NOT YET EXECUTED**. It may
only be considered after genuine permission/identity, rights, clocks and metadata preflight pass.

```powershell
uv run --locked python -m tb.ingest.broker.cli genuine-smoke --seconds 30 --max-events 100
```

Its existing gates may still refuse. No order or genuine-to-paper integration follows automatically.
Genuine P11b.1a and P11b.2b remain NO-GO; $100 genuine broker feasibility remains unverified.
