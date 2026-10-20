# Bootstrap the project and run diagnostics

The setup script prepares a local Python 3.12 environment, installs the exact locked dependencies, creates empty local data directories, and installs pre-commit hooks. The doctor command then reports local environment, hardware, optional feature, and data-folder status without making network requests.

## Prerequisites

- Windows 11 and PowerShell 7
- Git
- uv (the script prints the official WinGet command if it is missing)
- Node is optional during P00; setup warns and continues when it is absent

From the repository root:

```powershell
Set-Location -LiteralPath "E:\trading bot"
pwsh -ExecutionPolicy Bypass -NoProfile -File ".\scripts\setup.ps1"
```

The `Bypass` setting applies only to this child PowerShell process. The setup script itself never changes user, machine, or Group Policy configuration.

If uv is missing:

```powershell
winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
```

Restart PowerShell after WinGet changes `PATH`, then rerun setup.

## Optional settings

On first run, setup copies `.env.example` to `.env` only if `.env` does not exist. All values are blank and every keyed integration remains OFF. Add values locally when a later phase requires them; never commit or paste the file into logs or chat.

Setup preserves an existing `.env` byte-for-byte. Blank values are treated as missing, not configured.

## Run the offline doctor

```powershell
Set-Location -LiteralPath "E:\trading bot"
uv run tb doctor
```

Doctor reports:

- project and Python versions;
- executable and repository paths;
- free disk and available/total RAM;
- NVIDIA GPU name/memory when `nvidia-smi` is available;
- ON/OFF state for optional integrations without revealing values;
- presence of `data/bronze`, `data/silver`, and `data/gold`;
- `Network Used: False` as an explicit offline assertion.

`ollama` can show ON with zero API keys because it is a local endpoint configured by `OLLAMA_HOST`; this does not mean the Ollama service is currently running.

## Run quality checks

```powershell
Set-Location -LiteralPath "E:\trading bot"
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
uv run pre-commit run --all-files
```

## Troubleshooting

- **Script is not digitally signed:** use the process-scoped command shown above. Do not change machine policy for this project.
- **`uv` is still missing after WinGet:** close and reopen PowerShell so the updated `PATH` is loaded.
- **Node warning:** core setup and doctor still work. Node-dependent optional skills remain unavailable.
- **Feature unexpectedly ON:** check only the corresponding variable name in `.env`; do not print its value. Blank entries are OFF.
- **Hardlink warning from uv:** the cache and `E:` project may be on different filesystems. uv safely falls back to copies; this affects speed, not correctness.
