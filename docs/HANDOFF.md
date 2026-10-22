# Current handoff

P09.5 is complete on `codex/p09-5-alignment-safety` with local tag `phase-P09.5-done`.
The owner requested audit verification first and then the attached P09.5 implementation.
The original audit file is unchanged. No external order, paid call or final-period data access occurred.

- Last completed step: Ruff and format clean, strict MyPy clean on 88 files, full pytest **351
  passed, 3 optional live deselected**, 23 dependency warnings. Offline JSON/manifest/SQLite smoke
  and PowerShell entrypoint with a spaced output path passed.
- Reproduce: `uv run --locked python -m tb.paper.smoke`. Local fallback:
  `& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.paper.smoke`.
- Read `reports/phases/P09.5.md`, `reports/reviews/P09.5-audit-verification.md` and
  `docs/how-to/alignment-simulation.md` for changes, audit qualifications and example outcomes.
- Next development requires a separate instruction: read
  `prompts/P10-read-only-dashboard-after-alignment.md`. **Do not auto-start P10 or integrations.**
- Primary research is XAUUSD/EURUSD fully funded contract accounting; Binance Spot remains a
  secondary module and its guards still refuse data-only symbols. All external order permissions
  are false. One position; configured all-in risk 0.5%, daily equity halt 2%, peak halt 5%.
- No attached market-data volume, trained empirical models or qualifying strategy trials. Binance
  XAUT began after the locked period started; acquiring pre-2025 Binance XAUT is impossible.
  Never move the lock or replace XAUT with reference gold prices. Freeze prospective research first.
- Research replay is bounded/offline, not a continuous runner. Real 2025+ replay is refused here.
  Future P11 must persist circuit/position state and reconcile restart, receipt-clock and feed gaps.
- P06/P09 independent reviews remain owner-deferred; P09.5 is queued. Codex verification is not
  independent review approval. No independently certified Shariah source or broker identity exists.
- Local dependencies are installed from unchanged `uv.lock` in ignored `.venv`; uv bootstrap is
  in ignored `work/tooling`. No dependency constraints were relaxed.
