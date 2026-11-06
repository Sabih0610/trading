# MASTER 2026-12: final status (swing plan)

Completed 2026-11-06. Built and reviewed by Codex (M, N, O) and Claude (review and merge of M, N and O; build,
self-review and run of P while the owner was away, under the owner's 2026-11-06 authorization).

## Tracks

| Track | Result | Merge |
|---|---|---|
| **M**: multi-day holding (≤ 10-day compiled ceiling) | APPROVED. Old flat-EOD tests replaced by stricter ones; EOD oracle equal. | `1544af3` |
| **N**: causal daily/weekly bars plus same-day intrabar accessor | APPROVED. 1,795 passed. | `37e94da` |
| **O**: one-sided chart-signal library plus 5× cost rule | APPROVED. 1,833 passed. | `301ed5e` |
| **P**: swing rotation Stage 3b (27 trials; DSR N = 243) | **Insufficient evidence** (registered selector: 0/27 cells reached 20 training trades in either fold; maxima 13/15) | `4ca4635` |

## Swing verdict and frequency

- Registered verdict: **insufficient evidence**, so the strategy cannot pass. Nothing was re-tuned.
- Informational frozen 2024 cell (trial 9, pullback to SMA20, k 1.5):
  - 21 trades (**1.75 a month**), +0.13 R, PF 1.93, max DD 0.65%;
  - beat random entry;
  - lost to BTC buy-and-hold on return/DD.
- Design target was 5–15 trades a month. Achieved: about 1–2. **Low frequency is the decisive flaw.**

## Cumulative Stage 3 record

| Family | Trials | Outcome |
|---|---|---|
| Intraday crypto (P11f) | 162 | 0 pass |
| Intraday gold (P11g) | 54 | 0 promising |
| Swing rotation (P11p) | 27 | insufficient evidence |
| **Total counted for future DSR** | **243** | |

## Process notes

- P needed three starts. The first two crashed (a null-price loader bug; a random-benchmark stop above entry) before any
  outcome was seen. Each fix was journaled, committed with the full suite and pushed first. The frozen 2024 selection
  reproduced exactly.
- The owner removed about 28 leftover worktrees and duplicate virtual environments (about 25–30 GB) with
  `work/cleanup-e-drive.ps1`. The XAUT recorder had a 27-hour outage (2026-11-03/05). It was restarted, and it is now
  guarded every 30 minutes while a Claude session is open.

## Owner decisions needed

1. **Research direction:**
   - a new, higher-frequency swing registration (e.g. 3× cost rule, one position per asset, shorter trend filter; new trials added to the DSR);
   - a low-frequency system judged over a longer history;
   - or pause and keep the platform.
2. Paper trading, Testnet and orders: not authorized; nothing passed.
3. Operator items still open: `.env` ACL, collector boot recovery as admin, P14 rights/release, and the leftover
   `E:\trading-p11n\.venv` (~0.9 GB, now safe to delete).
