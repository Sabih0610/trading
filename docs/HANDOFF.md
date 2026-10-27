# Current handoff — P11b.2a.1 complete offline

2026-10-27 06:42 UTC. Branch codex/p11b-2a-1-validation from 47e74fc / phase-P11b.2a-done.
Milestone ref phase-P11b.2a.1-done. Stop for independent review; do not start P11b.2b.
Use git worktree list to locate validation, completed paper and unfinished OAuth checkouts.

[Report](../reports/phases/P11b.2a.1.md), [guide](how-to/windows-offline-validation.md),
[research](research/P11b.2a.1-research.md), [ADR0015](adr/0015-offline-validation-and-gated-windows-ci.md),
[input contract](specifications/P11b.2b-genuine-input-contract.md), [journal](journal/P11b.2a.1-journal.md).
No human or hosted approval claimed.

- Baseline 826 pass/3 live deselected. Final 853 pass/3 live deselected/23 existing warnings,
  159.24 seconds; locked sync, Ruff/format, strict MyPy (159 sources), smoke and owned acceptance pass.
- Four defects corrected: pending SELL cancellation scoped to symbol; initial date normalized UTC;
  actual evidence metadata checked; changed/missing schema refused before non-initializing ledger
  open. No automatic schema repair or old-study migration.
- Independent Decimal EUR/gold and 30-example lifecycle oracle, terminal entries, unavailable-mark
  restart and real process death before/after commit for entry/exit. Original risk/gap tests retained.
- Original 14 studies replay byte-identically under their original source pin. Fixed source keeps
  identical states/fills/chains/tails: 3,811 inputs, 16 fills/8 closed engineering trades.
  All $100 accounts flat; invented units/costs establish no actual broker capital feasibility.
- Fixed source digest f1205049a3c14643552f6861443a34018ce7a7aa221bb6ec18b0af136140aea5.
  Original snapshot byte SHA 31b8a042fc7695f5d887e6aaf2f311729572d2676f4244e06816975f807b3317.
  Portable summaries: reports/validation/P11b.2a.1; fresh smoke: reports/safety/P11b.2a.1.
- A1 Windows workflow local only: full action pins, Python 3.12.11 / uv 0.13.5, contents read,
  no persistent checkout credentials/cache/uploads, finite timeout, controlled temporary outputs.
  Public remote verified; Actions policy endpoint 403. Job requires owner variable
  OFFLINE_CI_APPROVED_FREE_RUNNER plus public visibility. No push/activation/billing/protection edit.
- Original OAuth checkout remains cc5a4ea with modified progress, untracked OAuth journal/owner
  audit and private .env unchanged. Completed paper checkout stays 47e74fc. No credentials copied.
- No genuine cTrader/MT5/OANDA/Twelve Data access, OAuth attempts, external orders, holdout reads,
  model retraining/promotion, risk relaxation or new framework. P11b.2b NO-GO/unstarted.
- Read-only Paper Lab AppTest checked warnings, both accounts, reasons/versions, shutdowns and
  unavailable marks. No trading controls or background server/collector created.

Next authorized action is independent review of the report and local diff. Re-run from a
credential-free worktree with the command below. See the guide for a uv path outside PATH.

```powershell
pwsh -NoProfile -File './scripts/check-offline.ps1'
```

Owner must separately authorize hosted push/activation after policy/free-runner review. P11b.1a
resumption requires actual approval/redirect/broker terms/view-only consent evidence. P11b.2b needs
separate scope plus every genuine-input matrix gate, independent eligibility and review.
