# Trading Bot

A research-first, Shariah-compliant intraday trading system for approved Binance spot assets. The system is long-only, deterministic risk controls always have final authority, AI may only veto or reduce a candidate trade, and no real-money trading is allowed before backtests, scenario tests, and at least 30 days of paper trading pass review.

Development is organized as resumable phases P00-P14. Human-readable status is in [PROGRESS.md](PROGRESS.md), the exact resume point is in [docs/HANDOFF.md](docs/HANDOFF.md), and project rules are in [AGENTS.md](AGENTS.md).

## Bootstrap

From PowerShell 7:

```powershell
Set-Location -LiteralPath "E:\trading bot"
pwsh -ExecutionPolicy Bypass -NoProfile -File ".\scripts\setup.ps1"
uv run tb doctor
```

See [the bootstrap and doctor guide](docs/how-to/bootstrap-and-doctor.md) for prerequisites and troubleshooting.

## Safety baseline

- Binance spot only; no leverage, margin, futures, perpetuals, options, lending, staking, or borrowing.
- Long-only: buy an approved asset, then sell only what is owned.
- Deterministic limits: at most 1% equity risk per trade, 1.0x total exposure, daily loss limit, trade-frequency limit, and end-of-day flatness.
- Secrets only in ignored `.env`; all integrations are optional and tests require no keys or network.
- Final test data from 2025 onward is locked behind an explicit flag and audit log.

## Quality gate

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```

P00 currently provides project tooling, typed configuration, secret-redacting structured logs, UTC/DST helpers, the offline doctor command, and the package/folder skeleton. Trading and data features are introduced only in later reviewed phases.
