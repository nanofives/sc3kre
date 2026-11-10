<#
.SYNOPSIS
    Make every Building Architect (BAT) building you have grow in zones as a building of its own.

.DESCRIPTION
    The game's Building Architect keeps the buildings it offers in Apps\BARender\BAT.DAT. This script turns each of
    them into a NEW zoned building (numbers 37000 to 37999) that grows next to the stock buildings of its class.
    No stock building is replaced. It needs the sc3mods road mod (sc3netmod), because the new buildings go into the
    files that mod serves the game from (mods\netmod\overlay).

    The first run writes bat_growables.ini in the game folder, one section per BAT building, with a class guessed
    from the building's type in the Building Architect. Edit it (enabled, class, weight) and run the script again.
    To add a building of your own, open the Building Architect in the game, add it with "Editar lista" / "Edit list"
    (that rewrites BAT.DAT), close the game and run this script again.

    Safe to run more than once: each run first puts back the files it changed last time, then applies the ini.
    A new sc3mods release replaces mods\netmod: run this script again after updating sc3mods.

.PARAMETER Game
    The game folder (the one with Apps). Defaults to this script's folder or the folder above it.

.PARAMETER Restore
    Take the BAT buildings out again: every changed file is put back as it was. bat_growables.ini is kept.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\tools\bat_growables.ps1
    powershell -ExecutionPolicy Bypass -File .\tools\bat_growables.ps1 -Restore
#>
# Task batconvert (2026-11-10). Python reference with the same bytes: re/tools/batgrow.py (`compare` checks a run).
# Design and evidence: verify/batconvert/RESULTS.md. Works on Windows PowerShell 5.1 and PowerShell 7.
[CmdletBinding()]
param([string]$Game, [switch]$Restore)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

function Hx([string]$x) { return [Convert]::ToUInt32($x, 16) }   # hex above 0x7FFFFFFF is a negative Int32 literal in PowerShell
$FF = [uint32]::MaxValue
$MAGIC = Hx '80C381D7'; $REC = 20; $FIRST_PAYLOAD = 0x5004; $BLOCK = 0x5000
$BAT_GROUP = (Hx 'BA1DBF1E'); $OVR_TYPE = (Hx '856CD19A'); $CS_TYPE = [uint32]0x6300
$BLD_TYPE = [uint32]0x207EDC0E; $BLD_GROUP = [uint32]0x57E
$FAM_TYPE = (Hx '81F53D09'); $FAM_GROUP = [uint32]0x01F58D3D
$TEXT_TYPE = [uint32]0x2026960B; $TEXT_GROUP = (Hx 'A1096A4F')
$GROUP = (Hx 'BA7C0001')
$ID_FIRST = 37000; $ID_LAST = 37999
$OVL = 'mods/netmod/overlay/'
$OCC_KOREA = 'Apps/Res/Occupant/OccupantAttribs_Korea.IXF'
$CS_KOREA = 'Apps/Res/Sprites/CSAttrib_Korea.IXF'
$BUILDFAM = 'Apps/Res/BUILDFAM.IXF'
$NAMES = 'SC3StringsNetpack.IXF'
$PIX_DAT = 'Apps/Res/Sprites/BA7C0001_batgrow.DAT'
$STATE_DIR = 'mods/netmod/batgrow'
$INI = 'bat_growables.ini'
$CATEGORY_ZONE = @{ 0x208 = 'R'; 0x209 = 'C'; 0x20A = 'I' }
$DEFAULT_CLASS = @{ 'R' = @{ 1 = 3300; 2 = 3900; 3 = 4500; 4 = 4500 }
                    'C' = @{ 1 = 5100; 2 = 5700; 3 = 6300; 4 = 6700 }
                    'I' = @{ 1 = 8700; 2 = 8700; 3 = 8900; 4 = 9100 } }
# Class (LandUse) -> the families it grows from and the stock building whose stats a new building copies, per lot
# size. Computed from the stock files by `py -3.12 re/tools/batgrow.py tables`, checked by `batgrow.py check-ps`.
# TABLE BEGIN
$Classes = [ordered]@{
    3100 = @{ Label = 'Residential light, low wealth'; Families = @(11); Bases = @{ 1 = @(112, 'OccupantAttribs.IXF') } }
    3300 = @{ Label = 'Residential light, mid wealth'; Families = @(4); Bases = @{ 1 = @(115, 'OccupantAttribs.IXF') } }
    3500 = @{ Label = 'Residential light, high wealth'; Families = @(10, 31); Bases = @{ 1 = @(120, 'OccupantAttribs.IXF'); 2 = @(3077, 'OccupantAttribs.IXF') } }
    3700 = @{ Label = 'Residential medium, low wealth'; Families = @(16); Bases = @{ 2 = @(141, 'OccupantAttribs.IXF'); 3 = @(3011, 'OccupantAttribs.IXF') } }
    3900 = @{ Label = 'Residential medium, mid wealth'; Families = @(28, 12); Bases = @{ 2 = @(3020, 'OccupantAttribs.IXF') } }
    4100 = @{ Label = 'Residential medium, high wealth'; Families = @(17); Bases = @{ 2 = @(142, 'OccupantAttribs.IXF'); 3 = @(176, 'OccupantAttribs.IXF') } }
    4300 = @{ Label = 'Residential dense, low wealth'; Families = @(29, 15); Bases = @{ 2 = @(145, 'OccupantAttribs.IXF'); 3 = @(3003, 'OccupantAttribs.IXF') } }
    4500 = @{ Label = 'Residential dense, mid wealth'; Families = @(30, 14); Bases = @{ 2 = @(144, 'OccupantAttribs.IXF'); 3 = @(3009, 'OccupantAttribs.IXF'); 4 = @(3028, 'OccupantAttribs.IXF') } }
    4700 = @{ Label = 'Residential dense, high wealth'; Families = @(13); Bases = @{ 3 = @(174, 'OccupantAttribs.IXF'); 4 = @(3071, 'OccupantAttribs.IXF') } }
    5100 = @{ Label = 'Commercial light, low wealth'; Families = @(7); Bases = @{ 1 = @(126, 'OccupantAttribs.IXF') } }
    5500 = @{ Label = 'Commercial light, high wealth'; Families = @(9); Bases = @{ 1 = @(125, 'OccupantAttribs.IXF'); 2 = @(148, 'OccupantAttribs.IXF') } }
    5700 = @{ Label = 'Commercial medium, low wealth'; Families = @(8); Bases = @{ 2 = @(156, 'OccupantAttribs.IXF'); 3 = @(180, 'OccupantAttribs.IXF'); 4 = @(8010, 'OccupantAttribs.IXF') } }
    6100 = @{ Label = 'Commercial medium, high wealth'; Families = @(23); Bases = @{ 2 = @(152, 'OccupantAttribs.IXF'); 3 = @(181, 'OccupantAttribs.IXF') } }
    6300 = @{ Label = 'Commercial dense, low wealth'; Families = @(24); Bases = @{ 2 = @(155, 'OccupantAttribs.IXF'); 3 = @(179, 'OccupantAttribs.IXF') } }
    6700 = @{ Label = 'Commercial dense, high wealth'; Families = @(22); Bases = @{ 3 = @(178, 'OccupantAttribs.IXF'); 4 = @(4009, 'OccupantAttribs.IXF') } }
    8100 = @{ Label = 'Industrial dirty, light'; Families = @(5); Bases = @{ 1 = @(5001, 'OccupantAttribs.IXF') } }
    8300 = @{ Label = 'Industrial dirty, medium'; Families = @(6); Bases = @{ 2 = @(163, 'OccupantAttribs.IXF') } }
    8500 = @{ Label = 'Industrial dirty, dense'; Families = @(18); Bases = @{ 1 = @(135, 'OccupantAttribs.IXF'); 2 = @(162, 'OccupantAttribs.IXF'); 3 = @(5039, 'OccupantAttribs.IXF') } }
    8700 = @{ Label = 'Industrial clean, light'; Families = @(20); Bases = @{ 1 = @(134, 'OccupantAttribs.IXF'); 2 = @(159, 'OccupantAttribs.IXF') } }
    8900 = @{ Label = 'Industrial clean, medium'; Families = @(19); Bases = @{ 2 = @(165, 'OccupantAttribs.IXF'); 3 = @(188, 'OccupantAttribs.IXF') } }
    9100 = @{ Label = 'Industrial clean, dense'; Families = @(21); Bases = @{ 3 = @(191, 'OccupantAttribs.IXF'); 4 = @(5006, 'OccupantAttribs.IXF') } }
    9300 = @{ Label = 'Farm'; Families = @(25); Bases = @{ 1 = @(5012, 'OccupantAttribs.IXF'); 2 = @(5010, 'OccupantAttribs.IXF'); 3 = @(5014, 'OccupantAttribs.IXF') } }
}
# TABLE END
$ClassMap = @{}     # plain hashtable: an [ordered] dictionary indexed with an int returns the Nth entry
foreach ($kv in $Classes.GetEnumerator()) { $ClassMap[[int]$kv.Key] = $kv.Value }

$cp = [System.Text.Encoding]::GetEncoding(1252)
$latin1 = [System.Text.Encoding]::GetEncoding(28591)     # byte-transparent text for BUILDFAM records

# ---------------------------------------------------------------------------------------------------- game folder
$here = $PSScriptRoot
if (-not $Game) {
    if (Test-Path -LiteralPath (Join-Path $here 'Apps\Sys\SYS.PAK')) { $Game = $here }
    else { $Game = Split-Path -Parent $here }
}
$Game = (Resolve-Path -LiteralPath $Game).Path
$apps = Join-Path $Game 'Apps'
if (-not (Test-Path -LiteralPath (Join-Path $apps 'Sys\SYS.PAK'))) { throw "Apps\Sys\SYS.PAK not found under $Game. Pass -Game <game folder>." }
if (Get-Process -Name 'SC3U' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and [IO.Path]::GetDirectoryName($_.Path) -ieq $apps }) {
    throw "SimCity 3000 is running from this folder. Close it first."
}

function P([string]$rel) { return Join-Path $Game ($rel -replace '/', '\') }
function Has([string]$rel) { return (Test-Path -LiteralPath (P $rel) -PathType Leaf) }
function ReadB([string]$rel) { return ,[System.IO.File]::ReadAllBytes((P $rel)) }
function U32([byte[]]$b, [int]$o) { return [BitConverter]::ToUInt32($b, $o) }
function Put32([byte[]]$b, [int]$o, [uint32]$v) { [Array]::Copy([BitConverter]::GetBytes($v), 0, $b, $o, 4) }
function Sub([byte[]]$b, [int]$o, [int]$n) { $r = New-Object byte[] $n; [Array]::Copy($b, $o, $r, 0, $n); return ,$r }
function Join-Bytes([byte[][]]$parts) {
    $ms = New-Object System.IO.MemoryStream
    foreach ($p in $parts) { $ms.Write($p, 0, $p.Length) }
    return ,$ms.ToArray()
}
function Sha([byte[]]$b) {
    $h = [System.Security.Cryptography.SHA256]::Create()
    return ([BitConverter]::ToString($h.ComputeHash($b)) -replace '-', '').ToLowerInvariant()
}
function Write-New([string]$rel, [byte[]]$bytes) {
    # temp + move: never write through a hard link, never leave a half-written file
    $path = P $rel
    $dir = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $dir)) { [void](New-Item -ItemType Directory -Path $dir -Force) }
    $tmp = "$path.batgrow-tmp"
    [System.IO.File]::WriteAllBytes($tmp, $bytes)
    Move-Item -LiteralPath $tmp -Destination $path -Force
}
function Key3([uint32]$g, [uint32]$i, [uint32]$t) { return '{0:X8}:{1:X8}:{2:X8}' -f $g, $i, $t }
function Lower-Sorted($list) {
    # case-insensitive name order the way the Python reference sorts (str.lower, ordinal)
    $n = @($list)
    if ($n.Count -lt 2) { return $n }
    $keys = [string[]]($n | ForEach-Object { $_.ToLowerInvariant() })
    $vals = [string[]]$n
    [Array]::Sort($keys, $vals, [StringComparer]::Ordinal)
    return $vals
}

# ---------------------------------------------------------------------------------------------------- IXF containers
# u32 magic, 20-byte index slots {group, instance, type, offset, size} up to an all-zero key, payloads after.
function Ixf-Slots([byte[]]$d) {
    if ($d.Length -lt 4 -or (U32 $d 0) -ne $MAGIC) { throw "not an IXF container" }
    $list = New-Object System.Collections.Generic.List[object]
    $n = 0
    while (4 + ($n + 1) * $REC -le $d.Length) {
        $o = 4 + $n * $REC
        $s = @((U32 $d $o), (U32 $d ($o + 4)), (U32 $d ($o + 8)), (U32 $d ($o + 12)), (U32 $d ($o + 16)))
        $list.Add($s); $n++
        if ($s[0] -eq 0 -and $s[1] -eq 0 -and $s[2] -eq 0) { return ,$list }
    }
    throw "IXF index has no terminator"
}
# -> @{ Map = key -> @(offset, size); Order = keys } of live slots, first wins
function Ixf-Records([byte[]]$d) {
    $sl = Ixf-Slots $d
    $map = New-Object 'System.Collections.Generic.Dictionary[string,object]'
    $order = New-Object System.Collections.Generic.List[object]
    for ($k = 0; $k -lt $sl.Count - 1; $k++) {
        $s = $sl[$k]
        if ($s[2] -eq $FF -or $s[3] -eq $FF -or $s[4] -eq $FF) { continue }
        $key = Key3 $s[0] $s[1] $s[2]
        if (-not $map.ContainsKey($key)) { $map[$key] = @([int]$s[3], [int]$s[4]); $order.Add($s) }
    }
    return @{ Map = $map; Order = $order; Data = $d }
}
function Rec-Get($ix, [uint32]$g, [uint32]$i, [uint32]$t) {
    $key = Key3 $g $i $t
    if (-not $ix.Map.ContainsKey($key)) { return $null }
    $e = $ix.Map[$key]
    return ,(Sub $ix.Data $e[0] $e[1])
}
# recs: list of @(group, instance, type, payload)
function Ixf-New($recs) {
    $n = $recs.Count
    $first = $FIRST_PAYLOAD
    if (4 + ($n + 1) * $REC -gt $FIRST_PAYLOAD) { $first = 4 + ($n + 1) * $REC }
    $head = New-Object byte[] $first
    Put32 $head 0 $MAGIC
    $off = $first; $o = 4
    foreach ($r in $recs) {
        Put32 $head $o $r[0]; Put32 $head ($o + 4) $r[1]; Put32 $head ($o + 8) $r[2]
        Put32 $head ($o + 12) $off; Put32 $head ($o + 16) $r[3].Length
        $off += $r[3].Length; $o += $REC
    }
    $ms = New-Object System.IO.MemoryStream
    $ms.Write($head, 0, $head.Length)
    foreach ($r in $recs) { $ms.Write($r[3], 0, $r[3].Length) }
    return ,$ms.ToArray()
}
# = ixf_insert.append: new slots where the terminator was, payloads at the end; when the reserved index is full it
# grows by whole 0x5000-byte blocks inserted before the first payload (GZResourceD 0x1000d145 / 0x1000d3f3).
function Ixf-Append([byte[]]$d, $recs) {
    $sl = Ixf-Slots $d
    $termAt = 4 + ($sl.Count - 1) * $REC
    $first = [long]$d.Length
    for ($k = 0; $k -lt $sl.Count - 1; $k++) {
        $s = $sl[$k]
        if ($s[3] -ne $FF -and $s[4] -ne $FF -and $s[3] -lt $first) { $first = [long]$s[3] }
    }
    $needEnd = $termAt + ($recs.Count + 1) * $REC
    if ($needEnd -gt $first) {
        for ($k = $termAt; $k -lt $first; $k++) { if ($d[$k] -ne 0) { throw "bytes between the index terminator and the first payload are not zero" } }
        $delta = [int]($BLOCK * [Math]::Floor(($needEnd - $first + $BLOCK - 1) / $BLOCK))
        $g = New-Object byte[] ($d.Length + $delta)
        [Array]::Copy($d, 0, $g, 0, [int]$first)
        [Array]::Copy($d, [int]$first, $g, [int]$first + $delta, $d.Length - [int]$first)
        for ($k = 0; $k -lt $sl.Count - 1; $k++) {
            if ($sl[$k][3] -ne $FF) { Put32 $g (4 + $k * $REC + 12) ([uint32]($sl[$k][3] + $delta)) }
        }
        $d = $g
        $sl = Ixf-Slots $d
    }
    $keys = @{}
    for ($k = 0; $k -lt $sl.Count - 1; $k++) { $keys[(Key3 $sl[$k][0] $sl[$k][1] $sl[$k][2])] = 1 }
    $total = $d.Length
    foreach ($r in $recs) { $total += $r[3].Length }
    $out = New-Object byte[] $total
    [Array]::Copy($d, 0, $out, 0, $d.Length)
    $blobLen = ($recs.Count + 1) * $REC
    for ($k = $termAt; $k -lt $termAt + $blobLen; $k++) { if ($out[$k] -ne 0) { throw "bytes after the index terminator are not zero" } }
    $off = $d.Length; $o = $termAt
    foreach ($r in $recs) {
        $key = Key3 $r[0] $r[1] $r[2]
        if ($keys.ContainsKey($key)) { throw ("key {0} already present" -f $key) }
        $keys[$key] = 1
        Put32 $out $o $r[0]; Put32 $out ($o + 4) $r[1]; Put32 $out ($o + 8) $r[2]
        Put32 $out ($o + 12) $off; Put32 $out ($o + 16) $r[3].Length
        [Array]::Copy($r[3], 0, $out, $off, $r[3].Length)
        $off += $r[3].Length; $o += $REC
    }
    return ,$out
}
# = netpack_lanes.replace_records for existing keys: payload appended at the end, slot re-pointed
function Ixf-Replace([byte[]]$d, $recs) {
    $sl = Ixf-Slots $d
    $pos = @{}
    for ($k = 0; $k -lt $sl.Count - 1; $k++) { $pos[(Key3 $sl[$k][0] $sl[$k][1] $sl[$k][2])] = 4 + $k * $REC }
    $total = $d.Length
    foreach ($r in $recs) { $total += $r[3].Length }
    $out = New-Object byte[] $total
    [Array]::Copy($d, 0, $out, 0, $d.Length)
    $off = $d.Length
    foreach ($r in $recs) {
        $key = Key3 $r[0] $r[1] $r[2]
        if (-not $pos.ContainsKey($key)) { throw "record $key not in the container" }
        [Array]::Copy($r[3], 0, $out, $off, $r[3].Length)
        Put32 $out ($pos[$key] + 12) $off; Put32 $out ($pos[$key] + 16) $r[3].Length
        $off += $r[3].Length
    }
    return ,$out
}

# ---------------------------------------------------------------------------------------------------- TKB1 exemplars
function Tkb1-Props([byte[]]$b) {
    if ($b.Length -lt 4 -or $cp.GetString($b, 0, 4) -ne 'TKB1') { throw "not a TKB1 record" }
    $out = New-Object System.Collections.Generic.List[object]
    $o = 4
    while ($o + 8 -le $b.Length) {
        $prop = U32 $b $o; $t = [BitConverter]::ToUInt16($b, $o + 4); $n = [BitConverter]::ToUInt16($b, $o + 6)
        $o += 8
        switch ($t) {
            7 { $ln = [int](U32 $b $o) + 4 }
            3 { $ln = 4 * $n }
            8 { $ln = 12 * $n }
            1 { $ln = $n }
            default { throw ("TKB1 prop 0x{0:X} has unknown type {1}" -f $prop, $t) }
        }
        $out.Add(@($prop, $t, $n, $o, $ln)); $o += $ln
    }
    if ($o -ne $b.Length) { throw "TKB1 walk ended at $o of $($b.Length) bytes" }
    return ,$out
}
function Tkb1-SetKey([byte[]]$b, [uint32]$prop, [uint32[]]$key) {
    foreach ($p in (Tkb1-Props $b)) {
        if ($p[0] -eq $prop) {
            if ($p[1] -ne 8 -or $p[2] -ne 1) { throw ("prop 0x{0:X} is not one key" -f $prop) }
            $c = [byte[]]$b.Clone()
            Put32 $c $p[3] $key[0]; Put32 $c ($p[3] + 4) $key[1]; Put32 $c ($p[3] + 8) $key[2]
            return ,$c
        }
    }
    throw ("prop 0x{0:X} not present" -f $prop)
}
function Tkb1-SetText([byte[]]$b, [uint32]$prop, [byte[]]$raw) {
    foreach ($p in (Tkb1-Props $b)) {
        if ($p[0] -eq $prop) {
            if ($p[1] -ne 7) { throw ("prop 0x{0:X} is not text" -f $prop) }
            $end = $p[3] + $p[4]
            return ,(Join-Bytes @((Sub $b 0 $p[3]), [BitConverter]::GetBytes([uint32]$raw.Length), $raw, (Sub $b $end ($b.Length - $end))))
        }
    }
    throw ("prop 0x{0:X} not present" -f $prop)
}

# ---------------------------------------------------------------------------------------------------- restore step
# state.json: files this script wrote last time, with the sha256 it wrote and whether the file existed before.
# A file still holding those bytes is put back from its backup (or deleted). A file that changed since (a new sc3mods
# release replaced it) no longer holds our records: it is left alone and its old backup is dropped.
function Undo-LastRun {
    $stPath = P "$STATE_DIR/state.json"
    if (-not (Test-Path -LiteralPath $stPath)) { return 0 }
    $st = Get-Content -LiteralPath $stPath -Raw | ConvertFrom-Json
    $n = 0
    foreach ($prop in $st.files.PSObject.Properties) {
        $rel = $prop.Name; $ent = $prop.Value
        $path = P $rel
        if ((Test-Path -LiteralPath $path) -and ((Sha (ReadB $rel)) -eq $ent.written)) {
            if ($ent.existed) {
                Move-Item -LiteralPath (P "$STATE_DIR/backup/$rel") -Destination $path -Force
            } else {
                Remove-Item -LiteralPath $path -Force
            }
            $n++
        } else {
            Write-Host "  $rel changed since the last run (sc3mods update?): left as it is"
        }
    }
    Remove-Item -LiteralPath (P $STATE_DIR) -Recurse -Force
    return $n
}

if ($Restore) {
    $n = Undo-LastRun
    Write-Host "Put back $n file(s). The BAT buildings no longer grow in zones. Your settings stay in $INI." -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------------------------------------------- checks
foreach ($rel in @(($OVL + $OCC_KOREA), ($OVL + $CS_KOREA), 'Apps/BARender/BAT.DAT', $BUILDFAM)) {
    if (-not (Has $rel)) {
        if ($rel.StartsWith($OVL)) { throw "$rel not found. The sc3mods road mod (mods\netmod) must be installed first." }
        throw "$rel not found."
    }
}
[void](Undo-LastRun)

$langs = @()
$textDir = P ($OVL + 'Apps/Res/Text')
if (Test-Path -LiteralPath $textDir) {
    $langs = @(Lower-Sorted (Get-ChildItem -LiteralPath $textDir -Directory | ForEach-Object { $_.Name }) |
               Where-Object { Has ($OVL + "Apps/Res/Text/$_/$NAMES") })
}
if ($langs.Count -eq 0) { throw "No mods\netmod\overlay\Apps\Res\Text\<language>\$NAMES found. Reinstall sc3mods." }

# ---------------------------------------------------------------------------------------------------- BAT.DAT
# Per building: an override record (type 0x856CD19A: byte lot size, frame-table key, u32 length + name, u32 length +
# architect, ...), its 0x6300 frame table (20 entries of 15 bytes from +0x18) and the pixel (type 0) + anchor (type 1)
# records the table names.
$batIx = Ixf-Records (ReadB 'Apps/BARender/BAT.DAT')
$bats = New-Object System.Collections.Generic.List[object]
foreach ($s in $batIx.Order) {
    if ($s[2] -ne $OVR_TYPE -or $s[0] -ne $BAT_GROUP) { continue }
    $p = Rec-Get $batIx $s[0] $s[1] $s[2]
    $b = @{ Inst = [uint32]$s[1]; Size = [int]$p[0]; Problem = $null; Name = [byte[]]@() }
    if ($p.Length -lt 21) { $b.Problem = 'override record too short'; $bats.Add($b); continue }
    $nl = [int](U32 $p 13)
    if (17 + $nl + 4 -gt $p.Length) { $b.Problem = 'override record too short'; $bats.Add($b); continue }
    $b.Name = Sub $p 17 $nl
    $k0 = U32 $p 1; $k1 = U32 $p 5; $k2 = U32 $p 9
    $tab = Rec-Get $batIx $k1 $k2 $k0
    if ($k0 -ne $CS_TYPE -or $null -eq $tab -or $tab.Length -lt 0x18 -or $cp.GetString($tab, 0, 4) -ne "BIN`r" -or (($tab.Length - 0x18) % 15) -ne 0) {
        $b.Problem = ('frame table {{0x{0:X},0x{1:X},0x{2:X}}} missing or not a 0x6300 table' -f $k0, $k1, $k2)
    } elseif ($b.Size -lt 1 -or $b.Size -gt 4) {
        $b.Problem = "lot size $($b.Size)"
    } else {
        $ents = @(); $pix = New-Object System.Collections.Generic.List[string]; $ok = $true
        for ($k = 0; $k -lt ($tab.Length - 0x18) / 15; $k++) {
            $o = 0x18 + 15 * $k + 2
            $e = '{0:X8}:{1:X8}' -f (U32 $tab $o), (U32 $tab ($o + 4))
            $ents += $e
            if (-not $pix.Contains($e)) { $pix.Add($e) }
        }
        $pixels = @()
        foreach ($e in $pix) {
            $pg = [Convert]::ToUInt32($e.Substring(0, 8), 16); $pi = [Convert]::ToUInt32($e.Substring(9, 8), 16)
            $p0 = Rec-Get $batIx $pg $pi 0; $p1 = Rec-Get $batIx $pg $pi 1
            if ($null -eq $p0 -or $null -eq $p1) { $ok = $false; break }
            $pixels += ,@($p0, $p1)
        }
        if (-not $ok -or $pix.Count -gt 0xFFFF) { $b.Problem = 'frame table names a pixel record BAT.DAT does not hold' }
        else { $b.Table = $tab; $b.Entries = $ents; $b.PixKeys = $pix; $b.Pixels = $pixels }
    }
    $bats.Add($b)
}

# .bld type record 0x644D7179 -> default zone (0x208 houses, 0x209 shops and offices, 0x20A factories). The .bld is
# matched to BAT.DAT by the last u32 of its record 0xE3F87B0F, else by name.
$catByInst = New-Object 'System.Collections.Generic.Dictionary[uint32,uint32]'
$catByName = New-Object 'System.Collections.Generic.Dictionary[string,uint32]'
$bldDir = Join-Path $Game 'Buildings'
if (Test-Path -LiteralPath $bldDir) {
    $files = @(Get-ChildItem -LiteralPath $bldDir -File | Where-Object { $_.Name.ToLowerInvariant().EndsWith('.bld') } | ForEach-Object { $_.Name })
    foreach ($fn in (Lower-Sorted $files)) {
        try { $ix = Ixf-Records ([System.IO.File]::ReadAllBytes((Join-Path $bldDir $fn))) } catch { continue }
        $cat = $null; $info = $null
        foreach ($s in $ix.Order) {
            if ($s[2] -eq 0x644D7179 -and $s[4] -ge 4) { $cat = U32 (Rec-Get $ix $s[0] $s[1] $s[2]) 0 }
            if ($s[2] -eq (Hx 'E3F87B0F')) { $info = Rec-Get $ix $s[0] $s[1] $s[2] }
        }
        if ($null -eq $cat -or $null -eq $info -or $info.Length -lt 6) { continue }
        $ii = U32 $info ($info.Length - 4)
        if (-not $catByInst.ContainsKey($ii)) { $catByInst[$ii] = $cat }
        $nm = $cp.GetString($info, 2, [Math]::Min([int]$info[1], $info.Length - 2))
        if (-not $catByName.ContainsKey($nm)) { $catByName[$nm] = $cat }
    }
}

# ---------------------------------------------------------------------------------------------------- the ini
$old = New-Object System.Collections.Generic.List[object]
if (Has $INI) {
    $cur = $null
    foreach ($ln in ($cp.GetString((ReadB $INI)) -split "`r`n|`n|`r")) {
        $s = $ln.Trim()
        if (-not $s -or $s.StartsWith(';')) { continue }
        if ($s -match '^\[\s*(\d+)\s*\]$') { $cur = @{ id = [int]$Matches[1] }; $old.Add($cur); continue }
        if ($null -ne $cur -and $s.Contains('=')) {
            $i = $s.IndexOf('=')
            $cur[$s.Substring(0, $i).Trim().ToLowerInvariant()] = $s.Substring($i + 1).Trim()
        }
    }
}
function Get-Val($sec, [string]$k, [string]$def) { if ($sec.ContainsKey($k)) { return [string]$sec[$k] } return $def }
function Hex32([string]$s) { try { return [Convert]::ToUInt32($s, 16) } catch { return $null } }

$byBat = New-Object 'System.Collections.Generic.Dictionary[uint32,object]'
$byName = New-Object 'System.Collections.Generic.Dictionary[string,object]'
$used = @{}
foreach ($s in $old) {
    $h = Hex32 (Get-Val $s 'bat' '')
    if ($null -ne $h -and -not $byBat.ContainsKey($h)) { $byBat[$h] = $s }
    $nm = Get-Val $s 'name' ''
    if (-not $byName.ContainsKey($nm)) { $byName[$nm] = $s }
    $used[$s.id] = 1
}
$liveBats = @{}
foreach ($b in $bats) { $liveBats[$b.Inst] = 1 }
$taken = @{}
$entries = New-Object System.Collections.Generic.List[object]
foreach ($b in $bats) {
    $name = $cp.GetString($b.Name)
    $s = $null
    if ($byBat.ContainsKey($b.Inst)) { $s = $byBat[$b.Inst] }
    if ($null -eq $s -or $taken.ContainsKey($s.id)) {
        $s = $null
        if ($byName.ContainsKey($name)) { $s = $byName[$name] }
        if ($null -ne $s) {
            $h = Hex32 (Get-Val $s 'bat' '')
            if ($null -ne $h -and $liveBats.ContainsKey($h)) { $s = $null }
        }
        if ($null -ne $s -and $taken.ContainsKey($s.id)) { $s = $null }
    }
    if ($null -eq $s) {
        $nid = $null
        for ($k = $ID_FIRST; $k -le $ID_LAST; $k++) { if (-not $used.ContainsKey($k)) { $nid = $k; break } }
        if ($null -eq $nid) { throw "No free number left in $ID_FIRST-$ID_LAST." }
        $used[$nid] = 1
        $cat = $null
        if ($catByInst.ContainsKey($b.Inst)) { $cat = $catByInst[$b.Inst] } elseif ($catByName.ContainsKey($name)) { $cat = $catByName[$name] }
        $zone = $null
        if ($null -ne $cat -and $CATEGORY_ZONE.ContainsKey([int]$cat)) { $zone = $CATEGORY_ZONE[[int]$cat] }
        $size = $b.Size; if ($size -lt 1 -or $size -gt 4) { $size = 1 }
        $z = $zone; if (-not $z) { $z = 'R' }
        $s = @{ id = $nid; enabled = $(if ($zone) { '1' } else { '0' }); class = [string]$DEFAULT_CLASS[$z][$size]; weight = '1' }
    }
    $taken[$s.id] = 1
    $entries.Add(@{ Id = [int]$s.id; Name = $name; Bat = $b.Inst; Size = $b.Size; Enabled = (Get-Val $s 'enabled' '1');
                    Class = (Get-Val $s 'class' ''); Weight = (Get-Val $s 'weight' '1'); Building = $b; Note = $null })
}
foreach ($s in $old) {
    if ($taken.ContainsKey($s.id)) { continue }
    $h = Hex32 (Get-Val $s 'bat' '0'); if ($null -eq $h) { $h = [uint32]0 }
    $sz = Get-Val $s 'size' ''
    $entries.Add(@{ Id = [int]$s.id; Name = (Get-Val $s 'name' ''); Bat = $h; Size = $(if ($sz -match '^[0-9]+$') { [int]$sz } else { 0 });
                    Enabled = (Get-Val $s 'enabled' '0'); Class = (Get-Val $s 'class' ''); Weight = (Get-Val $s 'weight' '1');
                    Building = $null; Note = 'not in BAT.DAT now: skipped' })
}
$entries = @($entries | Sort-Object { $_.Id })

function Check-Entry($e) {
    $b = $e.Building
    if ($null -eq $b) { return 'not in BAT.DAT now' }
    if ($e.Enabled -ne '1') { return 'enabled = 0' }
    if ($b.Problem) { return $b.Problem }
    if ($e.Id -lt $ID_FIRST -or $e.Id -gt $ID_LAST) { return "number $($e.Id) is outside $ID_FIRST-$ID_LAST" }
    if ($e.Class -notmatch '^[0-9]+$' -or -not $ClassMap.ContainsKey([int]$e.Class)) { return "class '$($e.Class)' is not one of the listed classes" }
    $c = $ClassMap[[int]$e.Class]
    if (-not $c.Bases.ContainsKey($b.Size)) { return ('class {0} has no {1}x{1} lot' -f $e.Class, $b.Size) }
    if ($e.Weight -notmatch '^[0-9]+$' -or [long]$e.Weight -lt 1 -or [long]$e.Weight -gt 1000) { return "weight '$($e.Weight)' is not a whole number from 1 to 1000" }
    return $null
}

# ---------------------------------------------------------------------------------------------------- build
$occ = New-Object System.Collections.Generic.List[object]
$cs = New-Object System.Collections.Generic.List[object]
$pix = New-Object System.Collections.Generic.List[object]
$nameRecs = New-Object System.Collections.Generic.List[object]
$lines = @{}
$baseCache = @{}
$grown = 0
foreach ($e in $entries) {
    $why = Check-Entry $e
    if ($why) { Write-Host ("  skip  [{0}] {1}: {2}" -f $e.Id, $e.Name, $why); continue }
    $b = $e.Building; $nid = [uint32]$e.Id; $lu = [int]$e.Class; $w = [int]$e.Weight
    $c = $ClassMap[$lu]
    $base = $c.Bases[$b.Size]
    if (-not $baseCache.ContainsKey($base[1])) { $baseCache[$base[1]] = Ixf-Records (ReadB "Apps/Res/Occupant/$($base[1])") }
    $ex = Rec-Get $baseCache[$base[1]] $BLD_GROUP ([uint32]$base[0]) $BLD_TYPE
    if ($null -eq $ex) { throw "stock building $($base[0]) not found in Apps\Res\Occupant\$($base[1])" }
    $ex = Tkb1-SetKey $ex 0x67 @($CS_TYPE, $GROUP, $nid)
    $ex = Tkb1-SetKey $ex 0x6D @($TEXT_TYPE, $TEXT_GROUP, $nid)
    $ex = Tkb1-SetText $ex 0x64 $b.Name
    [void](Tkb1-Props $ex)
    $occ.Add(@($BLD_GROUP, $nid, $BLD_TYPE, $ex))
    $tab = [byte[]]$b.Table.Clone()
    for ($k = 0; $k -lt $b.Entries.Count; $k++) {
        Put32 $tab (0x18 + 15 * $k + 2) $GROUP
        Put32 $tab (0x18 + 15 * $k + 6) ([uint32]([long]$nid * 65536 + $b.PixKeys.IndexOf($b.Entries[$k])))
    }
    $cs.Add(@($GROUP, $nid, $CS_TYPE, $tab))
    for ($o = 0; $o -lt $b.Pixels.Count; $o++) {
        $inst = [uint32]([long]$nid * 65536 + $o)
        $pix.Add(@($GROUP, $inst, [uint32]0, $b.Pixels[$o][0]))
        $pix.Add(@($GROUP, $inst, [uint32]1, $b.Pixels[$o][1]))
    }
    $nameRecs.Add(@($TEXT_GROUP, $nid, $TEXT_TYPE, (Join-Bytes @([BitConverter]::GetBytes([uint32]$b.Name.Length), $b.Name))))
    foreach ($f in $c.Families) {
        if (-not $lines.ContainsKey($f)) { $lines[$f] = New-Object System.Collections.Generic.List[string] }
        $lines[$f].Add(('Key: 1406,545184782,{0},{1}   {2}' -f $nid, $w, $latin1.GetString($b.Name)) + "`r`n")
    }
    Write-Host ("  grow  [{0}] {1}: class {2} ({3}), {4}x{4}, weight {5}, stats of stock {6}" -f $nid, $e.Name, $lu, $c.Label, $b.Size, $w, $base[0]) -ForegroundColor Green
    $grown++
}

$files = [ordered]@{}
if ($grown) {
    $files[$OVL + $OCC_KOREA] = Ixf-Append (ReadB ($OVL + $OCC_KOREA)) $occ
    $files[$OVL + $CS_KOREA] = Ixf-Append (ReadB ($OVL + $CS_KOREA)) $cs
    $files[$OVL + $PIX_DAT] = Ixf-New $pix
    foreach ($lang in $langs) {
        $rel = $OVL + "Apps/Res/Text/$lang/$NAMES"
        $files[$rel] = Ixf-Append (ReadB $rel) $nameRecs
    }
    if (Has ($OVL + $BUILDFAM)) { $bf = ReadB ($OVL + $BUILDFAM) } else { $bf = ReadB $BUILDFAM }
    $bfIx = Ixf-Records $bf
    $new = New-Object System.Collections.Generic.List[object]
    foreach ($f in ($lines.Keys | Sort-Object)) {
        $text = Rec-Get $bfIx $FAM_GROUP ([uint32]$f) $FAM_TYPE
        if ($null -eq $text) { throw "BUILDFAM.IXF has no family $f" }
        $t = $latin1.GetString($text)
        $m = [regex]::Match($t, 'BuildingCount:\s*(\d+)[^\r\n]*\r?\n')
        if (-not $m.Success) { throw "BUILDFAM family $f has no BuildingCount line" }
        $t = $t.Substring(0, $m.Index) + ('BuildingCount: {0}' -f ([int]$m.Groups[1].Value + $lines[$f].Count)) + "`r`n" +
             ($lines[$f] -join '') + $t.Substring($m.Index + $m.Length)
        $new.Add(@($FAM_GROUP, [uint32]$f, $FAM_TYPE, $latin1.GetBytes($t)))
    }
    $files[$OVL + $BUILDFAM] = Ixf-Replace $bf $new
}

# ---------------------------------------------------------------------------------------------------- write
$state = [ordered]@{ files = [ordered]@{} }
foreach ($rel in $files.Keys) {
    $existed = Has $rel
    if ($existed) {
        $bk = P "$STATE_DIR/backup/$rel"
        $dir = Split-Path -Parent $bk
        if (-not (Test-Path -LiteralPath $dir)) { [void](New-Item -ItemType Directory -Path $dir -Force) }
        [System.IO.File]::Copy((P $rel), $bk, $true)
    }
    Write-New $rel $files[$rel]
    $state.files[$rel] = [ordered]@{ existed = $existed; written = (Sha $files[$rel]) }
}
if ($files.Count) {
    [System.IO.File]::WriteAllText((P "$STATE_DIR/state.json"), ($state | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
}

$L = New-Object System.Collections.Generic.List[string]
$L.Add('; bat_growables.ini: your Building Architect (BAT) buildings that grow in zones as buildings of their own.')
$L.Add('; Written by bat_growables.ps1. Change enabled, class or weight, then run bat_growables.ps1 again.')
$L.Add('; Keep each building''s [number] and bat as they are: saved cities refer to the building by that number.')
$L.Add(';')
$L.Add('; enabled  1 = grows in zones, 0 = does not')
$L.Add('; class    the kind of zone lot it grows on (the lot sizes each class takes are listed after it):')
foreach ($kv in $Classes.GetEnumerator()) {
    $sizes = (@($kv.Value.Bases.Keys | Sort-Object) | ForEach-Object { '{0}x{0}' -f $_ }) -join ' '
    $L.Add((';   {0}  {1,-34} {2}' -f $kv.Key, $kv.Value.Label, $sizes))
}
$L.Add('; weight   how often the game picks it, against a stock building of the same class (stock ones have 1 to 10)')
$L.Add('; size     the lot size BAT.DAT gives it (read only)')
$L.Add('')
foreach ($e in $entries) {
    $L.Add("[$($e.Id)]"); $L.Add("name = $($e.Name)"); $L.Add(('bat = {0:X8}' -f $e.Bat)); $L.Add("size = $($e.Size)")
    $L.Add("enabled = $($e.Enabled)"); $L.Add("class = $($e.Class)"); $L.Add("weight = $($e.Weight)")
    if ($e.Note) { $L.Add("; $($e.Note)") }
    $L.Add('')
}
Write-New $INI ($cp.GetBytes(($L -join "`r`n")))

if ($grown) {
    Write-Host "Done: $grown BAT building(s) grow in zones. Start the game as usual." -ForegroundColor Green
} else {
    Write-Host "No BAT building is enabled in $INI. Nothing changed in the game files."
}
Write-Host "Settings: $(P $INI). Undo: run this with -Restore. After an sc3mods update, run this again."
