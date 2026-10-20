# P14 — Demo month runbook and go/no-go criteria

Follow `prompts/_PROTOCOL.md`.

## Goal
Prepare and document the ≥30-day paper/demo run and the objective criteria for going live small.

## Build
1. `docs/runbook.md`: daily checks, what alerts mean, how to pause/kill, how to recover from
   crashes, how to rotate keys, backup procedure (ledger + configs to external drive/cloud nightly).
2. `reports/demo/` templates: daily summary, weekly review (trades, vetoes, arena scores, costs,
   AI spend vs budget, data health), final demo report.
3. Go/no-go checklist computed automatically where possible:
   - Paper results within the backtest's expected range (expectancy, win rate, drawdown).
   - ≥ planned number of setups observed; no unresolved blocker incidents.
   - Slippage/fees in paper ≤ cost-model assumptions.
   - Each AI/ML filter shows non-negative shadow value or is switched off.
   - AI spend ≤ budget; reconciliation incidents = 0 (Testnet).
4. Only after a human signs the go decision in the ledger may live mode be enabled, starting with a
   small capital cap configured by the human.

## Acceptance
Runbook reviewed by Claude; checklist script implemented and tested on simulated data; report written.
