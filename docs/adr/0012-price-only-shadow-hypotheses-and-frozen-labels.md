# 0012 — Price-only shadow hypotheses and frozen future labels

Accepted2026-10-24 for owner-authorized offline P11b.0.1. EURUSD and XAUUSD can produce research
BUY/SELL/WAIT from completed reference OHLC. SELL denotes a downward hypothesis and grants no
short-sale, account, instrument or execution permission. Existing Spot and contract-risk rules
stay unchanged. Genuine provider rights remain unverified and no genuine run starts here.

Use the shared FeatureEngine with optional bounded EMA12/26 and strictly prior20-channel state.
ATR14 is the existing Wilder calculation. Default warm-up52 contiguous bars, a0.1ATR neutral/
breakout buffer, ATR/close0..0.02 and current range/priorATR<=4 were frozen before scenarios.
Initial qualified trend establishment is a transition; continued same regime emits WAIT. Close
breakouts exclude current high/low and optionally require1-3 completed closes. Gaps reset both
indicators and strategy state; filtered transitions are consumed rather than delayed into entries.

New hypotheses implement a distinct ReferenceSignal contract, not the execution StrategyPlugin
contract. The reference registry is separate from approved execution mappings. The unchanged old
strategies retain missing-input blocks. New config2.0.0 journals six decisions/event; legacy
configuration continues to define four. New studies use separate folders and exact version pins;
old input, journals and genuine evidence are never migrated or overwritten silently.

One SQLite transaction commits the admitted event, all six decisions and hash checkpoint.
Recovery reconstructs both feature and signal-suppression state. Persist exact configuration/hash,
versions and causal timestamps. Later outcome labels append separately and reconcile after restart.
The predeclared1/3/6 full-M5 horizons start at the first opening>=decision time, with zero-bps flat
threshold. Every outcome needs contiguous committed same-source future bars. WAIT is excluded;
missing outcomes remain missing. Always-WAIT and matched always-UP/previous-move comparisons are
research baselines. Overlap is flagged per symbol/strategy/horizon; synthetic/overlapping results
never establish trading skill, profitability or independent statistical significance.

Public projections contain counts, states, times, versions and labels, not raw price/features or
account P&L. Documentary approval review is offline, scoped, hash-bound, expiring and retention-
specific. A pending support request never grants rights. No approval is installed in this phase.
