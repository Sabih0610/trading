param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (Test-Path -LiteralPath (Join-Path $repoRoot '.env')) { throw 'Use the credential-free task checkout.' }
if (-not $Python) { $Python = Join-Path $repoRoot '.venv/Scripts/python.exe' }
$runner = Join-Path $repoRoot 'scripts/sealed-xaut.ps1'
$pwsh = (Get-Command pwsh).Source
$taskName = 'TradingBot-P11d-Sealed-XAUT'
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $runner + '" -Python "' + $Python + '"'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and ($existing.Actions.Arguments -notlike ('*' + $runner + '*'))) {
    throw 'Existing task belongs to another checkout; refusing to overwrite it.'
}
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $arguments -WorkingDirectory $repoRoot
$triggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn))
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType S4U -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Owner-authorized XAUT capture only; archive sealed until P14; no analytical reads.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output 'Sealed XAUT task registered and started. Inspect only reports/data_quality/xaut-collector-health.json.'
