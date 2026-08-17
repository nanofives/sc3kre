<#
.SYNOPSIS
  Scenario runner for the SC3 launch harness. Runs each scenario K times with a
  FIXED duration (never waiting on a human to close the window), grades every run
  with harness_check.py, and classifies the results.

  This encodes the rule that cost the most time this session: a single run is not
  evidence. Every scenario is repeated and its runs are classified by verdict, so a
  transient (like U-032) shows up as a mixed batch instead of a false conclusion.

.EXAMPLE
  pwsh re/scripts/harness_run.ps1                     # the windowed scenarios, 3x each
  pwsh re/scripts/harness_run.ps1 -Scenario windowed-render -Runs 5
  pwsh re/scripts/harness_run.ps1 -Scenario fullscreen-baseline   # takes over the display
  pwsh re/scripts/harness_run.ps1 -List

.NOTES
  Exit 0 only if every run of every selected scenario is PASS.
#>
param(
  [string]$Scenario = "all",
  [int]$Runs = 3,
  [int]$Kill = 30,
  [switch]$List
)
$ErrorActionPreference = "Stop"
$repo   = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$launch = Join-Path $repo "re\harness\bin\sc3launch.exe"
$gz     = Join-Path $repo "re\harness\gz_draw.txt"
$check  = Join-Path $repo "re\scripts\harness_check.py"
$verify = Join-Path $repo "re\scripts\harness_patches.py"
$outdir = Join-Path $repo "re\harness\test_logs"

# Switch sets. Every scenario passes -gzlog so blt_disp_1 is measurable.
#
# Automatable render scenarios MUST use -nointro: without it the intro movie plays
# and suspends the renderer, and unattended nobody skips it, so blt_disp_1 stays 0 for
# the whole run (the primary shows the movie, not the menu). That is a true result, not
# a harness bug - it just means the plain windowed path needs a human to skip the movie
# and cannot be graded unattended. 'windowed-movie' is kept as an opt-in INTERACTIVE
# scenario for exactly that reason.
$scenarios = [ordered]@{
  "windowed-nointro"    = "-nocom -windowed -origin -fix16 -fitclient -nointro"  # the render test
  "fullscreen-nointro"  = "-nocom -nointro"                                       # opt-in, takes the display
  "windowed-movie"      = "-nocom -windowed -origin -fix16 -fitclient"            # opt-in, INTERACTIVE (skip the movie by hand)
}
$defaultSet = @("windowed-nointro")

if ($List) {
  $scenarios.GetEnumerator() | ForEach-Object {
    $inDefault = if ($defaultSet -contains $_.Key) { " (in 'all')" } else { " (opt-in)" }
    "{0,-22} {1}{2}" -f $_.Key, $_.Value, $inDefault
  }
  return
}

if (-not (Test-Path $launch)) { Write-Error "sc3launch.exe not found - build re/harness first"; exit 3 }
if (-not (Test-Path $gz))     { Write-Error "gz_draw.txt trace table not found at $gz"; exit 3 }
New-Item -ItemType Directory -Force -Path $outdir | Out-Null

# Pre-flight: verify the patch manifest against the on-disk binaries BEFORE spending
# any game runs. A drifted binary makes every scenario meaningless.
Write-Host "== pre-flight: verifying patch sites ==" -ForegroundColor Cyan
& python $verify
if ($LASTEXITCODE -ne 0) {
  Write-Error "patch manifest verification failed (exit $LASTEXITCODE) - aborting before any run."
  exit 2
}

$selected = if ($Scenario -eq "all") { $defaultSet } else { @($Scenario) }
foreach ($s in $selected) {
  if (-not $scenarios.Contains($s)) { Write-Error "unknown scenario '$s' (see -List)"; exit 3 }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$grand = 0
$summary = @()
foreach ($s in $selected) {
  $switches = $scenarios[$s]
  Write-Host "`n== scenario: $s ($switches), $Runs run(s), ${Kill}s each ==" -ForegroundColor Cyan
  $verdicts = @()
  for ($i = 1; $i -le $Runs; $i++) {
    $log = Join-Path $outdir ("{0}_{1}_run{2}.log" -f $s, $stamp, $i)
    $args = "$switches -gzlog `"$gz`" -kill $Kill -log `"$log`""
    Write-Host ("  run {0}/{1} ..." -f $i, $Runs) -NoNewline
    $so = Join-Path $outdir ("{0}_{1}_run{2}.stdout" -f $s, $stamp, $i)
    Start-Process -FilePath $launch -ArgumentList $args -Wait -NoNewWindow `
        -RedirectStandardOutput $so | Out-Null
    $out = (& python $check $log 2>&1 | Out-String)
    $verdict = "?"
    if ($out -match ": (PASS|FAIL|HARNESS-FAIL) ===") { $verdict = $Matches[1] }
    $col = @{ "PASS"="Green"; "FAIL"="Yellow"; "HARNESS-FAIL"="Red" }[$verdict]
    if (-not $col) { $col = "Red" }
    Write-Host (" {0}" -f $verdict) -ForegroundColor $col
    $verdicts += $verdict
  }
  $pass = ($verdicts | Where-Object { $_ -eq "PASS" }).Count
  $classes = ($verdicts | Group-Object | ForEach-Object { "{0}x{1}" -f $_.Count, $_.Name }) -join ", "
  $ok = ($pass -eq $Runs)
  if (-not $ok) { $grand = 1 }
  $summary += [pscustomobject]@{ Scenario=$s; Result=("{0}/{1} PASS" -f $pass, $Runs); Breakdown=$classes; OK=$ok }
}

Write-Host "`n== summary ==" -ForegroundColor Cyan
$summary | ForEach-Object {
  $mark = if ($_.OK) { "PASS" } else { "FAIL" }
  $col  = if ($_.OK) { "Green" } else { "Red" }
  Write-Host ("  [{0}] {1,-22} {2,-12} {3}" -f $mark, $_.Scenario, $_.Result, $_.Breakdown) -ForegroundColor $col
}
Write-Host ("`nlogs: {0}" -f $outdir)
exit $grand
