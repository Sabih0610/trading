# P11m: Multi-day holding in risk, engine and paper (owner rule change 2026-11-05)

Follow `prompts/_PROTOCOL.md` and the rules in `prompts/MASTER-2026-12.md`. Branch `codex/p11m-multi-day-holding`.
Authority: owner approval in chat (2026-11-05) and `AGENTS.md` §2 "Holding period", already on `main`.

## Change
1. `risk/config.py` and `config/risk.yaml`: replace the "flat_by_end_of_day must remain true" rule with
   - `max_holding_days`: an int, a **compiled hard ceiling of 10**, config default 10. A value above 10, below 1,
     or non-integer is refused.
   - `flat_by_end_of_day`: may now be `false` globally. A strategy can still require it per proposal
     (existing intraday strategies keep their EOD behaviour unchanged).
   - Every other limit is unchanged: 0.5% / 2% / 5%, 1× exposure, one position, 3 trades/day/asset, the
     ceilings 1% / 3%, and no XAUT weekend entries.
2. `backtest/engine.py`, `paper/simulation.py`, `paper/offline/engine.py`:
   - When EOD flattening is not required, keep positions across UTC midnight.
   - Close any position at the first bar at or after `entry_time + max_holding_days` (timestamp-based, not bar-count based).
   - Mark positions to market daily for the 2% daily-loss and 5% drawdown circuits. A gap through the stop still
     exits at the adverse open.
   - Daily-loss accounting per UTC day must include overnight mark-to-market moves.
3. The dashboard shows `max_holding_days` and EOD mode.

## Tests (replace, never just delete)
- `tests/unit/test_risk_config.py` and `tests/review/full_audit/test_risk_rules.py` assert the **old** rule
  (`flat_by_end_of_day` must be true). This is an owner rule change, so replace them with equally strict
  tests of the new rule:
  - `max_holding_days` of 11, 0 or a fractional value is refused;
  - a position is force-closed at 10 days;
  - an intraday strategy that requires EOD is still flattened;
  - an overnight loss counts against the next UTC day's 2% limit;
  - the drawdown circuit fires on an overnight gap;
  - every other ceiling is unchanged.
  Record in the journal: "test changed because the owner changed the rule (AGENTS.md 2026-11-05)".
- Reproducibility: P11f and P11g registered replays still produce identical results (they request EOD).

## Done
Gates green; ADR "multi-day holding"; how-to updated; phase report `reports/phases/P11m.md`. No order code,
no change to any other risk number.
