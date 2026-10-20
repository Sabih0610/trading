# Seed list of data sources (from planning research, Oct 2026) — VERIFY EACH ONE in P02/P03

Nothing here is confirmed for production use. Codex must check current URLs, formats, rate limits,
history depth, timezone handling and terms of use, and record findings in the phase research notes.

## Market data (keyless)
| Need | Source | Notes to verify |
|---|---|---|
| XAUUSD + FX + oil history (M1/ticks) | Dukascopy historical data (e.g. via `dukascopy-node`) | Bid/ask, timezone, holiday gaps |
| BTC/ETH/SOL/XAUT spot history | Binance public archive data.binance.vision (klines, aggTrades) | XAUT listed on Binance 2026-03-26; CHECKSUM files |
| Recent bars | Binance REST klines (public) | Weights/rate limits |
| Live order book/trades | Binance spot WebSocket streams (public) | Local book sync procedure |
| US yields, dollar index | FRED keyless CSV (fredgraph.csv?id=…) | API key version later |

## Economic calendar
| Source | Notes to verify |
|---|---|
| Official: BLS, BEA, Federal Reserve FOMC calendar, EIA, ECB | Ground truth for release times |
| ForexFactory / Fair Economy weekly JSON feed | Current week only; forecast/previous but no actuals in free feed |
| ForexFactory calendar pages by date range | Public pages; check terms/robots; polite rate limits |
| Nasdaq economic calendar | Reported to support date-range history |
| FRED/ALFRED release dates | Needs FRED key (later) |

## News
| Source | Notes to verify |
|---|---|
| GDELT 2.0 DOC API | Free, keyless, ~1 request / 5 s, rolling window of recent months |
| GDELT 2.0 GKG/event 15-minute files | Full history; stream-filter by theme/keyword; large volume |
| RSS feeds (Fed, metals, FX/macro, CoinDesk, Cointelegraph, Decrypt, The Block) | Check each URL |
| Free crypto news aggregators with archives (e.g. cryptocurrency.cv) | Verify licence, quality, uptime |
| Finnhub, CryptoPanic, NewsData.io | Keyed; wire as disabled until keys exist |
