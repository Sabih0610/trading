[CmdletBinding()]
param(
    [string[]]$Sources = @("binance", "dukascopy"),
    [Parameter(Mandatory = $true)]
    [datetime]$From,
    [Parameter(Mandatory = $true)]
    [datetime]$To,
    [switch]$Resume,
    [switch]$Sample,
    [string]$BronzeRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    "run", "python", "-m", "tb.ingest.history.cli",
    "--sources", ($Sources -join ","),
    "--from", $From.ToString("yyyy-MM-dd"),
    "--to", $To.ToString("yyyy-MM-dd")
)
if ($Resume) {
    $arguments += "--resume"
}
if ($Sample) {
    $arguments += "--sample"
}
if ($BronzeRoot) {
    $arguments += @("--bronze-root", $BronzeRoot)
}

Push-Location -LiteralPath $repoRoot
try {
    & uv @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Historical download failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
