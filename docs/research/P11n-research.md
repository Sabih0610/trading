# P11n research: causal daily/weekly derivation

Questions: how to anchor weeks, represent incomplete windows, retain availability,
bridge known market closures and preserve old registered intraday generations?
Existing Python 3.12, Polars and shared FeatureEngine remain pinned; no new package.

| Choice | Decision and reason |
|---|---|
| Windows | UTC midnight daily, Monday00:00 UTC weekly, left-closed/right-open. Publish availability only at the exclusive end. |
| Coverage | Count distinct expected source minutes. Retain incomplete/closed placeholders with null prices where no observation exists; never fill OHLC or volume. |
| Features | Opt-in FeatureEngine.update_swing; do not change native feature calculations/output schemas. Warm-up stays null; prior Donchian excludes signal bar; pivots appear after three later complete bars. |
| XAU calendar | Reuse the approved HistData source-week/US rollover model. Explicit dated closure evidence is frozen before data access; broker/CME calendars are reference evidence, not a guarantee about HistData quotes. Unexpected observations inside a closure are retained and flagged, not erased. |
| Publication | Separate swing-v1 generations/manifests so no existing F/G generation or checksum changes. |

Primary sources checked 2026-11-05:

- [Polars group_by_dynamic](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.group_by_dynamic.html): explicit closed/label/start_by behavior and Monday weekly windows.
- [HistData FAQ](https://www.histdata.com/f-a-q/): original data are source-specific; its static-EST text is superseded for this admitted dataset by the owner's byte-verified [clock decision](../../prompts/P11e-fix-histdata-clock.md). Preserve approved code semantics instead of reinterpreting timestamps.
- [XM official Christmas2021 schedule](https://www.xm.com/assets/pdf/new/holiday_schedule/2021/EN_XM-holiday-trading-hours-2021.pdf): gold/silver closedDecember24 while FX has a different early close, demonstrating instrument/provider-specific closures.
- [OANDA official hours](https://www.oanda.com/assets/documents/252/Hours_of_Operation.pdf): metals sessions and reference-market holidays require instrument-specific calendars.
- [CME holiday hours](https://www.cmegroup.com/trading-hours.html): holidays may have partial or full closures and schedules can change. It is not HistData spot-provider authority and is not substituted as such.

Unknown: HistData does not publish a complete historical spot-gold holiday schedule
at the FAQ. Exact reference closure overrides and their evidence must be frozen and
identified before the genuine build; unknown early closes remain conservative
coverage flags. No holiday is inferred from missing quotes or changed after results.
