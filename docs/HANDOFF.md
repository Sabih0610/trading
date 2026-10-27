# Current handoff â€” shared publication of reviewed offline work

Candidate b669d430148ba0bb67c9f46f7560341a52165ff1 / phase-P11b.1a-prep-done is unchanged.
Owner authorized ongoing commits and pushes on 2026-10-27 for collaboration. The RC
documents and unchanged implementation are on codex/shared-research, following [CONTRIBUTING.md](../CONTRIBUTING.md).
The public history preserves phase messages/order and omits raw MT5 price payloads throughout;
original local branches/tags remain intact. Historical report SHAs are local provenance, with
Publication-Source trailers on corresponding public commits. Never push all original refs/tags.
[Publication checks and public SHA mapping](../reports/reviews/repository-publication.md).
Independent review remains pending. Genuine P11b.1a/P11b.2b remain NO-GO; hosted CI inactive.

[RC report](../reports/phases/P11b.1a-RC.md), [owner checklist](how-to/release-candidate-owner-checklist.md),
[redirect contingency](security/ctrader-redirect-contingency.md), [research](research/P11b.1a-RC-research.md),
[journal](journal/P11b.1a-RC-journal.md). Existing prep guide/integration plan remain applicable.

- Already integrated paper/safety/OAuth source verified by ancestry; 299 tracked implementation,
  configuration/test/CI files unchanged. No merge/cherry-pick/dependency/risk or runtime edits.
- Final gates: 937 pass / 3 live deselected / 23 existing warnings, 248.63 seconds; locked sync,
  Ruff/format, strict MyPy167, safety smoke and all 14 paper cases pass.
- Full fake loopback workflow: prepare/spent nonce, fake accounts-only redirect, mismatched/duplicate
  callback/code refusal, one fake exchange, view/expected-demo proof, private persistence and actual
  CTraderSettings load, inert status, expiry/server revocation and private clearing. Real TLS/quote
  client/browser constructors never reached. All temporary fake private storage/services cleaned.
- 14 owned studies/3,811 inputs/16 hypothetical fills; every state matches validated baseline.
  All $100 accounts flat; fresh read-only dashboard reader reconciles all studies.
- Original OAuth stays cc5a4ea with private .env, modified progress and untracked journal/owner
  audit preserved; completed paper/validation stay 47e74fc/b56cfb1. Old refs unchanged.
- Exact HTTP loopback/random-path registration acceptance remains UNVERIFIED in official docs;
  no portal login/test performed. Owner must privately verify after actual app approval. If rejected,
  stop for separately authorized redirect redesign; current helper cannot accept HTTPS callbacks.
- Review/evidence under reports/validation/P11b.1a-RC and reports/safety/P11b.1a-RC. No keys,
  callback values, account IDs, genuine quotes or private journals in new public-candidate artifacts.
- The RC review made no genuine auth, token exchange, data requests, broker orders, automatic refresh, push/merge,
  hosted activation, holdout read, model deployment/promotion or P11b.2b.

Next: independent source/report review; separate owner authorization for original-checkout integration
without copying .env; actual approval and exact callback acceptance; accounts-only single-demo consent.
A later bounded quote test needs separate authorization plus rights/clock/contract/cost evidence.
No genuine-to-paper integration follows automatically. See checklist for conditional Windows commands.

Safe now, in this credential-free checkout:

```powershell
pwsh -NoProfile -File './scripts/check-offline.ps1'
uv run --locked python -m tb.ingest.broker.onboarding.cli status
uv run --locked python -m tb.ingest.broker.onboarding.cli rehearsal
```

The ignored work/rc_review/rehearse.py is a disposable local acceptance harness, not new runtime code.
Use git worktree list to find originals; preserve their unfinished files. No human approval claimed.
