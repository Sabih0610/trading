# P11p postmerge audit - independent static findings

Date: 2026-11-06 UTC. Auditor: Codex. Scope: merged main
4ca46356d419dd2434c22bef19c0224c6062c30a, public source and public records only.
This is a static audit, not approval of a run, a new strategy registration or a
request to rerun genuine data. No genuine private input/result was opened and
no application/test/benchmark was executed for this audit.

The recorded verdict remains **insufficient evidence**, with no promotion.
It does not establish a valid profitable strategy or justify paper operations.
The findings below constrain interpretation and identify unfinished prompt work.
Claude should respond through a review file on main; do not change a frozen
batch, retune, regenerate it or describe changed-source starts as identical resumes.

## Registration identity and concurrent work

The actual [merged preregistration review](P11p-prereg-review.md) approves SHA256
ac6908761fd9c2590bd789c205a2e7db1a8fb1c18816b7c6acd3dc1e91f3d181,
on Claude's builder branch, with disclosed builder/self-review independence limits.
The [Part B review](P11p-review.md) records its merge as insufficient evidence.

Codex concurrently published documentation-only PR20 at b140172, proposing a
different SHA256 ebedb35802a4c19bf49a998f6767c6faa20f0ec0cb5f1b0f0691b720412d0ddd.
That proposal has NOT received approval. Approval for ac690876 cannot unlock
ebedb358. It must not become a second genuine batch or overwrite the run's original
registration. Retire the unused PR without merging it; preserve its historical
proposal/receipt. The owner's intended single test has already been attempted.

## Findings requiring reviewer disposition

### P-1: expected-open gaps are silently removed (high)

[Reader](../../src/tb/research/swing_data.py), COLUMNS and _bars:
every null-OHLC row is skipped, with no expected_minutes distinction and no
HistoryGap emitted. This treats an ended missing expected-open window like a
scheduled closed window. N deliberately preserves those barriers; only
expected-zero closed windows may be omitted. O daily lookbacks can therefore
bridge missing expected-open days after the reader has removed the barrier.
An old confirmed swing can also survive the missing window in swing_lows.

Required disposition: record this result limitation and preserve the original
batch. Specify owned regressions for expected-open null rows versus expected-zero
closures and support reset. Any repaired evaluator needs independent directions
and cannot be used to rerun this batch automatically. The assertion that null rows
cannot affect candidate results is not established merely by calling them closed days.

### P-2: terminal cash, return and timing evidence can disagree (high)

[Simulator](../../src/tb/backtest/swing_portfolio.py), final flattening:
the final close occurs AFTER the last daily return, path extrema and DD have
already been recorded. Its exit fee can enter NetTrade P&L without entering
FoldEvidence.daily_returns; metrics compound that incomplete equity-return path.
If the last day is missing, it closes at position.fill, which invents an executable
exit rather than marking unresolved inventory. Intraday stop exits are timestamped
at day open, so holding_days is not the actual fill-to-stop elapsed duration.

Required disposition: qualify the recorded return/DD/holding diagnostics.
Do not compute replacement genuine metrics. Future owned tests should reconcile
ending cash versus compounded returns after a terminal sale with costs, refuse
fabricated exits on a missing endpoint, and distinguish actual versus daily-resolution
holding-time measurements. The original preregistration did not fix a source-minute
terminal convention as requested in the root handoff.

### P-3: changed-source full restarts are not exact-identity resumes (high)

The [journal](../../docs/journal/P11p-journal.md) records three starts and three
implementation hashes. Attempt2 completed training/development and began the2024
random benchmark before the next source change and restart. An absent results.json
does not mean no computation or selection occurred. Reproducing one selected trial
does not prove unchanged full candidate paths, private outcomes or random paths.

[Runner](../../src/tb/backtest/swing_stage3.py), run(): only results.json prevents
a restart; frozen-2024-selection.json is overwritten. There is no immutable
registration/code/config/data checkpoint identity, lease, or exact-resume guard
in this function. The code accepts a changed years_dev argument as well.

Required disposition: preserve all attempt records and label the chronology
honestly. Do not claim this met the exact-identity technical-resume requirement
without independent evidence/explicit reviewer disposition. No further run is
authorized by this audit. Original F/G batches stay immutable.

### P-4: random frequency and aggregate ratios need qualification (medium)

random_p95 uses probability N/(days-10), with holds, cost vetoes and circuits.
That matches an attempt-rate parameter, not the candidate's realized completed
trade frequency. No equality check or unmatched-frequency status is recorded.
The development buy/hold DD is max(annualDD), rather than DD of the compounded
two-year path; this can miss a loss from a prior-year peak. Missing training
benchmarks are converted to zero in the development verdict path rather than
being unavailable. These paths were not reached for the reported insufficient
development verdict; that does not validate their correctness for a future pass.

Required disposition: no claim that the informational random win is evidence
against a matched-frequency distribution, or that future-pass checks are validated.
Use owned fixtures for future hardening; no genuine metric regeneration.

### P-5: required diagnostics and Swing view remain unfinished (medium)

The merged diff adds four research modules and their tests, without a dashboard
Swing view. In verdict(), the insufficient-evidence branch bypasses the metrics
section, so required holding duration, win rate, break-even and cost-share diagnostics
are absent from the public result. Do not treat a low-frequency nonpass as permission
to silently omit the requested report/view. A field may be explicitly unavailable
when not computable; do not invent values or open private results without first
fixing/documenting the publication-only path and its permission boundary.

Required disposition: finish a read-only Swing result presentation with owned
fixtures and explicit missing diagnostics, or document an actual owner-scope waiver.
Any source changes need their appropriate clean offline gate after the active
review window, without rerunning strategy research. The reported full-suite
hook invocation is not a concrete pass receipt; publish actual exact-source exit
status/counts when available, preserving M's separately recorded timeout/re-pass.

## Other disclosed limits

The macro-event calendar veto is explicitly absent in the merged review.
Do not call the prompt's calendar requirement implemented, or infer the effect
on returns from its effect on trade count. The journal exposes genuine source
coverage counts; do not repeat further quality diagnostics in public documents.
No new risk/default/allowlist/source change is proposed here.

## Completion boundary

M/N/O and the recorded P result are actually merged. This audit does not reverse
that Git fact or promote the result. MASTER remains open for disposition of these
findings, the required read-only output work, and an actual separate living-docs
PR merge. No final MASTER report/ready marker is created by this audit. The
coworker's unfinished living/final files are preserved without copying or editing.
