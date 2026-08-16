<#
  ghidra_headless.ps1 — SimCity 3000 RE  (NO-MCP driver)

  One command to drive Ghidra headlessly. Usable by ANY Claude account/instance
  (incl. claude2 / the worker) with just shell access — no MCP server required.

  Actions:
    -Import     Create/refresh the SC3 Ghidra project and import original\SC3U.exe (full auto-analysis)
    -Export     Re-run ExportAllDecomp.java -> re\ghidra_export\ (the greppable offline model)
    -Count      Print the function-count breakdown
    -Script <Name.java> [-Args "..."]   Run any post-script against the analyzed program

  Examples:
    pwsh re\scripts\ghidra_headless.ps1 -Import
    pwsh re\scripts\ghidra_headless.ps1 -Export
    pwsh re\scripts\ghidra_headless.ps1 -Script CountFunctions.java -Args "re\analysis\functions.csv"
#>
param(
  [switch]$Import,
  [switch]$Export,
  [switch]$Count,
  [string]$Script,
  [string]$ScriptArgs = "",
  [switch]$IOS,
  [string]$Module = ""
)
$ErrorActionPreference = "Stop"
# This script lives in <project>\re\scripts\ — project root is two levels up.
$Root      = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Ghidra    = Join-Path $Root "ghidra\ghidra_12.1.2_PUBLIC"
$Headless  = Join-Path $Ghidra "support\analyzeHeadless.bat"
$ProjDir   = Join-Path $Root "ghidra"
$ScriptDir = $PSScriptRoot

# Target profile: -PC (default, SC3U.exe) | -IOS (armv7 cross-ref) | -Module <NAME.DLL> (GZCOM sim module)
if ($Module) {
  # GZCOM director module from Apps\ (see re\analysis\MODULE_MAP.md). The sim lives here,
  # NOT in SC3U.exe. Each module gets its own Ghidra project + export dir.
  $ModDir = Join-Path $Root "original\modules"
  if (-not (Test-Path $ModDir)) { New-Item -ItemType Directory -Force $ModDir | Out-Null }
  $Bin = Join-Path $ModDir $Module
  if (-not (Test-Path $Bin)) {
    # Anchor an untouched reference copy out of the live game install.
    $src = Join-Path $Root "Apps\$Module"
    if (-not (Test-Path $src)) { throw "module not found in Apps\: $Module" }
    Copy-Item $src $Bin
    $h = (Get-FileHash $Bin -Algorithm SHA256).Hash
    Write-Host "anchored $Module  SHA-256=$h" -ForegroundColor Yellow
    Add-Content (Join-Path $ModDir "ANCHORS.txt") "$Module  $h  $((Get-Item $Bin).Length) bytes"
  }
  $stem      = [IO.Path]::GetFileNameWithoutExtension($Module)
  $ProjName  = "SC3_$stem"
  $ProcName  = $Module
  $ExportDir = Join-Path $Root "re\ghidra_export_$($stem.ToLower())"
}
elseif ($IOS) {
  $ProjName  = "SC3iOS"
  $Bin       = Join-Path $Root "original\SimCity_DLX_armv7"
  $ProcName  = "SimCity_DLX_armv7"
  $ExportDir = Join-Path $Root "re\ghidra_export_ios"
} else {
  $ProjName  = "SC3"
  $Bin       = Join-Path $Root "original\SC3U.exe"
  $ProcName  = "SC3U.exe"
  $ExportDir = Join-Path $Root "re\ghidra_export"
}

if (-not (Test-Path $Headless)) { throw "Ghidra not found at $Headless — run install first." }

function Invoke-Headless([string[]]$hlArgs) {
  Write-Host ">> analyzeHeadless $($hlArgs -join ' ')" -ForegroundColor Cyan
  & $Headless @hlArgs
  if ($LASTEXITCODE -ne 0) { throw "analyzeHeadless exited $LASTEXITCODE" }
}

if ($Import) {
  # Fresh import + full analysis. -overwrite so re-runs re-baseline cleanly.
  Invoke-Headless @($ProjDir, $ProjName, "-import", $Bin, "-overwrite")
}
elseif ($Export) {
  Invoke-Headless @($ProjDir, $ProjName, "-process", $ProcName, "-noanalysis", "-readOnly",
                    "-scriptPath", $ScriptDir, "-postScript", "ExportAllDecomp.java", $ExportDir)
  Write-Host "Export -> $ExportDir" -ForegroundColor Green
}
elseif ($Count) {
  Invoke-Headless @($ProjDir, $ProjName, "-process", $ProcName, "-noanalysis", "-readOnly",
                    "-scriptPath", $ScriptDir, "-postScript", "CountFunctions.java")
}
elseif ($Script) {
  $post = @($ProjDir, $ProjName, "-process", $ProcName, "-noanalysis", "-readOnly",
            "-scriptPath", $ScriptDir, "-postScript", $Script)
  if ($ScriptArgs) { $post += $ScriptArgs.Split(" ") }
  Invoke-Headless $post
}
else {
  Write-Host "Specify one of: -Import | -Export | -Count | -Script <Name.java>"
}
