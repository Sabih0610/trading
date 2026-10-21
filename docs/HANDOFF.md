# Current handoff

P07 is in progress under the owner's explicit direction to continue beyond the owner-deferred P06
Claude review. A Codex dependency audit found no P06 blocker but is not approval; later findings
must be recorded and fixed before affected results are relied upon.

- Last completed step: froze the P07 research decisions and sources for causal A/B/C plug-ins,
  scenario selection, lead-lag measurement, and robustness testing.
- Next step: implement the shared immutable feature-row strategy contract, then Strategy A with
  synthetic trigger/non-trigger and future-poisoning tests.
- Exact next command: `uv run pytest tests/unit/test_strategies.py -q` after the first plug-in slice.
- Data constraint: the verified sample is seven days, and authentic Binance XAUT history starts in
  the locked 2026 period. P07 can verify mechanics but must mark multi-year Strategy B evidence
  unavailable rather than trade XAUUSD or unlock 2025+ data.
- Review state: P06 independent Claude review is deferred by owner; see
  `reports/reviews/P06-codex-dependency-audit.md`.
- Safety state: strategies can only propose long entries; P06 risk remains final authority. No
  execution surface, credential access, final-period read, or data-only trading path is introduced.
