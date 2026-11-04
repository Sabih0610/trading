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

Data Health gains PAXG for the approved 2023/2024 years only. After Claude merged
H/I/J1/living, the unpublished K branch was rebased onto main 06467ef with no
conflict. The venue and Treasury health hooks, Treasury rights type and crypto
strategy deny-all policy remain intact. The narrow symbol-pattern overlap is
explicit in this diff; no shared living docs are edited on this branch.

See [research](../../docs/research/P11k-research.md),
[journal](../../docs/journal/P11k-journal.md), and
[runbook](../../docs/how-to/paxg-validation-data.md).

## Fixture validation

The new and adjacent tests passed 23 cases. The combined existing Vision, new
PAXG, Data Health and registry-config regressions passed 43 cases in 103.80s.
Ruff, formatting and strict mypy for all three changed source modules passed.
After rebasing onto main 06467ef, all-source Ruff/format passes on 580 files and
strict mypy remains clean for the three changed modules. Rebased source candidate
is `d7336327ed86e45bd1dbf6d424a95d9bd0935113` (tree
`7e59de7c091dcb5bfed8dcd867b57d11b26a5ec8`). Post-rebase regressions passed all
43 cases in 130.90s. The serialized full clean offline gate remains pending;
focused results do not claim it.

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

## Full gate interrupted for resource isolation

The clean d733632 gate passed Ruff/format (580 files) and strict mypy (206
sources). Its pytest run was deliberately interrupted at root's request on
2026-11-04 08:45 UTC when the separately registered G batch left insufficient RAM
for concurrent work. Only K's verified worker tree was stopped. The partial log
and interruption evidence are preserved privately; this is not a full-suite pass.
No acquisition or registration has started. K must rerun its full clean gate
alone after G completes, and pass it before the approved acquisition/build.


## Failed timing gate and merged G decision

The solo d733632 gate ended at 09:40 UTC with one timing-only Hypothesis failure
in `test_xaut_weekend_entries_always_fail`: initial 1271.87 ms versus the original
200 ms deadline, then 24.81 ms on replay. The result was 1 failed, 1580 passed,
2 skipped, 3 deselected, 2 xfailed, 23 warnings in 640.36s. The failed log and exit
record are preserved privately; no assertion or deadline has been weakened.
No acquisition followed this failed gate.

Claude subsequently approved/merged G on main 69034f6 with no promising candidate.
K validation is therefore skipped: **no promising gold candidate**. The independently
authorized acquisition still requires a genuine full clean pass before starting.
The unpublished K branch will rebase onto that merged main and verify the exact
property once before the original solo gate. No F/G result is rerun or relabelled.
