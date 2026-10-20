# P01 — Asset registry, Shariah gate and risk configuration

Follow `prompts/_PROTOCOL.md`.

## Goal
Encode the project rules as validated configuration plus code-level guards that every later phase uses.

## Research first
- Patterns for config-as-code with schema validation (pydantic v2) and versioning.
- How Binance spot symbol metadata (tick size, lot size, min notional) is represented — design the
  registry so these can later be filled from the public exchangeInfo endpoint (no key needed).

## Build
1. `config/assets.yaml`: entries for XAUTUSDT, BTCUSDT, ETHUSDT, SOLUSDT (tradable) and XAUUSD,
   EURUSD, USDJPY, GBPUSD, USDCAD, USDSEK, USDCHF, WTI, US10Y (data-only). Fields: symbol, role
   (tradable/data_only), venue, shariah_status (approved/pending/rejected), ruling_source,
   reviewed_on, phase, sessions, weekend_trading (bool), cost_model (fee_bps, spread_bps_default,
   slippage_bps_default), allowed_strategies, risk overrides (may only be stricter).
2. `config/risk.yaml`: global limits from AGENTS.md §2. Loader rejects any value looser than the
   hard ceilings defined in code.
3. `src/tb/risk/guards.py`: pure functions — `assert_tradable(symbol)`, `assert_long_only(order)`,
   `assert_spot(order)`, `check_exposure(...)`, `check_daily_loss(...)`, `check_session(...)`.
4. A repository-wide "forbidden endpoints" test that scans `src/` for futures/margin/earn/loan/
   staking/leverage strings and fails if any appear.

## Scenarios to self-test
Asset with status pending → rejected · risk.yaml trying 2% risk → rejected · sell order larger than
holdings → rejected · weekend XAUT entry → rejected · stricter per-asset override → accepted.

## Acceptance
Every guard has unit + property tests; config validation errors are human-readable; report written.
