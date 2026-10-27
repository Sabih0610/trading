# AI Trading Lab — RC remediation completion report

All six findings are fixed and self-reviewed. The complete offline gates and all
14 deterministic paper studies pass.
Genuine P11b.1a/P11b.2b remain NO-GO. No private credentials, real OAuth, market-data
API calls, orders, pushes, merge or hosted CI activation were used.

## Scope and provenance

The requested implementation baseline is `b669d430148ba0bb67c9f46f7560341a52165ff1`.
Work starts from sanitized shared HEAD `85f87ce3e9d5613a1fc2e0caacaaa5b0fdc07832`.
A fresh `git diff` verifies no implementation differences in src/tests/config/
scripts/.github/pyproject.toml/uv.lock between those revisions. Sanitized history
and documentation were retained. The original uncommitted independent review was
copied unchanged, with its hash checked against the preserved original.

The app's managed-worktree creation was unavailable in this projectless chat.
A separate detached local Git worktree was created under the chat's work folder.
No protected checkout was reset, switched, merged, cleaned or written. Existing
protected branch heads remain unchanged; private files were neither read nor
hashed. No fetch or other Git network operation was performed. An existing pinned
Python environment was reused with the new checkout's src first on PYTHONPATH;
no dependency installation/sync occurred.

## Changes and acceptance

| Finding | Fixed behavior | New regression cases |
|---|---|---:|
| F-01 | First stop-market activation persists before attempted fill; next eligible available bid closes once with original reason, fees and slippage after rebound/restart. | 4 |
| F-02 | Initial and periodic quote identity verification parse account rights separately from view-token scope; missing/unknown/NO_LOGIN closes the channel before the next quote. | 23 |
| F-03 | Genuine shadow display requires current documentary derived/display rights, exact source scope and digest, plus authorization metadata before opening the snapshot. Owned views remain independent. | 7 |
| F-04 | Original acquisition and earliest retention/grant deadline follow raw commits, cache, broker ledger and derived evidence. Reads/recovery/reuse/publication refuse at expiry; renewal cannot extend old evidence. | 10 |
| F-05 | Custom production transports retain genuine permission checks; only an explicit exact in-memory fixture transport labels synthetic and executes under Python socket denial. Cache provenance cannot be promoted. | 4 |
| F-06 | Complete table/index/trigger schema is checked read-only before existing journal startup. Missing/replaced/added schema refuses without repairing the database; malformed metadata releases its lease. | 7 |

Total: **55 new regression cases**, preserving existing assertions and risk limits.
The older Twelve Data reference reader/publisher and collector facade also use
current documentary rights, closing the equivalent stored-evidence path. No real
approval policy was created or changed. Negative tests used clearly fictional
permission documents and invented observations in disposable roots.

Stop behavior is explicitly stop-market: the stop price triggers compulsory exit,
not a guaranteed execution price. Available subsequent bid, modeled slippage and
both fees determine the hypothetical proceeds. Targets retain their existing
limit-style rule; no stop-limit feature or real order gateway was introduced.

## Validation

| Gate | Actual result |
|---|---|
| Installed environment / offline guard | PASS; Python 3.12.11, 26 direct pins; no installation/sync |
| Ruff lint / formatting | PASS; 440 files formatted |
| Strict MyPy | PASS; 169 source files |
| Complete non-live pytest | **992 passed, 3 live deselected, 23 existing warnings; 283.31 seconds** |
| Owned safety smoke | PASS |
| Deterministic paper studies | **14/14 PASS; 3811 inputs, 16 hypothetical fills; all accounts flat; 0 external orders** |
| Independent rational FX/gold cases | 6/6 PASS plus gap/restart/day-change oracle |
| OAuth/protocol negative checks | PASS; six scope/access cases, 72 nonallowlisted IDs and callback/code tests |
| Scope/safety review | PASS; risk, assets, dependency pins and .github unchanged |


Fresh baseline probes reproduced all six findings against the preserved source.
On the revised source, six independent rational FX/gold cash oracles pass, as do
the adverse-gap/restart/day-change oracle, six OAuth/scope/access denials, 72
nonallowlisted protocol denials and callback/code checks. The focused review set
passes **147 tests**. Test fixtures use only invented keys, identities and data.

The initial complete run recorded 989 passes and one new regression failure in
the static category used for a retention denial during startup. That category was
corrected; the assertion was retained. Additional source review hardened bounded
metadata object handling and explicit closure of schema-check connections.

The offline runner verifies installed direct pins and that the Python socket guard
refuses an external-address audit event without making a connection. It permits
owned loopback tests. It is an accident guard, not an OS firewall against hostile
native/subprocess code; no such bypass was used or claimed. Hosted CI was not run.

## Operational research plan

The lab works now for deterministic owned software/accounting research without
cTrader. Run `scripts/check-rc-remediation.ps1` with an existing pinned Python 3.12
environment, or `tb.paper.offline.cli demo` under the offline guard. See the
[runbook](../../docs/how-to/broker-independent-research.md) for exact commands.

The [Codex-ready implementation plan](../../docs/specifications/P11b-broker-independent-research-plan.md)
sequences a documentary dataset registry, bounded local-file importer,
preregistered research evaluation and an owner-reviewed retention/disposal tool.
These follow-on increments are planned, not implemented. No actual licensed
market dataset has been admitted. Public availability and OAuth tokens do not
constitute data licenses; synthetic scenarios do not establish trading profitability.

Licensed data must retain its actual provenance and may not be relabelled to
enter the owned-only paper engine. Training/validation split rules, 2025+ holdout
lock, common features, explicit costs and deterministic risk authority remain.
No AI can create/enlarge a trade, move a stop away or access keys. Generated USD100
and ENG10000 accounts remain separate hypothetical engineering studies.

Expiry/revocation denies usage immediately. A separate dry-run inventory must
identify raw/derived/cache/model/backup/export targets and permitted audit metadata
before any owner-authorized purge. No original evidence was deleted or rewritten.
Inaccessibility alone is not assumed to satisfy an actual provider's disposal terms.

## Review and release decisions

[Review record](../reviews/P11b-RC-remediation-review.md) documents automated
self-review of source and plan, with independent original audit reproductions and
accounting oracles. This is not independent human/organizational certification.

- Owned offline software research: GO; no empirical alpha claim.
- Independent human review/sign-off: pending.
- Genuine OAuth, connectivity, data admission and P11b.2b integration: NO-GO.
- External orders: disabled; no new execution gateway.
- Push/publication, merge or hosted CI activation: not authorized/performed here.

Actual app approval, accepted callback, consent, single-demo scope/account rights,
data-use rights, contract units/costs, independent clocks and eligibility require
separate owner evidence and explicit authorization. Approval alone enables none
of the remaining gates. Older unpinned journals/caches refuse; use new owned study
folders rather than repairing or migrating protected evidence automatically.

## Evidence and handover

Evidence is in `reports/validation/P11b-RC-remediation/`: fresh baseline
reproductions, independent oracles, preservation checks, safety review, final
quality summary and deterministic paper summary. Detailed raw test logs and
invented scenario databases stay under ignored `work/rc-validation/`.
The handover bundle supplies a reviewable patch, source and plain-language reports;
local revision and artifact hashes are recorded in its manifest.

The copied original review remains a historical audit record. Its statements that
findings were open and that no changes occurred describe that earlier audit, not
this remediation. Its original protected copy remains uncommitted and unchanged.

Observer 3.6.0 recorded workflow observation 0001 (startup protocol prelude) for
later review. No installed skill was changed or starter principle imported.

Ready for independent review: source/plan/report links complete; acceptance evidence
recorded; limits and owner gates explicit. Do not authorize genuine integration
implicitly from these offline results.
