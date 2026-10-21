# Pending items

- Optional: run the Claude review for P00 from `prompts/REVIEW_CLAUDE.md`. P00 is queued but is not a mandatory stop gate.
- Optional: run the Claude review for P01 from `prompts/REVIEW_CLAUDE.md`. P01 is queued but is not a mandatory stop gate.
- Binance spot-specific skills were unavailable at the audited upstream revision. No action is required; later phases will use official documentation unless a compatible skill is reviewed.
- P02 needs an owner/legal scope decision before live FRED data is stored or used: the current FRED services terms restrict using FRED content in development or training of AI/software systems. Fixture-backed adapter work can continue; direct public-domain source alternatives should be preferred for later ML.
- P02's full six-year Binance/Dukascopy transfer needs a data volume with at least 779 GB free. The current volume has about 118 GB free, so the disk preflight correctly blocks the job. The verified seven-day sample remains available for P03/P04 development.
- P03 automated Fair Economy/Forex Factory storage is disabled pending a verifiable automated-use/reuse terms decision. The current-week endpoint is technically reachable, but P03 will not treat reachability as permission.
- P03's full GDELT headline archive is waiting for the public DOC API cooldown after repeated HTTP 429 responses. Rerun the documented `download-news.ps1 -Sources gdelt ... -Resume` command without reducing its five-second request gate.
- P04 exact DXY/USDX replication needs an owner/licensing decision. ICE's current official brochure says use of its formulation, components, weights, values, or calculation methods requires express written consent. Do not label a generic USD basket as DXY/USDX.
