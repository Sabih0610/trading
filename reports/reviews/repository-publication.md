# Shared repository publication — 2026-10-27 UTC

The owner authorized committing and pushing completed, validated work for collaboration.
The publication branch is `codex/shared-research`, based on the existing remote `main` at
`6857b924229e29ed018a573d6abcd58ea61b2140`. Independent review remains pending.

## What was checked

- The 15 previously local phase commits and the RC documentation commit are preserved in order,
  with original messages and `Publication-Source` provenance trailers. Original local refs remain intact.
- Application source is identical at every one of the 16 compared phase snapshots. Only four MT5
  diagnostic JSON files differ: raw provider payloads are explicitly omitted from every public version.
- The outgoing 16-commit history contained 317 trees and 495 blobs. Exact checks against four
  locally configured private credential values and high-confidence credential patterns found no matches.
  Protected dataset/private runtime paths and unredacted MT5 price payloads were absent.
- New RC/collaboration documents passed privacy, JSON and 110 local-link checks; Git diff checks pass.
- The unchanged source previously passed the RC Windows gate: **937 passed, 3 live deselected,
  23 existing warnings**; Ruff, formatting, strict MyPy, safety smoke and all 14 owned paper cases pass.
  This publication does not claim a new full-suite run.
- Genuine-feed dashboard screenshots checked during publication display withheld/refused prices;
  no account credentials or numeric genuine quotes were shown in those views.

## Public commit provenance

Historical report SHAs and milestone tags identify original local review checkpoints. They were
not uploaded, because doing so would also upload original diagnostic payloads. Use this mapping
or the commit trailers to find the corresponding public phase snapshot.

| Original local commit | Public phase commit |
|---|---|
| `c35d7c7` | `7987d7d` |
| `a553490` | `30c7422` |
| `657a29e` | `02786fe` |
| `c3fb60c` | `d79c578` |
| `35cf719` | `68a72d8` |
| `44a4c4d` | `a1a92c4` |
| `9d5c777` | `77d41bb` |
| `45a6d5f` | `dbd7eca` |
| `20b710f` | `d00499b` |
| `e537d56` | `421bfff` |
| `15f9a80` | `bfc5dc8` |
| `cc5a4ea` | `bda9455` |
| `47e74fc` | `2731e50` |
| `b56cfb1` | `1e16790` |
| `b669d43` | `8a09ae0` |
| `32a2da7` | `1ac5d1d` |

## Boundaries and team workflow

`main` is preserved. Publish only the cleaned branch and later reviewed task branches; do not
push all original branches/tags. Head messages carry `[skip ci]` and pushes use `--no-follow-tags`
while hosted CI remains inactive. No provider activation, OAuth consent, external orders, risk
change, historical holdout access or subsequent phase implementation follows from publication.

The original credential-owning OAuth checkout and completed paper/validation worktrees remain
preserved. Credentials were compared in memory during the scan; no values or private hashes were
written into this record. See [CONTRIBUTING.md](../../CONTRIBUTING.md) and the
[RC report](../phases/P11b.1a-RC.md) for validation and remaining readiness work.
