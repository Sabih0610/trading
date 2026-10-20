# P00 — Bootstrap the repository

Follow `prompts/_PROTOCOL.md`. Work in `E:\trading bot` (quote the path; it contains a space).

## Goal
A clean, typed, tested Python 3.12 project skeleton that runs on Windows 11 + PowerShell 7 with
zero API keys, plus the project skills installed.

## Research first
- Current best practice for `uv`-managed Python projects on Windows (lockfiles, scripts, `src/` layout).
- ruff, mypy (strict), pytest, hypothesis, pre-commit setup in 2026; pydantic-settings for `.env`.
- Structured logging best practice (e.g. structlog or stdlib JSON logging) with secret redaction.
- Windows pitfalls: paths with spaces, long-path support, CRLF, file locking, PowerShell execution policy.

## Build
1. `pyproject.toml` (uv), `src/tb/` package, the folder tree from AGENTS.md §5, `tests/` tree.
2. `src/tb/core/config.py`: pydantic-settings loading `.env` (optional keys → `None`), plus
   `config/*.yaml` loading with validation. A `features_enabled()` report that lists which
   integrations are ON/OFF based on keys present.
3. `src/tb/core/logging.py`: JSON logs to `logs/`, console pretty logs, automatic redaction of any
   value that looks like a key/secret.
4. `src/tb/core/timeutil.py`: all timestamps UTC (`datetime` aware + int64 ns for data), helpers
   for sessions in Europe/London and America/New_York with DST handled by zoneinfo.
5. `scripts/setup.ps1`: checks Python/uv/Node/Git, creates venv, installs deps, installs pre-commit,
   copies `.env.example` → `.env` only if `.env` does not exist (never overwrite).
6. `scripts/install-skills.ps1` is provided in the kit — run it, then write `docs/skills.md`
   listing each installed skill, its folder, what it is for, and what we must ignore in it
   (anything non-spot or leveraged). Review every skill's files before keeping it.
7. `tb` CLI (Typer) with `tb doctor` that prints environment, enabled features, disk space on E:,
   RAM, GPU (via `nvidia-smi` if present), and data folder status.

## Scenarios to self-test
No `.env` at all · `.env` with garbage lines · path with spaces · missing Node (skills script must
fail gracefully) · running `tb doctor` offline.

## Acceptance
`scripts/setup.ps1` works from a fresh clone; `uv run tb doctor` runs offline; ruff/mypy/pytest green;
`docs/skills.md` written; phase report written.
