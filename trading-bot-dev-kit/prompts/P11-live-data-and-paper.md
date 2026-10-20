# P11 — Live market data collector and paper-trading engine (no keys needed)

Follow `prompts/_PROTOCOL.md`.

## Goal
Record live Binance public market data for XAUT/USDT (and later BTC/ETH/SOL) and run the full
pipeline in paper mode, simulating fills against the real live order book.

## Research first
- Binance spot WebSocket streams (klines, trades/aggTrades, bookTicker, diff depth) and the official
  procedure for maintaining a local order book from snapshot + diff updates; reconnect handling,
  server shutdown events, connection limits.
- A live gold reference without keys during this phase: evaluate free options (e.g. Dukascopy
  delayed/near-live feed, MT5 later) and document latency and gaps.

## Build
1. `src/tb/ingest/live/`: async collectors writing to Bronze (append-only Parquet in hourly
   files) + an in-memory latest-state store; sequence-gap detection and resync.
2. `src/tb/paper/`: paper broker consuming live book; fills use queue-position-aware limits or
   pessimistic market fills (walk the book), fees, partial fills; same Order API as live execution.
3. `tb run --mode paper`: features → strategies → ML → arena (mock/local) → risk → paper broker →
   ledger; Windows Task Scheduler scripts to start on boot and restart on crash.
4. Heartbeats and health metrics shown on the dashboard.

## Scenarios to self-test
WebSocket disconnect storm · sequence gap → resync · laptop sleep/resume · clock drift (sync check) ·
book crossed/locked · extreme spread widening · 24h soak test with memory monitoring.

## Acceptance
24-hour unattended paper run with no crashes and a complete ledger; report written.
