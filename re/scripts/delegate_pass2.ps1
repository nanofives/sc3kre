<#
  delegate_pass2.ps1 — second-pass module analysis: promote C1 rows to C2, and chase the
  OPEN list from the module's existing analysis doc.

  Pass 1 (delegate_module.ps1) produces a module map plus a mix of C1/C2 rows. Pass 2 is
  narrower and deeper: it hands the worker the EXACT C1 RVAs still outstanding for that module
  and the OPEN section already on disk, and asks for mechanical descriptions rather than more
  breadth.

  Requires $env:REPO_FLEET_DELEGATE (a headless read-only Claude runner); see HANDOFF.md.

  Usage:
    pwsh -NoProfile -File re\scripts\delegate_pass2.ps1 -Module SCENARIO
    pwsh -NoProfile -File re\scripts\delegate_pass2.ps1 -Module SIMADV -DryRun
#>
param(
  [Parameter(Mandatory = $true)][string]$Module,
  # Which existing analysis doc(s) the worker should read first. Defaults to <MODULE>.md.
  # SC3U has no single doc -- its findings are spread over SUBSYSTEMS/LAUNCH_CONTROL/etc.
  [string[]]$Doc,
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$stem = $Module.ToLower()

# SC3U is the odd one out: it is the EXE, its export dir is plain `ghidra_export` (no suffix)
# and its functions.csv module value is "SC3U.exe", not "SC3U.DLL".
if ($stem -eq "sc3u") {
  $dir = "ghidra_export"
  $modName = "SC3U.exe"
} else {
  $dir = "ghidra_export_$stem"
  $modName = if ($Module -like "*.dll") { $Module } else { "$Module.DLL" }
}
$fnDir = Join-Path $Root "re\$dir\functions"
if (-not (Test-Path $fnDir)) { throw "export dir missing: $fnDir" }
$count = (Get-ChildItem $fnDir -File).Count
$rows = Import-Csv (Join-Path $Root "functions.csv") |
        Where-Object { $_.module -eq $modName -and $_.confidence -eq "C1" }
if (-not $rows) { Write-Host "$modName has no C1 rows; pass 2 will chase the OPEN list only" -ForegroundColor Yellow }

$c1 = ($rows | ForEach-Object { "  $($_.rva)  $($_.ghidra_name)  $($_.size) bytes  — currently: $($_.new_name)" }) -join "`n"
if (-not $c1) { $c1 = "  (none — this module is already all C2)" }

# The OPEN section(s) of the existing doc(s), verbatim, so the worker attacks what is left.
if (-not $Doc) { $Doc = @("$($Module.ToUpper()).md") }
# pwsh -File passes an array parameter as ONE comma-joined string, so split it back out.
$Doc = @($Doc | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$docList = @()
$open = ""
foreach ($dn in $Doc) {
  $docPath = Join-Path $Root "re\analysis\$dn"
  if (-not (Test-Path $docPath)) {
    Write-Host "note: $dn does not exist, skipping" -ForegroundColor Yellow
    continue
  }
  $docList += "re/analysis/$dn"
  $lines = Get-Content $docPath
  $i = ($lines | Select-String -Pattern '^#+\s*.*OPEN' | Select-Object -First 1).LineNumber
  if ($i) {
    $open += "`n### from $dn`n" + (($lines[($i - 1)..([Math]::Min($i + 50, $lines.Count - 1))]) -join "`n")
  }
}
if (-not $docList) { throw "none of the named docs exist under re\analysis: $($Doc -join ', ')" }
if (-not $open) { $open = "(no OPEN section found in: $($docList -join ', '))" }
$docRef = $docList -join ", "

$prompt = @"
SimCity 3000 Unlimited reverse-engineering — SECOND PASS on $modName. Prior analysis already exists in: $docRef. READ THOSE FIRST, then go deeper. Do not re-derive what it already establishes.

CRITICAL SETUP FACTS:
- ``re/$dir/functions/`` EXISTS with $count decompiled ``0x<addr>_<Name>.c`` files. Grep it directly; do NOT trust directory listings, and do NOT report the exports as missing.
- YOU CANNOT WRITE FILES (Read/Grep/Glob only). Do NOT return NEEDS_EXECUTION. Return everything as MARKDOWN INLINE in your final message.

RULES (non-negotiable): NO-GUESSING. Only what the decompilation literally shows. Never "probably/likely/seems/appears". Cite [CONFIRMED @ 0xADDR] for every constant, offset and formula. Unknown meaning -> give the raw hex. Unknown purpose -> describe mechanically (reads X, calls Y, writes Z). Uncertain -> [UNCERTAIN] + exactly what evidence is missing. An honest "not determined" beats a plausible guess; claims are checked against the binary.

## JOB 1 — promote these C1 rows to C2

A C1 row is "classified by strings/xrefs only". C2 requires: the decompilation actually READ, the behaviour described MECHANICALLY, the callees identified, and a name. For EACH rva below, give: what it reads/writes (offsets, globals), which functions it calls, the constants it uses, and a ``sc3_<subsystem>_<verb>_<noun>`` name. If a body is too degraded or too trivial to reach C2, say so and leave it C1 — do not inflate.

$c1

## JOB 2 — chase the OPEN list already on disk

Verbatim from the existing doc(s):

$open

For each item: resolve it, or state precisely why it cannot be resolved from the text export alone (e.g. "the value is behind a vtable slot, which lives in .rdata and is not in the decompiled bodies" — that is a legitimate and useful answer, and the orchestrator can run VtableDump.java or pe_read.py for it).

## DELIVER (inline markdown)

1. **Promoted rows** — a CSV block, one row per function you genuinely raised to C2:
   ``rva,subsystem,confidence,new_name,evidence``
   Confidence must be C1 or C2 ONLY. Do NOT claim C3/C4 — those need runtime or a second witness, which you cannot produce; the merge step caps them anyway.
2. **OPEN list resolutions** — one short section per item: RESOLVED (with the RVA evidence) or STILL OPEN (with the exact blocker and which tool would break it).
3. **New findings** — anything material you hit along the way (message ids, tunable tables, cross-module edges), with RVAs.
4. **Revised OPEN** — the remaining unknowns, so the doc's OPEN section can be replaced wholesale.

Cross-reference if useful: ``re/ghidra_export_ios/functions`` (20,051 files) is the SAME ENGINE recompiled for ARM, UNSTRIPPED, with real C++ names. Algorithms and magic constants DO transfer; STRUCT OFFSETS DO NOT (proven: 0 of 5 goPowerPlant offsets matched). Mark any iOS-derived claim [iOS-HINT].
"@

if ($DryRun) { Write-Host $prompt; return }

$delegate = $env:REPO_FLEET_DELEGATE
if (-not $delegate) { throw "Set `$env:REPO_FLEET_DELEGATE to your read-only delegation helper (delegate.ps1)." }
& pwsh -NoProfile -File $delegate -Repo Simcity -Prompt $prompt
