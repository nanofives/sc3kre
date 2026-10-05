<#
  linux_import_all.ps1 - import every Loki Linux demo binary into Ghidra and dump matcher inputs.

  For each binary (sc3u_demo.x86 first: it DEFINES the GZ/RZ framework every library imports):
    ghidra_headless.ps1 -Linux <bin> -Import        (GCC 2.95 demangler pre-script)
    FuncFeatures.java  -> re\match_linux\lin_<stem>.tsv
    DumpElfVtables.java -> re\match_linux\lin_vt_<stem>.tsv
  Then, for every Windows module that has a Ghidra project, FuncFeatures -> re\match_linux\win_<stem>.tsv.

  Resumable: a binary whose lin_<stem>.tsv already exists is skipped. Each Ghidra project is separate, so
  -Throttle parallel workers never share a lock. Logs: log\linux_import\<stem>.log, summary in _status.txt.

    pwsh -NoProfile -File re\scripts\linux_import_all.ps1 [-Throttle 3] [-Only libSimUI.so,...]
#>
param([int]$Throttle = 3, [string[]]$Only = @())
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Drv  = Join-Path $PSScriptRoot "ghidra_headless.ps1"
$Out  = Join-Path $Root "re\match_linux"
$Log  = Join-Path $Root "log\linux_import"
New-Item -ItemType Directory -Force $Out, $Log | Out-Null
$status = Join-Path $Log "_status.txt"

$demo = Join-Path $Root "original\loki_demo\sc3u_demo"
$bins = @("sc3u_demo.x86") + (Get-ChildItem (Join-Path $demo "lib") -Filter *.so | Sort-Object Length -Descending | ForEach-Object Name)
if ($Only) { $bins = $bins | Where-Object { $Only -contains $_ } }

"$(Get-Date -Format s) START linux=$($bins.Count) throttle=$Throttle" | Add-Content $status

# The exe first and alone-ish: everything else imports from it, and it is the largest import.
$first = $bins | Select-Object -First 1
$rest  = $bins | Select-Object -Skip 1

$work = {
  param($bin, $Root, $Drv, $Out, $Log, $status)
  $stem = [IO.Path]::GetFileNameWithoutExtension($bin).ToLower()
  $feat = Join-Path $Out "lin_$stem.tsv"
  $vt   = Join-Path $Out "lin_vt_$stem.tsv"
  $lg   = Join-Path $Log "$stem.log"
  if (Test-Path $feat) { "$(Get-Date -Format s) SKIP $bin (features exist)" | Add-Content $status; return }
  $t0 = Get-Date
  try {
    & pwsh -NoProfile -File $Drv -Linux $bin -Import *>> $lg
    if ($LASTEXITCODE -ne 0) { throw "import exit $LASTEXITCODE" }
    & pwsh -NoProfile -File $Drv -Linux $bin -Script DumpElfVtables.java -ScriptArgs $vt *>> $lg
    & pwsh -NoProfile -File $Drv -Linux $bin -Script FuncFeatures.java -ScriptArgs $feat *>> $lg
    if (-not (Test-Path $feat)) { throw "no features written" }
    $n = (Get-Content $feat | Measure-Object -Line).Lines
    "$(Get-Date -Format s) OK   $bin  fns=$n  $([int]((Get-Date)-$t0).TotalMinutes) min" | Add-Content $status
  } catch {
    "$(Get-Date -Format s) FAIL $bin  $($_.Exception.Message)  (see $lg)" | Add-Content $status
  }
}

& $work $first $Root $Drv $Out $Log $status
# -Parallel refuses a ScriptBlock passed through $using: (measured 2026-10-05), so hand it over as text.
$workText = $work.ToString()
$rest | ForEach-Object -ThrottleLimit $Throttle -Parallel {
  & ([scriptblock]::Create($using:workText)) $_ $using:Root $using:Drv $using:Out $using:Log $using:status
}

# Windows side: features for every module with a Ghidra project (read-only; separate projects per module).
$mods = @("SC3U.exe") + (Get-ChildItem (Join-Path $Root "original\modules") -File | Where-Object { $_.Extension -match '(?i)\.dll' } | ForEach-Object Name)
$mods | ForEach-Object -ThrottleLimit $Throttle -Parallel {
  $m = $_; $stem = [IO.Path]::GetFileNameWithoutExtension($m).ToLower()
  $feat = Join-Path $using:Out "win_$stem.tsv"
  if (Test-Path $feat) { return }
  $lg = Join-Path $using:Log "win_$stem.log"
  if ($m -eq "SC3U.exe") { & pwsh -NoProfile -File $using:Drv -Script FuncFeatures.java -ScriptArgs $feat *>> $lg }
  else { & pwsh -NoProfile -File $using:Drv -Module $m -Script FuncFeatures.java -ScriptArgs $feat *>> $lg }
  $ok = Test-Path $feat
  "$(Get-Date -Format s) $(if ($ok) {'OK  '} else {'FAIL'}) win $m" | Add-Content $using:status
}
"$(Get-Date -Format s) DONE" | Add-Content $status
