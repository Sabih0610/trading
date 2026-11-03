# P11i Treasury yields journal

- 2026-11-03 00:55 UTC: Read current project rules, master/track prompts, protocol, rights review.
  Created a credential-free isolated worktree from origin/main 2013918.
  No shared living-doc edits; entries will be staged in the phase report.
- 2026-11-03 00:55 UTC: Saved exact dated official site-policy, privacy/legal and archive
  dataset HTML plus SHA-256 metadata under ignored work/rights. Relevant text
  has monitoring/anti-tamper notices, no storage/automated-download/model-use
  restriction. No inference of general redistribution permission.
- Safe original CSV source is the official 2020–2023 archive, plus the closed
  2024 per-year export. Bronze retains original bytes; Silver/Gold scope starts
  2020-10. 2025+ publications and arbitrary URLs are refused.

- Owned validation: 26 unit/integration cases pass; strict mypy clean on 194
  pre-rebase sources. Fixed tuple/list serialization in immutable resume and
  normalized changed-proposal validation to ResearchRefused. No old assertion,
  xfail, risk setting or default feature output was weakened.
- Rebased the unpublished source checkpoint onto approved main 6a64b22 after
  P11f merged. Final combined clean gate follows. The first baseline gate is
  allowed to finish; no concurrent full suite or genuine CSV build.
