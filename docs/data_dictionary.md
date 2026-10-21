# Data dictionary

This dictionary describes the P02 Bronze contracts. Bronze preserves published values wherever possible and adds only an explicit nanosecond UTC time field. P04 will create cleaned and aligned Silver schemas without modifying these files.

## Common manifest (`*_manifest.json`)

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Manifest contract version; currently 1. |
| `source` | string | Stable source name such as `binance_spot` or `dukascopy`. |
| `symbol` | string | Normalized instrument symbol. |
| `timeframe` | string | `1m`, `aggTrades`, or `tick`. |
| `source_url` | string | Exact source URL, or REST endpoint plus pagination count. |
| `requested_from`, `requested_to` | UTC datetime | Intended inclusive source range. |
| `actual_from`, `actual_to` | UTC datetime or null | Observed first and last row times. |
| `rows` | integer | Parquet row count. |
| `byte_count` | integer | Parquet byte length. |
| `source_sha256` | string | SHA-256 of source payload(s). |
| `parquet_sha256` | string | SHA-256 of committed Parquet bytes. |
| `downloaded_at` | UTC datetime | Retrieval completion time. |
| `code_version` | string | Git revision used by the adapter. |

## Binance spot 1-minute klines

Published columns are retained as strings: `open_time`, `open`, `high`, `low`, `close`, `volume`, `close_time`, `quote_asset_volume`, `number_of_trades`, `taker_buy_base_asset_volume`, `taker_buy_quote_asset_volume`, and `ignore`.

| Added field | Type | Meaning |
|---|---|---|
| `open_time_ns` | int64 | Kline opening time normalized to Unix nanoseconds. |

Archive values use milliseconds before 2025-01-01 and microseconds from that date; the adapter applies the official date contract and rejects out-of-partition results.

## Binance spot aggregate trades

Published string columns: `aggregate_trade_id`, `price`, `quantity`, `first_trade_id`, `last_trade_id`, `timestamp`, `buyer_was_maker`, and `best_price_match`.

| Added field | Type | Meaning |
|---|---|---|
| `timestamp_ns` | int64 | Aggregate-trade time normalized to Unix nanoseconds. |

## Dukascopy M1 candles

Each UTC day contains both source sides as distinct rows.

| Field | Type | Meaning |
|---|---|---|
| `timestamp_ns` | int64 | UTC candle time in Unix nanoseconds. |
| `seconds_from_day_start` | int64 | Raw BI5 seconds offset. |
| `open_raw`, `close_raw`, `low_raw`, `high_raw` | int64 | Raw integer prices. Divide by `price_scale` only in downstream processing. |
| `volume` | float64 | Published side volume. |
| `price_scale` | int64 | Instrument divisor. |
| `side` | string | `BID` or `ASK`. |

## Dukascopy XAUUSD ticks

| Field | Type | Meaning |
|---|---|---|
| `timestamp_ns` | int64 | UTC tick time in Unix nanoseconds. |
| `milliseconds_from_hour_start` | int64 | Raw BI5 millisecond offset. |
| `ask_raw`, `bid_raw` | int64 | Raw integer prices. |
| `ask_volume`, `bid_volume` | float64 | Published side volumes. |
| `price_scale` | int64 | XAUUSD price divisor (1000). |

Tick rows are stored only for XAUUSD and only for completed hours in the trailing 365 days.

## FRED fixture schema

The fixture-backed parser accepts `observation_date` plus one allowlisted series (`DGS10`, `DFII10`, or `DTWEXBGS`) and derives typed `date` and nullable `value` fields. No live FRED Bronze dataset is permitted while D-0011 remains open.

## Calendar events

| Field | Type | Meaning |
|---|---|---|
| `event_id` | SHA-256 string | Stable identity from normalized name, country, currency, and UTC date. |
| `name` | string | Canonical displayed event name. |
| `country` | string | Uppercase country/region code. |
| `currency` | 3-letter string | Currency associated with the event. |
| `importance` | enum | `low`, `medium`, `high`, `holiday`, or `unknown`. |
| `scheduled_utc` | UTC datetime | Authoritative or best available scheduled time. |
| `actual`, `forecast`, `previous` | nullable string | Source-published values, units preserved. |
| `source`, `source_url` | string | Winning source and provenance URL. |
| `fetched_at` | UTC datetime | Payload retrieval time. |
| `source_aliases` | list of strings | All reconciled contributing sources. |
| `time_conflict` | boolean | True when sources disagreed on the scheduled UTC time. |
| `conflicting_times_utc` | list of UTC datetimes | Every distinct observed time when a conflict exists. |

## News items

| Field | Type | Meaning |
|---|---|---|
| `id` | SHA-256 string | Hash of Unicode/case/punctuation-normalized headline text. |
| `headline` | string | Syndicated headline only; article text is excluded. |
| `source` | string | Publisher/feed name or GDELT domain. |
| `url` | string | Link to the publisher item. |
| `published_utc`, `fetched_at` | UTC datetime | Publication/discovery and retrieval times. |
| `topics` | list of strings | Transparent keyword tags for gold, central banks, inflation, oil, or crypto. |
| `language` | 2–3 letter string | Feed/GDELT language code; `und` means unknown. |
| `raw_hash` | SHA-256 string | Hash of the exact RSS entry or GDELT article object. |

Topic tags are metadata only. They do not create, size, or approve a trade.
