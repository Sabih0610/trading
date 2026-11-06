# P11p pre-registration review (self-review)

| Field | Value |
|---|---|
| Date | 2026-11-06 |
| Reviewer | Claude, **also the builder**. The owner authorized this on 2026-11-06 while away, with Codex not running. |
| Scope | `claude/p11p-swing-stage3`: `reports/stage3/P11p-preregistration.md` (SHA-256 `ac690876…`) and the four new modules |
| Verdict | **APPROVED** for a single Part B run. |

## Independence caveat

Builder and reviewer are the same agent, so this review cannot be fully independent. Mitigations:
- The design follows the owner-approved prompt `prompts/P11p-swing-stage3.md` and the verified research note.
- The registration and code are committed and pushed **before** any genuine data is read, giving a timestamped record.
- The 2024 selection is frozen to disk before 2024 bars load.
- Codex or the owner can audit the commit against the prompt afterwards.

## Checklist against the prompt

| Prompt item | Status |
|---|---|
| Universe (BTC, ETH, SOL, gold proxy) and data sources | ✅ Exact datasets. Gold dev XAUUSD 2021–2023, validation PAXG 2024. Data-only kept. |
| Registry costs, registry meaning (G-2), 1.5× / 2× | ✅ `CostAssumptions.from_asset` halves the quoted spread per fill; gold uses XAUT costs. |
| Weekly trend filter fixed (20 weeks, rising over 4) | ✅ Not searched. |
| Three triggers, at most 9 configurations each, 27 trials | ✅ Breakout {20, 40, 55}, pullback {SMA20, SMA50, swing}, pattern {30, 40, 60} × k {1.5, 2, 3}. Test asserts 27. |
| Rotation by 12-week momentum, one position | ✅ Fixed tie order. |
| RiskManager sizing unchanged; cost filter ≥ 5×; calendar veto | ✅ / ✅ / ⚠ No historical calendar is wired in. The registration states only the cost filter and circuits, so the calendar veto is **not applied**. This is a deviation from the prompt and is disclosed. |
| Exits: stop, trailing, trend loss, 10-day cap | ✅ Uses P11m's `holding_deadline`. |
| Intrabar ordering from the 1m path | ✅ Not applicable: no intraday target, so no ambiguity (stated in the registration). |
| Walk-forward folds, 2024 once, purge/embargo ≥ 10 days, ≥ 20-trade selector | ✅ |
| Pass bar, including DSR N = 27 + 216 | ✅ `DSR_TRIALS = 243`, tested. |
| No profit target as a design input | ✅ None. |
| No 2025+ data; nothing genuine committed | ✅ Reader refuses ≥ 2025; only aggregates are public. |

## Deviation to note honestly

- **Calendar veto not applied.** It would require wiring the P03 macro calendar's `known_at` history into the
  daily loop. It is left out to keep the registration simple and to avoid an unreviewed data path. Its effect on results
  has no known sign. It is fixed now, before data, so it cannot be used to tune the outcome.

## Gates (Part A, branch head)

Focused: `tests/unit/test_swing_stage3.py` 11 passed. Ruff and format clean. Strict mypy clean (228 sources). The full suite
runs in the commit hook.
