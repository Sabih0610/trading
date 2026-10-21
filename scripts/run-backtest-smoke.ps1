[CmdletBinding()]
param(
    [string]$RunId = "P06-toy",
    [string]$OutputRoot = "reports/backtests",
    [ValidateSet("1", "1.5", "2", "3")]
    [string]$Stress = "1"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location -LiteralPath $repoRoot
try {
    & uv run python -m tb.backtest.smoke --run-id $RunId --output-root $OutputRoot --stress $Stress
    if ($LASTEXITCODE -ne 0) {
        throw "Backtest smoke run failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
