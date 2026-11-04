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

# Repo -> skills to take (names = folder names that contain SKILL.md).
# Binance's former spot/read-only skill folders were removed upstream as of the P00 audit,
# so no Binance skill is installed until a compatible replacement is reviewed.
$Revisions = @{
  'https://github.com/tradermonty/claude-trading-skills' = 'cb0f3aadffed6d1089db4b224162c964368baa46'
  'https://github.com/sickn33/antigravity-awesome-skills' = '32b8ad933cfb84065a4ce5304c2557c9e39b25fa'
}
$Wanted = [ordered]@{
  'https://github.com/tradermonty/claude-trading-skills'              = @('backtest-expert','market-news-analyst','market-environment-analysis')
  'https://github.com/sickn33/antigravity-awesome-skills'             = @('quant-analyst')
}
# Never copy these even if requested by mistake.
$Forbidden = 'derivatives|futures|margin|earn|loan|staking|options|meme|p2p|backtesting-trading-strategies'

foreach ($repo in $Wanted.Keys) {
  $name = ($repo -split '/')[-1]
  $dest = Join-Path $Src $name
  $revision = $Revisions[$repo]
  if ($revision -notmatch '^[0-9a-f]{40}$') { throw "Missing reviewed commit for $repo" }
  if (Test-Path -LiteralPath $dest) {
    $remote = git -C "$dest" remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $remote -ne $repo) { throw 'Skill cache origin mismatch.' }
    $changes = git -C "$dest" status --porcelain
    if ($LASTEXITCODE -ne 0 -or $changes) { throw 'Preserve modified skill cache; review it before installation.' }
  }
  else {
    git init "$dest" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Skill cache initialization failed.' }
    git -C "$dest" remote add origin "$repo"
    if ($LASTEXITCODE -ne 0) { throw 'Skill cache origin setup failed.' }
  }
  git -C "$dest" fetch --no-tags --depth 1 origin "$revision" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Reviewed skill revision fetch failed.' }
  git -C "$dest" checkout --detach "$revision" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Reviewed skill checkout failed.' }
  $actual = git -C "$dest" rev-parse HEAD
  if ($LASTEXITCODE -ne 0 -or $actual -ne $revision) { throw 'Skill revision identity mismatch.' }

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
      $resolvedTargetRoot = [IO.Path]::GetFullPath($t)
      $resolvedOutput = [IO.Path]::GetFullPath($out)
      if (-not $resolvedOutput.StartsWith($resolvedTargetRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Skill destination escaped its intended root.'
      }
      $targetPath = $resolvedOutput
      while ($targetPath -and $targetPath -ne $Root) {
        if ((Test-Path -LiteralPath $targetPath) -and (Get-Item -LiteralPath $targetPath).LinkType) {
          throw 'Linked skill destinations are refused.'
        }
        $targetPath = Split-Path -Parent $targetPath
      }
      if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Recurse -Force }
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
