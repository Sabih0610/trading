# ADR 0027 - Strict limit defaults and gap-aware loss labels

Proposed for P11j Wave 2 review, 2026-11-04. F and G Part B are merged at the
69034f6 baseline. This changes future simulator/label semantics and preserves all
reviewed Stage 3 evidence. No runtime, provider or trading authorization is added.

## Decision

The default BacktestEngine buy-limit predicate is low < limit. Remove the public
research_trade_through_limit keyword instead of allowing false to restore touch
fills or silently ignoring it. Strict fills retain expiry, next-event admission,
conservative raw limit price, participation, cash/risk checks and OCO behavior.

GoldProxyBatch retains its registered touch path through a private engine subclass
constructed only after the adapter's purpose, input and score-window preflight.
No engine or runtime bar is exported. This preserves owned sensitivity coverage,
not permission to rerun the immutable G batch; source identity changes also bind
any technical resume to its original code. The production/default path is strict.

LabelBar requires a finite positive open within its OHLC bounds. A LOSS uses
min(open, stop) / entry - 1. Unknown opens are rejected rather than fabricated.
Adverse same-bar priority, target and timeout accounting, holding windows and
right-censor omission remain unchanged. No net-cost model or ML training starts.

## Consequences

The old constructor keyword raises TypeError. Label callers must provide genuine
opening prices when separately authorized; owned fixtures supply explicit opens.
The audit assertions remain unchanged and only their resolved strict xfails are
removed. New fixture tests prove gap and no-gap losses, invalid/missing opens,
no future-bar effect after an earlier target and the closed historical sensitivity.
C/D/E/G use MARKET entries, so D-3 does not affect those Stage 3 verdicts. D-4 only
changes future ML labels. F/G results, manifests and genuine labels are untouched.

See [research](../research/P11j-wave2-research.md) and
[phase report](../../reports/phases/P11j-wave2.md).
