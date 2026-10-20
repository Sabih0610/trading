# Current handoff

P01 is committed/tagged and P02 historical-data ingestion is in progress. P02 has loaded its prompt and is beginning current source/format/terms research before implementation.

- Last completed step: P02 shared atomic/retry/checksum/disk/partition/manifest core is green with 60 tests.
- Next step: implement fixture-backed Binance spot archive/REST, Dukascopy BI5, and gated FRED CSV adapters.
- Exact next command: add `src/tb/ingest/history/binance.py`, `dukascopy.py`, `fred.py` and their offline fixtures/tests.
- Open problems: live FRED use is pending an owner/legal scope decision; Dukascopy’s current official bulk route is credentialed requester-pays, so the keyless public feed is treated as best-effort. Neither blocks fixture-backed core/Binance/Dukascopy implementation.
- Safety state: P02 is public read-only ingestion; no keys or execution paths are in scope. The locked final period may be stored but must not be evaluated without the separate P07+ gate.
