# Data dictionary

## P11a.3 reference market data

Provider namespace `twelve_data` reuses the existing immutable Bronze/Silver/checkpoint schema;
`twelve_data_synthetic` is a separate dashboard fixture namespace. No historical reader or final
holdout authorization is expanded. Raw payloads and numeric price exports remain Git-ignored.

`Observation.kind=reference` carries `reference_price`, never bid/ask. All Twelve Data rows use
`source_provider=twelve_data`, `price_type=reference_midpoint`, `source_timezone=UTC`, preserved
`raw_source_time` (rate Unix timestamp or M1 open string), and optional
`source_metadata_timezone` (null when the actual Forex metadata omits it). No broker clock stamp.
M1 `interval_complete` is elapsed interval completion at receipt, not a provider finality claim.
Incomplete rows stay backfill; completed forward rows require new run coverage and timely receipt.
`volume_kind=unavailable`: tick/real volume, spread and broker quote sides remain null.

`ReferenceIdentity` identifies a Basic reference-data source, not a demo brokerage account.
`ReferenceExport` records independent instrument counts/readiness, references/completed bars,
collection/session times, stopped/running status, actual usage and UTC checks. Qualification
requires at least three distinct prospective completed M1 openings spanning 120s; exported claims
must contain that evidence. `price_display_authorized=false` and
`long_term_storage_authorized=false` are explicit limits. Recorded qualification and current
freshness differ. No execution, contract sizing, model approval or P&L is inferred.

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

## Silver market bars

Silver market files use the same schema across approved crypto assets and data-only market
references. Prices are midpoint values for Dukascopy and published kline values for Binance spot.

| Field | Type / unit | Source and meaning |
|---|---|---|
| `timestamp_ns` | int64 nanoseconds | UTC bar opening time copied from normalized Bronze. |
| `timestamp_utc` | UTC datetime (ns) | Human/query-friendly rendering of `timestamp_ns`. |
| `symbol` | string | Normalized instrument symbol. |
| `source` | string | `binance_spot` or `dukascopy`. |
| `open`, `high`, `low`, `close` | float64, quote units | Published Binance OHLC, or midpoint of paired Dukascopy BID/ASK OHLC. |
| `volume` | float64, source units | Published Binance base volume, or mean of Dukascopy BID/ASK side volumes. Values are not comparable across providers. |
| `close_spread` | float64, quote units, Dukascopy only | ASK close minus BID close. |
| `gap_minutes_before` | int64 minutes | Missing whole minutes since the preceding observed bar in the same partition. Zero means adjacent. |
| `is_spike` | boolean | Return exceeded both a past-only 12 scaled-MAD score and a 0.5% absolute-return floor. The row is retained. |
| `session_asia` | boolean | UTC time is in the project's 00:00–08:00 Asia research window. |
| `session_london` | boolean | Europe/London local time is 08:00–16:30; DST comes from IANA tzdata. |
| `session_new_york` | boolean | America/New_York local time is 09:30–16:00; DST comes from IANA tzdata. |
| `session_overlap` | boolean | London and New York tags are both true. |
| `is_weekend` | boolean | UTC calendar day is Saturday or Sunday. Rows are tagged, not removed. |
| `trading_day_id` | `YYYY-MM-DD` string | UTC calendar date used for deterministic grouping. |
| `market_kind` | enum string | `continuous` for crypto or `weekday` for market references. |

### Resampled market bars

The `5m`, `15m`, `1h`, `4h`, and `1d` folders are derived only from Silver `1m` bars. `open` is
the first value, `high`/`low` are extrema, `close` is the last value, and `volume` is the sum.

| Added/replaced field | Type / unit | Meaning |
|---|---|---|
| `timestamp_utc` | UTC datetime | Inclusive left edge of the bar. |
| `bar_end_utc` | UTC datetime | Exclusive right edge. The row is not emitted before this instant. |
| `timeframe` | string | `5m`, `15m`, `1h`, `4h`, or `1d`. |
| `source_rows` | unsigned integer | Number of observed 1m rows used. |
| `has_all_source_minutes` | boolean | True when `source_rows` equals the timeframe's expected minute count. |
| `max_gap_minutes_before` | int64 minutes | Largest source gap marker among included rows. |
| `is_spike` | boolean | True when any included 1m bar was flagged. |

## Silver XAUT/XAU alignment

| Field | Type / unit | Meaning |
|---|---|---|
| `timestamp_utc` | UTC datetime | Exact shared minute; rows are anchored on XAUTUSDT. |
| `xaut_usdt` | float64 USDT per XAUT | Binance spot close. |
| `xau_usd` | nullable float64 USD per troy ounce | Dukascopy midpoint close at exactly the same minute; null when absent or weekend-tagged. |
| `basis_bps` | nullable float64 basis points | `(xaut_usdt / xau_usd - 1) × 10,000`; null whenever `xau_usd` is null. |
| `quote_assumption` | string | Records that the comparison assumes nominal USDT/USD parity. |

No value is forward-filled. Exact DXY/USDX is not produced while D-0016 is open.

## Silver calendar, news, and common timeline

Calendar schedule columns are `event_id`, `name`, `country`, `currency`, `importance`,
`timestamp_utc`, `known_at`, `source`, `source_url`, `fetched_at`, and `time_conflict`.
`timestamp_utc` and `known_at` both equal the scheduled UTC instant. Release values from Bronze are
excluded because their first-publication time is not represented reliably.

News columns are `id`, `headline`, `source`, `url`, `timestamp_utc`, `known_at`, `fetched_at`,
`topics`, and `language`. `timestamp_utc` and `known_at` both equal `published_utc`.

The common timeline uses:

| Field | Type | Meaning |
|---|---|---|
| `timestamp_utc`, `known_at` | UTC datetime | Event time and earliest safe knowledge time. |
| `record_type` | string | `calendar` or `news`. |
| `record_id` | string | Source table's stable event/headline ID. |
| `title` | string | Event name or headline. |
| `source`, `url` | string | Provenance. |
| `importance` | nullable string | Calendar importance; null for news. |
| `topics_csv` | string | Comma-separated news topics; empty for calendar. |

## Silver manifest and quality JSON

Each Silver manifest has `schema_version`, `input_path`, `input_sha256`, `output_sha256`, `rows`,
`byte_count`, `transformation_version`, and `generated_at`. A market quality JSON has `dataset`,
input/output rows, `coverage_pct`, gap counts, missing minutes, flagged spikes, removed duplicates,
and first/last UTC times. Alignment quality additionally reports exact overlap and null-basis rows.

## Gold features

Gold retains its Silver columns and adds the following causal fields. Null means the declared
warmup/confirmation is not complete or the source input is unavailable.

| Field | Unit/type | Definition and availability |
|---|---|---|
| `input_gap` | boolean | True when elapsed time differs from the native timeframe; continuity state resets on this row. |
| `log_return` | natural-log return | `ln(close / previous_close)`; null on first row or after a gap. |
| `true_range` | quote units | Maximum of high-low and distances from prior close. |
| `atr14` | quote units | Mean of first 14 true ranges, then Wilder recurrence; 13-row warmup. |
| `realized_vol20` | per-bar log-return standard deviation | Sample standard deviation of the latest 20 returns. |
| `ema20`, `ema50` | quote units | Recursive EMA seeded by the first close, alpha `2/(n+1)`. |
| `ema20_slope`, `ema50_slope` | decimal change/bar | Current EMA divided by previous EMA minus one. |
| `confirmed_swing_high`, `confirmed_swing_low` | quote units | Strict 3-left/3-right pivot reported only on its confirmation bar. |
| `structure_event` | nullable enum | `bos_up/down` for continuation or `choch_up/down` for first opposite close beyond a confirmed swing. |
| `structure_direction` | -1/0/1 | Most recently confirmed break direction. |
| `sweep_event` | nullable enum | Confirmed high/low wick breach followed by close reclaim within at most three completed bars. |
| `fvg_direction`, `fvg_lower`, `fvg_upper` | enum / quote units | Three-bar wick non-overlap at least 0.25 of prior ATR; a price-pattern label only. |
| `fvg_fill_event`, `active_fvg_count` | enum / count | Subsequent partial/full range contact and active directional-gap count. |
| `order_block_low`, `order_block_high` | quote units | Last opposite-color candle in the prior ten bars when structure breaks; explicitly an approximation. |
| `htf_structure_direction`, `htf_structure_available` | -1/0/1, boolean | Latest higher-timeframe direction whose `bar_end_utc` is at or before this bar. |
| `session_vwap` | quote units | Cumulative daily typical-price × volume divided by volume. |
| `asia_range_high`, `asia_range_low` | quote units | Running Asia range; values freeze after the session. |
| `london_open`, `new_york_open` | quote units | First observed open in each local/DST-aware session. |
| `minutes_to_high_impact_event` | minutes | Nonnegative time to the next high-impact schedule already known; otherwise null. |
| `basis_bps`, `basis_zscore` | bps / z-score | Exact-time nominal XAUT/XAU basis and trailing 60-observation z-score. |
| `usd_index_change`, `yield_change` | nullable decimal change | Null while licensed/approved source inputs are unavailable. |
| `usd_index_available`, `yield_available` | boolean | False for the current gated macro inputs. |
| `book_available` | boolean | False in historical Gold; true only for a synchronized live Spot book. |
| `spread_bps` | basis points | Best-ask minus best-bid divided by midpoint. |
| `top_book_imbalance` | ratio [0,1] | Best-bid quantity divided by total best bid/ask quantity. |
| `weighted_quote` | quote units | Best quotes weighted by opposite-side touch quantity; not a model-estimated microprice. |
| `trade_flow_imbalance` | ratio [-1,1] | Buyer minus seller quantity divided by their sum. |
| `bid_depth_*bps`, `ask_depth_*bps` | base quantity | Displayed depth within 5, 10, or 25 bps of midpoint. |

The Gold manifest fields are `schema_version`, `input_path`, `lineage_sha256`, `output_sha256`,
`rows`, `byte_count`, `feature_set_version`, `feature_versions`, and `generated_at`.

## P11a market-feed evidence

Raw JSON/Parquet and BronzeManifest live in `data/bronze/mt5_feed/<session>/<batch>/`;
validated records mirror into `data/silver/mt5_feed/`. The session/checkpoint ledger is separate
from trading journals. Records retain canonical/broker symbol, quote/tick/candle kind, timeframe,
source/receipt UTC, bid/ask or OHLC, source volume/spread/flags and explicit evidence classification.
Candle tick volume is broker activity; quote/tick trade-volume semantics remain unverified.
`forward_observed`, `historical_backfill`, `historical_research` and `synthetic` are distinct.
Completed forward candles also record coverage_started_at. Old source facts deduplicate without
using receipt time or evidence labels as identity. No gap filling or guessed broker time correction.

Batch commit records bind file hashes, source code version, immutable session start, origin,
receipt and row/duplicate/evidence counts. Only database-committed batches advance checkpoints.
Small pointer/checksum-verified exports under `reports/market_feed/genuine` or `synthetic` drive
read-only monitoring and never combine with account P&L. Current quote admission remains failed
for the inspected genuine source; diagnostics are not historical research or trading evidence.

## P11a.1 acquisition diagnostics

`reports/mt5/P11a.1-*.json` stores timestamped demo fingerprint, raw integer seconds/milliseconds and exact UTC interpretations, receipt/monotonic duration, independent UTC references, native safety and unqualified M1 tails. These are diagnostic facts, not admitted market history. Quote counts are per explicit sampling run: attempts, received, valid, rejected, missing, duplicate, source updates and unique qualified forward quotes; admission probes are excluded. `rejected_by_reason` gives rejection counts. `AdmissionCheck` is strict boolean, fingerprint-bound and fresh for at most 60s. Dashboard snapshots add collection start/end, counts, admission, observed connection and coverage label; older snapshots default to unverified. Full market tick coverage is never implied. Ephemeral `_accepted_rows` exist only in a commit return value, not its immutable manifest.

## P11a.2 source clocks and provider provenance

`ClockProfile`: immutable versioned provider/broker/server/environment/build/instrument scope, source semantics, effective UTC periods or reviewed IANA zone, authoritative evidence hashes/reviewer, validation counts/time window/residual/reference sources, expiry and refresh conditions. UNVERIFIED/PROVISIONAL do not normalize; VERIFIED requires proof; EXPIRED/INVALID refuse. Fixture validation cannot enable genuine adapters. Historical applicability differs from current profile freshness.

`Observation.clock_stamp`: original representation/raw interpretation, normalized UTC, profile ID/content digest, conversion rule, provider/server/public identity. Legacy records default null and are never rewritten. Raw-source dedup excludes mutable profile/result fields, so profile changes do not manufacture new observations. `AdmissionCheck.instruments` independently masks each symbol; common security/host-clock/identity failure blocks all. Practice authorization is separate from native MT5 permission fields.

`oanda_practice` namespace reuses Bronze/Silver/checkpoints/manifests but stays outside historical ingestion and MT5 namespaces. OANDA unit constraints are not MT5 lot metadata. OANDA bid candles use broker price-update activity volume, not global market volume. Mock adapter rows remain synthetic. Read-only snapshots add clock_profiles, clock_diagnostics and instrument readiness; provider selection appears only for indexed configured data.

## P11b.0 reference shadow evidence

`DataRights` has policy/schema versions, exact provider/account fingerprint/instruments, reviewed
UTC time and per-usage status (`confirmed`, `unverified`, `prohibited`, `expired`). Status and
approval are distinct: an admitted usage needs explicit approval, reviewer, evidence and finite
unexpired expiry. `SHADOW_USAGES` covers retrieval, raw cache, history, derived storage and
persistent collection. AI analysis and ML training are separate unused gates. Policy digest is
part of the immutable study pin; no credential value is stored in the public policy or pin.

`SourcePin` binds owned-fixture/genuine mode, provider, public identity, producer/consumer code,
config and rights hashes. `ShadowEvent` binds exact M5 midpoint evidence ID, committed source
manifest path/hash and original Observation. Its interval identity ignores later receipt/price
changes so revisions cannot replace a frozen interval decision.

| ResearchDecision field | Meaning |
|---|---|
| `source_open_at`, `source_close_at` | UTC M5 interval endpoints; never decision availability. |
| `received_at`, `information_available_at` | Actual source receipt and admitted availability. |
| `decision_at` | Processing/decision UTC at or after receipt, including measured computation. |
| `signal`, `status`, `reasons` | BUY/SELL/WAIT research direction; candidate/blocked/control and explicit reasons. No order instruction. |
| `features`, `features_sha256` | Frozen causal price-only inputs and hash; missing volume/session/HTF remain unavailable. |
| `strategy_version`, `feature_version`, `source_version`, `consumer_version`, `rights_digest` | Exact reproducibility and permission lineage. |
| `execution_eligible`, `risk_sizing`, `advisory` | Fixed false / unavailable executable facts / disabled model. |
| `runtime_milliseconds` | Measured local processing duration; not provider or execution latency. |

The isolated shadow SQLite journal appends event, decisions and hash-linked checkpoint in one
transaction. Health includes run start/stop/recovery, duplicates/revisions, refusal and heartbeat.
Later labels append fixed same-source future reference direction without altering original inputs;
WAIT controls are not directional samples. This schema has no balances, positions, fills or P&L.

`ShadowSnapshot` is a bounded price-free projection: provenance, source readiness, latest UTC
candle/receipt/decision, counts, blockers, health, quota projection, observation/runtime lag,
versions and unavailable outcomes. `snapshots/current.json` names an immutable file and SHA256.
Fixture and genuine exports remain distinct; the dashboard never reads raw feature inputs.

## P11b.0.1 price-only research fields

Optional shared reference feature version2.0.0 adds `reference_ema_fast`, `reference_ema_slow`
(first-close recursive EMA), `reference_contiguous_bars`, `reference_close`, strictly prior-window
`prior_channel_high`/`prior_channel_low`, and `prior_atr14` from the existing shared Wilder state.
The current candle is appended after channel thresholds are calculated. Gap reset clears all
lookback and suppression state. These numeric inputs stay in the local rights-gated journal;
they are not exposed by the public dashboard projection.

`ResearchDecision` adds exact `strategy_config`/SHA256 and warming_up/filtered/ready states.
Candidate BUY/SELL remains a directional hypothesis with execution_eligible=false, unavailable
funded sizing and disabled advisory. Indexed decision UTC uses fixed six-digit microseconds;
legacy stored payloads are never rewritten. New config2.0.0 explicitly admits six strategy records
per event; legacy configuration defines four. Exact source/config/version changes refuse old
journal reuse rather than migrating it silently.

`EvaluationProtocol` is frozen in the new journal metadata before scoring: version, selected
1/3/6-M5 horizons, flat threshold bps and minimum descriptive non-overlap count. Future labels
store the original decision hash, committed future evidence IDs, evaluation start/end/availability,
UP/DOWN/FLAT, directional correctness, matched always-UP/previous-move outcomes and a per-group
non-overlap flag. WAIT abstains. Missing/pending counts do not become incorrect outcomes.
`available_directional_samples` counts scenario-specific decisions with labels;
`available_future_labels` counts all horizon labels, which are not independent observations.

Price-free snapshots add `strategy_states`, `evaluation`, `recent_labels` and the frozen protocol.
Column allowlists refuse raw price/account fields. Strategy readiness includes contiguous bars,
required warm-up, reason and version. Evaluations group by symbol/strategy/horizon and mark all
owned outcomes synthetic-only; no trade profit, balance, fill or investment recommendation.

Permission metadata adds documentary kind, project-relative evidence artifact/SHA256 and explicit
`permitted_retention_seconds`. Request-pending evidence cannot permit use. The offline review
workflow validates scope/reviewer/expiry/document integrity; explicit apply installs only a new
public policy version. No provider confirmation or approval is inferred. Finite genuine run
preflight requires all three storage retention durations to exceed run length by five minutes;
retention disposal remains a separately reviewed owner duty, with no automatic deletion here.


## P11b.1 broker quote evidence (data only)

`BrokerIdentity` pins ctrader_demo, fixed demo server, fingerprint, broker, denomination,
SCOPE_VIEW and checked-at/evidence mode. Owned identity is never a genuine account qualification.
`BrokerQuoteSource` exposes connection/identity/metadata/read/close facts only, with no sender.

| Field group | Semantics |
|---|---|
| `source_at`, `received_at`, `raw_timestamp`, `original_timestamp`, `source_timezone` | Explicit source epoch-ms contract and actual pre-buffer wire receipt UTC; original timestamp representation retained. No guessed offsets. |
| `bid_source_at`, `ask_source_at`, `bid_received_at`, `ask_received_at` | Independently timed sides; unchanged side keeps its old timestamps. Both must remain fresh. |
| `bid_relative`, `ask_relative`, `bid`, `ask`, `raw_event` | Exact protocol 1/100000 price values and Decimal sides; raw original update contains only present fields. No synthetic opposite side or source sequence. |
| `event_id`, `metadata_digest`, `rights_digest`, `rights_status` | Content-derived duplicate ID, metadata/rights versions and scoped-confirmation admission state. Receipt cannot create new source evidence. |
| `price_type`, `evidence` | Indicative bid/ask and owned_fixture/genuine kept distinct; no fill implication. |
| `BrokerContract.native_contract`, `native_costs` | Present raw financial fields preserved; cents-based volume/lot values normalize to units. Missing fields remain unknown. Digits provide a precision quantum, not confirmed economic tick size/value. |
| `Qualification` | Independent market/contract/cost/funded-minimum/legal/Shariah states. Before-cost floor differs from known-cost total capital. Local simulation remains false and P11b.2 NO-GO. |
| `ReferenceQuoteLink` | Original reference ID/version/provider/decision time, broker source/receipt times, delay/freshness/spread or explicit refusal. Both sides available after decision; no execution/account state. |

`BrokerObservation` extends the existing Observation with explicit ctrader_demo provider,
`broker_record_id` and full typed `broker_record_json`. FeedStore uses separate ctrader_demo
Bronze/Silver/checkpoint paths; DecisionLedger observations and broker input/hash checkpoint join
one FULL-sync transaction. Raw partial/refused updates remain raw evidence; only normalized
admissible quotes enter quote counts. Authentication/token/account-ID responses are excluded.

Genuine rights require the same documentary approval/hash/expiry/retention workflow under an
explicit broker provider argument. Existing Twelve Data apply scope remains unchanged. Private
UI projection withholds prices and reconstructible notional when display is not approved; mode,
source and hashes are checked, with genuine rights before opening snapshot data. No account P&L.

## P11b.2a owned offline paper evidence

All records have owned_fixture input provenance and owned_offline_paper account/evidence mode.
No financial value below can be relabelled as a genuine broker account or empirical return series.

| Record / field | Meaning |
|---|---|
| PaperPackage | Immutable synthetic contracts, side/fee/slippage assumptions, reference strategy/rights versions, finite bounds and disabled external orders. Separate source/code/risk pins. |
| PaperInput.id / raw / received_at | Deterministic local identity; original present quote-side fields/source epoch and independent receipt UTC, or original frozen ResearchDecision. Revised frozen inputs refuse. |
| PaperOrder | Local entry, signal_exit or standing protection; pending/rejected/expired/filled/cancelled, reason, created/expiry clocks, lots, reservation, cap and planned loss. |
| PaperPosition | Owned long, entry cash/fee/price, lots, protective ID/brackets and management clock. No unowned positions or broker identifiers. |
| PaperAccount.cash / reserved | Full account cash and its reserved subset; spendable balance is cash minus reserved. Reservation is not a second cash debit or reduction in equity. |
| equity / realized_pnl / unrealized_pnl | Net liquidation equity includes explicit exit costs. Equity minus initial cash reconciles to realized plus unrealized when marks exist; missing marks remain unavailable. |
| fees / slippage / quoted_spread_cost | Charged cash fees plus diagnostic adverse price/quoted-spread burdens already embedded in prices. Do not deduct diagnostics again. |
| safety / entries_today | Shared SafetyState day baseline, peak and persistent daily/peak latches; shared per-symbol entry counts. |
| hypothetical_fill | Stable fill/order/input/quote identities, actual owned side/source/receipt/intention clocks, lots/units/price, fee, cash delta and diagnostic costs. Not an external execution. |
| paper_events | Append-only raw input, effects, account state, payload/state hashes and previous-derived chain. Same transaction as DecisionLedger decisions. |
| paper_recoveries / interventions | Stable checkpoint-bound recovery proof and matching append-only DecisionLedger intervention. Repeated reconciliation does not duplicate it. |
| inputs.manifest.json / paper.manifest.json | Owned source bytes/counts/package version and account/code/risk pins. Corruption/change refuses rather than migrates. |
| reports/offline_paper/current.json | Hash pointer to an immutable bounded owned projection; read-only UI verifies checkpoint/ledger and independently sums fill cash flows. |
