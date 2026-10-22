# Current handoff

P10 is complete on `codex/p10-read-only-dashboard`, based on verified P09.5 c35d7c7.
Local phase tag: `phase-P10-done`. The original user-supplied audit is unchanged/untracked.
No dashboard action writes trading evidence, loads credentials or calls brokers/providers.

- Final gate: Ruff/format clean; strict MyPy clean on 93 files; full pytest **378 passed, 3 live
  deselected, 23 existing warnings in 35.30s**. Exact P09.5 safety smoke passed. Existing protections
  remain unchanged. A stale 351-count note in the P09.5 handoff was corrected by baseline verification.
- Actual browser review: all five views, desktop 1440x1000 and mobile 390x844; no horizontal page
  overflow. Stored-value chart domains fixed transient Vega warnings; fresh console has 0 errors/warnings.
- Local server is running at http://127.0.0.1:8501. Choose Synthetic demo in the sidebar to inspect
  seven isolated fixture accounts. Default Workspace records has no actual dataset and shows unavailable.
- Run `.\scripts\run-dashboard.ps1` if stopped. The script finds uv on PATH or the local bootstrap.
  Fresh checkout: generate once using `uv run --locked python -m tb.dashboard.fixtures`.
  Existing fixture roots are intentionally not overwritten. Guide: docs/how-to/dashboard.md.
- Read reports/phases/P10.md for changed files, actual gates, screenshots, fixture outcomes,
  source/metric validation, remaining limits and the recommended P11a plan.
- Dependencies: Streamlit 1.66.1 is pinned; no existing dependency constraints were loosened.
- UI reads only indexed exports with bounded/cached projections and mode/currency validation.
  Real 2025+ chart rows are excluded/refused; no final-test switch or raw-volume scan is present.
- Current feed/account/latch health, empirical strategies/models and calibration remain unavailable.
  Archived synthetic latches/version IDs do not establish a running trading process or market skill.
- P10 and P09.5 independent reviews are queued. Prior P06/P09 deferrals are not approvals.
- ADR 0006 recommends a conditional future hybrid with one minimal EA sender, after separately
  approved policy/eligibility/reconciliation gates. No EA or order pathway is implemented.
- **Stop here.** P11a read-only MT5 work requires a new instruction; P11/P12 are not started.
