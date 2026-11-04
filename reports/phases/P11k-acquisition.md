# P11k acquisition: approved PAXG archive built privately

The approved PAXG archive is registered and all 13 monthly files are downloaded
privately with verified vendor checksums. Both yearly Silver/Gold generations and
metadata-only Data Health verification completed on 2026-11-04 at 13:01 UTC.
No PAXG price analysis or strategy evaluation has occurred. K validation is
skipped: **no promising gold candidate** after G's approved merge on main 69034f6.

- [x] Register only the owner/reviewer-approved dataset and original finite lifetime.
- [x] Keep PAXG data-only, not Shariah assessed, with no executable strategies.
- [x] Pass fixture scenarios, lint, format, strict typing and full clean gate.
- [x] Download and metadata-verify all 13 approved monthly archives privately.
- [x] Complete the serialized yearly Silver/Gold build and metadata verification.
- [ ] Publish the completed report/PR and empty P11k-acquisition.ready marker.

## Boundary and implementation

Dataset `binance-vision-paxg-1m-2023-12-2024` permits PAXGUSDT 1m only,
2023-12-01 through 2024-12-31 23:59 UTC. December 2023 is indicator warm-up only
and is never scored. Earlier PAXG history and any 2025 archive are refused before
network access. The original terms evidence and private rights remain under
`work/rights/` and `work/research/`; finite retention ends no later than 2028-11-01.

The admitted Vision path constructs a fixed monthly PAXG kline URL only after
exact plan authorization. The existing executable archive builder still rejects
PAXG through the deterministic data-only guard. Existing sequential downloads,
ZIP/CHECKSUM validation, immutable Bronze, bounded yearly feature construction
and current rights/lifetime checks remain intact. PAXG's registry has reference
instrument type, pending Shariah status, local simulation disabled, and an empty
strategy allowlist.

Data Health gains only PAXG 2023/2024 JSON metadata. The unpublished branch was
rebased onto merged main 69034f6, preserving venue and Treasury health hooks,
Treasury rights types, crypto strategy deny-all and all reviewed risk rules.
No shared living docs are edited on this branch.

## Validation evidence

Exact tested candidate: `dcf81c542a0eb9b139be5ae36e7bea2ae6351db5`, tree
`6358a97f80fab099f519249137f8a3cd0f8a8202`. Full clean gate ended
2026-11-04 12:20:28 UTC with exit code 0.

| Check | Result |
|---|---|
| Full pytest | 1753 passed, 2 skipped, 3 deselected, 2 xfailed; 23 warnings; 610.21s |
| Ruff / format | Clean; 603 files |
| Strict mypy | Clean; 214 sources |
| Safety smoke / owned acceptance | Passed; all 14 owned studies |
| Vision/PAXG/health/config focused regressions | 43 passed after rebase onto approved H/I/J1/living main |
| Test-only cold setup fix focused checks | 32 passed; all nine original risk property ASTs and 200 ms deadline unchanged |

The environmental skips are absent private `.env` and optional development-kit ZIP;
live tests stay deselected. D-3/D-4 remain explicit inherited xfails in this tested
candidate, handled by the separately authorized J2 track. No assertion or deadline
was weakened. [Aggregate gate record](../validation/P11k-acquisition/summary.json).

The first gate was interrupted at root's request under RAM pressure. A subsequent
solo gate exposed cold registry setup timing in the weekend property: 1271.87 ms
initially versus its 200 ms deadline, then 24.81 ms on replay. One unchanged isolated
run reproduced 315.66 ms initially versus 32.18 ms replay. Both failed traces are
preserved. Root reviewed the separate test-only nine-line fixture: create a fresh
XAUT asset, verify actual Saturday refusal, discard it before Hypothesis examples.
Every generated example still reloads real policy; all original function ASTs,
inputs, assertions and the 200 ms bound are unchanged. No risk/configuration logic
changed. The full gate above then passed.

Later K ADR renumbering (0026 to 0028) and local links are documentation only;
source/configuration/scripts/tests/lockfiles still match the tested candidate.
This pass covers the actual acquisition source. A later rebase onto merged J2
changes common source/test bytes and requires a fresh integration gate before publication.

## Private acquisition status

All 13 monthly archive manifests were complete at the metadata-only check on
2026-11-04 12:24:30 UTC. The checker confirmed exact months, symbol, source URLs,
policy identity and matching vendor/computed checksum metadata. Genuine archives,
Parquet, checksums, manifests and detailed quality artifacts remain ignored and
private. No price row, chart or strategy analysis was inspected.

The BelowNormal worker paused after download while J2/reliability full suites ran.
Root released the build slot after their actual completion. Worker 13356 started
on 2026-11-04 at 12:56:49 UTC and completed at 13:01:19 UTC. Metadata-only
verification confirmed two complete yearly generations and twelve outputs: Silver
1m and Gold 1m/5m/15m/1h/4h for each year, with both Data Health rows complete.
No PAXG price analysis, chart or strategy evaluation occurred. Original rights and
retention are unchanged; expiry is 2028-10-31T23:59:59.344655Z.
See the [metadata-only completion record](../validation/P11k-acquisition/completion.json).
The acquisition is complete; integration validation and publication are pending.

## Decisions, runbook and limits

[Research](../../docs/research/P11k-research.md) ·
[ADR 0028](../../docs/adr/0028-data-only-paxg-validation-archive.md) ·
[Journal](../../docs/journal/P11k-journal.md) ·
[Runbook](../../docs/how-to/paxg-validation-data.md).

PAXG can have a premium/discount to spot gold and does not establish XAUT liquidity.
There is no gold validation verdict from this acquisition. G produced no promising
candidate, so no K pre-registration or validation run is started. Stage 4, paper,
Testnet, external orders, holdout access, P14 unsealing and risk-limit changes remain
out of scope.

## Living-doc entries

Record K's private acquisition/build status and finite retention without publishing
genuine observations. Dukascopy consent is withdrawn. After completed build, record
K validation skipped: "no promising gold candidate". PAXG stays data-only with no
executable strategies; December 2023 is warm-up only. Queue the acquisition PR only
after the actual yearly build and metadata verification finish.
