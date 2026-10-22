[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 8501,
    [string]$ReportRoot = "reports/dashboard"
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repoRoot
try {
    $phaseUv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -eq $phaseUv) {
        $phaseUvPath = Join-Path $repoRoot 'work/tooling/Scripts/uv.exe'
        if (-not (Test-Path -LiteralPath $phaseUvPath)) { throw "Install uv first or run scripts/setup.ps1." }
    }
    else { $phaseUvPath = $phaseUv.Source }
    $env:TB_DASHBOARD_REPORT_ROOT = [IO.Path]::GetFullPath((Join-Path $repoRoot $ReportRoot))
    & $phaseUvPath run --locked streamlit run 'src/tb/dashboard/app.py' --server.address 127.0.0.1 --server.headless true --server.port $Port --browser.gatherUsageStats false
    if ($LASTEXITCODE -ne 0) { throw "Dashboard stopped with code $LASTEXITCODE" }
}
finally { Pop-Location }
