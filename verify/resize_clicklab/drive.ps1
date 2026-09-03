# drive.ps1 - automated HUD-click visual test for the resize mod.
#
# Path-loads a city under the shipped mod, maximizes, settles, then posts mouse input at named
# client-space points and captures a full-window PNG around each. No hand-driving.
#
# Usage: drive.ps1 [-City Europolis] [-KeepOpen] [-Settle 10] [-Point "name:x:y" ...]

param(
    [string]   $City = 'Europolis',
    [string]   $Log,
    [string]   $OutDir,
    [int]      $Settle = 10,
    [switch]   $KeepOpen,
    [switch]   $NoClick,        # hand-test mode: set up, shoot the baseline, post NO input
    [switch]   $NoMaximize,     # leave the window at its native size (to read the stock layout)
    [string[]] $Point = @('btn_b:1747:1045', 'btn_a:1815:1055', 'bar_bg:1547:1053'),
    [string[]] $EnvVars = @('SC3RESIZE_CLUSTER=1')
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$bin  = Join-Path $root 're\harness\bin'
$sc3  = Join-Path $root "Cities\$City.sc3"
if (-not (Test-Path $sc3)) { throw "city not found: $sc3" }
if (-not $OutDir) { $OutDir = $PSScriptRoot }
if (-not $Log)    { $Log = Join-Path $OutDir 'run.log' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace W -Name U -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
public struct RECT { public int L, T, R, B; }
'@

foreach ($pair in $EnvVars) {
    $i = $pair.IndexOf('=')
    if ($i -gt 0) { Set-Item -Path ("Env:" + $pair.Substring(0, $i)) -Value $pair.Substring($i + 1) }
}
$env:SC3RESIZE_LOG = $Log
if (Test-Path $Log) { Remove-Item $Log -Force }

Write-Host "[*] city   : $sc3"
Write-Host "[*] log    : $Log"
Write-Host "[*] env    : $($EnvVars -join ' ')"

$killAfter = if ($KeepOpen) { 3600 } else { $Settle + 120 }
$proc = Start-Process -FilePath (Join-Path $bin 'resize_launch.exe') `
                      -ArgumentList @('-kill', $killAfter, '--', "`"$sc3`"") `
                      -PassThru -WindowStyle Minimized

function Wait-ForLogLine([string]$pattern, [int]$timeoutSec) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Log) {
            if (Select-String -Path $Log -Pattern $pattern -Quiet -ErrorAction SilentlyContinue) { return $true }
        }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

if (Wait-ForLogLine 'bridge captured' 90) { Write-Host "[+] city loaded (bridge captured)" }
else { Write-Warning "bridge never captured - the city may not have loaded" }
Start-Sleep -Seconds 5

$g = Get-Process -Name SC3U -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $g -or $g.MainWindowHandle -eq 0) { throw "no SC3U main window" }
$h = $g.MainWindowHandle
[void][W.U]::SetForegroundWindow($h)
if (-not $NoMaximize) { [void][W.U]::ShowWindow($h, 3) }   # SW_MAXIMIZE
Write-Host "[*] maximized 0x$('{0:X}' -f [int]$h); settling $Settle s"
Start-Sleep -Seconds $Settle

# Dismiss the startup tip dialog. While a modal is up the engine discards every click outside it,
# so leaving it there silently invalidates any click test that follows.
$dismiss = Join-Path $root 're\tools\dismiss_tips.py'
if (Test-Path $dismiss) { & python $dismiss --quiet 2>&1 | Out-Null; Write-Host '[*] startup tips dismissed' }

$cr = New-Object W.U+RECT
[void][W.U]::GetClientRect($h, [ref]$cr)
$cw = $cr.R - $cr.L; $ch = $cr.B - $cr.T
Write-Host "[*] client : ${cw}x${ch}"

function Shot([string]$name) {
    [void][W.U]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 250
    $r = New-Object W.U+RECT
    [void][W.U]::GetWindowRect($h, [ref]$r)
    $w = $r.R - $r.L; $ht = $r.B - $r.T
    $bmp = New-Object System.Drawing.Bitmap $w, $ht
    $gr  = [System.Drawing.Graphics]::FromImage($bmp)
    $gr.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
    $p = Join-Path $OutDir "$name.png"
    $bmp.Save($p, [System.Drawing.Imaging.ImageFormat]::Png)
    $gr.Dispose(); $bmp.Dispose()
    Write-Host "    shot $name  win=[$($r.L) $($r.T) $($r.R) $($r.B)] ${w}x${ht}"
}

function Click([int]$x, [int]$y) {
    $lp = [IntPtr](($y -shl 16) -bor ($x -band 0xFFFF))
    [void][W.U]::PostMessage($h, 0x0200, [IntPtr]0, $lp)   # WM_MOUSEMOVE
    Start-Sleep -Milliseconds 200
    [void][W.U]::PostMessage($h, 0x0201, [IntPtr]1, $lp)   # WM_LBUTTONDOWN
    Start-Sleep -Milliseconds 120
    [void][W.U]::PostMessage($h, 0x0202, [IntPtr]0, $lp)   # WM_LBUTTONUP
}

# Idle-animation baseline: two shots, no input.
Shot 's0_noise_a'
Start-Sleep -Milliseconds 1400
Shot 's0_noise_b'

foreach ($spec in ($(if ($NoClick) { @() } else { $Point }))) {
    $parts = $spec.Split(':')
    $name = $parts[0]; $x = [int]$parts[1]; $y = [int]$parts[2]
    Write-Host "[*] click $name ($x,$y)"
    Click $x $y
    Start-Sleep -Milliseconds 1400
    Shot "s_$name"
}

Write-Host "`n===== LOG LINES ====="
if (Test-Path $Log) {
    Select-String -Path $Log -Pattern 'FAULT CAUGHT|0xC0000005|size change|CLUSTER>|PARENT>.*->|STOREDRECT' |
        Select-Object -First 40 | ForEach-Object { $_.Line }
    Write-Host "[i] log lines: $((Get-Content $Log).Count)  client: ${cw}x${ch}"
}

if ($KeepOpen) {
    Write-Host "[*] leaving the game running (pid $((Get-Process -Name SC3U).Id))"
} else {
    Get-Process -Name SC3U -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process -Name resize_launch -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[*] closed"
}
