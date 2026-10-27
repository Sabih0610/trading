# RC remediation and implementation-plan review

2026-10-27 UTC. Automated self-review of the proposed source changes and research
plan, using the original independent review as the acceptance contract. This is
not a separate human/organizational review or a production certification.

The original baseline reproduction harness was copied into the chat's work folder
and executed against the preserved credential-free source. All six findings were
freshly reproduced with invented inputs. The revised implementation has 55 new
regression cases covering those findings; an additional focused set of 147 tests
passes after fixes. Final complete gate results are recorded in the phase report.

| Finding | Review conclusion and regression coverage |
|---|---|
| F-01 | Stop activation is stored in PaperPosition and the atomic event/effect checkpoint before any fill attempt. Rebounds cannot suppress it. Four new cases cover repeated missed fills, restart, worse/rebound bid, SELL/EOD competition, stale source, exact costs and one exit. |
| F-02 | The adapter uses the existing distinct account parser on both initial and repeated identity checks. 23 cases cover unavailable/malformed rights, valid available account enums under SCOPE_VIEW, and timed mid-session loss before receiving a quote. |
| F-03 | Current documentary review, derived/display scope and exact pointer identity/provider/instrument/digest checks precede snapshot opening. Seven denied-policy cases use read spies; stopped snapshots cannot reuse old approvals. Owned UI remains usable with a malformed genuine policy. |
| F-04 | Original acquisition and earliest permitted expiry are persisted across raw manifests, cache, broker ledger and derived snapshots. Ten new cases cover just-before/at/after expiry, mixed age, cache restart, policy renewal, raw recovery, shadow publication/recovery and provenance reuse. Older Twelve Data projections now use the same current-rights gate. |
| F-05 | A production transport argument remains genuine, including HTTPTransport and MockTransport. Only fixture_transport accepts an exact in-memory mock, with Python socket denial during handler/response processing. Four new cases test production injection and fixture forwarding/type refusal; a cache case prevents genuine cache content being relabelled synthetic. |
| F-06 | Existing shadow databases undergo read-only complete sqlite_master digest checking before DecisionLedger initialization. Seven cases cover missing/replaced triggers, missing empty table, added table/index, altered existing index and malformed metadata/lease recovery. Denied schema reopen preserves database bytes. |

## Additional review corrections

- Current-policy enforcement was extended to the older Twelve Data reference
  reader/publisher and collector facade so the same class of gap is not left on
  that path. No production policy or provider request was created by this change.
- Retention denials during shadow startup now retain a static retention/current-
  rights refusal category. The first complete run caught the wrong category;
  this was corrected, without weakening the new assertion.
- Metadata must be a bounded JSON object before schema fields are read; malformed
  metadata releases the lease. Read-only schema connections explicitly close.
- Legacy evidence without lifetime/schema pins refuses. There is no silent repair,
  migration, acquisition-clock rewrite, purge, risk increase or genuine-to-paper bridge.

## Plan review

The [Codex-ready plan](../../docs/specifications/P11b-broker-independent-research-plan.md)
defines dependencies, file responsibilities, data admission, research split,
bounded local import, evaluation and disposal acceptance tests. It correctly
identifies R1–R4 as future work, not implemented features. No genuine licensed
market dataset has been reviewed; fictional test permissions grant no real rights.

The plan protects 2025+ holdouts, disallows licensed-to-owned relabeling, preserves
the common feature engine and deterministic risk authority, and separates
directional research from executable quotes/fills and empirical profitability.
Disposal starts with an owner-reviewed dry-run inventory; no original evidence
is deleted. Genuine integration, orders, pushes and CI remain separate owner gates.

## Remaining limits and release decision

No unresolved P1/P2 issue was found in this bounded self-review after the recorded
corrections. This conclusion is limited to inspected paths and owned offline
cases. Python audit hooks are an accident guard, not an OS boundary against
malicious native code, subprocesses or a hostile same-user Python caller.

GO for owned offline software research after the final complete gates pass.
Independent human review remains pending. Genuine P11b.1a/P11b.2b, actual data
admission/integration, external orders, pushes and hosted CI remain NO-GO under
this task. Actual approval, callback compatibility, broker eligibility, data
rights, metadata, costs and independent clocks have not been verified here.
