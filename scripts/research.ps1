param(
    [string]$Python = '',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ResearchArguments
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (Test-Path -LiteralPath (Join-Path $repoRoot '.env')) {
    throw 'Use a separate credential-free research checkout.'
}
if (-not $Python) { $Python = Join-Path $repoRoot '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Provide an existing pinned Python 3.12 environment with -Python.' }
if (-not $ResearchArguments) { $ResearchArguments = @('status') }
$previousPath = $env:PYTHONPATH
Push-Location -LiteralPath $repoRoot
try {
    $env:PYTHONPATH = Join-Path $repoRoot 'src'
    if ($previousPath) { $env:PYTHONPATH += [IO.Path]::PathSeparator + $previousPath }
    & $Python -m tb.research.cli @ResearchArguments
    if ($LASTEXITCODE -ne 0) { throw 'Offline research command refused; see the static diagnostic above.' }
}
finally {
    $env:PYTHONPATH = $previousPath
    Pop-Location
}
