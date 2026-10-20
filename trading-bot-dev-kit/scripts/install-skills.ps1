<#
.SYNOPSIS
  Installs the project skill and selected third-party skills for Codex (.agents/skills) and
  Claude Code (.claude/skills). Third-party repos are cloned into .cache/skill-sources so you
  can REVIEW them; only the named skill folders are copied. Nothing is executed from them.

.EXAMPLE
  pwsh -File ".\scripts\install-skills.ps1"            # clone + copy
  pwsh -File ".\scripts\install-skills.ps1" -ListOnly  # clone and list available skills only
#>
[CmdletBinding()]
param([switch]$ListOnly)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Src  = Join-Path $Root '.cache\skill-sources'
$Targets = @((Join-Path $Root '.agents\skills'), (Join-Path $Root '.claude\skills'))

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git is required (winget install Git.Git).' }
New-Item -ItemType Directory -Force -Path $Src | Out-Null
$Targets | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

# Repo -> skills to take (names = folder names that contain SKILL.md). Spot/read-only only.
$Wanted = [ordered]@{
  'https://github.com/binance/binance-skills-hub'                     = @('spot','sub-account','assets','algo','p2p')
  'https://github.com/tradermonty/claude-trading-skills'              = @('backtest-expert','market-news-analyst','market-environment-analysis')
  'https://github.com/sickn33/antigravity-awesome-skills'             = @('quant-analyst')
  'https://github.com/jeremylongshore/claude-code-plugins-plus-skills' = @('backtesting-trading-strategies')
}
# Never copy these even if requested by mistake.
$Forbidden = 'derivatives|futures|margin|earn|loan|staking|options|meme'

foreach ($repo in $Wanted.Keys) {
  $name = ($repo -split '/')[-1]
  $dest = Join-Path $Src $name
  if (Test-Path $dest) { git -C "$dest" pull --ff-only | Out-Null }
  else { git clone --depth 1 "$repo" "$dest" | Out-Null }

  $available = Get-ChildItem -Path "$dest" -Recurse -Filter 'SKILL.md' -File |
               ForEach-Object { $_.Directory }
  Write-Host "`n== $name : $($available.Count) skills found" -ForegroundColor Cyan
  if ($ListOnly) { $available | ForEach-Object { Write-Host "   $($_.Name)" }; continue }

  foreach ($skill in $Wanted[$repo]) {
    if ($skill -match $Forbidden) { Write-Warning "Skipping forbidden skill '$skill'"; continue }
    $dir = $available | Where-Object { $_.Name -eq $skill } | Select-Object -First 1
    if (-not $dir) { Write-Warning "Skill '$skill' not found in $name (repo layout may have changed)"; continue }
    foreach ($t in $Targets) {
      $out = Join-Path $t $skill
      if (Test-Path $out) { Remove-Item -Recurse -Force "$out" }
      Copy-Item -Recurse -Path $dir.FullName -Destination "$out"
    }
    Write-Host "   installed $skill" -ForegroundColor Green
  }
}

# Project skill: keep .claude copy in sync with the .agents original.
$proj = Join-Path $Root '.agents\skills\trading-bot-rules'
if (Test-Path $proj) {
  Copy-Item -Recurse -Force -Path "$proj" -Destination (Join-Path $Root '.claude\skills')
  Write-Host "`nProject skill 'trading-bot-rules' synced to .claude/skills" -ForegroundColor Green
}
Write-Host "`nREVIEW every copied skill (SKILL.md and any scripts) before use. See docs/skills.md." -ForegroundColor Yellow
