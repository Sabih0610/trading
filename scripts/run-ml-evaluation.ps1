[CmdletBinding()]
param(
    [string]$Output = "reports/ml/P08.md"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location -LiteralPath $repoRoot
try {
    & uv run python -m tb.ml.evaluation --output $Output
    if ($LASTEXITCODE -ne 0) {
        throw "ML evaluation failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
