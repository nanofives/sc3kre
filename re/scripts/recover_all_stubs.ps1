<#
  recover_all_stubs.ps1 — recover GZCOM factory stubs across every imported module.

  BACKGROUND
  A GZCOM factory stub is reached only through its module's class-registration table, i.e. via a
  DATA reference. Ghidra's auto-analysis therefore often leaves it as a bare `LAB_*` with no
  function, and it is then completely absent from the text export. In SIMUI.DLL this hid 12 of
  the module's 40 registered classes.

  PIPELINE
    1. re\scripts\find_stub_gaps.py            -> re\scripts\stubs\<module>.txt (address lists)
    2. this script, per module:
         MakeFunctions.java @<list>            (MUTATES the program: runs WITHOUT -readOnly)
         ghidra_headless.ps1 -Export -Module   (refresh the text export)

  Long-running. Launch detached and watch the log:
    Start-Process pwsh -ArgumentList '-NoProfile','-File','re\scripts\recover_all_stubs.ps1' -WindowStyle Hidden
    Get-Content re\scripts\recover_stubs.log -Wait

  -Only <names>   restrict to a subset (module file names, e.g. SIMMISC.DLL)
  -SkipExport     create the functions but do not re-export (faster; export later in bulk)
#>
param(
  [string[]]$Only = @(),
  [switch]$SkipExport
)
$ErrorActionPreference = "Continue"
$Root     = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Log      = Join-Path $PSScriptRoot "recover_stubs.log"
$StubDir  = Join-Path $PSScriptRoot "stubs2"
$Ghidra   = Join-Path $Root "ghidra\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat"
$ProjDir  = Join-Path $Root "ghidra"
$Modules  = Join-Path $PSScriptRoot "modules.txt"

function Say([string]$m) {
  $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m
  Write-Host $line
  Add-Content $Log $line
}

# module file name -> ghidra project stem, from modules.txt plus the three done earlier
$all = @(Get-Content $Modules | Where-Object { $_.Trim() }) + @("SIMRCI.DLL", "SIMUTIL.DLL", "SimTransit.dll")
if ($Only.Count) { $all = $all | Where-Object { $Only -contains $_ } }

Say "=== stub recovery starting: $($all.Count) modules ==="
$totalCreated = 0; $touched = 0

foreach ($m in $all) {
  $stem = [IO.Path]::GetFileNameWithoutExtension($m)
  $list = Join-Path $StubDir "$($stem.ToLower()).txt"
  if (-not (Test-Path $list)) { Say "SKIP  $m (no gap list)"; continue }

  $n = (Get-Content $list | Where-Object { $_.Trim() }).Count
  Say "RECOVER $m — $n candidate addresses"

  $out = & $Ghidra $ProjDir "SC3_$stem" -process $m -noanalysis `
           -scriptPath $PSScriptRoot -postScript MakeFunctions.java "@$list" 2>&1
  $summary = $out | Select-String "MakeFunctions: created"
  if ($summary) {
    Say ("  " + ($summary.Line -replace '^INFO\s+', '' -replace '\s+\(GhidraScript\)\s*$', '' -replace '^MakeFunctions.java> ', ''))
    if ($summary.Line -match "created (\d+)") { $totalCreated += [int]$Matches[1]; if ([int]$Matches[1] -gt 0) { $touched++ } }
  } else {
    Say "  WARN no summary line — check the run"
  }

  if (-not $SkipExport) {
    & pwsh -NoProfile -File (Join-Path $PSScriptRoot "ghidra_headless.ps1") -Export -Module $m *>> $Log
    $c = (Get-ChildItem (Join-Path $Root "re\ghidra_export_$($stem.ToLower())\functions") -Filter *.c -ErrorAction SilentlyContinue).Count
    Say "  re-exported: $c functions"
  }
}

Say "=== finished: $totalCreated functions created across $touched modules ==="
