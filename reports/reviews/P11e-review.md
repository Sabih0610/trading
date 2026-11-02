# P11e review: approved history through the medallion

| Field | Value |
|---|---|
| Date | 2026-11-01 |
| Reviewer | Claude (reviewer role per `CLAUDE.md`, template `prompts/REVIEW_CLAUDE.md`) |
| Scope | [PR #4](https://github.com/Sabih0610/trading/pull/4), `origin/main` `5a0787a` → `c104464` (9 commits, 32 files, +2,960 / −48), plus the private outputs in `E:\trading-p11e` (quality metadata and raw Bronze CSVs, all pre-2025) |
| Verdict | **APPROVED** after fix round (`caaa9a5`, §7). Initial verdict: changes required (P11e-1). |

## 1. Rules audit

| Check | Result |
|---|---|
| Spot-only / long-only / no orders | Unchanged. No order code. XAUUSD/EURUSD remain `role: data_only`, "never executable". |
| Holdout (no 2025+) | Enforced in three places: `ForexDatasetPlan.coverage_end < HOLDOUT`, `validate_period` refuses whole archives that cross 2025 **before** any HTTP request, and `decode_histdata` refuses any row ≥ 2025. Choosing to withhold HistData's 2024 annual file (its last 5 hours fall in UTC 2025) instead of downloading it is correct. |
| Rights registry | `ForexDatasetPlan` reuses `authorize()`: owner plus a distinct reviewer, documentary evidence, finite retention. Dukascopy requires `provider_confirmation` evidence at `work/rights/dukascopy-consent.*`, and the consent text is hashed but never read (as instructed). HistData requires two terms-absence snapshots. |
| Dukascopy gate | Legacy `download_dukascopy_day`/`tick_hour` now refuse unless the client is an `httpx.MockTransport` under `TB_OFFLINE_VALIDATION=1`, so genuine network use is impossible without the registered plan. The consent file was absent, so Dukascopy was never contacted. This is correct. |
| Polite access | At most 3 sequential attempts, 1/2/4 s back-off, no redirects, 30 s timeout, response size cap, failure diagnostics contain no prices. |
| Nothing genuine committed | The diff adds only `.py`/`.md`/`.json`/`.ps1`; `reports/validation/P11e/summary.json` holds gate results only; the quality table template is blank. I scanned the added docs for prices and scores: none found. |
| Sealed XAUT | Untouched. |
| Tests / risk | No assertion bodies weakened; the 3-symbol dashboard assertion is kept alongside a new 5-symbol one. No risk defaults changed. |

## 2. Data verification (private outputs, read locally, not committed)

| Instrument | Years built | Quality |
|---|---|---|
| BTCUSDT / ETHUSDT / SOLUSDT | 2020 Q4 → 2024, all complete | 99.1–99.999; zero duplicates or revisions. **Ready for Stage 3.** |
| XAUUSD / EURUSD | 2021, 2022, 2023 only | 2021–22: 97.9–99.8. **2023: 85.9 / 86.7**, with about 28% of minutes missing from February to July in both symbols (a HistData source gap). 2020 Q4 and **2024 are missing**, so gold has no validation year. |

## 3. Findings

| ID | Severity | File:line | Description | Fix |
|---|---|---|---|---|
| P11e-1 | **major** | `src/tb/ingest/history/forex.py` `decode_histdata` (constant `+timedelta(hours=5)`), `src/tb/silver/forex.py` (weekend/rollover grid in fixed UTC−5); my research finding 11 and rights review §3 | **HistData timestamps are not fixed EST.** Raw 2021–2023 files show the weekly open stamped at 17:00 (EURUSD) / 18:00 (XAUUSD) all year, and one hour earlier only in the weeks when the US and EU are on different daylight-saving time (2022: 13 and 20 March and 30 October; the same pattern in 2021 and 2023). That is a clock of **UTC−4 while Europe is on summer time and UTC−5 otherwise**. On each EU fall-back Sunday (2021-10-31, 2022-10-30, 2023-10-29) the 19:00–19:59 stamps appear twice in a row. *Correction after Codex's question:* the second copy is a byte-identical provider duplicate (60/60 identical OHLC), so removing it was right. The constant +5 h therefore labels about 7 months of each year **1 hour late** in UTC. It also puts the weekend/rollover expected grid an hour off in summer, and misaligns XAUUSD against the UTC crypto and XAUT series and the session features. Labels run late rather than early, so this is stale data rather than lookahead, but session and cross-asset research on these bars would be wrong. The provider's FAQ claims "EST without DST"; the data contradicts it. My research note repeated that claim and is corrected below. | Convert with an offset chosen per trading week: +4 h for weeks whose Sunday open falls inside EU summer time (`Europe/London` on BST), +5 h otherwise. Use one offset for the whole week; fall-back Sunday is +5 h. Drop the repeated hour only when it is byte-identical, recorded as `provider_duplicate_hour`; otherwise quarantine the day. Build the expected weekend/rollover grid from the same rule. Add real-pattern fixture tests covering a mismatch week, the fall-back Sunday repeat, and a week open landing at 21:00/22:00 UTC (EURUSD) and 22:00/23:00 UTC (XAUUSD). Add a quality check that flags any week whose open is not at the expected UTC instant. Rebuild Silver/Gold for XAUUSD/EURUSD 2021–2023. |
| P11e-2 | major (data, owner action) | private quality table | Gold/FX coverage is 2021–2023 only and 2023 is poor. Stage 3 cannot validate gold on 2024. | Owner saves Dukascopy's permission email as `work/rights/dukascopy-consent.(eml\|pdf\|txt)`. Dukascopy serves exact UTC daily files with BID and ASK, which covers 2020 Q4, 2024, and fills the 2023 gaps. Then rerun B0. Keep HistData as a cross-check only. |
| P11e-3 | minor (Stage 3 gate) | `config/assets.yaml` (XAUUSD/EURUSD `spread_bps_default: "0"`) | The HistData bid-only "spread floor" is zero, so long-entry costs would be too optimistic. Codex flagged this correctly and changed nothing. | Before Stage 3, set the floor from Dukascopy's measured BID/ASK spread (median and 95th percentile per session), or from a conservative documented value if Dukascopy is unavailable. Owner sign-off required. |
| P11e-4 | minor | `src/tb/ingest/history/pipeline.py` `_require_owned_dukascopy_fixture` | The gate inspects the private `client._transport`, which could break on an httpx upgrade (it would fail closed, so this is safe but brittle). | Pass an explicit `owned_fixture` transport marker, or inject the transport in tests. |
| P11e-5 | minor | `forex.py` `request_bytes` | HTTP 429 is retried on the fixed 1/2/4 s schedule and ignores `Retry-After`. | Honour `Retry-After` (capped), or stop at the first 429. |

## 4. Correction to my earlier research

`reports/reviews/data-plan-research.md` finding 11, `dataset-rights-review-2026-11-01.md` §3, `docs/ROADMAP.md` and `prompts/P11e-acquire-history.md` B1.4 all stated that HistData uses "fixed EST, no DST, constant +5 h". That was based on HistData's own documentation and was never checked against real files. The real 2021–2023 files contradict it (P11e-1). Those documents are corrected in this commit. Codex implemented exactly what it was told.

## 5. Gates (rerun independently on `c104464` in a clean, credential-free worktree)

| Gate | Result |
|---|---|
| `pytest` (default) | **1,302 passed**, 1 skipped (S-5 environmental), 3 live deselected, 5 xfailed (R-3, R-4, D-3, D-4, S-1); 11 m 12 s. Matches Codex's report. |
| `ruff check` / `ruff format --check` | Clean / 500 files formatted |
| `mypy src` (strict) | Clean, 187 source files |

The gates pass because the tests encode the HistData clock that the specification wrongly
described; P11e-1 was found by checking the real files, not by the suite.

## 6. Recommendation

Do not merge yet. Codex should fix P11e-1 and P11e-4/5 on the PR branch, then rebuild the HistData Silver/Gold. Binance BTC/ETH/SOL is clean and can go to Stage 3 as soon as this PR merges. The owner should save the Dukascopy consent file (P11e-2) so the fix round can also fetch the exact-UTC BID/ASK history. P11e-3 is a Stage 3 entry gate.

## 7. Fix round re-review (PR #4 head `caaa9a5`)

| Finding | Status | Evidence |
|---|---|---|
| P11e-1 HistData clock | **Fixed** | `histdata_clock.week_offset`: one offset per Sunday-anchored week, +4 h when London noon on that Sunday is BST, +5 h otherwise. By hand: the 2022-03-13/20 and 2022-10-30 mismatch weeks get +5 h, and 2022-03-27 gets +4 h. The repeat is dropped only for a contiguous 120-row block with byte-identical OHLCV; otherwise the day is quarantined. The Silver weekend/rollover grid uses the same mapping. |
| P11e-4 `_transport` inspection | **Fixed** | Explicit fixture marker; still fails closed. |
| P11e-5 429 handling | **Fixed** | `Retry-After` honoured, capped at 60 s, at most 3 attempts; stops on a missing or invalid header. `failed_requests` now counts real attempts. |
| P11e-2 Dukascopy coverage | Open (owner) | Consent file still absent; acquisition correctly skipped. Gold/FX remains 2021–2023. |
| P11e-3 spread floor | Open (Stage 3 gate) | Unchanged by design. |

**Independent data check** (my own script over the rebuilt private Silver, not Codex's table):

| File | Strictly increasing UTC | Week opens on time | Early | Late (reason) |
|---|---|---|---|---|
| EURUSD 2021 | yes | 50 | 0 | 1 (< 1 h) |
| EURUSD 2022 | yes | 51 | 0 | 0 |
| EURUSD 2023 | yes | 39 | 0 | 12 (1–2 h, 2023 source gaps) |
| XAUUSD 2021 | yes | 51 | 0 | 0 |
| XAUUSD 2022 | yes | 50 | 0 | 1 (Monday holiday open) |
| XAUUSD 2023 | yes | 35 | 0 | 16 (1–2 h source gaps, 1 holiday) |

No week opens early anywhere; before the fix every BST week opened 60 min late. Exactly 60 provider-duplicate minutes per year are recorded.

**Gates** (rerun independently on `caaa9a5`, clean credential-free worktree): pytest **1,337 passed**,
1 skipped (S-5 environmental), 3 live deselected, 5 xfailed (unchanged audit minors); 11 m 07 s.
Ruff clean, 503 files formatted, strict mypy clean on 188 source files. The branch merges cleanly into `main` (`ec75191`).

**Verdict: APPROVED.** Merge PR #4. BTC/ETH/SOL 2020-10 → 2024 are ready for Stage 3. Gold/FX 2021–2023 are usable for development only. Gold validation on 2024 needs Dukascopy (P11e-2), and gold/FX costs need P11e-3 before any Stage 3 gold result counts.
