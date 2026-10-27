# Codex implementation plan — RC repairs and broker-independent research

Status: F-01–F-06 are implemented; complete offline gates pass (992 tests and 14 paper studies). The remaining
research increments below are planned, not claimed implemented. This plan is
reviewed against the original findings, repository risk/data rules and runnable
offline boundaries. Review is automated self-review; independent human sign-off
and genuine integration remain pending.

## Execution contract for the next Codex session

Read AGENTS.md, prompts/_PROTOCOL.md, the original independent review, the remediation
completion report and broker-independent research runbook. Start from the local
remediation branch or a clean copy of its reviewed patch. Preserve original
worktrees, private files and all evidence. Do not fetch/push, activate CI, load
credentials, authenticate, contact a provider, submit an order or access 2025+
holdouts. Use installed pinned packages and the offline guard. Stop if a required
dataset license is missing; continue owned tests and document the missing evidence.

## Implemented remediation map

| Finding | Implementation responsibility | Acceptance evidence |
|---|---|---|
| F-01 | paper/offline/models.py and engine.py: persist original stop activation before fill attempt; keep a stop-market exit compulsory across rebounds/restarts | Missed/repeated unavailable fills, rebound/worse bid, stale source, SELL/EOD competition, two restarts, exact cash/fees and one exit |
| F-02 | broker/ctrader.py: reuse distinct account-rights parser for connect and reverify; close on missing/unknown/NO_LOGIN | Available account rights with view token accepted; invalid rights and session transition refused before quote |
| F-03 | dashboard/shadow.py plus shadow/reporting.py: current documentary scope, digest/identity/provider/instruments and price-free authorization pointer before snapshot read | Absent/expired/revoked/substituted policy read spies; stopped snapshot cannot bypass; owned views independent |
| F-04 | ingest/retention.py and broker/reference/shadow writers/readers, raw commit manifests, cache lifetimes and recovery metadata | Original acquisition, before/at/after deadline, mixed-age refusal, cache restart and renewal refusal, publication/recovery denial |
| F-05 | ingest/owned_transport.py and twelve_data/client.py: production custom transport remains genuine; exact explicit fixture mock executes under socket denial | Standard/custom/mock injection requires genuine rights; invalid fixture type/forwarding refused; cache provenance protected |
| F-06 | shadow/journal.py: complete schema digest before initializer on existing DB; create only for new journals | Missing/replaced trigger, missing empty table, added schema/index and changed existing index refuse without changing database bytes |

Do not weaken an assertion or widen risk/permissions to achieve a green gate.
Existing genuine entry points now require current documentary review. No actual
approval policy is installed or inferred by tests; fictional documents exist
only in disposable test roots.

## R1 — Offline dataset registry and rights admission

Prerequisites: final RC gates pass; owner selects an actually owned/licensed local
dataset and supplies its documentary scope privately. No dataset is approved yet.

Create a dedicated research namespace, e.g. `src/tb/research/datasets.py`,
`src/tb/research/rights.py` and `tests/unit/test_research_admission.py`. Keep ownership
of this increment together. Add explicit licensed-local provenance rather than
using owned_fixture/synthetic. Reuse bounded canonical hashing, current rights and
retention helpers where appropriate; define schema version changes deliberately.
No network import or generic provider client belongs in the importer.

Deliver a check-only registry command that validates path containment, source and
dataset identity, file hashes, reviewer/documentary evidence, allowed uses,
original acquisition, immutable retention deadline and coverage. Public templates
must start unverified; checking structure is not granting rights. Installing a
policy or moving/deleting data is a separate explicit action.

Tests: missing/ambiguous license, wrong identity/hash/instrument, expired/revoked
grant, missing training/display rights, path escape, oversized file, changed
policy, old acquisition under renewal and a valid owned fictional example. Missing
scope must refuse before opening price-bearing files; spy on those reads.

## R2 — Bounded local-file research ingestion

Depends on R1. Add `src/tb/research/importer.py`, a finite CLI, owned small fixtures
and integration tests. Stream CSV/Parquet chunks within the 16 GB machine budget;
preserve original Bronze bytes and generate a manifest. UTC source/receipt and
availability semantics must be explicit. Separate midpoint/reference and bid/ask.
Reuse the shared feature engine and existing no-lookahead rules. Admit only
approved instrument scope; no broker adapter or paper execution bridge.

Tests: empty/single/mixed inputs, duplicates, out-of-order times, revisions, DST,
future/unavailable bars, gaps, NaN/inf, incomplete OHLC, wrong units, corrupt hashes,
large chunked input, path with spaces and restart. Never reopen a real dataset
after its deadline. Demonstrate refusal of a licensed-to-owned provenance cast.

## R3 — Preregistered research and evaluation report

Depends on R2 and separate ML/AI permission when relevant. Add finite research
commands that freeze hypotheses, strategy/feature versions, baselines, split,
label horizons, overlap treatment and metrics before scoring. Use 2020-10–2023-12
training and 2024 validation only when rights/coverage allow. 2025+ remains locked.
An insufficient-data result is valid; no tuning on the holdout or on test failures.

Report signal coverage, missing outcomes, uncertainty, controls and sample limits.
Keep directional performance separate from hypothetical execution. Local paper
cash tests retain invented contracts/costs and label that assumption. Models may
only score/veto/reduce size; no keys, order gateway or automatic promotion.

Tests: prospective availability, no train/serve skew, label leakage, overlap and
missing outcomes, control baselines, locked-holdout refusal, expired dataset/model
use, zero-provider/key execution, deterministic replay and price-free denied UI.

## R4 — Retention inventory and reviewed disposal tool

Depends on R1's dataset and derivative graph. Implement a check-only inventory of
raw/Silver/Gold, journals, cache, report, model, backup and export dependencies.
Generate an exact dry-run target list with hashes and deadlines. An actual purge
requires the owner's explicit approval of that list and contractual audit/backup
rules; default is denial and a report, not deletion. Never rewrite Bronze facts.

Tests: path escapes/symlinks, changed hashes, omitted dependent artifacts, protected
worktrees, concurrent writers, Windows locked files and interrupted operations.
Recovery must resume from the inventory without silently claiming full disposal.

## Separate future genuine integration gate

This is not the next automatic increment. Require explicit owner authorization,
actual cTrader approval, independently accepted exact callback, consent/view scope,
single-demo identity/account rights, current data licenses, clocks, contract units,
costs and eligibility evidence. Review integration in a separate clean checkout.
Genuine-to-paper work, external orders, publication/push and CI activation each
need their own explicit decision. Never copy private credentials into a patch.

## Verification and review gates for every increment

Run `scripts/check-rc-remediation.ps1` with an existing pinned Python environment.
Run new targeted admission/no-lookahead/retention tests first, then full Ruff,
formatting, strict MyPy, all non-live pytest, safety smoke and 14 owned paper cases.
Record actual exit codes, test totals, source/risk pins and scenario summaries.
Check changed sources for secret values, forbidden endpoints, genuine order paths,
holdout access and workflow activation. Update journal, living state and handoff.

Review checklist: all six findings remain closed by assertions; no provenance
laundering; no reset of original acquisition; current rights before file reads;
schemas verified before writes; risk defaults unchanged; no real-performance claim
from synthetic evidence; no unauthorized integration, push or hosted execution.
