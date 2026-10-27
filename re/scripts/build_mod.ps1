<#
.SYNOPSIS
  Build one mod DLL (or mods_launch.exe) from any source folder into any output folder.

.DESCRIPTION
  The per-mod scripts in re/harness/build_*.ps1 are gitignored and always write to re/harness/bin, which every
  session shares. This one is tracked, so it exists in a git worktree too, and it writes where you tell it:
  a child session builds from its own worktree into its own instance folder (re/harness/inst_<name>/) and never
  touches bin/, obj/ or combo/. Same compiler flags as the per-mod scripts.

.EXAMPLE
  pwsh re/scripts/build_mod.ps1 -Mod sc3resize -Src <worktree>\re\harness\src -Out re\harness\inst_query
  pwsh re/scripts/build_mod.ps1 -Mod mods_launch -Src re\harness\src -Out re\harness\inst_query
#>
param(
    [Parameter(Mandatory)] [ValidateSet('sc3resize', 'sc3bigcity', 'sc3overscroll', 'sc3simrun', 'sc3perf', 'sc3netmod', 'sc3cartrips', 'sc3undo', 'sc3autosave', 'mods_launch', 'sc3mods')]
    [string] $Mod,
    [Parameter(Mandatory)] [string] $Src,
    [Parameter(Mandatory)] [string] $Out
)
$ErrorActionPreference = 'Stop'
$Src = (Resolve-Path $Src).Path
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Out = (Resolve-Path $Out).Path
$obj = Join-Path $Out "obj_$Mod"
New-Item -ItemType Directory -Force -Path $obj | Out-Null

$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path $vswhere)) { throw "vswhere.exe not found" }
$vsroot = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsroot) { $vsroot = (& $vswhere -products * -property installationPath | Select-Object -First 1) }
$vcvars = Join-Path $vsroot 'VC\Auxiliary\Build\vcvars32.bat'
if (-not (Test-Path $vcvars)) { throw "vcvars32.bat not found at $vcvars" }

$cl = '/nologo /W3 /O2 /MT /GS- /D_CRT_SECURE_NO_WARNINGS /DWIN32 /D_WIN32_WINNT=0x0501'
if ($Mod -eq 'mods_launch') {
    $line = "cl $cl `"$Src\mods_launch.c`" /Fe`"$Out\mods_launch.exe`" /link /SUBSYSTEM:CONSOLE kernel32.lib"
} elseif ($Mod -eq 'sc3mods') {
    # The mod loader (2026-10-27, replaces the version.dll proxy): Apps\sc3mods.dll, imported by an SC3U.exe that
    # re/scripts/sc3mods_patch.ps1 has patched.
    $line = "cl $cl /LD `"$Src\sc3mods.c`" /Fe`"$Out\sc3mods.dll`" /link /SUBSYSTEM:WINDOWS /DEF:`"$Src\sc3mods.def`" kernel32.lib"
} else {
    $libs = 'kernel32.lib user32.lib' + $(if ($Mod -eq 'sc3perf') { ' gdi32.lib' } else { '' })
    $line = "cl $cl /LD `"$Src\$Mod.c`" /Fe`"$Out\$Mod.dll`" /link /SUBSYSTEM:WINDOWS $libs"
}
# A global CL=/MP12 breaks VC6-era builds of these sources; clear it for the child cmd.
$bat = Join-Path $obj '_build.bat'
Set-Content -Path $bat -Encoding ASCII -Value @"
set CL=
call "$vcvars" >nul
cd /d "$obj"
$line
if errorlevel 1 exit /b 1
"@
& cmd.exe /c "`"$bat`""
if ($LASTEXITCODE -ne 0) { throw "build failed (exit $LASTEXITCODE)" }
$f = if ($Mod -eq 'mods_launch') { "$Out\mods_launch.exe" } elseif ($Mod -eq 'sc3mods') { "$Out\sc3mods.dll" } else { "$Out\$Mod.dll" }
Write-Host ("[+] built {0} ({1} bytes)" -f $f, (Get-Item $f).Length)
