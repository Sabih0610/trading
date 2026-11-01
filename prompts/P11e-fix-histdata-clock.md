# P11e fix round: HistData clock, Dukascopy retry, PR #4 review findings

Follow `prompts/_PROTOCOL.md`. Continue on branch `codex/p11e-acquire-history` (PR #4) in the
`E:\trading-p11e` checkout and rebase onto current `main` first. Read
[P11e review](../reports/reviews/P11e-review.md). All P11e hard rules still apply: nothing ≥ 2025-01-01 UTC,
nothing genuine committed, no strategy evaluation, sealed XAUT untouched, never read `.env`.

## 1. P11e-1 (major): HistData timestamps follow EU daylight saving time
Real 2021–2023 files contradict the "fixed EST" claim:
- Weekly opens are stamped 17:00 (EURUSD) / 18:00 (XAUUSD) almost all year, and one hour earlier
  only in US/EU DST-mismatch weeks (e.g. 2022-03-13, 2022-03-20, 2022-10-30).
- On each EU fall-back Sunday (2021-10-31, 2022-10-30, 2023-10-29) the stamps 19:00–19:59 appear
  twice in a row. **Correction (verified on raw bytes):** the second copy is an exact duplicate,
  with 60/60 identical OHLC bars. Both copies continue from 18:59 and into 20:00. It is a provider
  duplicate, not a second real hour.

Required:
1. Convert per trading week: **+4 h** when the week's Sunday open falls while `Europe/London` is on
   summer time (BST), **+5 h** otherwise. One offset covers the whole week, fall-back Sunday
   included: the EU has already fallen back by Sunday, so 2022-10-30 is all +5 h, and the 16:00
   EURUSD open lands at 21:00 UTC, which is correct for US EDT.
   The repeated hour: keep the first copy, and drop the second only if every OHLCV field is
   byte-identical to the first. Record it as `provider_duplicate_hour`. If any bar differs,
   quarantine that day and flag it. Never give part of a week a different offset. Stop and ask only if
   real data contradicts this rule (e.g. a non-identical repeat).
2. Build the expected weekend and rollover grid in Silver from the same rule.
3. Add a quality check: every week's first bar must land at the expected UTC open (EURUSD
   21:00/22:00 UTC, XAUUSD 22:00/23:00 UTC for US summer/winter), or the week is flagged with its
   offset. Weeks whose open is late because data is missing (common in 2023) are flagged, not shifted.
4. Fixture tests shaped like the real pattern: a mismatch week, the fall-back identical repeat (60 duplicate
   bars dropped and recorded, strictly increasing UTC; a non-identical repeat quarantines the day), a normal summer week (+4 h) and a winter week (+5 h), and the 2024-12-31
   holdout boundary unchanged. Replace the "constant +5 h across March/November" contract test.
   This is a correction of a wrong specification, not a weakened test; say so in the journal.
5. Update ADR 0021, the FX runbook, the data dictionary and `prompts/P11e-acquire-history.md` B1.4.
6. Rebuild private XAUUSD/EURUSD Silver/Gold for 2021–2023 from the existing Bronze bytes (no
   re-download). Report old versus new duplicates_removed and the week-open check results in the
   private quality table. Commit only the code, tests and docs.

## 2. Dukascopy (P11e-2): rerun B0 if the consent file is now present
If the owner has saved `work/rights/dukascopy-consent.*` (copy it from `E:\trading bot\work\rights\`),
run B0 exactly as specified: register, probe one 2024 day per symbol, then the bulk download
2020-10 → 2024-12, with the failure rule and the HistData fallback. Dukascopy becomes the
primary gold/FX source and HistData a cross-check. When both exist for a year, add a private
cross-check (UTC alignment of hourly closes; median bid difference). If the file is still absent,
say so and skip this part.

## 3. Minor
- P11e-4: replace the `client._transport` inspection in `_require_owned_dukascopy_fixture` with an
  explicit injected marker. It must still fail closed.
- P11e-5: honour `Retry-After` on 429 (capped at 60 s, still at most 3 attempts), or stop at the
  first 429. Test both paths.
- P11e-3 is **not** for this round. Do not change `config/assets.yaml` spreads; leave the
  owner-review flag in place.

## Acceptance
Full suite, ruff, format and strict mypy green in a clean checkout. Private quality table updated.
`reports/phases/P11e.md` gets a "Fix round" section. Push to the same branch (`[skip ci]`,
`--no-follow-tags`) and do not merge `main`.
