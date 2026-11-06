# P11p journal: Stage 3b swing rotation

## 2026-11-06: Part A frozen before any genuine data

- Builder and reviewer: Claude. The owner is away and authorized autonomous continuation on 2026-11-06. Codex is not running.
- Built: `research/swing_data.py` (rights-checked swing-v1 reader), `strategies/swing_rotation.py` (27-trial catalogue and
  causal per-day signal table), `backtest/swing_portfolio.py` (daily one-position rotation simulator reusing
  RiskManager, CostAssumptions and AccountCircuitBreaker), `backtest/swing_stage3.py` (walk-forward, N = 243 DSR,
  bootstrap, comparators, verdict), and `tests/unit/test_swing_stage3.py` (11 owned-fixture tests).
- Design notes recorded before data:
  - No intraday target, so the stop is the only intraday event and no ordering ambiguity can arise.
  - Gold 2024 warms up on PAXG alone, with no stitching.
  - 2024 is loaded only after the frozen selection is written.
  - No config or allowlist change.
- One fixture test initially failed because my fixture put the drop *within* the day (a correct stop exit at −1R); the
  test fixture was corrected to a genuine open gap. The simulator was unchanged.
- **Pre-registration SHA-256:** `ac6908761fd9c2590bd789c205a2e7db1a8fb1c18816b7c6acd3dc1e91f3d181`
- **Implementation SHA-256** (concatenation of the four source modules): `6f301b91eaf9eed18a6550577de52027f384213c55370b5063d2ca8de6f32a4c`
- No genuine registry, manifest or price file has been opened for P11p.
