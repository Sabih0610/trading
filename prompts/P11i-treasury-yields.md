# P11i: US Treasury yields through the medallion

Follow `prompts/_PROTOCOL.md` and the rules in `prompts/MASTER-2026-11.md`. Branch
`codex/p11i-treasury-yields`. Authority: owner (2026-11-02), ROADMAP Stage 2, and
[rights review 2026-11-02](../reports/reviews/dataset-rights-review-2026-11-02.md) §1.

## Build
1. **Evidence first:** save dated copies of the treasury.gov policy/disclaimer page and the
   dataset page under `work/rights/` with SHA-256. If either restricts storage, automated
   download or model use, **stop this track** and write `reports/phases/P11i-blocked.md`.
2. Register `us-treasury-par-yield-2020-2024` (owner `Sabih0610`, reviewer
   `Claude (AI reviewer)`, `provider_terms`, retention 2028-11-01), reusing the registry
   model with its owner and distinct-reviewer checks.
3. Bronze: original archive CSV (≤ 2023) and 2024 daily CSV bytes plus manifests. Silver: one row per
   publication date, all tenors, typed Decimal, `known_at` = publication date 23:59:59 America/New_York
   converted to UTC; holidays have no row (never forward-fill in Silver). Stitch the 2023/2024
   sources and test that the overlapping/adjacent days agree in format and tenor set.
4. Gold features (causal): 2y and 10y levels, 2s10s slope and 1-day changes, **available
   only from the bar after `known_at`** (backward as-of join). Add to the shared FeatureEngine
   behind a flag, off by default, so existing feature hashes do not change.
5. Data Health: coverage and quality for the yield dataset.
6. Tests: as-of join never uses the same-day value before `known_at`; holiday gaps are not
   filled; any 2025 row is refused; stitch boundary; archive format variations.

## Done
Gates green; how-to; ADR; phase report `reports/phases/P11i.md` with a private quality table.
Nothing genuine committed.
