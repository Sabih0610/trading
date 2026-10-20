# P12 — Execution adapter (Binance Spot Testnet) — runs only when keys are added

Follow `prompts/_PROTOCOL.md`. Build and test fully with mocks; live Testnet tests are
`@pytest.mark.live` and skipped until the user adds Testnet keys to `.env`.

## Goal
A single, minimal execution service — the only code that ever touches exchange keys — supporting
spot market/limit orders and OCO (stop + target), with continuous reconciliation.

## Research first
Binance Spot API current docs: order types, OCO/order-list endpoints, filters (tick size, lot size,
min notional), User Data Stream via WebSocket API, rate-limit weights, recvWindow and time sync,
idempotent client order IDs, Testnet differences and supported symbols.

## Build
1. `src/tb/execution/binance_spot.py` implementing the same Order API as the paper broker.
2. Pre-trade checks: guards from P01 + exchange filters; reject anything non-spot or short.
3. Reconciliation loop: local state vs exchange (open orders, balances, fills); mismatch ⇒ pause
   trading + alert. Startup recovery after crash.
4. Kill switch: cancel all open orders and stop new entries (CLI, dashboard control, file flag).
5. Key hygiene: keys read only here; startup check refuses to run if the key has withdrawal
   permission (where the API exposes permissions) and logs a warning to IP-restrict the key.

## Scenarios to self-test (mocked + Testnet when keys exist)
Partial fills · OCO one leg filled · order rejected by filters · duplicate submit (idempotency) ·
timestamp outside recvWindow · 429/418 rate limiting · disconnect during an open position.

## Acceptance
Mock suite green; Testnet suite green once keys are present; report written.
