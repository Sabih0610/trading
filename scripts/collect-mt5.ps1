param(
    [ValidateRange(1, 17280)][int]$Polls = 2,
    [switch]$Offline,
    [switch]$TickHistory,
    [string]$OutputRoot = '.'
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
try {
    $taskUv = Get-Command uv -ErrorAction SilentlyContinue
    $taskUvPath = if ($taskUv) { $taskUv.Source } else { Join-Path $taskRoot 'work/tooling/Scripts/uv.exe' }
    $taskArgs = @('run', '--locked', 'python', '-m', 'tb.ingest.mt5.cli', '--polls', "$Polls", '--root', $OutputRoot)
    if ($Offline) { $taskArgs += '--offline' }
    if ($TickHistory) { $taskArgs += '--tick-history' }
    & $taskUvPath @taskArgs
    if ($LASTEXITCODE -ne 0) { throw 'Read-only market collection was unavailable or refused.' }
} finally { Pop-Location }
