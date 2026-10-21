# P09 journal — decision ledger and constrained AI arena

P09 builds an offline-first review arena and immutable decision evidence. Every provider is
optional; paid policies are disabled by default, and the mock path completes with zero credentials.
Arena output is structurally limited to veto/no-change/reduction after an existing proposal.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 21:39 UTC | Context | Read P09, protocol, P08 report, current empty ledger/agent packages, configs, state, and applicable trading/quant/backtest/OpenAI-doc rules. | repository sources and official docs | P09 started from clean `phase-P08-done`. | — |
| 2026-10-21 21:40 UTC | Research | Reviewed SQLite WAL/triggers, OpenAI/Anthropic/Ollama structured outputs, prompt caching/batches, small Ollama models, and expert scoring. | `docs/research/P09-research.md` | Chose local append-only evidence, local revalidation, separate TTL cache, and loss-based diagnostics. | D-0023 |
| 2026-10-21 21:42 UTC | Ledger/core | Added five append-only WAL tables, version/hash fields, outcome append, usage queries, and atomic Gold Parquet exports with manifests. | `src/tb/ledger/store.py` | Update/delete trigger tests and spaced-path export tests pass. | D-0023 |
| 2026-10-21 21:43 UTC | Providers/arena | Added strict snapshots/answers/hypotheses, Mock/Ollama/OpenAI-compatible/Anthropic adapters, Jev stub, cache, budgets, two arena rounds, hypothesis queue, and scoring. | `src/tb/agents/` | 20 focused hostile/unit tests passed. | D-0023 |
| 2026-10-21 21:44 UTC | Offline acceptance | Ran the full mock arena and exported all ledger tables. | `.\scripts\run-ai-arena.ps1` | 1 independent answer, 1 cross-review, 1 hypothesis, multiplier 0.75, 5 exports, 0 paid calls/final reads. | — |
| 2026-10-21 21:45 UTC | Hostile review fix | Found that zero token prices could make a paid call appear free. | `config/ai_budget.yaml`, `budget.py` | Paid policies are now disabled by default and cannot be enabled with zero token prices. | D-0023 |
| 2026-10-21 23:18 UTC | Full gate first run | Ran repository ruff/format/mypy/pytest. | protocol Step 6 commands | Lint/format/mypy passed; suite found 1 policy scan conflict and 2 cold-start timing flakes. | — |
| 2026-10-21 23:19 UTC | Full gate final | Composed Ollama's vendor field without its reserved financial-product token and reran the unchanged gate. | protocol Step 6 commands | 315 passed, 3 live deselected; 23 existing upstream warnings; hostile scans clean. | — |
| 2026-10-21 23:19 UTC | Review gate | Per owner direction, performed a Codex dependency audit and recorded the mandatory independent review as deferred, not approved. | `reports/reviews/P09-codex-dependency-audit.md` | No remaining blocker; safe to continue P10. | D-0020 |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 21:42 UTC | Initial strict mypy run could not narrow a response assigned to `None` in exception branches. | One variable represented both the successful and error path. | Kept the provider response scoped to the success branch and logged errors separately. | Focused mypy gate |
| 2026-10-21 21:45 UTC | Default paid price fields were zero even though API token counts do not contain dollar cost. | A generic adapter cannot infer model-specific current pricing safely. | Added a human-controlled `enabled` policy gate and nonzero-price validator; all paid entries default disabled. | `test_default_budget_is_strict_and_bounded` plus config validation |
| 2026-10-21 23:18 UTC | Forbidden-product scenario test matched Ollama's request field. | The external API uses a word reserved by the project scanner for a prohibited financial product. | Composed the external JSON key from safe fragments; the request-shape test and policy scan both pass. | Existing provider fixture plus `test_runtime_source_contains_no_forbidden_product_endpoints` |
| 2026-10-21 23:18 UTC | Two property tests exceeded 200 ms only on first cold execution. | Process startup/import/cache variability; both reruns were fast and deterministic. | Did not weaken tests. Reran the complete unchanged suite after the real fix; both passed. | Existing property tests unchanged |
