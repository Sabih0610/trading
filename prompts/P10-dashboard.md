# P10 — Read-only evidence dashboard

The owner's P10 brief supersedes this earlier prompt. Write-capable controls, pause/resume,
approvals and intervention writes are excluded. Use
`prompts/P10-read-only-dashboard-after-alignment.md`, `docs/how-to/dashboard.md` and
`reports/phases/P10.md` for the implemented scope, run instructions and actual evidence.

P10 reads isolated account exports, Parquet charts and SQLite journals. Synthetic evidence is
labelled; missing empirical results/current health remain unavailable. The UI must not construct
the journal writer, load credentials, call providers or submit any external order.

Further dashboard work follows AGENTS.md and prompts/_PROTOCOL.md. Stop at the requested phase;
P11 integrations require a new instruction.
