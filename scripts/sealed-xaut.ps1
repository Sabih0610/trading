param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (Test-Path -LiteralPath (Join-Path $repoRoot '.env')) { throw 'Use the credential-free task checkout.' }
if (-not $Python) { $Python = Join-Path $repoRoot '.venv/Scripts/python.exe' }
Push-Location -LiteralPath $repoRoot
try {
    while ($true) {
        & $Python -m tb.ingest.sealed_book --capture --seconds 86400 --root $repoRoot
        if ($LASTEXITCODE -ne 0) { throw 'Sealed collector stopped; Task Scheduler will retry.' }
    }
}
finally { Pop-Location }
