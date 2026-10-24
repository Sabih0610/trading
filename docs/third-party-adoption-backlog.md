# Third-party adoption backlog

This is a proposed backlog from the [source adoption audit](../reports/reviews/third-party-repository-adoption.md), inspected 2026-10-24 UTC.
Only A1 and A2 are recommended for the next separately authorized research phase.
Neither is implemented or approved by this document. No dependencies, trading routes or permissions changed.
The platform remains at P11b.0.1; P11b.1 is design only.

## Priority and scope

| Priority / ID | Proposed improvement | Value and dependency | Estimated effort | Status |
|---|---|---|---|---|
| 1 / A1 | Windows offline quality/safety CI | Verify existing locked checks on changes; no checked-in CI exists. Can stand alone. | 1–2 engineer-days | Proposed; owner/independent review pending |
| 2 / A2 | Bounded local source/import/test map | Reduce repeated manual navigation and improve review/handoff. Use stdlib AST; no runtime dependency or AI service. Can stand alone; A1 can subsequently verify it. | 1–2 engineer-days | Proposed; owner/independent review pending |

Estimates are planning judgments, not benchmarks. Implement one reviewed item per change with its own acceptance evidence. Do not begin either from the audit instruction alone.

## A1 — Windows offline quality/safety CI

**Origin:** Aider's Windows test workflow and Alpaca-py's mocked CI pattern. Preserve our existing Ruff/MyPy/pytest/pre-commit rules. Exact upstream pins, licenses and source links are in the [audit evidence](../reports/reviews/third-party-repository-evidence.json). Both upstreams use Apache-2.0, but the proposal is our own workflow, not copied YAML.

**Proposed files:** one `.github/workflows/offline-quality.yml`, a short developer how-to and, only if needed, a narrowly scoped PowerShell check entrypoint. No application logic/configuration changes. Resolve paths from checkout; do not embed machine-specific paths.

**Implementation contract:** Python 3.12 and the existing `uv.lock`; normal `push`/`pull_request` events; Windows runner; `contents: read`; reviewed full-SHA Action pins; checkout does not persist credentials; finite timeout and owned temporary output directory. Do not use privileged `pull_request_target` execution, a self-hosted runner carrying `.env`, any provider key, new paid service or paid runner enablement. Package setup can access the package registry; tests must remain offline and mock all providers. Hosted free allowance and appropriate runner availability must be checked before activating the workflow.

**Required checks:** existing Ruff lint, format check, strict MyPy on `src`, full default pytest selection and synthetic paper safety smoke. Keep optional live tests deselected and show their count. Do not suppress errors or convert failed commands into successful exit status. No upstream test harness or auto-edit loop.

**Acceptance evidence:**

1. A clean checkout without `.env` passes the existing suite and paper safety smoke; optional SDK absence disables its integration rather than connecting a terminal.
2. In an isolated temporary fixture/change, a lint error, type error, failing pytest and smoke failure each fail the job. The fail-fast shell/exit behavior must be demonstrated; no permanent failing test is added.
3. Tests exercise only owned/mocked inputs and create output in a temporary folder. No provider request, account connection, final-holdout read, external order or model call occurs.
4. Fork execution has no provider secrets/write token. Action versions resolve to reviewed upstream SHAs. Logs/artifacts contain no credentials, market observations, source `.env`, runtime journals or entire work folders; owned summaries, if retained, have a finite retention period.
5. Record actual runtime and resource limits on the selected Windows runner. Branch protection is a separate owner/repository setting; a green run is not code review or merge approval.

**Cost / exposure:** no trading-runtime cost; existing suite took 123.74 seconds locally during this audit, with CI setup time unmeasured. CI adds a runner/registry/action supply-chain surface. No new Python package is needed. Recheck individual Action licenses/notices; retain Apache notices if any upstream source is later reused. Do not claim a hosted run succeeded until it actually runs; this audit did not create one.

## A2 — Bounded local source/import/test map

**Origin:** Aider's token-bounded definition/reference map. Use a smaller independently written AST implementation suitable for this Python-only repository. Aider is Apache-2.0; no Aider code, graph library, model client or full assistant installation is required.

**Proposed files:** one development-only module such as `scripts/source_map.py`, focused tests and a short usage guide. Choose the final location during the authorized implementation review. It must never be imported into the shadow, risk, ingestion or AI decision path.

**Implementation contract:** explicitly invoked; approved tracked `src/tb/**/*.py` and `tests/**/*.py` only; resolve the repository root; verify each resolved file stays inside allowed roots, including Windows junction/symlink cases. Parse source with `ast` without importing modules. Output relative paths, top-level definition names/line numbers, imports and heuristic test links only. Include a source-tree fingerprint, generator version, truncation/warning state and deterministic ordering. Do not emit bodies, values/defaults, docstrings/comments, log contents or config values.

**Hard bounds proposed for review:** at most 500 files, 256 KiB per file, 16 MiB total input and 256 KiB output; report truncation explicitly, never silently call a partial map complete. No persistent arbitrary-object cache. Target under five seconds and 100 MiB extra memory on the current repository, measured at acceptance rather than assumed.

**Acceptance evidence:**

1. Identical approved source produces byte-identical content/fingerprint; a relevant edit invalidates the map; no timestamp-only cache reuse.
2. Definition/import/test hints match small owned fixtures; syntax errors and oversized files yield clear bounded warnings, not imports or execution. Runtime dispatch/dynamic imports are explicitly outside static proof.
3. Decoy secrets and prices in `.env`, untracked files, disallowed roots, literals/comments and runtime evidence never appear. Paths into `data`, `reports`, `mlruns`, `.git`, `.venv`, attachments and work caches are rejected by the allowlist. Do not scan locked market observations to test this.
4. Spaces, Unicode, Windows junction/path escape, duplicate/case-normalized paths, empty repositories and excessive files/output have deterministic safe behavior. Test using disposable owned fixtures only.
5. No network, LLM, module imports, subprocess commands from source, file edits, Git mutation or live runtime access occurs. A strictly fixed read-only Git file-list operation, if used, takes no source-controlled command string and is separately tested.
6. Measure time/memory; confirm the map can be deleted/regenerated without changing any ledger. Document that related-test paths are hints and not a substitute for the full quality gate.

**Cost / exposure:** one bounded scan on demand, no persistent collector or runtime-loop cost. New dependency count zero. Path parsing/disclosure are the main risks; a broad repo upload would defeat the design. If a later proposal copies Aider code, include its Apache-2.0 license, relevant notices and modification markings before review.

## Deferred candidates — not next-phase recommendations

| Candidate | Why deferred / condition to reconsider | Permitted future boundary |
|---|---|---|
| TradingView research signal inbox | No present data/evidence need; upstream has no license and unsafe direct order routing. Need independently verified supported sender authentication, plan entitlement and data rights. | Versioned non-executable events with UTC receipt/provenance, replay rejection across restart, strict caps; no account/quantity/risk commands, order/strategy conversion or broker imports. |
| Strategy dependency/reason visualization | Current read-only dashboard already shows decisions/readiness. Confirm a concrete usability gap first. | Display derived from existing definitions; no editable/executable graph or second strategy engine. |
| Alpaca stock data/stream adapter | No approved stock research scope, regional/plan/rights qualification or Windows streaming reliability proof. | Separate read-only facade behind the existing feed and Bronze/Silver boundaries; forbid TradingClient construction/order paths, including paper. Metadata never substitutes for Shariah approval. |
| PyBroker/vectorbt uncertainty/sensitivity research | Existing walk-forward/purge/stress mechanisms overlap; Commons Clause and dependencies require review. Current overlapping/sparse reference labels cannot justify naive bootstrap or grid selection. | Separately frozen methodology, bounded isolated experiments on eligible owned/authorized inputs; no independent risk/simulation authority. |
| QuantStats reporting/parity | No qualified funded return series for current reference shadow hypotheses. Annualization/missing-data/economic conventions need agreement first. | Explicit local return arrays and fixed metrics; disable symbol downloads/network. Do not manufacture P&L from direction labels. |
| Nautilus microstructure/event study | No measured throughput problem; major-version/native/Python compatibility and LGPL/component review burden. | Source methodology reference; no complete-platform installation, execution adapter or second risk engine. |
| Qlib rolling model methodology | Existing MLflow/validation/arena overlap; MLflow dependency conflict; no approved empirical market-model dataset. | Read methods only; no external artifacts/config execution, held-out tuning or framework migration. |

Rights review, clock evidence, executable bid/ask/contracts/costs, independent phase review and P11b.1 authorization remain in the [existing pending list](pending.md). No item here relaxes those prerequisites. Owner review is the next action; the audit stops without implementation.
