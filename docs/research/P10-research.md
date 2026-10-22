# P10 research

Build a read-only evidence dashboard, reusing the existing accounting and risk system. Missing
accounts, health or empirical evaluation must remain unavailable. Synthetic fixture profitability
is isolated from real accounts and never becomes model accuracy or an empirical trial.

| Question | Compared choices | Selected approach |
|---|---|---|
| UI | Custom frontend; Streamlit | Owner-requested Streamlit 1.66.1 with native tables/Vega charts, bounded cached pure readers and AppTest. |
| SQLite | Existing DecisionLedger constructor; new read adapter | mode=ro + query_only, no schema initialization or migrations, no immutable flag on an active WAL database. |
| Large histories | Load all JSON/Parquet; bounded read | Keyset SQLite pagination; streaming aggregates; projected, filtered and capped lazy Parquet scans. |
| Evidence | Mix demo and real totals; isolated accounts | Explicit collection/source/mode/currency, independent metrics and missing-value states. |
| Unknown record fields | Render raw payloads; explicit projection | Display a small whitelist with text/token masking; never read .env or Settings. |
| Future P12 | Python direct; EA; hybrid | Compare separately in ADR; no sending code in P10. Single future order authority required. |

## Primary sources, accessed 2026-10-22

- Streamlit package/version: https://pypi.org/project/streamlit/ (1.66.1)
- AppTest: https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest
- Caching: https://docs.streamlit.io/develop/concepts/architecture/caching
- Vega charts: https://docs.streamlit.io/develop/api-reference/charts/st.vega_lite_chart
- SQLite WAL: https://www.sqlite.org/wal.html
- SQLite URI: https://www.sqlite.org/uri.html
- MetaQuotes Python interface: https://www.mql5.com/en/docs/python_metatrader5
- MetaQuotes order acknowledgement: https://www.mql5.com/en/docs/trading/ordersend
- MetaQuotes transaction events: https://www.mql5.com/en/docs/event_handlers/ontradetransaction

## Decisions and risks

Cache result data rather than live database handles, and invalidate using DB/WAL file stamps plus
a short TTL. Read-only WAL readers must include committed WAL state; immutable is inappropriate
for a database that another process can change. SQLite can maintain coordination sidecars even
for a read connection; evidence rows and schema must remain untouched.

Display metrics from stored account/outcome/marked-equity records, not guessed initial balances.
Closed-trade balance changes cannot establish intratrade maximum drawdown. Corrupt/incomplete
records invalidate affected metrics; pagination must not silently turn page totals into account totals.
Parquet is read only from explicitly indexed report exports with manifests; real 2025+ chart
observations remain blocked. No raw locked data is opened to populate the dashboard.

No terminal/broker feed, current latch, external account or actual model accuracy is inferred from
old synthetic records. Chart exports, snapshot contracts and P11 live health remain future inputs.
