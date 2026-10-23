# 0011 — Reference shadow decisions require explicit rights and causal availability

Accepted2026-10-23 for offline P11b.0. Runtime is deterministic Python with no execution/account
writer. Genuine use requires each applicable versioned permission confirmed AND affirmatively
approved for exact source/account/instruments and unexpired. Default Basic policy blocks it.

Keep source opening/close separate from receipt/availability/decision time. Admit completed M5
only after close+120s and timely receipt/coverage. Freeze first interval identity and reject
revisions, backfill, future events and catch-up after downtime. Never change an earlier decision.

Reuse shared causal features with explicit missing volume/sessions. Existing strategies lack
eligible reference inputs: journal WAIT with the blocker, never invent an EMA trading strategy.
BUY/SELL schema values denote research directions only; no orders, balances, fills or P&L fields.

An isolated DecisionLedger-derived SHADOW journal uses append-only SQLite WAL/FULL records and
atomic input/decision/checkpoint writes. Identity binds provider, credential fingerprint, rights,
code/config/feature/strategy versions. Recovery reconstructs feature state from committed inputs;
durable slots/dedup and process lease prevent parallel or repeated decisions. Missing or corrupt
state is not an empty healthy journal. Existing market files are read-only and never rewritten.

Offline event replay uses owned synthetic evidence and a simulated receipt clock. Production
consumer is independently runnable but no unattended task or genuine trial is installed/started.
Later labels append to frozen decisions and report directional reference behavior, not win rate
or broker P&L. P11b.1 remains a design handoff only.
