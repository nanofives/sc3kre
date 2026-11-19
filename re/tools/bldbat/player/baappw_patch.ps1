<#
.SYNOPSIS
    Make BaappW.exe, a windowed copy of your own Building Architect (Apps\Baapp.exe), for render_bld.ps1.

.DESCRIPTION
    BaappW.exe is a NEW file: a byte copy of your Apps\Baapp.exe plus one section (.bawin) that holds a copy of the
    exe's import table with one more entry, bawinonly.dll!bawinonly_state. No code byte of the Building Architect is
    changed and Baapp.exe itself is never written. bawinonly.dll (shipped beside this script, our code) then keeps the
    Building Architect in a window and fixes two crashes before its display starts:
      - windowed only: GZGraphicD's fullscreen display-mode switch and exclusive mode are refused; if any byte it
        patches is not the expected one the process ends before any display starts (fail closed);
      - FIX16 (16-bit surface format on a 32-bit desktop) and STRTOKFIX (a stock heap overrun on prop .met files);
      - with BAWIN_BATCH set (render_bld.ps1 does that) it renders .bld files with the Building Architect's own
        batch renderer and exits.
    Run it again any time: it only writes what differs. -Remove deletes BaappW.exe and bawinonly.dll again.
    Neither Baapp.exe nor BaappW.exe is ever shipped: you make BaappW.exe on your own PC from your own game.

.PARAMETER Apps
    The game's Apps folder (with Baapp.exe). Defaults to this script's folder, its Apps subfolder, ..\Apps or ..\..\Apps (the sc3mods zip puts the kit in tools\bld_render).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File baappw_patch.ps1 -Apps "C:\GOG Games\SimCity 3000 Unlimited\Apps"
#>
[CmdletBinding()]
param(
    [string]$Apps,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'

# Stock Baapp.exe builds this script accepts, and the BaappW.exe it must make from each (checked after the build:
# the same bytes re/tools/bldbat/ba_patch.py writes; any difference = nothing is written).
$BUILDS = @{
    '1829CBE2DF17CC67C07BF5DA8ED4AA3B3D9F6CA7F51BD9EE5A233B7BB7A57B5E' = @{ Name = 'GOG 2.0.949 (647,168 bytes)'; Out = 'B377E7968BA17E7197BE2FC6E8A32EB411DDDA699CDA4B952FDFE90884344BD8' }
}
$DLL = 'bawinonly.dll'; $EXPORT = 'bawinonly_state'; $SECNAME = '.bawin'

function Bytes-Sha256([byte[]]$b) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($b))).Replace('-', '') } finally { $sha.Dispose() }
}
# a signed copy (as Steam ships the game exe) differs only by the appended signature, the security directory and
# the checksum (re/scripts/sc3mods_patch.ps1): compare the normalised bytes
function Strip-Signature([byte[]]$b) {
    $lf = [BitConverter]::ToInt32($b, 0x3c); $opt = $lf + 24
    $so = [BitConverter]::ToUInt32($b, $opt + 0x80); $ss = [BitConverter]::ToUInt32($b, $opt + 0x84)
    $len = $b.Length
    if ($so -gt 0 -and $ss -gt 0 -and $so + $ss -ge $b.Length - 8 -and $so -le $b.Length) { $len = [int]$so }
    $o = New-Object byte[] $len
    [Array]::Copy($b, 0, $o, 0, $len)
    [Array]::Copy([BitConverter]::GetBytes([uint64]0), 0, $o, $opt + 0x80, 8)
    [Array]::Copy([BitConverter]::GetBytes([uint32]0), 0, $o, $opt + 0x40, 4)
    return ,$o
}
function Align([long]$v, [long]$a) { return [long](($v + $a - 1) - (($v + $a - 1) % $a)) }
function PutU32([byte[]]$b, [int]$o, [long]$v) { [Array]::Copy([BitConverter]::GetBytes([uint32]$v), 0, $b, $o, 4) }
function PutU16([byte[]]$b, [int]$o, [int]$v) { [Array]::Copy([BitConverter]::GetBytes([uint16]$v), 0, $b, $o, 2) }

# The import added as in ba_patch.add_import: the old descriptors + one for bawinonly.dll, its lookup and address
# tables (one name each), the hint/name entry and the DLL name, in one new section; the import directory points there.
function Add-Import([byte[]]$b) {
    $lf = [BitConverter]::ToInt32($b, 0x3C)
    $nsec = [BitConverter]::ToUInt16($b, $lf + 6)
    $optsz = [BitConverter]::ToUInt16($b, $lf + 20)
    $opt = $lf + 24
    if ([BitConverter]::ToUInt16($b, $opt) -ne 0x10B) { throw 'Baapp.exe is not PE32' }
    $secAlign = [BitConverter]::ToUInt32($b, $opt + 32); $fileAlign = [BitConverter]::ToUInt32($b, $opt + 36)
    $sizeImage = [BitConverter]::ToUInt32($b, $opt + 56); $sizeHdrs = [BitConverter]::ToUInt32($b, $opt + 60)
    $impRva = [BitConverter]::ToUInt32($b, $opt + 104)
    $st = $opt + $optsz
    $secs = @()
    for ($i = 0; $i -lt $nsec; $i++) {
        $o = $st + 40 * $i
        $nm = [Text.Encoding]::ASCII.GetString($b, $o, 8).TrimEnd([char]0)
        if ($nm -eq $SECNAME) { throw 'this file already has the .bawin section' }
        $secs += ,@([BitConverter]::ToUInt32($b, $o + 8), [BitConverter]::ToUInt32($b, $o + 12), [BitConverter]::ToUInt32($b, $o + 16), [BitConverter]::ToUInt32($b, $o + 20))
    }
    if ($st + 40 * ($nsec + 1) -gt $sizeHdrs) { throw 'no room for a section header' }
    $io = -1
    foreach ($s in $secs) {   # VirtualSize, VA, RawSize, RawPtr
        $span = [Math]::Max($s[0], $s[2])
        if ($impRva -ge $s[1] -and $impRva -lt $s[1] + $span) { $io = [int]($impRva - $s[1] + $s[3]) }
    }
    if ($io -lt 0) { throw 'import table in no section' }
    $descs = New-Object System.Collections.Generic.List[byte[]]
    while ($true) {
        $d = New-Object byte[] 20; [Array]::Copy($b, $io, $d, 0, 20)
        $zero = $true; foreach ($x in $d) { if ($x -ne 0) { $zero = $false; break } }
        if ($zero) { break }
        $descs.Add($d); $io += 20
    }
    $newRva = Align $sizeImage $secAlign
    $dsz = 20 * ($descs.Count + 2)
    $ilt = $dsz; $iat = $ilt + 8; $ibn = $iat + 8
    $name = $ibn + 2 + $EXPORT.Length + 1
    $name += ($name -band 1)
    $blob = New-Object byte[] ($name + $DLL.Length + 1)
    for ($i = 0; $i -lt $descs.Count; $i++) { [Array]::Copy($descs[$i], 0, $blob, 20 * $i, 20) }
    $k = 20 * $descs.Count
    PutU32 $blob $k ($newRva + $ilt); PutU32 $blob ($k + 4) 0; PutU32 $blob ($k + 8) 0
    PutU32 $blob ($k + 12) ($newRva + $name); PutU32 $blob ($k + 16) ($newRva + $iat)
    PutU32 $blob $ilt ($newRva + $ibn)
    PutU32 $blob $iat ($newRva + $ibn)
    $e = [Text.Encoding]::ASCII.GetBytes($EXPORT); [Array]::Copy($e, 0, $blob, $ibn + 2, $e.Length)
    $n = [Text.Encoding]::ASCII.GetBytes($DLL); [Array]::Copy($n, 0, $blob, $name, $n.Length)
    $rawSize = Align $blob.Length $fileAlign
    $rawOff = Align $b.Length $fileAlign
    $out = New-Object byte[] ($rawOff + $rawSize)
    [Array]::Copy($b, 0, $out, 0, $b.Length)
    [Array]::Copy($blob, 0, $out, $rawOff, $blob.Length)
    $h = $st + 40 * $nsec
    $sn = [Text.Encoding]::ASCII.GetBytes($SECNAME); [Array]::Copy($sn, 0, $out, $h, $sn.Length)
    PutU32 $out ($h + 8) $blob.Length; PutU32 $out ($h + 12) $newRva; PutU32 $out ($h + 16) $rawSize
    PutU32 $out ($h + 20) $rawOff; PutU32 $out ($h + 24) 0; PutU32 $out ($h + 28) 0
    PutU16 $out ($h + 32) 0; PutU16 $out ($h + 34) 0; PutU32 $out ($h + 36) 3221225536   # 0xC0000040 (a hex literal would parse as a negative Int32)
    PutU16 $out ($lf + 6) ($nsec + 1)
    PutU32 $out ($opt + 56) (Align ($newRva + $blob.Length) $secAlign)
    PutU32 $out ($opt + 104) $newRva; PutU32 $out ($opt + 108) $dsz
    PutU32 $out ($opt + 96 + 88) 0; PutU32 $out ($opt + 96 + 92) 0      # bound imports (0 in stock already)
    PutU32 $out ($opt + 64) 0                                            # checksum (not checked for exes)
    return ,$out
}

# --- locate the game ---------------------------------------------------------------------------------------------
if (-not $Apps) {
    foreach ($c in @($PSScriptRoot, (Join-Path $PSScriptRoot 'Apps'), (Join-Path (Split-Path $PSScriptRoot) 'Apps'), (Join-Path (Split-Path (Split-Path $PSScriptRoot)) 'Apps'))) {
        if (Test-Path -LiteralPath (Join-Path $c 'Baapp.exe')) { $Apps = $c; break }
    }
    if (-not $Apps) { throw "Baapp.exe not found next to this script. Pass -Apps <the game's Apps folder>." }
}
$Apps = (Resolve-Path -LiteralPath $Apps).Path
$exe = Join-Path $Apps 'Baapp.exe'; $outExe = Join-Path $Apps 'BaappW.exe'; $outDll = Join-Path $Apps $DLL
if (-not (Test-Path -LiteralPath $exe)) { throw "Baapp.exe not found in $Apps." }
$running = Get-Process -Name 'BaappW', 'Baapp' -ErrorAction SilentlyContinue | Where-Object { $_.Path -and ([IO.Path]::GetDirectoryName($_.Path) -ieq $Apps) }
if ($running) { throw "The Building Architect is running from $Apps (PID $($running.Id -join ', ')). Close it first." }

if ($Remove) {
    foreach ($f in @($outExe, $outDll, (Join-Path $Apps 'bawinonly.log'))) {
        if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force; Write-Host "removed $f" }
    }
    exit 0
}

$raw = [IO.File]::ReadAllBytes($exe)
$h = Bytes-Sha256 $raw
$build = $BUILDS[$h]
$src = $raw
if (-not $build) {
    $norm = Strip-Signature $raw
    $build = $BUILDS[(Bytes-Sha256 $norm)]
    if ($build) { $src = $norm; $build = @{ Name = $build.Name + ' (signed copy)'; Out = $build.Out } }
}
if (-not $build) {
    Write-Host "Baapp.exe in $Apps is not a build this script knows (SHA-256 $h, $($raw.Length) bytes)."
    Write-Host 'Nothing was written. Please report the hash above.'
    exit 2
}
Write-Host "Baapp.exe: $($build.Name)"
$new = Add-Import $src
$nh = Bytes-Sha256 $new
if ($nh -ne $build.Out) { throw "the made BaappW.exe ($nh) is not the expected $($build.Out). Nothing was written." }

$dllSrc = Join-Path $PSScriptRoot $DLL
if (-not (Test-Path -LiteralPath $dllSrc)) { throw "$DLL not found next to this script ($PSScriptRoot)." }
# delete first, never write through a hard link (dev test trees link Apps files)
if (-not (Test-Path -LiteralPath $outExe) -or (Get-FileHash -LiteralPath $outExe -Algorithm SHA256).Hash -ne $nh) {
    if (Test-Path -LiteralPath $outExe) { Remove-Item -LiteralPath $outExe -Force }
    [IO.File]::WriteAllBytes($outExe, $new)
    Write-Host "wrote $outExe"
} else { Write-Host "BaappW.exe is up to date" }
if ([IO.Path]::GetFullPath($dllSrc) -ine [IO.Path]::GetFullPath($outDll)) {
    $dh = (Get-FileHash -LiteralPath $dllSrc -Algorithm SHA256).Hash
    if (-not (Test-Path -LiteralPath $outDll) -or (Get-FileHash -LiteralPath $outDll -Algorithm SHA256).Hash -ne $dh) {
        if (Test-Path -LiteralPath $outDll) { Remove-Item -LiteralPath $outDll -Force }
        Copy-Item -LiteralPath $dllSrc -Destination $outDll
        Write-Host "copied $DLL into $Apps"
    } else { Write-Host "$DLL is up to date" }
}
exit 0
