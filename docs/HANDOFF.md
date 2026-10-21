# Current handoff

P02 is complete/tagged and P03 calendar/news ingestion is in progress. P03's current source/terms audit is recorded with decisions D-0013 through D-0015.

- Last completed step: verified official schedule contracts, Finance Calendar limits/attribution, GDELT terms/rate behavior, and live RSS endpoints; documented the comparison in `docs/research/P03-research.md`.
- Next step: add strict `CalendarEvent` and `NewsItem` schemas, deterministic identity/deduplication, official-source reconciliation, and DST tests before source adapters.
- Exact next command: create `src/tb/ingest/calendar/models.py`, `reconcile.py`, `src/tb/ingest/news/models.py`, and their unit/property tests.
- Open problems: Fair Economy live storage is terms-gated under D-0015. The full P02 transfer remains blocked on storage under D-0012; live FRED remains pending D-0011.
- Safety state: P03 sources are public read-only metadata. News ingestion will store headlines/links only, no article bodies; no source can create or modify a trade.
