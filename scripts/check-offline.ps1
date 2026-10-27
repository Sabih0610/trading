param([string]$Uv = 'uv', [string]$TemporaryRoot = '')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (Test-Path -LiteralPath (Join-Path $repoRoot '.env')) {
    throw 'Run offline validation in a separate checkout without a private .env.'
}
if (-not $TemporaryRoot) {
    $TemporaryRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
}
$temporaryBase = (Resolve-Path -LiteralPath $TemporaryRoot).Path
$outputRoot = Join-Path $temporaryBase ('tb-offline-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $outputRoot | Out-Null
$oldPythonPath = $env:PYTHONPATH
$oldOffline = $env:TB_OFFLINE_VALIDATION
$oldUvOffline = $env:UV_OFFLINE
$oldUtf8 = $env:PYTHONUTF8
Push-Location -LiteralPath $repoRoot
try {
    # Dependency installation is the only registry-network step. No provider keys are loaded.
    & $Uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Locked dependency sync failed.' }
    $env:UV_OFFLINE = '1'
    $env:TB_OFFLINE_VALIDATION = '1'
    $env:PYTHONPATH = Join-Path $repoRoot 'scripts/offline_guard'
    $env:PYTHONUTF8 = '1'
    & $Uv run --locked ruff check .
    if ($LASTEXITCODE -ne 0) { throw 'Ruff failed.' }
    & $Uv run --locked ruff format --check .
    if ($LASTEXITCODE -ne 0) { throw 'Formatting failed.' }
    & $Uv run --locked mypy src
    if ($LASTEXITCODE -ne 0) { throw 'MyPy failed.' }
    & $Uv run --locked pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Pytest failed.' }
    & $Uv run --locked python -m tb.paper.smoke --output-root (Join-Path $outputRoot 'smoke')
    if ($LASTEXITCODE -ne 0) { throw 'Paper safety smoke failed.' }
    & $Uv run --locked python -m tb.paper.offline.cli demo --output-root (Join-Path $outputRoot 'owned')
    if ($LASTEXITCODE -ne 0) { throw 'Owned acceptance failed.' }
    Write-Output ('Offline validation passed. Temporary owned outputs: ' + $outputRoot)
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    $env:TB_OFFLINE_VALIDATION = $oldOffline
    $env:UV_OFFLINE = $oldUvOffline
    $env:PYTHONUTF8 = $oldUtf8
    Pop-Location
}
