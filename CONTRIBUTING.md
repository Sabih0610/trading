# Working together

The shared development branch is `codex/shared-research`. It contains the completed research,
offline paper engine and OAuth preparation, with release review evidence. Read [PROGRESS.md](PROGRESS.md)
and [the handoff](docs/HANDOFF.md) before starting. Independent review is still pending.

## Start a task

From PowerShell at your clone's root, fetch the latest work and create your own task branch:

```powershell
git fetch origin
git switch -c codex/your-task origin/codex/shared-research
```

Replace `codex/your-task` with a unique, descriptive name. Coordinate which files each person owns.
Keep unrelated edits separate; preserve other people's unfinished changes. Never reset, stash or
overwrite a coworker's work to make a command succeed.

## Commit completed work

The owner authorizes committing and pushing completed, validated task work to this repository.
Use small commits with plain descriptions of the change. Explain the reason and validation in the
body when useful. Examples:

- `fix(paper): refuse a duplicate intention after restart`
- `test(risk): cover loss shutdown after an adverse gap`
- `docs(oauth): explain the remaining owner setup steps`

For implementation changes, run the credential-free offline gate:

```powershell
pwsh -NoProfile -File './scripts/check-offline.ps1'
```

For documentation-only changes, check the diff, links and privacy. State when test results are from
an unchanged, previously validated source candidate rather than a fresh run.

Keep `.env`, account details, tokens, raw provider observations, datasets and local journals out of
Git. `.env.example` contains names with empty values only. Review the outgoing history as well as
the final diff before publishing; deleting sensitive content in a later commit does not remove it
from earlier commits.

## Share and review

Fetch before publishing, push your task branch without force, and open a pull request for review.
Do not merge `main` or rewrite a shared branch automatically. Do not push all local branches or
milestone tags: older local diagnostic history contains genuine observations excluded from the
public development branch. The original local branches and tags remain preserved.

Hosted Windows CI remains inactive pending its separate approval. Until then, include `[skip ci]`
in the pushed head commit message and use `git push --no-follow-tags`. This intentionally skips
hosted execution; it is not a hosted test pass. Do not change approval variables or billing.

Publication history preserves the phase order and original messages, with `Publication-Source`
trailers identifying local source commits. MT5 raw price payloads were removed throughout that
history. Original SHAs/tags in historical reports identify local review provenance and may not
resolve on GitHub. Application source is unchanged from the validated local candidate.

Committing code does not enable genuine providers, OAuth consent, paper integration or external
orders. Those boundaries remain governed by [AGENTS.md](AGENTS.md) and the phase reports.
