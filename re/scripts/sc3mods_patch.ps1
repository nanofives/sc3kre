<#
.SYNOPSIS
    Install or remove the sc3mods loader by adding a normal PE import to your own SC3U.exe.

.DESCRIPTION
    The sc3kre mods are loaded by Apps\sc3mods.dll. For the Windows loader to map that DLL on a normal game start,
    SC3U.exe must import it. This script adds one import descriptor for sc3mods.dll to Apps\SC3U.exe. It does not
    change any game code and it patches nothing at run time: the only edit is one entry in the exe's import table,
    which is how every program lists the DLLs it needs.

    It is safe to run more than once (idempotent), it keeps an untouched backup, and -Restore puts the stock exe back.

    The game exe is never shipped. You run this on your own install.

.PARAMETER Apps
    The folder with SC3U.exe. Defaults to this script's folder, or an Apps subfolder of it.

.PARAMETER Restore
    Put the stock SC3U.exe back from the backup and stop loading the mods.

.PARAMETER DllName
    The loader DLL to import. Default sc3mods.dll.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File sc3mods_patch.ps1
    powershell -ExecutionPolicy Bypass -File sc3mods_patch.ps1 -Restore
#>
[CmdletBinding()]
param(
    [string]$Apps,
    [switch]$Restore,
    [string]$DllName = 'sc3mods.dll'
)

$ErrorActionPreference = 'Stop'

# SC3U.exe anchor (SimCity 3000 Unlimited, GOG). RVAs are only valid for this exact binary.
$ANCHOR = '49DD55E183C68DFFE6AC57E85A91EF3B3E79C45A9D137EDFCBB3840026349DC7'
$SECNAME = '.sc3mod'          # the section this script adds; also how it recognises an already-patched exe
$EXPORT  = 'sc3mods_version'  # the one function the new import references

function Sha256Hex([string]$path) {
    (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}

# --- locate the exe ---------------------------------------------------------------------------------------------
if (-not $Apps) {
    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'SC3U.exe')) { $Apps = $PSScriptRoot }
    elseif (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'Apps\SC3U.exe')) { $Apps = Join-Path $PSScriptRoot 'Apps' }
    else { $Apps = $PSScriptRoot }
}
$exe = Join-Path $Apps 'SC3U.exe'
$bak = Join-Path $Apps 'SC3U.exe.orig'
if (-not (Test-Path -LiteralPath $exe)) { throw "SC3U.exe not found in $Apps. Pass -Apps <folder>." }

# only a game started from THIS folder holds this exe (dev trees run several installs side by side)
$full = (Resolve-Path -LiteralPath $exe).Path
if (Get-Process -Name 'SC3U', 'SC3U_mods' -ErrorAction SilentlyContinue |
        Where-Object { -not $_.Path -or [IO.Path]::GetDirectoryName($_.Path) -ieq [IO.Path]::GetDirectoryName($full) }) {
    throw "SimCity 3000 is running. Close it first."
}

# --- read a PE into a byte array and give field helpers ---------------------------------------------------------
function Read-Pe([string]$path) {
    $b = [System.IO.File]::ReadAllBytes($path)
    $lfanew = [BitConverter]::ToInt32($b, 0x3c)
    if ([BitConverter]::ToUInt16($b, $lfanew) -ne 0x4550) { throw "$path is not a PE (no PE signature)." }
    $opt = $lfanew + 24
    if ([BitConverter]::ToUInt16($b, $opt) -ne 0x10b) { throw "$path is not PE32 (x86)." }
    [pscustomobject]@{
        Bytes   = $b
        Lfanew  = $lfanew
        Opt     = $opt
        NSec    = [BitConverter]::ToUInt16($b, $lfanew + 6)
        SizeOptHdr = [BitConverter]::ToUInt16($b, $lfanew + 20)
        SecAlign = [BitConverter]::ToUInt32($b, $opt + 0x20)
        FileAlign = [BitConverter]::ToUInt32($b, $opt + 0x24)
        SizeOfImage = [BitConverter]::ToUInt32($b, $opt + 0x38)
    }
}
function Sec-Table([object]$pe) { $pe.Lfanew + 24 + $pe.SizeOptHdr }
function Has-Section([object]$pe, [string]$name) {
    $t = Sec-Table $pe
    for ($i = 0; $i -lt $pe.NSec; $i++) {
        $o = $t + $i * 40
        $n = [System.Text.Encoding]::ASCII.GetString($pe.Bytes, $o, 8).TrimEnd([char]0)
        if ($n -eq $name) { return $true }
    }
    return $false
}

# --- standard PE checksum (imagehlp CheckSumMappedFile): DWORD sum with carry, fold to 16 bits, + file length ----
function Set-Checksum([byte[]]$b, [int]$opt) {
    $cf = $opt + 0x40
    $b[$cf] = 0; $b[$cf + 1] = 0; $b[$cf + 2] = 0; $b[$cf + 3] = 0
    $len = $b.Length
    [uint64]$sum = 0
    $full = $len - ($len % 4)
    for ($i = 0; $i -lt $full; $i += 4) {
        $sum = ($sum -band 0xffffffffL) + [BitConverter]::ToUInt32($b, $i) + ($sum -shr 32)
    }
    if ($full -lt $len) {                       # tail bytes (zero-padded) as a final dword
        [uint32]$tail = 0
        for ($k = 0; $k -lt ($len - $full); $k++) { $tail = $tail -bor ([uint32]$b[$full + $k] -shl (8 * $k)) }
        $sum = ($sum -band 0xffffffffL) + $tail + ($sum -shr 32)
    }
    $sum = ($sum -band 0xffff) + ($sum -shr 16)
    $sum = $sum + ($sum -shr 16)
    [uint32]$chk = ([uint32]($sum -band 0xffff)) + [uint32]$len
    [Array]::Copy([BitConverter]::GetBytes($chk), 0, $b, $cf, 4)
}

function Write-Atomic([string]$dest, [byte[]]$bytes) {
    # never patch in place: dev trees hard-link the exe, so an in-place write would change every linked tree.
    $tmp = "$dest.patch_tmp"
    [System.IO.File]::WriteAllBytes($tmp, $bytes)
    Move-Item -LiteralPath $tmp -Destination $dest -Force
}

# ================================================================================================================
# RESTORE
# ================================================================================================================
if ($Restore) {
    if (-not (Test-Path -LiteralPath $bak)) { throw "No backup SC3U.exe.orig in $Apps. Nothing to restore." }
    $bh = Sha256Hex $bak
    if ($bh -ne $ANCHOR) { throw "Backup SC3U.exe.orig hash $bh is not the stock anchor. Refusing to restore it." }
    if ((Sha256Hex $exe) -eq $ANCHOR) {
        Write-Host "SC3U.exe is already stock. Nothing to restore." -ForegroundColor Green
    } else {
        Write-Atomic $exe ([System.IO.File]::ReadAllBytes($bak))
        Write-Host "Restored stock SC3U.exe from the backup." -ForegroundColor Green
    }
    Remove-Item -LiteralPath $bak -Force
    Write-Host "Removed the backup. The mods will not load now (stock game)." -ForegroundColor Green
    Write-Host "To load the mods again, run this script with no arguments."
    exit 0
}

# ================================================================================================================
# PATCH
# ================================================================================================================
$h = Sha256Hex $exe

# already patched?
$pe0 = Read-Pe $exe
if (Has-Section $pe0 $SECNAME) {
    Write-Host "SC3U.exe already imports $DllName (section $SECNAME present). Nothing to do." -ForegroundColor Green
    if (-not (Test-Path -LiteralPath $bak)) {
        Write-Host "  note: no SC3U.exe.orig backup is present; -Restore will not work until you reinstall stock." -ForegroundColor DarkYellow
    }
    # still check the loader DLL is here
    if (-not (Test-Path -LiteralPath (Join-Path $Apps $DllName))) {
        Write-Host "  WARNING: $DllName is missing from $Apps. The game will fail to start until it is there." -ForegroundColor Red
    }
    exit 0
}

if ($h -ne $ANCHOR) {
    throw "SC3U.exe hash $h is neither the stock anchor nor an exe this script patched. Refusing. Reinstall the stock game exe, then run this again."
}

# back up the pristine exe
if (-not (Test-Path -LiteralPath $bak)) {
    [System.IO.File]::Copy($exe, $bak)   # Copy, not link: the backup must survive a rewrite of the exe
    Write-Host "Backed up stock SC3U.exe -> SC3U.exe.orig" -ForegroundColor Green
} elseif ((Sha256Hex $bak) -ne $ANCHOR) {
    throw "SC3U.exe.orig exists but is not the stock anchor. Move it aside and run again."
}

$b = $pe0.Bytes
$opt = $pe0.Opt
$secAlign = $pe0.SecAlign
$fileAlign = $pe0.FileAlign
function Align([uint32]$v, [uint32]$a) { return [uint32](([uint32]($v + $a - 1)) -band (-bnot ($a - 1))) }

# read the existing import directory
$impVA = [BitConverter]::ToUInt32($b, $opt + 0x68)
$impSz = [BitConverter]::ToUInt32($b, $opt + 0x6c)

# map an RVA to a file offset through the section table
$secTab = Sec-Table $pe0
function Rva-ToOff([uint32]$rva) {
    for ($i = 0; $i -lt $pe0.NSec; $i++) {
        $o = $secTab + $i * 40
        $vs = [BitConverter]::ToUInt32($b, $o + 8)
        $va = [BitConverter]::ToUInt32($b, $o + 12)
        $rs = [BitConverter]::ToUInt32($b, $o + 16)
        $pr = [BitConverter]::ToUInt32($b, $o + 20)
        $span = [Math]::Max($vs, $rs)
        if ($rva -ge $va -and $rva -lt $va + $span) { return [int]($pr + ($rva - $va)) }
    }
    throw "RVA 0x$("{0:X}" -f $rva) is in no section."
}

# copy the original descriptors (20 bytes each) up to the null terminator
$impOff = Rva-ToOff $impVA
$orig = New-Object System.Collections.Generic.List[byte[]]
$p = $impOff
while ($true) {
    $entry = New-Object byte[] 20
    [Array]::Copy($b, $p, $entry, 0, 20)
    $allZero = $true
    foreach ($x in $entry) { if ($x -ne 0) { $allZero = $false; break } }
    if ($allZero) { break }
    $orig.Add($entry)
    $p += 20
}
Write-Host ("Found {0} existing import descriptors." -f $orig.Count)

# ---- build the new section blob ----
$newVA  = Align $pe0.SizeOfImage $secAlign       # new section's RVA (SizeOfImage is already section-aligned)
$descCount = $orig.Count + 1                      # + sc3mods; a null terminator follows
$descBytes = ($descCount + 1) * 20
# layout after the descriptor array
$iltOff  = $descBytes                             # ILT: 2 DWORDs
$iatOff  = $iltOff + 8                            # IAT: 2 DWORDs
$ibnOff  = $iatOff + 8                            # IMAGE_IMPORT_BY_NAME: WORD hint + name + NUL
$nameBytes = [System.Text.Encoding]::ASCII.GetBytes($EXPORT)
$ibnLen  = 2 + $nameBytes.Length + 1
if (($ibnLen -band 1) -ne 0) { $ibnLen++ }       # keep the next item WORD-aligned
$dllOff  = $ibnOff + $ibnLen                      # DLL name string
$dllBytes = [System.Text.Encoding]::ASCII.GetBytes($DllName)
$dllLen  = $dllBytes.Length + 1
$blobLen = $dllOff + $dllLen

$blob = New-Object byte[] $blobLen
# original descriptors verbatim (their RVA fields still point into the original sections)
for ($i = 0; $i -lt $orig.Count; $i++) { [Array]::Copy($orig[$i], 0, $blob, $i * 20, 20) }
# our descriptor
$d = $orig.Count * 20
[Array]::Copy([BitConverter]::GetBytes([uint32]($newVA + $iltOff)), 0, $blob, $d + 0, 4)   # OriginalFirstThunk
[Array]::Copy([BitConverter]::GetBytes([uint32]0), 0, $blob, $d + 4, 4)                     # TimeDateStamp
[Array]::Copy([BitConverter]::GetBytes([uint32]0), 0, $blob, $d + 8, 4)                     # ForwarderChain
[Array]::Copy([BitConverter]::GetBytes([uint32]($newVA + $dllOff)), 0, $blob, $d + 12, 4)   # Name
[Array]::Copy([BitConverter]::GetBytes([uint32]($newVA + $iatOff)), 0, $blob, $d + 16, 4)   # FirstThunk
# (the null terminator descriptor is already all-zero)
# ILT + IAT both point at the IMAGE_IMPORT_BY_NAME, then a null thunk
[Array]::Copy([BitConverter]::GetBytes([uint32]($newVA + $ibnOff)), 0, $blob, $iltOff, 4)
[Array]::Copy([BitConverter]::GetBytes([uint32]($newVA + $ibnOff)), 0, $blob, $iatOff, 4)
# IMAGE_IMPORT_BY_NAME: hint 0, name, NUL
[Array]::Copy($nameBytes, 0, $blob, $ibnOff + 2, $nameBytes.Length)
# DLL name
[Array]::Copy($dllBytes, 0, $blob, $dllOff, $dllBytes.Length)

$rawLen = [int](Align ([uint32]$blobLen) $fileAlign)
$newRaw = $b.Length                               # append at the current end of file (file is file-aligned)

# ---- assemble the new file ----
$out = New-Object byte[] ($newRaw + $rawLen)
[Array]::Copy($b, 0, $out, 0, $b.Length)
[Array]::Copy($blob, 0, $out, $newRaw, $blobLen)

# new section header
$shOff = $secTab + $pe0.NSec * 40
$nameField = New-Object byte[] 8
[Array]::Copy([System.Text.Encoding]::ASCII.GetBytes($SECNAME), 0, $nameField, 0, $SECNAME.Length)
[Array]::Copy($nameField, 0, $out, $shOff, 8)
[Array]::Copy([BitConverter]::GetBytes([uint32]$blobLen), 0, $out, $shOff + 8, 4)   # VirtualSize
[Array]::Copy([BitConverter]::GetBytes([uint32]$newVA),   0, $out, $shOff + 12, 4)  # VirtualAddress
[Array]::Copy([BitConverter]::GetBytes([uint32]$rawLen),  0, $out, $shOff + 16, 4)  # SizeOfRawData
[Array]::Copy([BitConverter]::GetBytes([uint32]$newRaw),  0, $out, $shOff + 20, 4)  # PointerToRawData
# relocations/linenumbers all zero (already)
$chars = [Convert]::ToUInt32('C0000040', 16)   # CNT_INIT_DATA|READ|WRITE (write: the loader fills our IAT in place)
[Array]::Copy([BitConverter]::GetBytes($chars), 0, $out, $shOff + 36, 4)

# header edits
[Array]::Copy([BitConverter]::GetBytes([uint16]($pe0.NSec + 1)), 0, $out, $pe0.Lfanew + 6, 2)   # NumberOfSections
$newSizeImg = Align ([uint32]($newVA + $blobLen)) $secAlign
[Array]::Copy([BitConverter]::GetBytes([uint32]$newSizeImg), 0, $out, $opt + 0x38, 4)            # SizeOfImage
[Array]::Copy([BitConverter]::GetBytes([uint32]$newVA), 0, $out, $opt + 0x68, 4)                 # IMPORT dir VA
[Array]::Copy([BitConverter]::GetBytes([uint32]$descBytes), 0, $out, $opt + 0x6c, 4)             # IMPORT dir size
# clear the bound-import directory (index 11): a stale bound table would skip our new import
[Array]::Copy([BitConverter]::GetBytes([uint32]0), 0, $out, $opt + 0xb8, 4)
[Array]::Copy([BitConverter]::GetBytes([uint32]0), 0, $out, $opt + 0xbc, 4)

# recompute the PE checksum
Set-Checksum $out $opt

Write-Atomic $exe $out
$nh = Sha256Hex $exe
Write-Host ("Patched SC3U.exe: added import of {0} (new section {1} at RVA 0x{2:X})." -f $DllName, $SECNAME, $newVA) -ForegroundColor Green
Write-Host ("  new SHA-256: {0}" -f $nh)

# remove a leftover loader from older releases (version.dll beside the exe), only if it is ours
$oldLoader = Join-Path $Apps 'version.dll'
if (Test-Path -LiteralPath $oldLoader) {
    $txt = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($oldLoader))
    if ($txt.Contains('sc3modldr ') -or $txt.Contains('sc3mods ')) {
        Remove-Item -LiteralPath $oldLoader -Force
        Write-Host "  removed the old Apps\version.dll loader (superseded by $DllName)." -ForegroundColor DarkYellow
    } else {
        Write-Host "  note: Apps\version.dll is present but is not ours (left as-is)." -ForegroundColor DarkYellow
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $Apps $DllName))) {
    Write-Host "  WARNING: $DllName is not in $Apps yet. Copy it there before starting the game." -ForegroundColor Red
}
Write-Host ""
Write-Host "Start the game normally (SC3U.exe or your shortcut). To go back to stock: run this with -Restore." -ForegroundColor Cyan
exit 0
