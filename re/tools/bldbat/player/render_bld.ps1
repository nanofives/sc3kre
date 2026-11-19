<#
.SYNOPSIS
    Render a folder of Building Architect .bld files into real game frames (all four views), with the Building
    Architect itself, in a window. No Python, no Frida.

.DESCRIPTION
    1. Makes or refreshes Apps\BaappW.exe and Apps\bawinonly.dll from your own Baapp.exe (baappw_patch.ps1).
    2. Starts BaappW.exe windowed (-w -r800x600) with BAWIN_BATCH = the folder. bawinonly.dll waits for the main
       menu, calls the Building Architect's batch renderer once for every .bld in the folder and closes it.
       The Building Architect window shows for one to two minutes. Do not close it.
    3. Writes <folder>\bld_frames.ixf (the frames, in the game's BAT.DAT format) and <folder>\bld_frames.txt (what
       ran). The game's own Apps\BARender\BAT.DAT is never touched. The building importer (classifier page or
       bldimport.py) then uses bld_frames.ixf as the art of the .bld files next to it.
    While it runs, this script reads every display's mode 50 times a second; if any mode changes it ends the
    Building Architect at once and reports a failure (bawinonly.dll already refuses every fullscreen switch: this is
    the second, independent guard).

.PARAMETER Folder
    The folder with the .bld files (or a text file with one .bld path per line).

.PARAMETER Apps
    The game's Apps folder. Defaults to this script's folder, its Apps subfolder, or ..\Apps.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File render_bld.ps1 "C:\Downloads\my buildings"
    (or drop the folder on render_bld.cmd)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)] [string]$Folder,
    [string]$Apps,
    [string]$Out,
    [int]$TimeoutSec = 1800,
    [int]$MenuWaitMs = 4000
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Folder)) { throw "$Folder does not exist." }
$Folder = (Resolve-Path -LiteralPath $Folder).Path
if (-not $Apps) {
    foreach ($c in @($PSScriptRoot, (Join-Path $PSScriptRoot 'Apps'), (Join-Path (Split-Path $PSScriptRoot) 'Apps'))) {
        if (Test-Path -LiteralPath (Join-Path $c 'Baapp.exe')) { $Apps = $c; break }
    }
    if (-not $Apps) { throw "Baapp.exe not found next to this script. Pass -Apps <the game's Apps folder>." }
}
$Apps = (Resolve-Path -LiteralPath $Apps).Path

& (Join-Path $PSScriptRoot 'baappw_patch.ps1') -Apps $Apps
if ($LASTEXITCODE) { exit $LASTEXITCODE }

$isDir = (Get-Item -LiteralPath $Folder).PSIsContainer
$base = if ($isDir) { $Folder } else { Split-Path $Folder }
if (-not $Out) { $Out = Join-Path $base 'bld_frames.ixf' }
$Out = [IO.Path]::GetFullPath($Out)
if ($Out -notlike '*.ixf' -or (Split-Path $Out -Leaf) -ieq 'BAT.DAT' -or $Out -match '\\(BARender|Res\\BA)\\') {
    throw "-Out must be a .ixf file outside BARender and Res\BA (the game's BAT.DAT is never written)."
}
$report = $Out.Substring(0, $Out.Length - 4) + '.txt'      # bawinonly: <out minus .ixf>.txt
if ($isDir) {
    $n = @(Get-ChildItem -LiteralPath $Folder -File | Where-Object { $_.Name -like '*.bld' }).Count
    if (-not $n) { throw "no .bld files in $Folder" }
    Write-Host "$n .bld files in $Folder"
}

# --- the display-mode watch (outside the Building Architect's process) ------------------------------------------
if (-not ('BawModeWatch' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
public class BawModeWatch {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct DISPLAY_DEVICE {
        public int cb;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string DeviceName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceString;
        public int StateFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceID;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceKey;
    }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct DEVMODE {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmDeviceName;
        public short dmSpecVersion, dmDriverVersion, dmSize, dmDriverExtra;
        public int dmFields, dmPositionX, dmPositionY, dmDisplayOrientation, dmDisplayFixedOutput;
        public short dmColor, dmDuplex, dmYResolution, dmTTOption, dmCollate;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmFormName;
        public short dmLogPixels;
        public int dmBitsPerPel, dmPelsWidth, dmPelsHeight, dmDisplayFlags, dmDisplayFrequency;
        public int dmICMMethod, dmICMIntent, dmMediaType, dmDitherType, dmReserved1, dmReserved2, dmPanningWidth, dmPanningHeight;
    }
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern bool EnumDisplayDevices(string dev, int i, ref DISPLAY_DEVICE dd, int flags);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern bool EnumDisplaySettingsEx(string dev, int mode, ref DEVMODE dm, int flags);
    public static string Snapshot() {
        var sb = new StringBuilder();
        for (int i = 0; ; i++) {
            var dd = new DISPLAY_DEVICE(); dd.cb = Marshal.SizeOf(dd);
            if (!EnumDisplayDevices(null, i, ref dd, 0)) break;
            if ((dd.StateFlags & 1) == 0) continue;
            var dm = new DEVMODE(); dm.dmSize = (short)Marshal.SizeOf(dm);
            if (EnumDisplaySettingsEx(dd.DeviceName, -1, ref dm, 0))
                sb.AppendFormat("{0} {1}x{2} {3}bpp {4}Hz at {5},{6}; ", dd.DeviceName, dm.dmPelsWidth, dm.dmPelsHeight,
                                dm.dmBitsPerPel, dm.dmDisplayFrequency, dm.dmPositionX, dm.dmPositionY);
        }
        return sb.ToString();
    }
    public string Start0, Changed;
    public int Samples, Pid;
    public volatile bool Stop;
    Thread t;
    public void Begin() { Start0 = Snapshot(); t = new Thread(Run); t.IsBackground = true; t.Start(); }
    void Run() {
        while (!Stop) {
            string s = Snapshot(); Samples++;
            if (s != Start0 && Changed == null) {
                Changed = s;
                try { if (Pid != 0) Process.GetProcessById(Pid).Kill(); } catch { }
            }
            Thread.Sleep(20);
        }
    }
    public void End() { Stop = true; if (t != null) t.Join(2000); }
}
'@
}

$watch = New-Object BawModeWatch
$watch.Begin()
Write-Host "displays: $($watch.Start0)"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = Join-Path $Apps 'BaappW.exe'
$psi.Arguments = '-w -r800x600'
$psi.WorkingDirectory = $Apps
$psi.UseShellExecute = $false
$psi.EnvironmentVariables['BAWIN_BATCH'] = $Folder
$psi.EnvironmentVariables['BAWIN_BATCH_OUT'] = $Out
$psi.EnvironmentVariables['BAWIN_BATCH_TIMEOUT'] = "$TimeoutSec"
$psi.EnvironmentVariables['BAWIN_BATCH_WAIT'] = "$MenuWaitMs"
$t0 = Get-Date
$p = [System.Diagnostics.Process]::Start($psi)
$watch.Pid = $p.Id
Write-Host "Building Architect started (PID $($p.Id)), rendering. Do not close its window."
if (-not $p.WaitForExit(($TimeoutSec + 60) * 1000)) {
    try { $p.Kill() } catch { }
    $p.WaitForExit(10000) | Out-Null
}
Start-Sleep -Milliseconds 300
$watch.End()
$code = $p.ExitCode
$secs = [int]((Get-Date) - $t0).TotalSeconds
Write-Host ("Building Architect ended after {0} s, exit code 0x{1:X}; display modes sampled {2} times, changed: {3}" -f $secs, $code, $watch.Samples, $(if ($watch.Changed) { 'YES' } else { 'no' }))
if (Test-Path -LiteralPath $report) { Get-Content -LiteralPath $report | Where-Object { $_ -match '^(result|render|guards|menu)' } | ForEach-Object { Write-Host "  $_" } }
if ($watch.Changed) {
    Write-Host "FAILED: a display mode changed ($($watch.Changed)); the Building Architect was stopped."
    exit 3
}
if ($code -ne 0 -or -not (Test-Path -LiteralPath $Out)) {
    Write-Host "FAILED: see $report and $(Join-Path $Apps 'bawinonly.log')"
    exit 1
}

# list what the IXF holds: override records (type 0x856CD19A): u8 lot, u32 x 3 key, u32 name length, name
$b = [IO.File]::ReadAllBytes($Out)
$names = @()
for ($o = 4; $o + 20 -le $b.Length; $o += 20) {
    $g = [BitConverter]::ToUInt32($b, $o); $i = [BitConverter]::ToUInt32($b, $o + 4); $ty = [BitConverter]::ToUInt32($b, $o + 8)
    if ($g -eq 0 -and $i -eq 0 -and $ty -eq 0) { break }
    if ($ty -ne 2238501274) { continue }        # 0x856CD19A
    $off = [BitConverter]::ToUInt32($b, $o + 12)
    $nl = [BitConverter]::ToUInt32($b, $off + 13)
    $names += ('{0} ({1}x{1})' -f [Text.Encoding]::GetEncoding(1252).GetString($b, $off + 17, $nl), $b[$off])
}
Write-Host ("rendered {0} buildings into {1}:" -f $names.Count, $Out)
$names | ForEach-Object { Write-Host "  $_" }
exit 0
