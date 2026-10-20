# P13 — Automated learning loop (retraining, champion/challenger, drift)

Follow `prompts/_PROTOCOL.md`.

## Goal
Scheduled jobs that label new outcomes, retrain models, compare challengers to champions on unseen
data, detect drift, and propose promotions for human approval.

## Research first
MLOps for small local systems: retraining cadence, minimum-sample rules, champion/challenger and
shadow deployment, drift detection (PSI, ADWIN, Page-Hinkley), contextual bandits (Thompson
sampling) for choosing among strategy variants per regime, loss-reason tagging.

## Build
1. Jobs (`src/tb/jobs/` + `scripts/schedule-jobs.ps1` for Task Scheduler): nightly labeling and
   silver/gold refresh; weekly retrain; weekly arena scoring; monthly summary report.
2. Loss tagging: bad setup / bad timing (news) / execution / normal loss, with evidence fields.
3. Champion/challenger: challenger runs in shadow ≥ N setups; promotion requires beating the
   champion after costs on unseen data AND a human approval row in the ledger.
4. Drift monitors on features and on calibration; alerts on the dashboard.
5. Optional contextual bandit selecting among approved strategy variants, exploration capped and
   risk-manager limits unchanged.
6. Rule: automation never edits risk.yaml or assets.yaml.

## Scenarios to self-test
Too few new samples (skip retrain) · drift alarm · challenger better on train but worse on
validation (not promoted) · job crash mid-run (idempotent rerun).

## Acceptance
A simulated 8-week replay on historical data shows the loop working end-to-end; report written.
