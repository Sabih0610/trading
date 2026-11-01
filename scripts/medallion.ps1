param(
    [string]$Python = '',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$MedallionArguments
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (Test-Path -LiteralPath (Join-Path $repoRoot '.env')) { throw 'Use a credential-free medallion checkout.' }
if (-not $Python) { $Python = Join-Path $repoRoot '.venv/Scripts/python.exe' }
if (-not $MedallionArguments) { $MedallionArguments = @('status') }
Push-Location -LiteralPath $repoRoot
try {
    & $Python -m tb.ingest.history.vision_cli @MedallionArguments
    if ($LASTEXITCODE -ne 0) { throw 'Medallion command refused; consult the diagnostic.' }
}
finally { Pop-Location }
