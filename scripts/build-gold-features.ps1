[CmdletBinding()]
param(
    [string]$SilverRoot,
    [string]$GoldRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$arguments = @("run", "python", "-m", "tb.features.pipeline")
if ($SilverRoot) {
    $arguments += @("--silver-root", $SilverRoot)
}
if ($GoldRoot) {
    $arguments += @("--gold-root", $GoldRoot)
}

Push-Location -LiteralPath $repoRoot
try {
    & uv @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Gold feature build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
