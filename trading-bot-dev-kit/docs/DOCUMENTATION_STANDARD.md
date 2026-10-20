# Documentation standard (mandatory for every phase)

Goal: anyone (including the owner, who is not reading the code) can see what was done, why, how to
run it, and what's pending — at any moment, even mid-phase.

## Living files (update continuously)
| File | Content | When |
|---|---|---|
| `PROGRESS.md` | Table of all phases: status, dates, commit, report link, review status | At start and end of each phase |
| `docs/state/progress.json` | Machine-readable version of the same (used for resuming) | Same |
| `docs/HANDOFF.md` | Current state, last completed step, next exact step/command, open problems | End of every session and every phase |
| `CHANGELOG.md` | Human-readable list of what changed, per phase (Keep a Changelog style) | End of each phase |
| `docs/decisions/DECISIONS.md` | Decision log: ID, date, phase, decision, options considered, reason, link to ADR/research | Immediately when a decision is made |
| `docs/pending.md` | Things waiting on the human: keys, reviews, approvals, scholar questions | Whenever something becomes pending |
| `docs/review_queue.md` | Phases waiting for Claude review, with status | End of each phase |

## Per-phase files
| File | Content |
|---|---|
| `docs/journal/<PHASE>-journal.md` | Timestamped step log written DURING the phase: what you did, commands run, results, errors and how they were fixed (use the template) |
| `docs/research/<PHASE>-research.md` | Questions, options compared, sources with URLs and dates, chosen approach |
| `docs/adr/NNNN-title.md` | Architecture decision records for significant choices |
| `reports/phases/<PHASE>.md` | Final phase report: summary, files created, decisions, test + scenario results, limitations, how to run |
| `docs/how-to/<component>.md` | Plain-language guide for each runnable component: purpose, commands, inputs/outputs, troubleshooting |

## Style
- Plain language first, technical detail second. Start each document with a 3–5 line summary.
- Every command shown must be copy-pasteable PowerShell from the repo root (quote the path).
- Use UTC timestamps `YYYY-MM-DD HH:MM UTC`.
- Never put secrets in any document. Refer to keys only by variable name.
- Link related files instead of duplicating content.
