# P11h review: Binance venue status monitor

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/p11h-venue-status` at `67e4978` (17 files, +1,505) |
| Verdict | **APPROVED**, merged. |

## Checks

| Check | Result |
|---|---|
| Rights (review 2026-11-02 §2) | Only `GET https://api.binance.com/api/v3/exchangeInfo`; no keys, no `sapi`, no web scraping. The API terms URL is recorded. |
| Polite polling | `reserve_poll` refuses intervals under 60 s. Bounded failures; `Retry-After` honoured, and an oversized value closes the gate rather than retrying early. |
| Veto-only | `risk/venue.py` and `paper/simulation.size_candidate` can only **reject entries** (`ASSET_POLICY` / venue reason). A `TRADING` status merely delegates to the unchanged `RiskManager`. No exit, size-increase or trade-creation path. |
| Fail closed | Unknown status, non-`TRADING`, conflicting statuses at the same `known_at`, or status older than 10 minutes vetoes entries. A permissive decision requires a fresh `TRADING` fact (model validator). |
| No fabricated history | Refused in historical backtests (`venue_status_disabled_for_historical_backtests`) and for non-synthetic simulator specs. Owned paper inputs accept only owned-fixture evidence with a matching symbol and clock. |
| Storage | A private SQLite journal stores status **changes** only; the latest poll receipt is operational freshness state. |
| Conflict rules | No shared living docs edited. Merges cleanly with I, J1 and the living-docs PR. |

## Gates (`67e4978`, clean worktree)

pytest **1,500 passed**, 1 skipped (S-5), 3 live deselected, 5 xfailed. Ruff clean, 543 files formatted, strict mypy clean on 200 sources.

## Follow-up

None blocking. Live polling is not started by this phase; enabling it in a future paper phase needs the owner's go-ahead.
