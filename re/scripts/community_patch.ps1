<#
.SYNOPSIS
    Install or remove the community mods (Apache Flyover, Civic Deals, Extra Cheats) on your own game files.

.DESCRIPTION
    These three mods are by thronevintagetech and Null 45, shipped with the authors' permission in the community folder
    of the sc3mods release. Their DLLs load through the game's own DLL scan, they do not need sc3mods.dll.

    Two of them add new petitions to Reunirse (Meet), which needs entries in game files that are not ours to ship:
      Apps\Sys\SYS.PAK                                  PetitionerExtraInfo.ini 0xD9, 0xDA, 0xDB
      Apps\Res\Text\<language>\Sc3StringsPetitioner*.IXF  six files, new records 0xD9, 0xDA, 0xDB
    This script adds those entries to YOUR copies (every original record is kept), copies the community DLLs and
    sprites into Apps, and on a Spanish game writes the Civic Deals texts in Spanish. Every file it changes is
    backed up once as <file>.community-orig. It is safe to run more than once. -Restore undoes everything.

.PARAMETER Game
    The game folder (the one with Apps). Defaults to this script's folder or the folder above it.

.PARAMETER Restore
    Put every changed file back and remove the community DLLs.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\community\community_patch.ps1
    powershell -ExecutionPolicy Bypass -File .\community\community_patch.ps1 -Restore
#>
[CmdletBinding()]
param([string]$Game, [switch]$Restore)
$ErrorActionPreference = 'Stop'
$SUFFIX = '.community-orig'

$here = $PSScriptRoot
if (-not $Game) {
    if (Test-Path -LiteralPath (Join-Path $here 'Apps\Sys\SYS.PAK')) { $Game = $here }
    else { $Game = Split-Path -Parent $here }
}
$apps = Join-Path $Game 'Apps'
if (-not (Test-Path -LiteralPath (Join-Path $apps 'Sys\SYS.PAK'))) { throw "Apps\Sys\SYS.PAK not found under $Game. Pass -Game <game folder>." }
if (Get-Process -Name 'SC3U' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and [IO.Path]::GetDirectoryName($_.Path) -ieq (Resolve-Path -LiteralPath $apps).Path }) {
    throw "SimCity 3000 is running. Close it first."
}
$data = Get-Content -LiteralPath (Join-Path $here 'install_data.json') -Raw | ConvertFrom-Json
$cp = [System.Text.Encoding]::GetEncoding(1252)

function Save-Once([string]$path) {
    if ((Test-Path -LiteralPath $path) -and -not (Test-Path -LiteralPath ($path + $SUFFIX))) {
        [System.IO.File]::Copy($path, $path + $SUFFIX)
    }
}
function Write-New([string]$path, [byte[]]$bytes) {
    # temp + move: never write through a hard link, and never leave a half-written file
    $tmp = "$path.community-tmp"
    [System.IO.File]::WriteAllBytes($tmp, $bytes)
    Move-Item -LiteralPath $tmp -Destination $path -Force
}
function U32([byte[]]$b, [int]$o) { return [BitConverter]::ToUInt32($b, $o) }

# ================================================================================================================
if ($Restore) {
    $n = 0
    Get-ChildItem -LiteralPath $apps -Recurse -File -Filter "*$SUFFIX" | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination ($_.FullName.Substring(0, $_.FullName.Length - $SUFFIX.Length)) -Force
        $n++
    }
    foreach ($rel in $data.files) {
        $dst = Join-Path $Game ($rel -replace '/', '\')
        if (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst -Force; $n++ }
    }
    Write-Host "Restored $n file(s). The community mods are off." -ForegroundColor Green
    exit 0
}

# ---- SYS.PAK: 51 x [u32 A][u32 nameLen][name], u32 A_last, then records [u32 lines][u32 len, chars]... ----------
function Read-Pak([byte[]]$b) {
    $names = New-Object System.Collections.Generic.List[string]
    $o = 0
    while ($o + 8 -le $b.Length) {
        $nl = U32 $b ($o + 4)
        if ($nl -eq 0 -or $nl -gt 128) { break }
        $ok = $true
        for ($i = 0; $i -lt $nl; $i++) { $c = $b[$o + 8 + $i]; if ($c -lt 32 -or $c -ge 127) { $ok = $false; break } }
        if (-not $ok) { break }
        $names.Add([System.Text.Encoding]::ASCII.GetString($b, $o + 8, [int]$nl)); $o += 8 + [int]$nl
    }
    $p = $o + 4
    $recs = New-Object System.Collections.Generic.List[object]
    foreach ($n in $names) {
        $lc = U32 $b $p; $p += 4
        $lines = New-Object System.Collections.Generic.List[string]
        for ($i = 0; $i -lt $lc; $i++) { $ln = [int](U32 $b $p); $p += 4; $lines.Add($cp.GetString($b, $p, $ln)); $p += $ln }
        $recs.Add($lines)
    }
    if ($p -ne $b.Length) { throw "SYS.PAK: unexpected layout (records end at $p of $($b.Length)). Not changed." }
    return @{ Names = $names; Recs = $recs }
}
function Build-Pak($pak) {
    $blobs = New-Object System.Collections.Generic.List[byte[]]
    foreach ($lines in $pak.Recs) {
        $ms = New-Object System.IO.MemoryStream
        $ms.Write([BitConverter]::GetBytes([uint32]$lines.Count), 0, 4)
        foreach ($l in $lines) { $raw = $cp.GetBytes($l); $ms.Write([BitConverter]::GetBytes([uint32]$raw.Length), 0, 4); $ms.Write($raw, 0, $raw.Length) }
        $blobs.Add($ms.ToArray())
    }
    $tocEnd = 0; foreach ($n in $pak.Names) { $tocEnd += 8 + $n.Length }
    $starts = @(); $pos = $tocEnd + 4
    foreach ($bl in $blobs) { $starts += $pos; $pos += $bl.Length }
    $out = New-Object System.IO.MemoryStream
    for ($i = 0; $i -lt $pak.Names.Count; $i++) {
        $a = if ($i -eq 0) { $pak.Names.Count } else { $starts[$i - 1] }
        $raw = [System.Text.Encoding]::ASCII.GetBytes($pak.Names[$i])
        $out.Write([BitConverter]::GetBytes([uint32]$a), 0, 4); $out.Write([BitConverter]::GetBytes([uint32]$raw.Length), 0, 4); $out.Write($raw, 0, $raw.Length)
    }
    $out.Write([BitConverter]::GetBytes([uint32]$starts[$starts.Count - 1]), 0, 4)
    foreach ($bl in $blobs) { $out.Write($bl, 0, $bl.Length) }
    return ,$out.ToArray()
}

$pakPath = Join-Path $apps 'Sys\SYS.PAK'
$pakBytes = [System.IO.File]::ReadAllBytes($pakPath)
$pak = Read-Pak $pakBytes
if (-not ([System.Linq.Enumerable]::SequenceEqual([byte[]](Build-Pak $pak), [byte[]]$pakBytes))) {
    throw "SYS.PAK does not rebuild byte for byte. Not changed."
}
$changed = 0
foreach ($op in $data.syspak) {
    $idx = -1
    for ($i = 0; $i -lt $pak.Names.Count; $i++) { if ($pak.Names[$i] -ieq $op.member) { $idx = $i } }
    if ($idx -lt 0) { throw "SYS.PAK has no $($op.member). Not changed." }
    $lines = $pak.Recs[$idx]
    if ($op.insert) {
        if ($lines.Contains($op.insert[0])) { continue }
        $k = $lines.IndexOf($op.after)
        if ($k -lt 0) { throw "SYS.PAK $($op.member): line '$($op.after)' not found. Not changed." }
        $lines.InsertRange($k + 1, [string[]]$op.insert); $changed++
    } else {
        $k = $lines.IndexOf($op.replace)
        if ($k -ge 0) { $lines[$k] = $op.with; $changed++ }
    }
}
if ($changed) { Save-Once $pakPath; Write-New $pakPath (Build-Pak $pak); Write-Host "SYS.PAK: $changed change(s)" -ForegroundColor Green }
else { Write-Host "SYS.PAK: already done" }

# ---- petitioner IXF: u32 magic, 20-byte index slots {group, instance, type, offset, size} up to a zero slot ----------
function Ixf-Records([byte[]]$b) {
    $list = @(); $o = 4
    while ($o + 20 -le $b.Length) {
        $g = U32 $b $o; $in = U32 $b ($o + 4); $t = U32 $b ($o + 8)
        if ($g -eq 0 -and $in -eq 0 -and $t -eq 0) { break }
        $list += ,@($g, $in, $t, (U32 $b ($o + 12)), (U32 $b ($o + 16)), $o)
        $o += 20
    }
    return @{ List = $list; Term = $o }
}
function Ixf-Text([byte[]]$b, $rec) { $off = [int]$rec[3]; $n = [int](U32 $b $off); return [byte[]]$b[($off + 4)..($off + 3 + $n)] }

$textDir = Join-Path $apps 'Res\Text'
function Folder-Lang([string]$folder) {
    # the game's ENGLISH folder holds Spanish on a Spanish install: tell by the stock 0xD7 heading against English-UK's
    if ($folder -ine 'ENGLISH') { return 'en' }
    $uk = Join-Path $textDir 'English-UK\Sc3StringsPetitionerHeading.IXF'
    $me = Join-Path $textDir 'ENGLISH\Sc3StringsPetitionerHeading.IXF'
    if (-not (Test-Path -LiteralPath $uk) -or -not (Test-Path -LiteralPath $me)) { return 'en' }
    $a = [System.IO.File]::ReadAllBytes($uk); $b = [System.IO.File]::ReadAllBytes($me)
    $ra = (Ixf-Records $a).List | Where-Object { $_[1] -eq 0xD7 } | Select-Object -First 1
    $rb = (Ixf-Records $b).List | Where-Object { $_[1] -eq 0xD7 } | Select-Object -First 1
    if (-not $ra -or -not $rb) { return 'en' }
    if ([System.Linq.Enumerable]::SequenceEqual([byte[]](Ixf-Text $a $ra), [byte[]](Ixf-Text $b $rb))) { return 'en' }
    return 'es'
}

$spanishGame = $false
foreach ($dir in Get-ChildItem -LiteralPath $textDir -Directory) {
    $lang = Folder-Lang $dir.Name
    if ($dir.Name -ieq 'ENGLISH' -and $lang -eq 'es') { $spanishGame = $true }
    $added = 0
    foreach ($fileGroup in ($data.ixf | Group-Object file)) {
        $path = Join-Path $dir.FullName $fileGroup.Name
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $b = [System.IO.File]::ReadAllBytes($path)
        $ix = Ixf-Records $b
        $todo = @($fileGroup.Group | Where-Object { $i = $_.instance; -not ($ix.List | Where-Object { $_[1] -eq $i }) })
        if (-not $todo.Count) { continue }
        $first = ($ix.List | Where-Object { $_[3] -ne 0xFFFFFFFF -and $_[3] -ne 0 } | ForEach-Object { $_[3] } | Measure-Object -Minimum).Minimum
        if ($ix.Term + 20 * ($todo.Count + 1) -gt $first) { throw "$path has no spare index slots. Not changed." }
        for ($i = $ix.Term; $i -lt $ix.Term + 20 * ($todo.Count + 1); $i++) { if ($b[$i] -ne 0) { throw "$path index slots are not empty. Not changed." } }
        $r0 = $ix.List[0]
        $exclusive = ((U32 $b ([int]$r0[3])) -eq $r0[4])   # this file's size field counts the text only
        $ms = New-Object System.IO.MemoryStream
        $ms.Write($b, 0, $b.Length)
        $slot = $ix.Term
        foreach ($rec in $todo) {
            $text = [Convert]::FromBase64String($(if ($lang -eq 'es') { $rec.es } else { $rec.en }))
            $off = [uint32]$ms.Length
            $ms.Write([BitConverter]::GetBytes([uint32]$text.Length), 0, 4); $ms.Write($text, 0, $text.Length)
            $size = if ($exclusive) { $text.Length } else { $text.Length + 4 }
            $arr = $ms.GetBuffer()
            foreach ($pair in @(@(0, [uint32]$rec.group), @(4, [uint32]$rec.instance), @(8, [uint32]0x2026960B), @(12, $off), @(16, [uint32]$size))) {
                [Array]::Copy([BitConverter]::GetBytes([uint32]$pair[1]), 0, $arr, $slot + $pair[0], 4)
            }
            $slot += 20; $added++
        }
        Save-Once $path
        $out = New-Object byte[] $ms.Length; [Array]::Copy($ms.GetBuffer(), $out, $ms.Length)
        Write-New $path $out
    }
    if ($added) { Write-Host "$($dir.Name) [$lang]: $added record(s)" -ForegroundColor Green }
}

# ---- files --------------------------------------------------------------------------------------------------------
foreach ($rel in $data.files) {
    $src = Join-Path $here ($rel -replace '/', '\')
    $dst = Join-Path $Game ($rel -replace '/', '\')
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
Write-Host "Copied $($data.files.Count) community file(s) into Apps" -ForegroundColor Green

# ---- Spanish Civic Deals texts --------------------------------------------------------------------------------------
if ($spanishGame) {
    $p = Join-Path $Game ($data.dll_es.file -replace '/', '\')
    $b = [System.IO.File]::ReadAllBytes($p)
    foreach ($e in $data.dll_es.edits) {
        $old = [Convert]::FromBase64String($e.old); $new = [Convert]::FromBase64String($e.new)
        $cur = New-Object byte[] $old.Length; [Array]::Copy($b, [int]$e.off, $cur, 0, $old.Length)
        if (-not [System.Linq.Enumerable]::SequenceEqual($cur, $old)) { throw "SC3KCivicDeals.dll is not the expected v1.0 at 0x$('{0:X}' -f $e.off). Spanish texts not written." }
        [Array]::Copy($new, 0, $b, [int]$e.off, $new.Length)
    }
    Write-New $p $b
    Write-Host "Civic Deals texts in Spanish ($($data.dll_es.edits.Count) strings)" -ForegroundColor Green
}
Write-Host "Done. Start the game as usual. To remove the community mods: run this with -Restore." -ForegroundColor Green
