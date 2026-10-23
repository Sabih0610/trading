# Current handoff — P11a.1

P11a.1 is complete as a diagnostic/software deliverable, NOT DATA-QUALIFIED.
Branch codex/p11a-1-feed-qualification; local tag phase-P11a.1-done; parent c3fb60c.
Stop here. P11b is NO-GO and not started; no orders, EA, paid AI or 24/7 job.

- Owner manually disabled native trading/dangerous shell and showed exact XAUUSD. Native trading false and shell-tool absence verified; exact gold/FX metadata and changing raw quotes are available.
- Both SDK source epochs remain approximately +10800 seconds. Windows/Python/native UTC and independent Cloudflare/Microsoft clocks agree within uncertainty. W32Time service stopped; no automatic clock/service edits or guessed broker offset.
- Two bounded diagnostics at 11:53 and 12:00 UTC on 2026-10-23: four explicit samples per instrument in total, all future-timestamp rejected. Zero qualified quotes/candles/M5 intervals. Guarded 1800-second request refused with exit 2 before extended collection. Bronze raw/manifests preserved; Silver diagnostic admitted rows zero.
- Build 6281 / optional SDK 5.0.6231 / MetaQuotes-Demo / USD, fingerprint prefix 2699de315a80. No account number/name/balance in public reports.
- Four-tool Codex MCP config is installed/ignored; only fixed reads. Earlier Codex tools worked, but two final calls through the existing stdio session were refused. Fresh boundary client and SDK demo identity succeeded at handoff; cause/session renewal is unverified. See reports/mt5/P11a.1-handoff-connectivity.json. Credentials in ignored .env; inheritance disabled/current-user-only ACL verified. No token in changed public files. Hosted Market Data and MetaEditor availability remain unverified and are unnecessary for this collector.
- Fresh native security, identity, UTC reference and quote checks gate every genuine collector startup/poll. Unknown state fails closed; offline mocks remain keyless. Exact epoch parsing, receipt monotonic checks, hidden-symbol refusal, counts and normalized committed-row exports are implemented.
- Final full tests without optional SDK: 483 passed, 3 live deselected, 23 existing warnings, 54.44s. Strict MyPy clean (109 source files); Ruff/format and paper safety/offline smoke passed. Report details intermediate corrected failures. Optional SDK 5.0.6231 restored afterward using uv sync --locked --extra mt5.
- Dashboard at http://127.0.0.1:8501 is read-only; Market Feed shows separate safety/connection/validity and latest one-sample diagnostic counts. No invalid prices or account-P&L combination. Collector stopped. Desktop/mobile screenshots in reports/screenshots/P11a.1/.
- Need provider-supported UTC/DST contract or separately reviewed data-only alternative, valid 30-minute evidence/two M5 intervals, contract tick-value consistency, costs/pip/session/holiday/conversion and feasible funded 1x capital. Native blocking-call hard timeout requires future process supervision. No empirical reliability/performance claim.
- Read reports/phases/P11a.1.md, docs/research/P11a.1-research.md, docs/adr/0008-mt5-clock-and-security-admission.md, docs/how-to/mt5-feed-qualification.md and docs/P11b-proposal.md.
- Existing 2025+ holdout, risk/eligibility and previous P11a records unchanged. Original supplied audit remains untouched/untracked. Independent review queued; no push/PR requested.

Commands from repository root (PowerShell):

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.mt5.cli --offline --polls 3 --root 'work/P11a.1-offline'
& '.\work\tooling\Scripts\uv.exe' run --locked --extra mt5 python -m tb.ingest.mt5.diagnostics --samples 3
.\scripts\run-dashboard.ps1
```

Diagnostic-only exit 0 means a report was produced, not data qualification. Future --collect requires fresh admission and separate supervised use; current source fails. Do not rerun the old P11a smoke to overwrite its archived evidence. No further development until separately requested.
