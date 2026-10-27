[CmdletBinding()]
param([string]$OutputRoot = "reports/safety/P09.5")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repoRoot
try {
    & uv run --locked python -m tb.paper.smoke --output-root $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "Alignment smoke failed: $LASTEXITCODE" }
}
finally { Pop-Location }
