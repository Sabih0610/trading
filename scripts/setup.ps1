<#
.SYNOPSIS
  Prepare the Trading Bot development environment on Windows.

.DESCRIPTION
  Checks prerequisites, asks uv to provision Python 3.12, synchronizes the locked
  environment, installs pre-commit hooks, and creates .env from .env.example only
  when .env does not already exist. It never changes PowerShell execution policy.
#>
[CmdletBinding()]
param([switch]$SkipPreCommit)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Get-RequiredCommand {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$InstallHint
    )

    $Resolved = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Resolved) {
        throw "Required command '$Name' was not found. $InstallHint"
    }
    return $Resolved
}

Write-Host "Trading Bot setup: $ProjectRoot" -ForegroundColor Cyan
Write-Host "PowerShell: $($PSVersionTable.PSVersion)"
Write-Host "Execution policy: $(Get-ExecutionPolicy) (setup will not change it)"

$UvCommand = Get-RequiredCommand -Name 'uv' -InstallHint 'Install with: winget install --id astral-sh.uv -e'
$GitCommand = Get-RequiredCommand -Name 'git' -InstallHint 'Install with: winget install --id Git.Git -e'
$PythonCommand = Get-Command 'python' -ErrorAction SilentlyContinue
$NodeCommand = Get-Command 'node' -ErrorAction SilentlyContinue

Write-Host "uv: $(& $UvCommand.Source --version)"
Write-Host "git: $(& $GitCommand.Source --version)"
if ($PythonCommand) { Write-Host "system Python: $(& $PythonCommand.Source --version)" }
else { Write-Warning 'System Python is missing; uv will install managed Python 3.12.' }
if ($NodeCommand) { Write-Host "Node: $(& $NodeCommand.Source --version)" }
else { Write-Warning 'Node is missing. Core setup continues; Node-dependent optional skills are unavailable.' }

Push-Location -LiteralPath $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        Write-Host 'Created .env from .env.example (all keys remain empty).' -ForegroundColor Green
    }
    else {
        Write-Host 'Preserved existing .env.' -ForegroundColor Green
    }

    foreach ($Directory in @('data\bronze', 'data\silver', 'data\gold', 'logs')) {
        New-Item -ItemType Directory -Force -Path $Directory | Out-Null
    }

    & $UvCommand.Source python install 3.12
    if ($LASTEXITCODE -ne 0) { throw 'uv could not install or find Python 3.12.' }
    & $UvCommand.Source sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }

    if (-not $SkipPreCommit) {
        & $UvCommand.Source run pre-commit install
        if ($LASTEXITCODE -ne 0) { throw 'pre-commit hook installation failed.' }
    }
}
finally {
    Pop-Location
}

Write-Host 'Setup complete. Run: uv run tb doctor' -ForegroundColor Green
