$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
try {
    $taskEnvPath = Join-Path $taskRoot '.env'
    if (Test-Path -LiteralPath $taskEnvPath) {
        $taskCurrentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        & icacls $taskEnvPath /inheritance:r /grant:r "*$($taskCurrentSid):(F)" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Credential file ACL update failed.' }
    }
    $taskUv = Get-Command uv -ErrorAction SilentlyContinue
    $taskUvPath = if ($taskUv) { $taskUv.Source } else { Join-Path $taskRoot 'work/tooling/Scripts/uv.exe' }
    & $taskUvPath run --locked python -m tb.ingest.mt5.setup
    if ($LASTEXITCODE -ne 0) { throw 'Restricted MT5 MCP setup was refused.' }
} finally { Pop-Location }
