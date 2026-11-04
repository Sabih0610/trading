# PAXG validation archive (build only)

Use a credential-free task checkout and the pinned environment. PAXG is a data-only
reference, never executable. This component downloads the approved 13 monthly
archives and builds yearly Silver/Gold using the existing shared feature engine.
It does not run a strategy or display prices.

The private proposal is `work/research/proposals/binance-vision-paxg-1m-2023-12-2024.json`.
It records the owner/reviewer approval, terms PDF evidence and SHA-256, and the
original finite lifetime ending 2028-11-01. Preserve the proposal, registry and
rights evidence; changing them invalidates existing admission.

From the credential-free checkout root:

```powershell
uv sync --locked
pwsh -NoProfile -File './scripts/medallion.ps1' register 'work/research/proposals/binance-vision-paxg-1m-2023-12-2024.json'
pwsh -NoProfile -File './scripts/medallion.ps1' download 'binance-vision-paxg-1m-2023-12-2024'
pwsh -NoProfile -File './scripts/medallion.ps1' build 'binance-vision-paxg-1m-2023-12-2024'
pwsh -NoProfile -File './scripts/medallion.ps1' status
```

Resume download with the same command; complete Bronze is verified before skipping.
Do not change the scope, request 2025, overwrite Bronze or bypass a checksum/rights
refusal. Build remains one bounded UTC year at a time, retaining causal feature
state between 2023 and 2024. Inspect Data Health JSON metadata only; keep genuine
archives, features and quality artifacts ignored and private.

December 2023 is indicator warm-up only and must never be scored. Opening prices,
charts or strategy analysis requires the later K pre-registration approval. That
registration can be prepared only after G Part B is merged and only if G marks a
candidate promising. A future result must be labelled "validated on PAXG proxy",
never "validated on XAUT". No validation run is enabled by these build commands.
