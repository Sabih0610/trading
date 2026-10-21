[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [datetime]$From,
    [Parameter(Mandatory = $true)]
    [datetime]$To,
    [string[]]$Sources = @("gdelt", "federal_reserve", "ecb", "coindesk", "cointelegraph", "decrypt"),
    [switch]$Resume,
    [string]$BronzeRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    "run", "python", "-m", "tb.ingest.news.cli",
    "--sources", ($Sources -join ","),
    "--from", $From.ToString("yyyy-MM-dd"),
    "--to", $To.ToString("yyyy-MM-dd")
)
if ($Resume) {
    $arguments += "--resume"
}
if ($BronzeRoot) {
    $arguments += @("--bronze-root", $BronzeRoot)
}

Push-Location -LiteralPath $repoRoot
try {
    & uv @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "News download failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
