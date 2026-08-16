<#
  import_all_modules.ps1 — bulk-import the GZCOM director DLLs into Ghidra.

  Drives ghidra_headless.ps1 -Module for every module listed in re\scripts\modules.txt
  (one filename per line). Each module gets its own Ghidra project SC3_<stem> and export
  dir re\ghidra_export_<stem>. Already-exported modules are skipped, so the script is
  resumable — re-run it after an interruption and it picks up where it left off.

  Long-running (hours for the full set). Launch it DETACHED and watch the log:

    Start-Process pwsh -ArgumentList '-NoProfile','-File','re\scripts\import_all_modules.ps1' -WindowStyle Hidden
    Get-Content re\scripts\import_all.log -Wait

  -Only <names>   restrict to a subset (comma-separated filenames)
  -Force          re-import even if an export already exists
#>
param(
  [string[]]$Only = @(),
  [switch]$Force
)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Log  = Join-Path $PSScriptRoot "import_all.log"
$List = Join-Path $PSScriptRoot "modules.txt"

function Say([string]$m) {
  $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m
  Write-Host $line
  Add-Content $Log $line
}

$modules = Get-Content $List | Where-Object { $_.Trim() }
if ($Only.Count) { $modules = $modules | Where-Object { $Only -contains $_ } }

Say "=== bulk import starting: $($modules.Count) modules ==="
$ok = 0; $skip = 0; $fail = @()

foreach ($m in $modules) {
  $stem   = [IO.Path]::GetFileNameWithoutExtension($m)
  $expDir = Join-Path $Root "re\ghidra_export_$($stem.ToLower())\functions"

  if ((-not $Force) -and (Test-Path $expDir) -and (Get-ChildItem $expDir -Filter *.c -ErrorAction SilentlyContinue | Select-Object -First 1)) {
    Say "SKIP  $m (export already present)"; $skip++; continue
  }

  $t0 = Get-Date
  Say "IMPORT $m ..."
  & pwsh -NoProfile -File (Join-Path $PSScriptRoot "ghidra_headless.ps1") -Import -Module $m *>> $Log
  if ($LASTEXITCODE -ne 0) { Say "FAIL  $m (import exit $LASTEXITCODE)"; $fail += $m; continue }

  Say "EXPORT $m ..."
  & pwsh -NoProfile -File (Join-Path $PSScriptRoot "ghidra_headless.ps1") -Export -Module $m *>> $Log
  if ($LASTEXITCODE -ne 0) { Say "FAIL  $m (export exit $LASTEXITCODE)"; $fail += $m; continue }

  $n = (Get-ChildItem $expDir -Filter *.c -ErrorAction SilentlyContinue).Count
  Say ("DONE  {0} — {1} functions in {2:n1} min" -f $m, $n, ((Get-Date) - $t0).TotalMinutes)
  $ok++
}

Say "=== finished: $ok imported, $skip skipped, $($fail.Count) failed ==="
if ($fail.Count) { Say "failed: $($fail -join ', ')" }
