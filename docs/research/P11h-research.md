# P11h research — Spot venue status as an entry veto

Use the official public Spot status field only, with no API key or order capability.
Status metadata is a current control input, never historical price evidence.
The approved rights review permits this narrow use; full Product Terms version
verification remains the same open item recorded by the reviewer.

| Question | Options | Decision and reason |
|---|---|---|
| Source | Announcement scraping / public exchangeInfo | One official GET with the four approved symbols; no announcement or binance.com page scraping. |
| Cadence | Aggressive retry / persisted next-at reservation | At least 60 seconds between attempts, retained across restart/concurrent callers. Official route weight observed as 20; 429/418 waits are honored rather than shortened. |
| Availability clock | Server timestamp / local complete-response receipt | Local receive time only. Ahead/behind server clocks cannot create earlier evidence. |
| Storage | Full polling history / changes plus operational receipt | Append-only status transitions; duplicate successful polls only refresh the four-row freshness state. Poll scheduling/error counters are operational metadata, not duplicate status history. |
| Entry integration | Change RiskManager / optional separate precheck | A separate wrapper can reject before the unchanged risk manager; TRADING merely delegates. Shared paper sizing accepts an optional immutable veto fact; exits never consult it. |
| Replay | Use today's status in past tests / explicit refusal | Historical backtest engine has no monitor dependency. Historical contract replay refuses an enabled venue book. Owned Paper Lab accepts only owned-fixture facts. |
| UI | Poll on page render / read private health JSON | Data Health recomputes staleness using stored receipt facts; no network or mutation in the UI. |

Primary sources accessed 2026-11-03:

- [Official Spot REST API](https://developers.binance.com/en/docs/products/spot/rest-api): HTTP 429/418 and Retry-After semantics; use local bounded HTTP behavior.
- [Official Binance Spot API repository, REST specification](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md): exchangeInfo symbol array, status field and weight.
- [Official Spot terms notice](https://developers.binance.com/en/docs/products/spot/PROD-TERMS-OF-USE): observed last-modified date **2026-10-30**. This notice points to Product Terms; it does not identify a full API-contract version. The stored metadata therefore says `full_product_terms_version: unverified`.
- [HTTPX timeout guidance](https://www.python-httpx.org/advanced/timeouts/): finite per-operation timeouts, plus our elapsed streaming deadline and response byte cap.

Authority: [Claude's distinct-reviewer approval, section 2](../../reports/reviews/dataset-rights-review-2026-11-02.md)
and [master prompt](../../prompts/MASTER-2026-11.md). Installed Python 3.12.15 and
HTTPX 0.28.1 remain pinned; no dependencies or risk defaults change.

Limitations: this is not a historical venue-status tape. Only the latest unchanged
receipt is retained; a past query without a retained fresh fact fails closed.
An invalid/incomplete poll is refused atomically and cannot refresh evidence.
Repeated failure eventually makes entry status stale, while all exits stay enabled.
