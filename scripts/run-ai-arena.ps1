[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $RepoRoot
try {
    uv run python -m tb.agents.evaluation --root $RepoRoot
}
finally {
    Pop-Location
}
