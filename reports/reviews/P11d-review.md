# P11d review — audit fixes, historical medallion, sealed forward capture

| Field | Value |
|---|---|
| Date | 2026-11-01 |
| Reviewer | Claude (reviewer role per `CLAUDE.md`, template `prompts/REVIEW_CLAUDE.md`) |
| Scope | [PR #3](https://github.com/Sabih0610/trading/pull/3), `origin/main` `66be38c` → `d00ee6e` (19 commits, 101 files, +3,403 / −139) |
| Verdict | **APPROVED WITH FIXES** — one major (collector file granularity), three minor; no blockers |

## 1. Rules audit

| Check | Result |
|---|---|
| Spot-only / long-only / no leverage | Unchanged. Scanner hardened (S-2): case-insensitive, `.py`/`.yaml`/`.ps1`, AST SDK-import check, order endpoints. |
| AI cannot create or enlarge trades | Unchanged. |
| Risk limits not bypassable | Strengthened: R-1 (XAUT weekend flag now enforced), R-2 (per-asset circuit limits). AGENTS.md §2 now states ceilings vs defaults correctly. |
| Secrets | S-3, S-4, S-5 fixed. No credential reads; collector refuses to run in a checkout containing `.env`. |
| Network in tests | S-6: telemetry disabled; default fixture denies non-loopback DNS/TCP/UDP. |
| Locked 2025+ data | Historical plans capped at `coverage_end < HOLDOUT` (`research/models.py`). Sealed forward data: every Parquet read in `src/` goes through `tb.core.holdout.read_unsealed_parquet` / `scan_unsealed_parquet` (only call sites of `pl.read_parquet`/`scan_parquet`; no DuckDB reads), which refuse `forward_sealed` by path, sidecar manifest, frame column and typed marker. `tests/scenario/test_forward_sealed.py` exercises the readers. |
| No orders | No order code added; collector is public WebSocket only. |

## 2. Audit-fix verification

- All `tests/review/full_audit/` changes are **decorator removals only** — no assertion or body edits (diff-checked; Codex's AST comparison agrees).
- Remaining strict xfails: R-3, R-4, D-3, D-4, S-1, plus environmental S-5 (owner `.env` ACL) — all minor, listed in `docs/pending.md`.
- Modified existing tests are legitimate consequences of the fixes: D-2 fixture moves its volume cap to the prior bar; D-5 expectation changes to fetch time with an added schedule assertion; T-1 adds explicit `.env` skips with reasons; T-2 replaces 20 s waits with a READY signal and 120 s cold-start bound. No test was weakened.

## 3. Findings

| ID | Severity | File:line | Description | Suggested fix |
|---|---|---|---|---|
| P11d-1 | **major** (operational) | `src/tb/ingest/sealed_book.py` (`flush`, triggered at `len(self.rows) >= 1000`) | The collector writes a new Parquet file **and** a manifest every 1,000 messages. Observed live: 1,118 files in ~83 minutes (~400 Parquet + 400 manifests per hour, ~10,000 file pairs/day, ~3.5 M/year). The prompt asked for hourly files. Because the archive is sealed and read-denied, it **cannot be compacted later** without breaching the seal, so the file count is permanent and will slow the eventual P14 read, backups and directory operations. | Flush on time, not message count: one file per 15 minutes (or per hour with a crash-safe staging file outside the sealed namespace), still sealed on write. Keep the 1,000-row path only as a memory cap with a much higher limit (e.g. 200k rows). Add a test asserting files per hour ≤ 4. Existing files can stay as they are. |
| P11d-2 | minor | `src/tb/research/registry.py` (`assert isinstance(policy, DatasetPolicy)`) | `assert` used for control-flow type narrowing; stripped under `python -O`. | Replace with an explicit `if not isinstance(...): raise ResearchRefused(...)`. |
| P11d-3 | minor (ops) | Task `TradingBot-P11d-Sealed-XAUT` → `E:\trading-p11d` | The collector runs from the PR's worktree. After merge that worktree must be kept and updated to `main` (the owner checkout has `.env`, which the collector refuses by design). Deleting or switching it stops capture. | Document `E:\trading-p11d` as the dedicated collector checkout in the how-to; update it with `git pull` after merge and restart the task. |
| P11d-4 | minor (ops) | `scripts/install-sealed-xaut-task.ps1` | Boot trigger fell back to logon-only because registration without elevation failed; capture stops while no user is logged on. | Owner decision: run the installer once as administrator if unattended capture after reboot is wanted. |

## 4. Live collector check (health file only; no sealed data read)

`reports/data_quality/xaut-collector-health.json` in `E:\trading-p11d`: started 2026-11-01 06:13 UTC, connected, heartbeat current, **0 reconnects, 0 sequence gaps**, `sealed: true`, ~5 MB written.

## 5. Gates (rerun independently on `d00ee6e` in a clean credential-free worktree)

| Gate | Result |
|---|---|
| `pytest` (default) | **1,253 passed**, 1 skipped (S-5 environmental, no `.env`), 3 live deselected, 5 xfailed (R-3, R-4, D-3, D-4, S-1) — 10 m 21 s |
| `ruff check` / `ruff format --check` | Clean / 293 files formatted |
| `mypy src` (strict) | Clean — 183 source files |

## 6. Recommendation

Merge: all gates pass, no rule is weakened, the seal is enforced at a single read choke-point, and
historical acquisition correctly stops at **BLOCKED — DATASET NOT AUTHORIZED** pending owner +
reviewer approval. Fix P11d-1 immediately afterwards — every hour of capture adds ~400 permanent
sealed files — then P11d-2/3; P11d-4 is an owner choice.
