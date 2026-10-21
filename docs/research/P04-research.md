# P04 research — Silver validation, resampling, anomalies, and cross-market alignment

P04 must turn immutable Bronze into reproducible Silver without hiding bad data or leaking future bars. Current Polars window semantics support the needed completed-bar contract, while an exact ICE Dollar Index replica is paused because ICE's current materials reserve the formulation, components, weights, and calculation method for licensed use.

## Questions asked

- Can Polars validate and resample partition-at-a-time without adding a heavy validation framework?
- Which dynamic-window boundaries prevent a bar at time *t* from using later source rows?
- How should price spikes, gaps, closed sessions, and duplicate ticks remain auditable?
- When is a cross-market XAUT/XAU basis valid rather than stale?
- Can this project lawfully reproduce the ICE USDX/DXY formula and weights?

## Options compared

| Topic | Options | Decision | Reason |
|---|---|---|---|
| Validation | Pandera Polars; Great Expectations; explicit Polars expressions | Typed explicit Polars validators with collected partition summaries | Pandera's Polars data-level checks materialize lazy frames and its integration remains less mature. The required checks are small, source-specific, and clearer as tested expressions without another framework. |
| Resampling | Rolling windows; dynamic windows closed left/right | Sorted `group_by_dynamic`, `closed="left"`, `label="left"`, plus explicit completed-window cutoff | Polars documents default windows as `[start, start + period)`. Dropping a still-open final window prevents lookahead in both batch and live use. |
| Spikes | Delete; winsorize; flag robustly | Flag log-return median absolute deviation anomalies; never silently drop or replace | Real flash moves and bad ticks need separate downstream treatment and must remain auditable. Degenerate MAD uses a fail-closed fallback flag rule. |
| Gaps | Fill forward universally; leave absent; market-aware flags | Preserve absent minutes and report market/session-aware gaps | Forward filling prices across outages or closed markets can fabricate tradable observations. |
| XAUT/XAU basis | Last observation carried forward; exact timestamp inner match; bounded as-of | Exact/bounded same-minute availability only, otherwise null | XAUT can trade while XAUUSD is closed. Stale reference prices must produce null basis. |
| DXY | Exact ICE replica; configurable generic basket; omit | Gate exact ICE replica; provide a separately named configurable geometric USD basket only after legal naming/weights review | ICE's brochure says use of the formulation, components, weights, values, or methods requires express written consent. |

## Chosen implementation contracts

- Silver partitions are derived only from Bronze files whose manifests validate; lineage records every input checksum and transformation version.
- Convert raw numeric strings/integers strictly, reject non-finite prices/volumes, sort UTC time, and deterministically retain one row per primary key.
- Preserve `is_spike`, `gap_minutes_before`, session tags, weekend flag, and trading-day ID as columns. Reports count every correction/flag.
- Build 5m, 15m, 1h, 4h, and 1d bars from cleaned 1m bars with left-labeled half-open windows. A window is emitted only after its right boundary is at or before the processing cutoff.
- News uses `known_at = published_utc`; scheduled calendar events use `known_at = scheduled_utc`. Later actual values require their own observation time and cannot be backfilled into the scheduled event row for model features.
- The XAUT/XAU basis is null whenever both markets lack a valid same-minute observation; no unbounded forward fill.

## Source findings

Polars documents that dynamic groups require sorted time and that the default/explicit left-closed windows are `[start, start + period)`. This is suitable only when the still-open terminal window is excluded. Pandera can validate Polars, but its documentation notes that data-level LazyFrame checks cause collection/materialization and that the backend has unsupported features compared with pandas; direct expressions are the leaner fit here.

BIS high-frequency FX research describes explicit outlier checks and cautions that unchanged quotes may represent illiquidity rather than information. P04 therefore flags robust return anomalies and gaps instead of deleting or interpreting them automatically.

ICE documents USDX as a geometric six-currency index and publishes a formula/weights, but its official brochure also states that any use of the formulation, components, weights, values, or methods is prohibited without express written consent. The project will not encode that proprietary replica until the owner resolves licensing. A generic basket must not be labelled DXY/USDX or presented as the ICE index.

## Sources

Accessed 2026-10-21 UTC.

- [Polars `group_by_dynamic`](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.group_by_dynamic.html) — sorted-index requirement and half-open window semantics.
- [Polars time-series grouping guide](https://docs.pola.rs/user-guide/transformations/time-series/rolling/) — dynamic grouping examples.
- [Pandera Polars validation](https://pandera.readthedocs.io/en/stable/polars.html) — LazyFrame materialization and backend limitations.
- [BIS high-frequency data filtering appendix](https://www.bis.org/publ/work626_appendix.pdf) — cautious outlier filtering and illiquidity caveats.
- [BIS observation-frequency research](https://www.bis.org/publications/working-paper-249-frequency-observation-and-estimation-integrated-volatility-deep-and-liquid-financial-markets) — microstructure-noise considerations.
- [ICE FX Indexes methodology](https://www.ice.com/publicdocs/data/ICE_FX_Indexes_Methodology.pdf) — geometric index description and component framework.
- [ICE USDX brochure](https://www.ice.com/publicdocs/ICE_USDX_Brochure.pdf) — proprietary-rights and express-consent notice.

## Risks and unknowns

- Exact DXY replication is blocked on licensing decision D-0016.
- The verified Bronze sample is one week for market data; seasonal quality thresholds must not be tuned as if it were the full six-year corpus.
- Robust spike thresholds need sensitivity reporting in later backtests; flagged data must remain visible under all thresholds.
- Session labels describe market context, not guaranteed venue liquidity or execution availability.
