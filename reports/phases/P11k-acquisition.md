# P11k acquisition: PAXG proxy build

The owner replaced Dukascopy with an explicitly approved PAXG data-only archive.
This track adds the narrow acquisition boundary and metadata health support.
Genuine acquisition and the full clean gate are pending; no strategy evaluation,
price inspection or validation verdict has occurred.

- [x] Read owner/reviewer scope on main fb3de46 and inspect existing medallion.
- [x] Keep PAXG data-only, not Shariah assessed, with no executable strategies.
- [x] Add exact plan scope and fixture scenarios before provider acquisition.
- [x] Pass focused fixtures, lint, format and strict typing.
- [ ] Run the serialized full offline gate in a clean checkout.
- [ ] Copy existing terms evidence, register approval, acquire and build privately.
- [ ] Verify price-free metadata, publish and request Claude review.

The approved dataset is `binance-vision-paxg-1m-2023-12-2024`: PAXGUSDT 1m only,
2023-12-01 through 2024-12-31 23:59 UTC. The downloader keeps its sequential rate
limiting, checksum and resume behavior; the yearly builder keeps immutable raw
inputs and the shared causal FeatureEngine. The executable URL builder continues
to reject PAXG through the existing deterministic data-only guard.

Data Health gains PAXG for the approved 2023/2024 years only. This is a minimal
shared-file overlap with the open H/I tracks and must be reconciled during review;
no source from those tracks is silently copied or replaced. No shared living docs
are edited on this branch.

See [research](../../docs/research/P11k-research.md),
[journal](../../docs/journal/P11k-journal.md), and
[runbook](../../docs/how-to/paxg-validation-data.md).

## Fixture validation

The new and adjacent tests passed 23 cases. The combined existing Vision, new
PAXG, Data Health and registry-config regressions passed 43 cases in 103.80s.
Ruff, formatting and strict mypy for all three changed source modules passed.
The full clean offline gate remains pending; these focused results do not claim it.

## Living-doc entries

Record K acquisition as build-only and independent of G's result. Remove the old
Dukascopy-consent blocker: consent is withdrawn. Keep K validation gated on merged
G Part B, a promising gold candidate, frozen parameters, and an approved K
pre-registration. PAXG cannot become executable, and December 2023 is warm-up only.

## Remaining work

Serialize the full clean gate with the other tracks. Then
register the existing written approval and original terms evidence before any
network acquisition. Publish only documentary/aggregate build completion, with all
genuine data and detailed quality artifacts private. No strategy run is authorized.
