# RC remediation journal

2026-10-27 UTC — Read full independent review and repository rules. Verified
implementation equivalence to b669d43. Created separate credential-free detached
worktree at sanitized 85f87ce; no fetch, provider operation or private-file read.

2026-10-27 UTC — Reviewed official HTTPX transport documentation, cTrader
account/token enums and SQLite schema guidance. Chosen changes: durable stop
activation, explicit fixture interface, exact current rights plus immutable
acquisition deadlines, and complete schema digest verification before startup.

2026-10-27 UTC — Fresh original harness reproduced all six baseline findings.
Implemented 55 new regressions, reused rational accounting and protocol oracles.
Focused final set: 147 passed. Initial full pass: 989 passed/one new category
failure/3 live deselected; corrected retention refusal category without weakening
assertion. Hardened malformed metadata/lease handling and explicit schema-reader
closure. Final full gate run in progress with source inputs pinned.

2026-10-27 UTC — Final complete validation: 992 passed, 3 live deselected,
23 existing warnings; Ruff/format, strict MyPy169, 26 installed dependency pins,
offline guard, safety smoke and all 14 deterministic studies pass. Source/test/runner
inputs remained unchanged through the run. 3811 inputs and 16 hypothetical fills;
all accounts flat and zero external orders. No original credential/worktree edits.
