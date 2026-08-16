<#
  backup.ps1 — mirror the irreplaceable RE artifacts off the working drive.

  WHAT AND WHY. The public repo (github.com/nanofives/sc3kre) deliberately carries only
  tools + notes, so the expensive derived artifacts are versioned NOWHERE. This covers them:

    ghidra\*.rep, *.gpr   ~500 MB, 31 projects  — HOURS of Ghidra auto-analysis. The single
                                                  most expensive thing here. Regenerating means
                                                  re-importing 31 binaries and re-analysing.
    re\ghidra_export*\    ~? MB,  31 dirs       — the greppable decompilation. Regenerable from
                                                  the .rep projects, but only if those survive.
    re\data\              ~650 MB               — 63,691 rendered sprites + the record CSVs.
                                                  Regenerable from re\tools + the game install.
    re\analysis, re\tools, re\scripts, functions.csv, *.md
                                                — cheap, and also in git; copied anyway so a
                                                  restore is self-contained.

  NOT copied: ghidra\ghidra_12.1.2_PUBLIC\ (872 MB, just re-download it) and the retail game
  install (Apps\ Cities\ Buildings\ Scripts\ IPA\ original\ and the loose *.exe/*.dll) — that
  is EA/Maxis property, it came from GOG, and copying it around is not our business.

  Uses robocopy /MIR, so re-runs are incremental: only changed files move.
  /MIR DELETES files at the destination that are gone from the source -- that is the point of a
  mirror, but it means the destination is not an archive of history. Pass -NoMirror for /E.

  Usage:
    pwsh -NoProfile -File re\scripts\backup.ps1                 # to the default destination
    pwsh -NoProfile -File re\scripts\backup.ps1 -Dest E:\bk     # elsewhere
    pwsh -NoProfile -File re\scripts\backup.ps1 -WhatIf         # list only, copy nothing
#>
param(
  [string]$Dest = "D:\Backups\Simcity-RE",
  [switch]$NoMirror,
  [switch]$WhatIf
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# source (relative to $Root) -> destination subfolder
$jobs = @(
  @{ Src = "ghidra";      Dst = "ghidra";      Xd = @("ghidra_12.1.2_PUBLIC") },
  @{ Src = "re";          Dst = "re";          Xd = @("sessions") },
  @{ Src = ".";           Dst = "root";        Files = @("*.md", "functions.csv"); NoRecurse = $true }
)

$mode = if ($NoMirror) { "/E" } else { "/MIR" }
if (-not (Test-Path $Dest)) {
  if ($WhatIf) { Write-Host "would create $Dest" -ForegroundColor Yellow }
  else { New-Item -ItemType Directory -Force $Dest | Out-Null }
}

$total = 0
foreach ($j in $jobs) {
  $src = Join-Path $Root $j.Src
  $dst = Join-Path $Dest $j.Dst
  $args = @($src, $dst)
  # robocopy grammar is: robocopy <src> <dst> [file ...] [options]. NEVER put an empty string
  # in here -- an empty argument breaks the file-filter parse and robocopy silently falls back
  # to *.*, which on the project root means copying the whole retail game (caught by -WhatIf:
  # 33 files / 380 MB instead of the intended handful of .md).
  if ($j.Files) { $args += $j.Files }
  if (-not $j.NoRecurse) { $args += $mode }
  $args += @("/NFL", "/NDL", "/NJH", "/R:1", "/W:1", "/MT:8")
  foreach ($x in ($j.Xd | Where-Object { $_ })) { $args += @("/XD", (Join-Path $src $x)) }
  if ($WhatIf) { $args += "/L" }

  Write-Host ">> robocopy $($j.Src) -> $dst" -ForegroundColor Cyan
  & robocopy @args | Select-Object -Last 6
  # robocopy exit codes: 0-7 are success (8+ = failure). 1=copied, 2=extra, 4=mismatch.
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $($j.Src) with exit $LASTEXITCODE" }
  $total += $LASTEXITCODE
}

if (-not $WhatIf) {
  $sz = (Get-ChildItem $Dest -Recurse -File -ErrorAction SilentlyContinue |
         Measure-Object Length -Sum).Sum
  Write-Host ("`nbackup at {0}: {1:N0} MB" -f $Dest, ($sz / 1MB)) -ForegroundColor Green
  Set-Content (Join-Path $Dest "BACKUP_INFO.txt") @"
SimCity 3000 RE — artifact backup
written: $(Get-Date -Format o)
source : $Root
mode   : $mode

Contains the artifacts that are versioned nowhere else:
  ghidra\*.rep + *.gpr   Ghidra analysis projects (the expensive one — hours of auto-analysis)
  re\ghidra_export*\     greppable decompilation
  re\data\               rendered sprites + record CSVs
  re\analysis|tools|scripts, functions.csv, *.md   (also on github.com/nanofives/sc3kre)

Deliberately excluded: the Ghidra installer, and the retail game install (EA/Maxis property).
Restore = copy back over a fresh checkout of the repo, then re-place the game install yourself.
"@
}
