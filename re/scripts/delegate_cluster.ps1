<#
  delegate_cluster.ps1 — attack a slice of the C0 backlog: the N largest unreviewed functions
  in one module.

  WHY THIS EXISTS: delegate_pass2.ps1 promotes C1 -> C2, but the C1 tier is now EMPTY
  (2026-08-15), so pass 2 has no Job 1 left and only chases OPEN lists. The remaining backlog is
  31,307 C0 functions. This is the driver for that: it hands a worker a concrete, bounded slice
  chosen by the one heuristic that has worked all along -- code size -- and asks for C1/C2
  classification with evidence.

  Requires $env:REPO_FLEET_DELEGATE (a headless read-only Claude runner); see HANDOFF.md.

  Usage:
    pwsh -NoProfile -File re\scripts\delegate_cluster.ps1 -Module SIMRCI -Top 25
    pwsh -NoProfile -File re\scripts\delegate_cluster.ps1 -Module SIMMISC -Top 20 -DryRun
#>
param(
  [Parameter(Mandatory = $true)][string]$Module,
  [int]$Top = 25,
  [string]$Hint = "",
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$stem = $Module.ToLower()

if ($stem -eq "sc3u") { $dir = "ghidra_export"; $modName = "SC3U.exe" }
else {
  $dir = "ghidra_export_$stem"
  $modName = if ($Module -like "*.dll") { $Module } else { "$Module.DLL" }
}
$fnDir = Join-Path $Root "re\$dir\functions"
if (-not (Test-Path $fnDir)) { throw "export dir missing: $fnDir" }
$count = (Get-ChildItem $fnDir -File).Count

$all = Import-Csv (Join-Path $Root "functions.csv")
# Match the module case-insensitively -- the tracker mixes SIMRCI.DLL / SimTransit.dll styles.
$mine = $all | Where-Object { $_.module -ieq $modName }
if (-not $mine) { throw "no rows for module '$modName' in functions.csv" }
$c0 = $mine | Where-Object { $_.confidence -eq "C0" -and $_.size -match '^\d+$' } |
      Sort-Object { [int]$_.size } -Descending | Select-Object -First $Top
if (-not $c0) { throw "$modName has no sized C0 rows left" }

$done = ($mine | Where-Object { $_.confidence -ne "C0" }).Count
$left = ($mine | Where-Object { $_.confidence -eq "C0" }).Count
$list = ($c0 | ForEach-Object { "  $($_.rva)  $($_.ghidra_name)  $($_.size) bytes" }) -join "`n"
$bytes = ($c0 | Measure-Object { [int]$_.size } -Sum).Sum

$existing = Join-Path $Root "re\analysis\$($Module.ToUpper()).md"
$ctx = if (Test-Path $existing) { "A module map already exists at ``re/analysis/$($Module.ToUpper()).md`` — READ IT FIRST and build on it; do not re-derive the director/registration table." }
       else { "No module map exists for this module yet." }

$prompt = @"
SimCity 3000 Unlimited reverse-engineering — C0 BACKLOG CLUSTER for $modName$(if ($Hint) { " ($Hint)" }).

$ctx

CRITICAL SETUP FACTS:
- ``re/$dir/functions/`` EXISTS with $count exported bodies. Grep it directly; do NOT trust directory listings and do NOT report the exports as missing.
- YOU CANNOT WRITE FILES (Read/Grep/Glob only). Do NOT return NEEDS_EXECUTION. Return everything as MARKDOWN INLINE in your final message.
- Module status: $done functions classified, **$left still C0**. This task covers the $Top largest of those C0 functions ($('{0:N0}' -f $bytes) bytes of code).

RULES (non-negotiable): NO-GUESSING. Only what the decompilation literally shows. Never "probably/likely/seems/appears". Cite [CONFIRMED @ 0xADDR] for every constant, offset and formula. Unknown meaning -> give the raw hex. Unknown purpose -> describe mechanically (reads X, calls Y, writes Z). Uncertain -> [UNCERTAIN] + exactly what evidence is missing. An honest "not determined" beats a plausible guess; claims are checked against the binary.

## THE SLICE — the $Top largest C0 functions in this module

$list

## WHAT TO DO

For EACH function above, in size order (biggest first — if you run short, having 10 deep results beats 25 shallow ones):
1. Read the decompiled body.
2. Say mechanically what it does: what it reads/writes (struct offsets, globals), which functions it calls, which constants/tunables/message ids it uses, and what its arguments are.
3. Assign a subsystem and a ``sc3_<subsystem>_<verb>_<noun>`` name.
4. Rate it C1 (classified from strings/xrefs only) or C2 (body read + mechanically described + callees identified + named). **Do NOT claim C3/C4** — those need runtime or a second witness you cannot produce, and the merge step caps them anyway.

Look especially for: a per-tick / Simulate entry point, save/load serialisation, message-id dispatch tables, and any tunable table with named keys — those are the highest-value finds and should be called out prominently.

## DELIVER (inline markdown)

1. **Classification table** as a CSV block — one row per function you actually read:
   ``rva,subsystem,confidence,new_name,evidence``
2. **Notable findings** — anything structural (tick entry, serialiser, dispatch table, tunables), with RVAs.
3. **Not determined** — any function in the slice you could not classify, and the exact missing evidence.

Cross-reference if useful: ``re/ghidra_export_ios/functions`` (20,051 files) is the SAME ENGINE recompiled for ARM, UNSTRIPPED, with real C++ names (cSC3..., goCitySimulator, goZoneDeveloper...). Algorithms and magic constants DO transfer; STRUCT OFFSETS DO NOT (proven: 0 of 5 goPowerPlant offsets matched). Mark any iOS-derived claim [iOS-HINT].
"@

if ($DryRun) { Write-Host $prompt; return }

$delegate = $env:REPO_FLEET_DELEGATE
if (-not $delegate) { throw "Set `$env:REPO_FLEET_DELEGATE to your read-only delegation helper (delegate.ps1)." }
& pwsh -NoProfile -File $delegate -Repo Simcity -Prompt $prompt
