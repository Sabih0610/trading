# Current handoff

P04 is complete/tagged and P05 feature-engine research is in progress. The verified Bronze sample
has deterministic, UTC-aligned Silver inputs with checksum lineage and quality reports.

- Last completed step: initialized P05 and began current-source research for causal rolling windows,
  confirmed pivots, streaming parity, and Binance spot order-book inputs.
- Next step: finish `docs/research/P05-research.md`, record the feature-contract decision, then write tests for a shared streaming state machine before its batch adapter.
- Exact next command: create `tests/unit/test_feature_engine.py` with warmup, confirmed-pivot, gap,
  and batch/stream equality cases, then implement `src/tb/features/engine.py`.
- Open problems: exact DXY is gated under D-0016; P05 macro features must represent it as unavailable rather than fabricate it. GDELT history awaits cooldown; full P02 history lacks storage; live FRED remains pending D-0011.
- Safety state: P04 is offline transformation only. It creates no orders, changes no risk limit, grants no AI authority, reads no secret, and proves completed-bar causality.
