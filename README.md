# Trading Bot

A research-first intraday platform with XAUUSD/EURUSD local contract simulation and secondary Binance Spot research. It targets Shariah-compliant operation; project approval labels are not independent certification. The system is long-only, deterministic risk controls have final authority, and AI may only veto or reduce a candidate trade. External demo and real-money orders are disabled.

Development is organized as resumable phases P00-P14. Human-readable status is in [PROGRESS.md](PROGRESS.md), the exact resume point is in [docs/HANDOFF.md](docs/HANDOFF.md), and project rules are in [AGENTS.md](AGENTS.md).

Working with a teammate: see [CONTRIBUTING.md](CONTRIBUTING.md) for the shared development branch,
clear commit messages, local checks and pull request workflow.

P11c.0 adds the [offline local market-research workflow](docs/how-to/local-market-research.md):
owned CSV/Parquet demonstration, permission-gated historical registry/import,
frozen EMA/channel evaluation, replay, reports and the read-only Local Market Research view.
Genuine historical research is blocked until independently authorized data exists.
The current MVP is on `codex/p11c-0-research-mvp`, pending independent review.

## Install and run (Windows)

Prerequisites: **Windows 11, PowerShell 7, Git and [uv](https://docs.astral.sh/uv/getting-started/installation/)**.
If uv is missing, run `winget install --id astral-sh.uv -e`, then reopen PowerShell.
uv installs Python 3.12 and the project's locked dependencies:

```powershell
git clone --branch codex/p11c-0-research-mvp --single-branch https://github.com/Sabih0610/trading.git
Set-Location -LiteralPath '.\trading'
uv python install 3.12
uv sync --locked

# Check the environment, then generate and evaluate owned sample data.
.\.venv\Scripts\python.exe -m tb.cli doctor
pwsh -NoProfile -File '.\scripts\research.ps1' -ResearchArguments demo

# Start the read-only dashboard.
.\.venv\Scripts\python.exe -m streamlit run 'src/tb/dashboard/app.py' --server.address 127.0.0.1 --server.port 8501
```

Open **http://127.0.0.1:8501** and select **Local Market Research**. Stop the dashboard
with **Ctrl+C**. If port 8501 is occupied, use `--server.port 8502` and open that port.

Installation needs internet access for packages; the demo itself uses only generated
fixtures and needs **no API keys or `.env` file**. Its results are **SOFTWARE TEST ONLY**.
Use a fresh clone: research commands refuse a workspace containing `.env`; the older
`setup.ps1` creates one, so use the install commands above for this workflow.

To inspect readiness and retention without starting the dashboard:

```powershell
pwsh -NoProfile -File '.\scripts\research.ps1' -ResearchArguments status
pwsh -NoProfile -File '.\scripts\research.ps1' -ResearchArguments inventory
```

See the [research runbook](docs/how-to/local-market-research.md) for datasets, reports
and replay, or [bootstrap troubleshooting](docs/how-to/bootstrap-and-doctor.md).

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

The platform includes ingestion/cleaning, shared features, strategy/ML libraries,
append-only evidence, a persistent offline paper engine and permission-gated local
market research. Empirical trading value remains unproven; genuine datasets and
broker connectivity require separate qualification. External orders remain disabled.
See the [dashboard guide](docs/how-to/dashboard.md),
[Offline Paper Lab](docs/how-to/offline-paper-lab.md) and
[P11c.0 completion report](reports/phases/P11c.0.md) for scope and actual validation.
