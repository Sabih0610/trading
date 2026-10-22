# Trading Bot

A research-first intraday platform with XAUUSD/EURUSD local contract simulation and secondary Binance Spot research. It targets Shariah-compliant operation; project approval labels are not independent certification. The system is long-only, deterministic risk controls have final authority, and AI may only veto or reduce a candidate trade. External demo and real-money orders are disabled.

Development is organized as resumable phases P00-P14. Human-readable status is in [PROGRESS.md](PROGRESS.md), the exact resume point is in [docs/HANDOFF.md](docs/HANDOFF.md), and project rules are in [AGENTS.md](AGENTS.md).

## Bootstrap

From PowerShell 7 at the repository root:

```powershell
pwsh -ExecutionPolicy Bypass -NoProfile -File ".\scripts\setup.ps1"
uv run tb doctor
```

See [the bootstrap and doctor guide](docs/how-to/bootstrap-and-doctor.md) for prerequisites and troubleshooting.

## Safety baseline

- Existing Binance execution policy is Spot-only; gold/FX have separate local simulation permission.
- Long-only: buy an approved asset, then sell only what is owned.
- Research/paper defaults: 0.5% all-in planned risk, 2% daily equity-loss halt, 5% peak drawdown halt, 1.0x fully funded exposure, one position, trade-frequency limits and end-of-day flatness.
- Secrets only in ignored `.env`; all integrations are optional and tests require no keys or network.
- Final test data from 2025 onward is locked behind an explicit flag and audit log.

## Quality gate

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```

P00-P09.5 provide ingestion/cleaning, shared features, Spot backtesting, strategy/ML libraries,
the restricted AI arena, append-only evidence and local contract simulation. Empirical trading
value remains unproven. Start with the [offline alignment simulation](docs/how-to/alignment-simulation.md)
and the [integration roadmap](docs/P09.5-integration-spec.md). The dashboard and continuous feed/runner
remain future phases.
