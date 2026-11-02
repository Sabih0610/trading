param([Parameter(Mandatory)][string]$DataRoot)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$inputRoot = (Resolve-Path -LiteralPath $DataRoot).Path
if ((Test-Path -LiteralPath (Join-Path $repoRoot '.env')) -or
    (Test-Path -LiteralPath (Join-Path $inputRoot '.env'))) {
    throw 'Stage 3 requires credential-free checkouts.'
}
$python = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run uv sync --locked first.' }
$logRoot = Join-Path $repoRoot 'work/stage3-logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$process = Start-Process -FilePath $python -WindowStyle Hidden -WorkingDirectory $repoRoot `
    -ArgumentList @('-m', 'tb.backtest.stage3_runner', '--data-root', ('"' + $inputRoot + '"')) `
    -RedirectStandardOutput (Join-Path $logRoot ($stamp + '.out.log')) `
    -RedirectStandardError (Join-Path $logRoot ($stamp + '.err.log')) -PassThru
Write-Output ('Stage 3 background PID: ' + $process.Id)
Write-Output 'Resume by repeating this command with identical inputs and code. Never change the registration.'
