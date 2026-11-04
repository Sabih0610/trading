# Strict replay limits and gap-aware label inputs

P11j Wave 2 repairs two audit findings for future simulator calls and existing
label utilities. The default buy-limit replay now needs a strict trade-through.
Labels require a real opening price and account for a gap below the stop.
This does not start ML training, trading or any provider-enabled workflow.

## Default replay

Construct BacktestEngine with the usual symbol and funded initial_cash. A LIMIT
proposal can fill only on a later eligible bar whose low is strictly below its
limit. A touch remains unfilled until trade-through or normal expiry. MARKET
entries, conservative raw fill pricing, participation, risk/cash validation and
same-bar exit policy are unchanged.

The removed research_trade_through_limit constructor keyword raises TypeError.
Remove it from ordinary callers; do not replace it with another touch override.
GoldProxyBatch still holds its previously registered historical touch/strict
sensitivity internally after closed research preflight. It exports no engine or
runtime bars. Its historical results are immutable and must not be rerun.

## LabelBar migration

Every LabelBar needs timestamp, open, high, low and close. All prices must be
finite and positive; open and close must lie within low/high. Do not fill an
unknown open from the close, stop, previous price or another provider.

For a long candidate stopped on a completed later bar, realized_return is
min(bar.open, candidate.stop_price) / candidate.entry_price - 1. The existing
adverse same-bar ordering remains; a later target print cannot improve a gap loss.
Target/timeout treatment and right-censor omission are unchanged. These remain
gross price labels without a newly invented cost model.

## Owned verification

Run from a credential-free checkout, with no .env:

```powershell
uv sync --locked --offline
uv run --locked pytest -q './tests/unit/test_research_trade_through_limit.py' './tests/unit/test_audit_wave2_labels.py' './tests/unit/test_ml_labeling.py' './tests/unit/test_backtest_engine.py' './tests/review/full_audit/test_data_leakage.py::test_triple_barrier_gap_through_stop_is_not_filled_at_stop' './tests/review/full_audit/test_data_leakage.py::test_limit_touch_without_trade_through_is_not_filled' './tests/review/full_audit/test_data_leakage.py::test_triple_barrier_same_bar_is_adverse'
```

After the coordinated heavy gate slot is free, the complete required check is:

```powershell
pwsh -NoProfile -File './scripts/check-offline.ps1'
```

Do not run that full gate concurrently with another track's suite. No command in
this guide loads providers, genuine datasets, credentials or historical batches.
Missing open errors require a valid upstream owned/authorized input, not a default.
F/G Stage 3 verdicts preceded this repair and remain unchanged. C/D/E/G use MARKET
entries; D-4 affects only future labels. See the
[phase report](../../reports/phases/P11j-wave2.md),
[research note](../research/P11j-wave2-research.md) and
[ADR 0027](../adr/0027-strict-limits-and-gap-labels.md).
