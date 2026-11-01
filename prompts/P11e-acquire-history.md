# P11e — Acquire approved history (BTC/ETH/SOL + gold/FX) through the medallion

Follow `prompts/_PROTOCOL.md`. Start from current `main`; branch `codex/p11e-acquire-history`;
work in a credential-free checkout. Authority: owner approval in chat (2026-11-01) and
[dataset rights review](../reports/reviews/dataset-rights-review-2026-11-01.md) (reviewer: Claude,
distinct from owner). Scopes, permissions, conditions and retention in that review are binding.

## Goal
Real pre-2025 1-minute history for **BTCUSDT, ETHUSDT, SOLUSDT** (Binance Vision) and **XAUUSD,
EURUSD** (Dukascopy under the owner's written permission; HistData as backup) in Bronze → Silver → Gold, yearly-compacted, quality-scored and visible in Data
Health — ready for Stage 3 backtests. **No strategy evaluation in this phase.**

## Hard rules
- Nothing from 2025-01-01 UTC onward is requested, read or stored. Sealed XAUT capture untouched.
- No genuine data, derived prices or quality artifacts committed to git (the repo is public).
  Commit only code, tests, docs, and metadata templates without real values.
- Never weaken tests or risk rules; never read `.env`.
- Dukascopy: download **only** with the owner's written-permission file registered (Part B). Its
  Terms of Use §3 prohibit automated access and database storage without written consent.

## Part A — Binance Vision acquisition (existing P11d path)
1. Save the Vision terms PDF (<https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf>) under
   `work/rights/binance-vision-terms-v1.0-2026-08-26.pdf`; compute SHA-256.
2. Write `work/research/proposals/binance-vision-spot-1m-2020-2024.json` (`VisionDatasetPlan`):
   - `dataset_id`: `binance-vision-spot-1m-2020-2024`; instruments BTCUSDT, ETHUSDT, SOLUSDT; interval `1m`
   - coverage 2020-10-01T00:00Z → 2024-12-31T23:59Z
   - `rights.owner_approved: true`, `owner_approved_by: "Sabih0610"`,
     `reviewer: "Claude (AI reviewer)"`, `reviewed_at: 2026-11-01`
   - permissions `retrieval`, storage uses, `private_display`, `ml_training`, each with
     `evidence_kind: provider_terms`, the artifact path and its SHA-256
   - retention deadline 2028-11-01
   - `derived_report_rules` exactly as the model requires
3. Run `scripts/medallion.ps1 register …`, `download binance-vision-spot-1m-2020-2024`, `build …`.
   Long downloads in the background with resume; disk preflight.
4. Confirm per symbol-year: checksums verified, quality JSON written, Silver/Gold one file per
   symbol(×timeframe)/year, Data Health shows them. SOL starts at its first available month ≥ 2020-10.

## Part B — Gold and FX: Dukascopy first, HistData as backup

### B0. Try Dukascopy first (owner has written permission — rights review §2a)
1. Look for the owner's permission file `work/rights/dukascopy-consent.*`. Do not open it beyond
   computing its SHA-256 and checking it is non-empty. If it is **missing**, record
   "Dukascopy consent file not found" in the phase report and go straight to B1 (HistData).
2. If present: register `dukascopy-xauusd-eurusd-m1-2020-2024` in the registry with
   `owner_approved_by: "Sabih0610"`, `reviewer: "Claude (AI reviewer)"`,
   `evidence_kind: provider_confirmation`, the artifact path and SHA-256, retention 2028-11-01.
   Extend the plan model/registry if needed, with the same owner + distinct reviewer checks.
3. Gate the existing Dukascopy downloader on that registered consent (refuse without it; test it).
4. **Probe**: download one XAUUSD and one EURUSD day (BID and ASK M1) from 2024. Success means
   valid decoded candles with plausible prices. Then run the full 2020-10 → 2024-12 range for both
   symbols, sequentially and rate-limited, with resume.
5. **Failure rule:** if the probe or bulk download fails technically (HTTP 403/429, connection
   refused/blocked, empty or undecodable files for most requested hours, or the endpoint is gone),
   stop Dukascopy after a bounded number of retries with back-off — do not hammer — and record
   for the owner: endpoint, UTC time, HTTP status/error class, how many requests succeeded/failed,
   and a short sample of the error message (no data). Write it to
   `reports/phases/P11e-dukascopy-failure.md` so the owner can report it to Dukascopy. Keep
   whatever completed successfully. Then continue with B1 for anything Dukascopy did not deliver.
6. Dukascopy Silver: UTC timestamps, BID and ASK columns kept, mid and spread derived, same quality
   checks and yearly layout as Binance; weekend close and daily rollover gaps flagged, not errors.

### B1. Backup: HistData (new adapter) — only for what Dukascopy did not deliver
1. Research note: confirm the HistData Generic ASCII M1 download flow, file naming, and that no
   terms page has appeared since 2026-11-01; save dated copies of the homepage and FAQ under
   `work/rights/` with SHA-256.
2. Add a HistData adapter behind the existing ingest interface, plus a `HistDataDatasetPlan`
   (or a generalized plan model) in the same registry with the same owner + distinct reviewer
   checks, `evidence_kind: provider_terms` (dated terms-absence evidence), retention 2028-11-01.
   Dataset ID `histdata-xauusd-eurusd-m1-2020-2024`; XAUUSD and EURUSD; 2020-10 → 2024-12.
3. Bronze: original zip/CSV bytes + manifest (URL, SHA-256, download time, evidence pointer).
   Polite sequential downloads with resume; no parallel requests.
4. Silver: **timestamps are fixed EST without DST — convert with a constant +5 h
   (`Etc/GMT+5`), never `America/New_York`**; prices are **bid-only** — store a `price_side: bid`
   column/manifest field; volume is not meaningful (store, flag as zero/unreliable). Same quality
   checks as Binance, with the expected grid excluding the weekend close (Fri ~17:00 NY →
   Sun ~17:00 NY, expressed in fixed UTC−5) and daily rollover gaps flagged, not treated as errors.
5. Gold: same yearly layout and shared causal FeatureEngine; resamples 5m/15m/1h/4h.
6. Cost model note for Stage 3: Dukascopy bars carry real BID/ASK spread; HistData bid-only bars
   need an added spread for long entries — expose the configured XAUUSD/EURUSD spread defaults as
   the floor; do not infer spread from bid bars. Record per symbol-year which source was used.
7. Tests (fixtures only): fixed-offset conversion across March/November DST dates (no shift),
   weekend gap not counted as missing, bid-side marking, resume after partial download, terms
   evidence missing → registry refusal, nothing ≥ 2025 accepted.

## Part C — Dukascopy compliance
- The Dukascopy downloader refuses to run unless a `provider_confirmation` evidence artifact
  (Dukascopy's written consent) is registered; clear refusal message pointing to the rights review.
- Keep the existing 7-day sample; it may be re-acquired under the consented dataset, otherwise mark
  it "not for evaluation".
- Never mix sources silently: each Silver/Gold file records its source (`dukascopy` or `histdata`)
  and price side (`bid_ask` or `bid`).

## Scenarios to self-test
Interrupted download → resume · checksum mismatch → refused · missing month → recorded gap ·
HistData DST boundary → no hour shift · weekend/rollover gaps → flagged not errors · 2024-12-31
23:59 boundary · approval/evidence missing → BLOCKED · Dukascopy without consent → refused · Dukascopy 403/429/
blocked → bounded back-off, failure report written, HistData fallback ·
compacted vs uncompacted → identical Gold hashes · Data Health with all five instruments.

## Acceptance
- Five instruments in Bronze/Silver/Gold for 2020-10 → 2024-12 (or a precise per-file reason for
  any gap), quality scores visible in Data Health; nothing ≥ 2025; nothing genuine committed.
- Full suite, ruff, format, strict mypy green in a clean checkout.
- Phase report `reports/phases/P11e.md` with a per symbol-year quality table, ADR for the HistData
  adapter, living docs updated. Push the branch (`[skip ci]`, `--no-follow-tags`), open a PR, do not
  merge `main`.
