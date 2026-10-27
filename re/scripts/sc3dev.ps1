<#
.SYNOPSIS
  One child workspace per mod task: create, build, run, inspect, remove. Replaces the hand-made
  Proyectos\Simcity_wt_<name> + Simcity_stock_<name> pairs (130 sibling folders by 2026-10-27).

.DESCRIPTION
  Everything lives inside the main repo, under folders the deny-by-default .gitignore already hides:

    Simcity\dev\<name>\wt      git worktree, branch child/<name>   (edit ONLY here)
    Simcity\dev\<name>\tree    hard-linked test tree of the base, no mods in Apps except the loader
    Simcity\dev\<name>\inst    built mods, perf.ini, logs           (SC3MODS_DIR for the game)
    Simcity\stage\release      the LAN staging folder = the default base (was Proyectos\Simcity_release)

  The base's Apps\SC3U.exe is already patched to import sc3mods.dll (sc3mods_patch.ps1), so a tree only needs the
  loader built into its own Apps\. Never edit a linked file in place: delete it and copy first.

  Commands:
    new    <name> [-From main] [-Base <dir>] [-NoBuild]   worktree + tree + loader + all mods
    build  <name> [-Mods a,b]                             build from the worktree (default: every mod the loader loads)
    run    <name> [-City <file in tree\Cities>] [-Stock]  windowed, per-pid mutex, prints the PID (set SC3_PID to it)
    status [-Size]                                        one row per child: branch, merged, ahead, dirty, game running
    remove <name> [-Force]                                refuses if unmerged, dirty, or its game is running
    prune                                                 remove every child that is merged and clean

.EXAMPLE
  pwsh re/scripts/sc3dev.ps1 new autosave
  pwsh re/scripts/sc3dev.ps1 build autosave -Mods sc3resize
  pwsh re/scripts/sc3dev.ps1 run autosave -City "Europolis 1024.sc3"
  pwsh re/scripts/sc3dev.ps1 status
  pwsh re/scripts/sc3dev.ps1 prune
#>
param(
    [Parameter(Mandatory, Position = 0)] [ValidateSet('new', 'build', 'run', 'status', 'remove', 'prune')]
    [string] $Cmd,
    [Parameter(Position = 1)] [string] $Name,
    [string] $From = 'main',
    [string] $Base,
    [string[]] $Mods,
    [string] $City,
    [switch] $Stock,
    [switch] $NoBuild,
    [switch] $Force,
    [switch] $Size
)
$ErrorActionPreference = 'Stop'

# The built-in list in sc3mods.c (load order). sc3mods itself goes to tree\Apps.
$AllMods = 'sc3resize', 'sc3bigcity', 'sc3overscroll', 'sc3simrun', 'sc3perf', 'sc3netmod', 'sc3undo', 'sc3autosave'

# Works from main or from any worktree: the common .git dir sits in main.
$Main = Split-Path (git -C $PSScriptRoot rev-parse --path-format=absolute --git-common-dir)
$Dev = Join-Path $Main 'dev'
if (-not $Base) {
    $Base = Join-Path $Main 'stage\release'
    if (-not (Test-Path $Base)) { $Base = Join-Path (Split-Path $Main) 'Simcity_release' }   # until the move
}

function Paths([string]$n) {
    if (-not $n) { throw "name required" }
    if ($n -notmatch '^[a-z0-9_-]+$') { throw "name '$n': use lowercase letters, digits, - or _" }
    $r = Join-Path $Dev $n
    [pscustomobject]@{ Root = $r; Wt = "$r\wt"; Tree = "$r\tree"; Inst = "$r\inst"; Branch = "child/$n" }
}

function Build([object]$p, [string[]]$list) {
    $bm = Join-Path $p.Wt 're\scripts\build_mod.ps1'
    $src = Join-Path $p.Wt 're\harness\src'
    $env:CL = $null
    & $bm -Mod sc3mods -Src $src -Out "$($p.Tree)\Apps"
    foreach ($m in $list) { & $bm -Mod $m -Src $src -Out $p.Inst }
}

function GameProcs([string]$tree) {
    Get-Process -Name 'SC3U' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($tree, [StringComparison]::OrdinalIgnoreCase) }
}

function Info([string]$dir) {
    $n = Split-Path $dir -Leaf
    $p = Paths $n
    $hasWt = Test-Path "$($p.Wt)\.git"
    $merged = $ahead = $dirty = '-'
    if ($hasWt -and (git -C $Main branch --list $p.Branch)) {
        $ahead = [int](git -C $Main rev-list --count "main..$($p.Branch)" 2>$null)
        $merged = if ($ahead -eq 0) { 'yes' } else { 'no' }
        $dirty = (git -C $p.Wt status --porcelain | Measure-Object -Line).Lines
    }
    $row = [ordered]@{ name = $n; branch = $p.Branch; merged = $merged; ahead = $ahead; dirty = $dirty
                       running = @(GameProcs $p.Tree).Count }
    if ($Size) {
        # worktree + instance only: the tree is hard links to the base and costs almost nothing
        $row.gb_wt_inst = [math]::Round(((Get-ChildItem $p.Wt, $p.Inst -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum).Sum) / 1GB, 2)
    }
    [pscustomobject]$row
}

function Remove([object]$p, [bool]$force) {
    if (@(GameProcs $p.Tree).Count) { throw "$($p.Root): a game from this tree is running; close it first" }
    if (Test-Path "$($p.Wt)\.git") {
        $i = Info $p.Root
        if (-not $force -and $i.merged -ne 'yes') { throw "$($p.Branch) has $($i.ahead) commit(s) not on main; merge it or pass -Force" }
        if (-not $force -and $i.dirty -gt 0) { throw "$($p.Wt) has $($i.dirty) uncommitted change(s); commit them or pass -Force" }
    }
    # rmdir /s does not follow junctions, and deleting a hard link never touches the base's copy
    cmd /c "rmdir /s /q `"$($p.Root)`""
    if (Test-Path $p.Root) { throw "$($p.Root) still present (a file is in use)" }
    git -C $Main worktree prune
    if (git -C $Main branch --list $p.Branch) { git -C $Main branch $(if ($force) { '-D' } else { '-d' }) $p.Branch }
    Write-Host "[-] removed $($p.Root)"
}

switch ($Cmd) {
    'new' {
        $p = Paths $Name
        if (Test-Path $p.Root) { throw "$($p.Root) exists" }
        if (-not (Test-Path "$Base\Apps\SC3U.exe")) { throw "base $Base has no Apps\SC3U.exe" }
        git -C $Main worktree add -b $p.Branch $p.Wt $From
        if ($LASTEXITCODE) { throw "git worktree add failed" }
        py -3.12 (Join-Path $Main 're\tools\netmod\link_tree.py') $Base $p.Tree
        if ($LASTEXITCODE) { throw "link_tree failed" }
        New-Item -ItemType Directory -Force $p.Inst | Out-Null
        if (-not $NoBuild) { Build $p $AllMods }
        Write-Host "[+] $($p.Root)  (branch $($p.Branch) from $From, base $Base)"
    }
    'build' {
        $p = Paths $Name
        Build $p $(if ($Mods) { $Mods } else { $AllMods })
    }
    'run' {
        $p = Paths $Name
        $exe = "$($p.Tree)\Apps\SC3U.exe"
        $env:SC3MODS_MULTI = '1'
        $env:SC3RESIZE_WINMEM = '0'                  # always windowed (memory feedback-always-windowed)
        if ($Stock) { $env:SC3MODS_OFF = '1' } else { $env:SC3MODS_DIR = $p.Inst }
        $sp = @{ FilePath = $exe; WorkingDirectory = "$($p.Tree)\Apps"; PassThru = $true }
        if ($City) { $sp.ArgumentList = "`"$($p.Tree)\Cities\$City`"" }
        $proc = Start-Process @sp
        Set-Content "$($p.Root)\last_pid" $proc.Id
        Write-Host "[+] SC3U pid $($proc.Id)  logs: $($p.Inst)   (set SC3_PID=$($proc.Id) for sc3io tools)"
    }
    'status' {
        if (-not (Test-Path $Dev)) { Write-Host "no children under $Dev"; break }
        Get-ChildItem $Dev -Directory | ForEach-Object { Info $_.FullName } | Format-Table -AutoSize
    }
    'remove' { Remove (Paths $Name) $Force.IsPresent }
    'prune' {
        if (-not (Test-Path $Dev)) { break }
        $rows = @(Get-ChildItem $Dev -Directory | ForEach-Object { Info $_.FullName })
        $i = 0
        foreach ($r in $rows) {
            $i++
            if ($r.merged -eq 'yes' -and $r.dirty -eq 0 -and $r.running -eq 0) {
                Remove (Paths $r.name) $false
                Write-Host "[$i/$($rows.Count)] $($r.name) PASS"
            } else {
                Write-Host "[$i/$($rows.Count)] $($r.name) SKIP (merged=$($r.merged) dirty=$($r.dirty) running=$($r.running))"
            }
        }
    }
}
