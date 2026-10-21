[CmdletBinding()]
param(
    [string]$BronzeRoot,
    [string]$SilverRoot,
    [string]$ReportRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$arguments = @("run", "python", "-m", "tb.silver.pipeline")
if ($BronzeRoot) {
    $arguments += @("--bronze-root", $BronzeRoot)
}
if ($SilverRoot) {
    $arguments += @("--silver-root", $SilverRoot)
}
if ($ReportRoot) {
    $arguments += @("--report-root", $ReportRoot)
}

Push-Location -LiteralPath $repoRoot
try {
    & uv @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Silver build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
