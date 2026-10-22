# ADR 0005: Read-only dashboard evidence boundary

Date: 2026-10-22. Status: accepted for P10.

The Streamlit process reads explicit report exports and a dedicated SQLite mode=ro connection.
It never constructs DecisionLedger, generates fixtures, reads credentials, changes policy or calls
providers/brokers. Filtering/pagination changes only the UI session state.

Source descriptors separate synthetic, historical real, shadow, local paper and future demo
evidence. Each account has one currency and a stored initial balance. Unavailable snapshots,
health and calibration stay unavailable; no account is combined with another demo or currency.

The application projects known safe fields instead of exposing arbitrary JSON. Source paths stay
within the selected report root. Real locked observations are refused before Parquet collection.
SQLite pages are bounded and ordered by rowid; summaries stream outcomes independently of pages.

Fixture generation is an explicit offline CLI using existing P09.5 tools, separate from dashboard
imports. Existing safety libraries and tests remain unchanged. See P10 research and phase report.
