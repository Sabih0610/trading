# P11j Wave 2 - Strict limit fills and gap-aware labels

Both Stage 3 result batches were approved and merged before this work began.
The new credential-free branch starts at main 69034f6. D-3 changes future default
LIMIT fills to strict trade-through; D-4 makes existing loss labels use a lower
gap opening price. No genuine observations, labels or F/G batch were read or run.

- [x] Read merged F/G approval, Wave 2, rules and exact audit findings.
- [x] Implement conservative default fills and explicit gap-aware label inputs.
- [x] Preserve audit assertions and remove only the two resolved strict xfails.
- [x] Pass focused fixtures, strict typing and lint/format checks.
- [ ] Pass complete offline gates in a clean checkout, one full suite at a time.
- [ ] Publish with [skip ci]/--no-follow-tags and the empty review marker.

## Change and scope

BacktestEngine now fills a buy LIMIT only when a later eligible bar has low < limit.
The old public research_trade_through_limit keyword is removed, so false cannot
restore touch fills. Signal-bar admission, expiry, conservative raw limit price,
participation, funded cash/exposure/risk checks, EOD flattening and bracket
ordering remain. MARKET C/D/E/G behavior is unchanged.

The already registered G-1 touch sensitivity remains in a private subclass inside
GoldProxyBatch. It is constructed only after the closed research-purpose, input
and scoring-window preflight; no bare engine or runtime bars are exported. Owned
fixtures compare touch and strict paths through that adapter. The main engine has
no touch-mode constructor switch. This preserves diagnostic coverage without
reopening G's immutable result or bypassing its code/config/data identity.

LabelBar now requires finite positive open with coherent OHLC bounds. A long LOSS
uses min(open, stop) / entry - 1, so a gap below the stop is not booked at an
unavailable stop price. Unknown opens fail closed. Existing target, adverse
same-bar, timeout, next-bar candidate, right-censor and no-candidate behaviors
remain. D-4 affects ML labels only; no training, model, Stage 4 or order starts.

## Validation and scenarios

The focused command in the [runbook](../../docs/how-to/strict-limit-and-gap-labels.md)
passed **66 tests in 11.63s**. Strict mypy passes on all three modified sources.
An additional **95** owned gold adapter/runtime-boundary/batch fixtures passed
in **49.77s**. Full-repository Ruff passes and **603 files** are formatted. These
are focused/static checks, not a full-suite claim; the clean offline gate is
pending the coordinated slot.

| Scenario | Expected and observed |
|---|---|
| Production limit touch | No fill; original D-3 assertion now passes |
| Strict touch followed by trade-through | Fills only while still within original expiry |
| Removed false/true constructor keyword | TypeError; cannot weaken default fills |
| Signal bar already below limit | No same-bar entry |
| Gap below limit / below stop | Conservative limit entry; adverse open stop exit retained |
| Same-bar target on intrabar limit fill | No invented target win |
| Both held bracket orderings | Existing stop-first / research target-first retained |
| MARKET entries under touch/strict historical sensitivity | Exactly identical result to default engine |
| Stop gap, including later target high | LOSS uses lower opening price, preserving adverse priority |
| Stop touch / ordinary stop cross | Stop price used |
| Missing, nonfinite or out-of-range open | Validation refusal |
| Future gap after an earlier target | Earlier label unchanged |
| Missing candidate / right-censored label | No label invented |

An AST comparison against main 69034f6 proves all **43** assertion nodes in the
modified audit module and all **6** existing unit-label assertions are unchanged.
Only D-3/D-4 strict xfail decorators are removed. Existing label fixtures gain
explicit owned opens; the gap fixture opens at its existing bar high 90 and keeps
its original loss bound. No skip, assertion or unrelated xfail is weakened.

## Historical result boundary

Stage 3 verdicts were produced before these engine/label semantics. Never rerun,
retune, relabel or overwrite them. F's MARKET C/D/E and G's MARKET C/G are unaffected
by D-3. A's approved G-1 already reported a strict-path sensitivity. D-4 changes
future ML labels, not strategy evaluations. No genuine label generation occurs.
No 2024 data, 2025+ holdout, sealed forward archive, paper/Testnet/live workflow,
provider credential or risk configuration is accessed or changed by this task.

## Evidence and usage

[Research](../../docs/research/P11j-wave2-research.md),
[journal](../../docs/journal/P11j-wave2-journal.md),
[ADR 0027](../../docs/adr/0027-strict-limits-and-gap-labels.md) and the
[runbook](../../docs/how-to/strict-limit-and-gap-labels.md) record the decision,
required-open API migration and exact owned commands. Limit trade-through is a
bar approximation, not measured queue position. Labels remain gross price returns;
no unregistered transaction-cost label model is added.

## Living-doc entries

After review/merge, the separate living-docs PR records D-3/D-4 resolved, only their
strict xfails removed, strict production LIMIT defaults, required OHLC opens and
gap-aware future LOSS returns, full clean gate evidence and the preserved historical
Stage 3 identities. Shared living files and the merged Wave 1 report are untouched.
This completes the authorized audit repair scope only; no next research/trading
stage is started.

Full gate and publication are pending; this candidate is not yet ready for review.
