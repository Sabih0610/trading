param(
    [string]$Python = '',
    [string]$OutputRoot = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (Test-Path -LiteralPath (Join-Path $repoRoot '.env')) {
    throw 'Use a separate credential-free checkout for offline validation.'
}
if (-not $Python) { $Python = Join-Path $repoRoot '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'An existing Python 3.12 environment is required.' }
if (-not $OutputRoot) { $OutputRoot = Join-Path $repoRoot ('work/rc-validation/' + [guid]::NewGuid().ToString('N')) }
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$OutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$oldPath, $oldOffline, $oldUtf8 = $env:PYTHONPATH, $env:TB_OFFLINE_VALIDATION, $env:PYTHONUTF8
$results = [ordered]@{}
Push-Location -LiteralPath $repoRoot
try {
    $env:PYTHONPATH = (Join-Path $repoRoot 'src') + [IO.Path]::PathSeparator + (Join-Path $repoRoot 'scripts/offline_guard')
    $env:TB_OFFLINE_VALIDATION = '1'
    $env:PYTHONUTF8 = '1'
    $dependencyCheck = @'
import importlib.metadata as md
import sys, tomllib
from pathlib import Path
from packaging.requirements import Requirement
assert sys.version_info[:2] == (3,12)
config=tomllib.loads(Path('pyproject.toml').read_text())
requirements=config['project']['dependencies']+config['dependency-groups']['dev']
for text in requirements:
    requirement=Requirement(text)
    assert md.version(requirement.name) in requirement.specifier, requirement.name
try:
    sys.audit('socket.connect', None, ('203.0.113.1',443))
except RuntimeError:
    pass
else:
    raise AssertionError('offline network guard is not active')
print(f'{len(requirements)} installed direct pins match; Python external socket guard verified without a connection')
'@
    & $Python -c $dependencyCheck *> (Join-Path $OutputRoot 'dependencies.log')
    if ($LASTEXITCODE -ne 0) { throw 'Installed dependency or offline guard check failed.' }
    $results['dependencies'] = 'PASS'
    $checks = [ordered]@{
        lint = @('-m', 'ruff', 'check', '.')
        format = @('-m', 'ruff', 'format', '--check', '.')
        types = @('-m', 'mypy', 'src')
        tests = @('-m', 'pytest', '-q')
        smoke = @('-m', 'tb.paper.smoke', '--output-root', (Join-Path $OutputRoot 'smoke'))
        scenarios = @('-m', 'tb.paper.offline.cli', 'demo', '--output-root', (Join-Path $OutputRoot 'owned'))
    }
    foreach ($name in $checks.Keys) {
        Write-Output ('Running offline ' + $name)
        $arguments = $checks[$name]
        $timer = [Diagnostics.Stopwatch]::StartNew()
        & $Python @arguments *> (Join-Path $OutputRoot ($name + '.log'))
        $exitCode = $LASTEXITCODE
        $timer.Stop()
        $results[$name] = [ordered]@{ status = $(if ($exitCode -eq 0) { 'PASS' } else { 'FAIL' }); seconds = [math]::Round($timer.Elapsed.TotalSeconds, 2) }
        $results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputRoot 'quality.json') -Encoding utf8
        if ($exitCode -ne 0) { Get-Content -LiteralPath (Join-Path $OutputRoot ($name + '.log')) -Tail 60; throw ('Offline ' + $name + ' failed.') }
        Write-Output ('PASS ' + $name)
    }
    Write-Output ('Offline gates passed. Owned outputs: ' + $OutputRoot)
}
finally {
    $env:PYTHONPATH, $env:TB_OFFLINE_VALIDATION, $env:PYTHONUTF8 = $oldPath, $oldOffline, $oldUtf8
    Pop-Location
}
