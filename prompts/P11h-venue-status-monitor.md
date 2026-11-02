# P11h: Binance venue status monitor (veto-only)

Follow `prompts/_PROTOCOL.md` and the rules in `prompts/MASTER-2026-11.md`. Branch
`codex/p11h-venue-status`. Authority: owner (2026-11-02), ROADMAP Stage 2, and
[rights review 2026-11-02](../reports/reviews/dataset-rights-review-2026-11-02.md) §2.

## Build
1. `tb.ingest.venue_status`: poll the public `GET /api/v3/exchangeInfo?symbols=[...]` for
   XAUTUSDT, BTCUSDT, ETHUSDT and SOLUSDT every ≥ 60 s (configurable, minimum 60). Store
   **status changes only** (symbol, old, new, `known_at`, raw status string) in an append-only
   private store. Bounded retries; honour 429/418 and `Retry-After`; never hammer.
2. A pure `venue_veto(symbol, at) -> VetoDecision` that blocks **new entries** when the latest
   known status at `at` is not `TRADING`, or is unknown or stale (> 10 min; fail closed for
   entries only). It can never create, enlarge or reverse a trade, or force a sale.
3. Wire it as an **optional** input to the paper/offline simulation entry gate and the risk
   pre-check **as a veto only**, disabled in backtests on history (no historical status
   exists, so never fabricate one).
4. Data Health: show the current status per symbol and the last change.
5. Tests (fixtures, no network): status change recorded once; duplicate polls are no-ops;
   `BREAK`/`HALT`/unknown → entry veto; stale → veto; veto never touches exits; 429 back-off;
   malformed JSON refused; clock skew (server time ahead or behind) uses `known_at` = local
   receive time.

## Done
Gates green; how-to `docs/how-to/venue-status.md`; ADR; phase report `reports/phases/P11h.md`.
No keys, no `sapi`, no web scraping, no orders.
