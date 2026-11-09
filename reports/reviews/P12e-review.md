# P12e review: CFTC gold positioning pipeline

Builder/reviewer: Claude (owner request 2026-11-09). Spec: `prompts/P12e-gold-crowd-positioning.md`.
Verdict: **APPROVED for a genuine build.** Data-only; the side study itself is a separate later registration.

| Rule | Status |
|---|---|
| Rights | CFTC Web Policy: government information is public domain. The hashed page is the evidence. Same registry, owner, reviewer, retention and refusal-before-read discipline as SEC/Treasury |
| No lookahead | `known_at` = Tuesday + 6 days at 23:59:59 New York. That is later than the normal Friday 15:30 release and covers holiday delays of up to 3 days. Tests prove `reading_at` never returns a report before its `known_at`, and that later data cannot change earlier COT Index values |
| Holdout | Allowlist 2016–2024; the 2024-12-31 report (known only in 2025) is dropped and counted; a 2025 year makes no request |
| Integrity | Gold code 088691 only, Tuesday dates only, one row per date, file year must match, legacy and disaggregated open interest must agree, integer positions only |
| Secrets | No keys; the SEC contact file in the private root is reused for the User-Agent |

Tests: 13 owned-fixture tests, including a 200-example property test (index bounded in 0–100; values older
than the window cannot change it). Load-only check on the real 2024 files: 52 weekly gold reports, the last
kept one is 2024-12-24, 1 dropped.

Minor: the CFTC re-publishes corrected files, so a re-download could differ from the original weekly
release. Bronze hashes freeze what we used. A 2018–19-style government shutdown delay would exceed the
3-day slack, but no such delay occurred in 2020–2024. The 2019 shutdown only affects lookback history,
which was public long before 2020.
