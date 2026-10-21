# Current handoff

P07 is complete and tagged. P08 is in progress, beginning with leakage-safe labels, interval-aware
purging/embargo, and deterministic score-to-size reduction. Its empirical value-add comparison is
blocked on the same missing 2020-2024 XAUT candidate history and will not be fabricated.

- Last completed step: researched current P08 validation/model/tracking constraints and recorded
  decision D-0022.
- Next step: implement triple-barrier setup labeling and purged/embargo folds with a leakage-canary
  test.
- Exact next command after that slice: `uv run pytest tests/unit/test_ml_validation.py -q`.
- P07 data blocker: all A/B/C verdicts remain REWORK / NOT EVALUABLE with zero empirical trials;
  see `reports/strategies/P07.md` and `docs/pending.md`.
- Review state: P06 independent Claude review is deferred by owner; P07 is queued. Neither is
  represented as approved.
- Safety state: strategies only propose approved long entries; deterministic risk retains final
  authority. No credential, execution, data-only trading, or final-period access path was added.
