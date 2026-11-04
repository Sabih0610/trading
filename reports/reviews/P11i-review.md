# P11i review: US Treasury yields through the medallion

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/p11i-treasury-yields` at `0d18a7a` (19 files, +1,726) |
| Verdict | **APPROVED**, merged. |

## Checks

| Check | Result |
|---|---|
| Rights (review 2026-11-02 §1) | Dated treasury.gov site-policy, privacy and dataset pages are saved with SHA-256. I read them independently: they contain only the standard anti-tampering notice (no unauthorized upload or modification) and nothing restricting storage, automated download or model use. The condition is met. |
| Registry | `TreasuryDatasetPlan` reuses `authorize()` (owner plus distinct reviewer, `provider_terms`, retention 2028-11-01). Missing, revoked or tampered evidence refuses before any private read. |
| Holdout | Any 2025 publication is refused before Bronze commit. Earlier-2020 archive rows stay in Bronze for provenance only; Silver/Gold admit 2020-10-01 → 2024-12-31. |
| Causality | `known_at` = publication date 23:59:59 America/New_York (in UTC). Only strictly later bars can use a value (backward as-of). The 2024-12-31 value becomes known in 2025 UTC and is therefore never usable before the holdout. Holidays stay absent and are never forward-filled. |
| Feature engine | `enable_treasury_yields=False` by default and adds nothing unless enabled with admitted context, so existing feature hashes are unchanged. |
| Conflict rules | No shared living docs edited. |

## Gates (`0d18a7a`, clean worktree, run alone)

pytest **1,481 passed**, 1 skipped (S-5), 3 live deselected, 5 xfailed. Ruff clean, 546 files formatted, strict mypy clean on 203 sources.

An earlier run done in parallel with another suite had one failure in
`tests/integration/test_paper_validation.py::test_process_death_on_each_side_of_commit_recovers_exactly_once[entry-after_checkpoint]`.
That test is untouched by this track, it passed 4/4 in isolation, and the full solo rerun above is green.

## Follow-up

| ID | Severity | Action |
|---|---|---|
| P11i-1 | minor (test reliability) | The paper process-death test is timing-sensitive under machine load. Add it to J1's reliability audit (bounded waits / readiness signal instead of timing), without changing its assertions. |
