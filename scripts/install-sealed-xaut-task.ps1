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
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$triggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn -User $user))
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Owner-authorized XAUT capture only; archive sealed until P14; no analytical reads.' -Force -ErrorAction Stop | Out-Null
    Write-Output 'Boot and logon triggers registered.'
}
catch {
    # Standard-user registration can run only after that user logs on; no elevation or password.
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $triggers = @(New-ScheduledTaskTrigger -AtLogOn -User $user)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Sealed XAUT capture; user-logon/crash recovery; boot trigger requires operator privileges.' -Force -ErrorAction Stop | Out-Null
    Write-Output 'User logon/crash task registered. Unattended boot registration requires operator privileges.'
}
Start-ScheduledTask -TaskName $taskName
Write-Output 'Sealed XAUT task registered and started. Inspect only reports/data_quality/xaut-collector-health.json.'
