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

## 2026-11-06: technical defect during data loading (no outcome observed)

- The first Part B start crashed while **loading** XAUUSD development bars (`decimal.InvalidOperation`): P11n keeps
  market-closed calendar rows (weekends, holidays) with null OHLC. No simulation had run, no selection was written and
  no result exists (the output directory was empty).
- Fix: `swing_data._bars` skips rows with null OHLC. A closed day has no tradable bar, consistent with the registered
  "never filled" rule. The registration is **unchanged** (SHA-256 still `ac690876…`). Only the reader changed, so the
  implementation hash is re-recorded below before the single real run.
- **Implementation SHA-256 after the loader fix:** `0e92c3e41103c89c5958d3f58d40febf72c6ae03c25ae513230e6e2f3b1b4bdd`
- A load-only check (development data through 2023 only, no simulation) succeeded: crypto 1,187 daily / 170 weekly bars each; gold 771 complete days, with ATR available on 502 of them.

## 2026-11-06: second technical defect (random benchmark only; no outcome observed)

- Attempt 2 completed every development computation and wrote `frozen-2024-selection.json` (selected trial **9**),
  then crashed in the 2024 **random-entry benchmark**. A random entry after price had fallen below the latest confirmed
  swing low gave a stop above the decision price, and `ExitPlan` correctly refused it. No `results.json` exists, and no
  metric was printed or read.
- All 27 training cells and both development folds ran without hitting this case, so the fix cannot change any
  candidate result. The fix: such an entry is cancelled (`plan = None`), the same as the registered "fill at or below
  the stop is cancelled" rule. The random draw happens before the plan, so seeded sequences are unchanged.
- Regression test added (12 fixture tests pass). The rerun must reproduce the same frozen selection (trial 9); a
  mismatch would stop the batch.
- **Implementation SHA-256 after this fix:** `9ffac2e8d23f4948235f5934b13344126c43579b34567b0d2159cd3b8e40a57d`
