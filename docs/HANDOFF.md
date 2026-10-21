# Current handoff

P05 is complete/tagged and ready for routine Claude review. The verified sample has causal,
versioned Gold features for all approved Spot assets and six timeframes.

- Last completed step: P05 full gate passed with 140 tests and 3 live tests deselected; 168 Gold
  partitions / 51,940 rows built and a repeat skipped every unchanged write.
- Next step: start P06 research and define an event-driven, long-only Spot simulator whose sizing
  and kill switches reuse the deterministic risk-policy authority.
- Exact next command: read `prompts/P06-backtester-and-risk.md`, initialize its journal/report/state,
  then research current fee/slippage simulation, purged validation, and deterministic risk controls.
- Open problems: exact DXY is gated under D-0016; P05 macro features must represent it as unavailable rather than fabricate it. GDELT history awaits cooldown; full P02 history lacks storage; live FRED remains pending D-0011.
- Safety state: P04 is offline transformation only. It creates no orders, changes no risk limit, grants no AI authority, reads no secret, and proves completed-bar causality.
