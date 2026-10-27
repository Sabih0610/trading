# P10 — Read-only evidence dashboard after P09.5

Continue this repository without rebuilding P00-P09.5. Read AGENTS.md, prompts/_PROTOCOL.md,
docs/DOCUMENTATION_STANDARD.md, docs/HANDOFF.md, reports/phases/P09.5.md and
docs/P09.5-integration-spec.md first. Follow the installed trading-bot-rules skill.

Build a read-only Streamlit monitoring dashboard using src/tb/core/contracts.py::DashboardSnapshot.
Use repository-relative paths, immutable report/ledger reads and mockable data access. Identify
each panel as synthetic, historical real, shadow, local paper or broker demo. Display zero
empirical strategy trials and zero market-trained models accurately; mock arena output proves
mechanics only. Include data source, coverage, freshness, checksum/provenance, equity/drawdown,
positions/rejections/shutdowns, news and provider enablement/cost status, and unresolved reviews.

Use reports/safety/P09.5 only as explicitly synthetic example data. Missing reports/volumes must
show unavailable, not fabricated metrics. Never open locked market observations to populate charts.
Do not load or display secrets. No order buttons, routing clients, policy-edit controls, paid API
calls or final-test access. Keep broker-demo and live eligibility false.

Test the report reader and status distinctions, empty/malformed/stale files, append-only ledger
reads, no keys and Windows paths with spaces. Verify UI in a browser and run the complete quality
gate; update all mandatory phase documents. Stop after P10 and report actual checks and limitations.
