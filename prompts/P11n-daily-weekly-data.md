# P11n: Daily and weekly bars, with intrabar paths, through the medallion

Follow `prompts/_PROTOCOL.md` and the rules in `prompts/MASTER-2026-12.md`. Branch `codex/p11n-daily-weekly`.
Use the existing approved private datasets only; **no new downloads, nothing from 2025**:
- `binance-vision-spot-1m-2020-2024` (BTC, ETH, SOL);
- `histdata-xauusd-eurusd-m1-2020-2024` (XAUUSD 2021–2023, the XAUT development proxy);
- `binance-vision-paxg-1m-2023-12-2024` (PAXG, the 2024 gold validation proxy).

## Build
1. Gold timeframes **1d** (UTC day) and **1w** (Monday 00:00 UTC). Each bar records the count of observed versus
   expected source minutes:
   - crypto is 24/7;
   - XAUUSD follows its session clock (weekends and rollover excluded);
   - PAXG is 24/7.
   A bar is `complete` only if it meets a pre-set coverage threshold (≥ 95% of expected minutes); incomplete
   bars are kept and flagged, never filled.
2. Shared causal features on 1d/1w: SMA/EMA 20/50/100/200, slopes, ATR14, Donchian highs/lows 20/55,
   realized volatility 20, swing highs/lows (confirmed only after N later bars, so causal). Reuse the FeatureEngine.
3. **Intrabar path access:** for any daily bar, a private read-only accessor returns that day's 1m (or 1h)
   path, so the engine can decide whether stop or target was hit first, **using only that day's own minutes**.
   It is used only for fill ordering inside the engine and never as a signal input.
4. Data Health: 1d/1w coverage per symbol-year.

## Tests
No-lookahead property tests (future minutes cannot change a completed daily bar or its features);
week boundary; XAUUSD weekend and holiday days not counted missing; PAXG/XAUUSD source labels kept;
any 2025 minute refused; the intrabar accessor refuses other days.

## Done
Gates green; how-to; phase report `reports/phases/P11n.md`. Nothing genuine committed.
