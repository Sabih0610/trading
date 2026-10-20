# Current handoff

P01 is committed/tagged and P02 historical-data ingestion is in progress. P02 has loaded its prompt and is beginning current source/format/terms research before implementation.

- Last completed step: P02 official-source research recorded with decisions D-0009–D-0011.
- Next step: add pinned HTTP/Parquet dependencies and implement/test the shared atomic download, retry, manifest, partition, and disk-estimation core before source adapters.
- Exact next command: update `pyproject.toml`, lock with uv, then add `src/tb/ingest/history/core.py` and offline tests.
- Open problems: live FRED use is pending an owner/legal scope decision; Dukascopy’s current official bulk route is credentialed requester-pays, so the keyless public feed is treated as best-effort. Neither blocks fixture-backed core/Binance/Dukascopy implementation.
- Safety state: P02 is public read-only ingestion; no keys or execution paths are in scope. The locked final period may be stored but must not be evaluated without the separate P07+ gate.
