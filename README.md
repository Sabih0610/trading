# Trading Bot

A research-first intraday platform with XAUUSD/EURUSD local contract simulation and secondary Binance Spot research. It targets Shariah-compliant operation; project approval labels are not independent certification. The system is long-only, deterministic risk controls have final authority, and AI may only veto or reduce a candidate trade. External demo and real-money orders are disabled.

Development is organized as resumable phases P00-P14. Human-readable status is in [PROGRESS.md](PROGRESS.md), the exact resume point is in [docs/HANDOFF.md](docs/HANDOFF.md), and project rules are in [AGENTS.md](AGENTS.md).

Working with a teammate: see [CONTRIBUTING.md](CONTRIBUTING.md) for the shared development branch,
clear commit messages, local checks and pull request workflow.

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

P00-P11a provide ingestion/cleaning, shared features, Spot backtesting, strategy/ML libraries,
the restricted AI arena, append-only evidence, local contract simulation, a read-only dashboard
and an optional read-only MT5 data collector with a constrained native MCP inspection proxy.
Empirical trading value remains unproven. Open the [dashboard guide](docs/how-to/dashboard.md),
[offline alignment simulation](docs/how-to/alignment-simulation.md) or
[integration roadmap](docs/P09.5-integration-spec.md). See the [MT5 feed guide](docs/how-to/mt5-market-feed.md)
for setup and actual limitations: current EURUSD timestamps are refused and hidden XAUUSD quotes
are unavailable. Persistent paper operation and external gateways remain future work.
