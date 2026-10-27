# Build progress

Current P11c.0: broker-independent registry/import/evaluation/replay/dashboard and
dry-run retention inventory implemented on local branch `codex/p11c-0-research-mvp`
from repaired `978aad2`. Final **1,084 tests pass / 3 live deselected**, all quality
gates, smoke and 14 unchanged paper states pass; 92 new research cases and all 55
remediation regressions pass. See the [phase report](reports/phases/P11c.0.md).
[Windows guide](docs/how-to/local-market-research.md). Genuine historical evaluation
is BLOCKED — DATASET NOT AUTHORIZED. No push/main merge/CI/provider/OAuth/orders;
stop for review. The following checkpoints are historical.

Current: F-01–F-06 remediation implemented in a separate credential-free checkout;
complete offline gates pass: 992 tests/3 live deselected and 14 owned studies. No integration, push or hosted CI authorization.
[Report](reports/phases/P11b-RC-remediation.md) · [Research operations](docs/how-to/broker-independent-research.md) · [Codex plan](docs/specifications/P11b-broker-independent-research-plan.md).

Historical checkpoints follow; their earlier publication authorization does not apply to this task.

P11b.1a-RC offline review complete; owner authorized committing/publishing on 2026-10-27.
Shared development branch: `codex/shared-research`; original candidate **b669d43** and local tags
remain preserved. RC review docs are included in publication; application source is unchanged.
937 tests passed/3 live deselected at the RC review; full fake OAuth, all gates, smoke,
14 matching paper scenarios and dashboard reconciliation pass. Original credentials/work preserved.
[RC report](reports/phases/P11b.1a-RC.md) · [Owner checklist](docs/how-to/release-candidate-owner-checklist.md).
Exact portal callback acceptance remains unverified; genuine P11b.1a/P11b.2b NO-GO. Hosted CI inactive.

Previous preparation checkpoint:

P11b.1a-Prep is complete offline on `codex/p11b-1a-prep`, tag `phase-P11b.1a-prep-done`.
937 tests pass / 3 live deselected; locked gates, paper smoke, 14 owned paper cases and fake local
OAuth rehearsal pass. Root credentials/worktrees preserved; no genuine auth, token exchange or quote.
[Prep report](reports/phases/P11b.1a-prep.md) · [Owner guide](docs/how-to/ctrader-oauth-after-approval.md).
P11b.1a genuine is unfinished/pending owner approval and consent; P11b.2b NO-GO/unstarted.
Hosted CI remains inactive. Stop for independent review.

Previous validation milestone:

P11b.2a.1 is complete offline on `codex/p11b-2a-1-validation`, tag `phase-P11b.2a.1-done`.
853 tests pass, 3 optional live tests deselected; all locked quality/safety gates and 14 owned
studies pass. Four defects fixed; independent Decimal/recovery tests added. Original evidence and
OAuth checkout preserved. A1 Windows CI implemented locally, hosted activation gated/unverified.
[Validation report](reports/phases/P11b.2a.1.md) · [Windows guide](docs/how-to/windows-offline-validation.md).
Independent review queued; P11b.2b remains NO-GO/unstarted.

Previous completed baseline:

P11b.2a is complete offline on `codex/p11b-2a-offline-paper`, from cc5a4ea / phase-P11b.1-done.
826 tests pass; Ruff, 394-file formatting, strict MyPy (158 sources) and existing safety smoke pass.
Fourteen owned studies replay 3,811 inputs with identical snapshot bytes; no $100 entries, no external orders.
The $10,000 engineering accounts demonstrate gains/losses, gaps, expiration and persistent shutdowns.
P11b.1a and its credentials/uncommitted work remain in the original preserved checkout; owner reports app approval pending.
Genuine cTrader/MT5/OANDA qualification and Twelve Data sustained rights remain unresolved. **P11b.2b is unstarted/NO-GO.**
[Report](reports/phases/P11b.2a.md) · [Operator guide](docs/how-to/offline-paper-lab.md).
A1 is now implemented locally in P11b.2a.1 with hosted activation gated; A2 remains proposed. Independent phase review is queued.

| Phase | Title | Status | Started (UTC) | Completed (UTC) | Commit | Report | Review |
|---|---|---|---|---|---|---|---|
| P00 | Bootstrap | done | 2026-10-20 22:29 | 2026-10-20 22:45 | `phase-P00-done` | [report](reports/phases/P00.md) | queued |
| P01 | Asset registry, Shariah gate, risk config | done | 2026-10-20 22:45 | 2026-10-20 22:52 | `phase-P01-done` | [report](reports/phases/P01.md) | queued |
| P02 | Historical market data | done | 2026-10-20 22:54 | 2026-10-21 01:02 | `phase-P02-done` | [report](reports/phases/P02.md) | queued |
| P03 | Calendar and news | done | 2026-10-21 01:03 | 2026-10-21 01:20 | `phase-P03-done` | [report](reports/phases/P03.md) | queued |
| P04 | Silver cleaning | done | 2026-10-21 01:22 | 2026-10-21 01:38 | `phase-P04-done` | [report](reports/phases/P04.md) | queued |
| P05 | Feature engine | done | 2026-10-21 01:39 | 2026-10-21 01:55 | `phase-P05-done` | [report](reports/phases/P05.md) | queued |
| P06 | Backtester and risk manager | done | 2026-10-21 01:56 | 2026-10-21 12:30 | `phase-P06-done` | [report](reports/phases/P06.md) | deferred by owner; audit has no blocker |
| P07 | Strategies and scenarios | done | 2026-10-21 20:46 | 2026-10-21 21:00 | `phase-P07-done` | [report](reports/phases/P07.md) | queued; empirical data blocked |
| P08 | ML models | done | 2026-10-21 21:02 | 2026-10-21 21:38 | `phase-P08-done` | [report](reports/phases/P08.md) | queued; empirical data blocked |
| P09 | Decision ledger and AI arena | done | 2026-10-21 21:39 | 2026-10-21 23:19 | `phase-P09-done` | [report](reports/phases/P09.md) | deferred by owner; audit has no blocker |
| P09.5 | Architecture alignment and safety hardening | done | 2026-10-22 17:36 | 2026-10-22 18:01 | `phase-P09.5-done` | [report](reports/phases/P09.5.md) | queued; empirical value unproven |
| P10 | Read-only evidence dashboard | done | 2026-10-22 18:36 | 2026-10-22 19:10 | `phase-P10-done` | [report](reports/phases/P10.md) | queued |
| P11a | Read-only MT5 feed and forward evidence | done | 2026-10-23 00:55 | 2026-10-23 01:36 | `phase-P11a-done` | [report](reports/phases/P11a.md) | queued; genuine quotes refused |
| P11a.1 | MT5 recovery and qualification | done; NOT data-qualified | 2026-10-23 11:39 | 2026-10-23 12:10 | `phase-P11a.1-done` | [report](reports/phases/P11a.1.md) | queued; P11b NO-GO |
| P11a.2 | Source-clock profiles and alternative feed qualification | done; NOT data-qualified | 2026-10-23 16:36 | 2026-10-23 17:06 | `phase-P11a.2-done` | [report](reports/phases/P11a.2.md) | queued; per-instrument NO-GO |
| P11a.3 | Twelve Data Basic reference feed | done; bounded M1 qualified for EUR/USD and XAU/USD | 2026-10-23 18:00 | 2026-10-23 18:29 | `phase-P11a.3-done` | [report](reports/phases/P11a.3.md) | queued; no executable quotes or P11b |
| P11b.0 | Reference shadow research engine | done offline; genuine rights blocked | 2026-10-23 18:56 | 2026-10-23 19:43 | `phase-P11b.0-done` | [report](reports/phases/P11b.0.md) | queued; no fills or orders |
| P11b.0.1 | Gold and forex price-only shadow strategies | done offline; genuine rights blocked | 2026-10-24 01:37 | 2026-10-24 02:07 | `phase-P11b.0.1-done` | [report](reports/phases/P11b.0.1.md) | queued; no orders/fills |
| P11b.1 | Read-only broker quote and contract readiness | done offline; genuine unverified | 2026-10-25 00:28 | 2026-10-25 01:11 | `phase-P11b.1-done` | [report](reports/phases/P11b.1.md) | queued; P11b.2 NO-GO |
| P11b.2a | Offline paper trading, risk validation and recovery | done; owned software tests only | 2026-10-27 | 2026-10-27 01:35 | `phase-P11b.2a-done` | [report](reports/phases/P11b.2a.md) | queued; genuine P11b.2b NO-GO |
| P11b.2a.1 | Independent paper-engine validation and gated Windows CI | done; offline only | 2026-10-27 | 2026-10-27 06:42 UTC | `phase-P11b.2a.1-done` | [report](reports/phases/P11b.2a.1.md) | queued; hosted inactive, P11b.2b NO-GO |
| P11b.1a-Prep | Secure owner-assisted OAuth readiness | done; offline only | 2026-10-27 | 2026-10-27 10:11 UTC | `phase-P11b.1a-prep-done` | [report](reports/phases/P11b.1a-prep.md) | queued; genuine authorization pending |
| P11b.1a-RC | Integrated offline release review | review complete; documentation publication authorized | 2026-10-27 | 2026-10-27 10:59 UTC | `b669d43` local source candidate; cleaned publication history | [report](reports/phases/P11b.1a-RC.md) | queued; genuine NO-GO |
| P12 | Separately reviewed demo-only gateways; optional stock paper | not started | — | — | — | — | human gate; external orders disabled |
| P13 | Controlled offline learning and AI value evaluation | not started | — | — | — | — | — |
| P14 | 30+ day forward paper/demo evaluation | not started | — | — | — | — | — |
