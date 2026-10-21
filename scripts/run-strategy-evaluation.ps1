[CmdletBinding()]
param(
    [string]$Output = "reports/strategies/P07.md"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location -LiteralPath $repoRoot
try {
    & uv run python -m tb.strategies.evaluation --output $Output
    if ($LASTEXITCODE -ne 0) {
        throw "Strategy evaluation failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
