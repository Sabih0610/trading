# P11k acquisition review: PAXG/USDT data-only archive

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/p11k-gold-2024` at `f34bc86` |
| Verdict | **APPROVED**, merged. The validation run stays **skipped**: G marked no candidate promising (MASTER Track K step 3). |

## Checks against [rights review 2026-11-04](dataset-rights-review-2026-11-04.md)

| Item | Result |
|---|---|
| Scope enforced in code | `VisionDatasetPlan` refuses any PAXGUSDT plan other than exactly `binance-vision-paxg-1m-2023-12-2024`, PAXGUSDT only, `1m`, 2023-12-01 → 2024-12-31 23:59 UTC. No other PAXG history can be admitted. |
| Download path | A research-only monthly 1m URL with `.CHECKSUM`, used only after plan admission. The executable archive builder and `assert_tradable` still refuse the instrument. |
| Config | `PAXGUSDT`: `role: data_only`, `venue: external_reference`, `local_simulation: false`, empty `allowed_strategies`, "never executable", no Shariah assessment. It is not tradable. |
| Data | 13 monthly archives (2023-12 → 2024-12), vendor and computed checksums matched; Bronze, Silver and Gold are private and ignored. Nothing is committed. |
| No peeking | The report states that no PAXG price rows, charts or strategy evaluation were inspected. G produced no promising candidate, so nothing will be run on it. |
| Holdout | Coverage ends before 2025-01-01; nothing from 2025 is requested. |

## Gates (`f34bc86`, clean worktree, run alone)

pytest **1,772 passed**, 2 skipped (S-5, PowerShell-7 installer test), 3 live deselected, 0 xfailed. Ruff clean, 619 files formatted, strict mypy clean on 214 sources. I independently confirmed the private Bronze holds exactly the 13 monthly archives 2023-12 → 2024-12.
