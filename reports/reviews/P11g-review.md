# P11g review: gold development test (XAUUSD 2021–2023 → XAUT proxy)

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/p11g-stage3-gold-dev` at `94b0b1c`, plus the private run `work/stage3/P11g/registered-gold-54-v1` in `E:\trading-p11e` |
| Verdict | **APPROVED**, merged. **No gold candidate is promising.** |

## 1. Integrity

| Check | Result |
|---|---|
| Registration | Byte-identical from the G-1/G-2 amendment `91dcac4` to the head. SHA-256 `806c2db7…`, matching the run identity and the frozen-parameters file. |
| Code freeze | No `src/`, `config/` or `scripts/` change after the published freeze `1a35463`. The implementation SHA is recorded (`db07f2f3…`). |
| Single batch | `status.json` shows `stage = complete`, 3 strategies, runtime about 37 min, peak RSS about 3.4 GB. |
| Rules | XAUUSD stays data-only and the proxy is labelled on every result; no 2024+ input; the RiskManager and XAUT override are unchanged; no orders; living docs untouched. |
| Public data | `P11g-verdicts.json` and `P11g-frozen-params.json` hold verdicts, aggregate metrics, quality-gate counts, circuit counts and the frozen config only. I scanned both: no prices, returns, equity or trades. |

## 2. Verdicts and independent checks

| Strategy | Verdict | Independent check |
|---|---|---|
| **G** `session_orb` | **Reject** in both orderings | 15m, entry window 60, buffer 0.05 ATR. 87 evaluation trades, PF 0.12, −0.48R per trade at base cost, falling to −0.72R at 2×. Linear extrapolation to zero cost gives about **−0.24R/trade, negative even before costs**. The 5% circuit latched in every evaluation fold. |
| **A** `london_sweep_mss_fvg` | Insufficient evidence | I replayed A's rules independently on the 2021 Gold 5m bars and found 21 setups that year, so the features (4,747 structure events and 7,892 gaps in 2022 alone) do reach the strategy. Most LIMIT orders at the FVG midpoint never fill, so A's training cells reached only **4–19 completed trades**, under the pre-registered 20 (the cell-to-strategy mapping is verified from the recorded parameters). The trades it did make averaged −0.62R to −0.72R. Too rare to judge; not a defect. |
| **C** `trend_vwap_pullback` | Insufficient evidence | No volume-backed VWAP exists in HistData. This was pre-registered; C never fired. |

**Main finding.** At XAUT's registry costs (about 0.38% per round trip) the cost is about the size of a typical intraday gold stop, so each trade starts near −1R. Intraday XAUT strategies need expected moves several times larger than that to survive.

**Track K consequence.** No strategy is promising, so the PAXG 2024 validation run is **skipped** (MASTER Track K step 3). PAXG acquisition may still complete as data only.

## 3. Gates (`94b0b1c`, clean worktree, run alone)

pytest **1,627 passed**, 1 skipped, 3 live deselected, 5 xfailed (this branch predates J1's xfail removals; the merged `main` state is re-tested by the merge commit's hook). Ruff clean, 556 files formatted, strict mypy clean on 205 sources.

## 4. Owner decision needed

Every pre-registered Stage 3 candidate (crypto C/D/E, gold A/C/G) has now failed or been untestable. Stage 4 and 5 do not start. Realistic next directions, for the owner to choose:
1. **Longer holding periods** (multi-day), so costs are small relative to the move. This requires an `AGENTS.md` change to the "flat by end of day" rule.
2. **New intraday hypotheses** whose expected move is at least 3–5× the round-trip cost, each pre-registered, with their trials added to the multiple-testing record.
3. **Pause strategy research**, keeping the data, monitoring and dashboard platform.
