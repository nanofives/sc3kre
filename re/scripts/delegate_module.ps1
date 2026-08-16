<#
  delegate_module.ps1 — fan one read-only GZCOM-module analysis at a delegated worker.

  Wraps an external read-only delegation helper (delegate.ps1, NOT part of this repo) with the
  standard SimCity RE module-analysis brief, so the
  per-module prompt (setup facts, NO-GUESSING rules, GZCOM recipe, deliverable shape) lives in
  one place instead of being retyped per module.

  Usage:
    pwsh -NoProfile -File re\scripts\delegate_module.ps1 -Module SIMNTWRK -Hint "networks"
#>
param(
  [Parameter(Mandatory = $true)][string]$Module,
  [string]$Hint = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dir = "ghidra_export_" + $Module.ToLower()
$fnDir = Join-Path $Root "re\$dir\functions"
if (-not (Test-Path $fnDir)) { throw "export dir missing: $fnDir" }
$count = (Get-ChildItem $fnDir -File).Count

$prompt = @"
SimCity 3000 Unlimited reverse-engineering. Read-only analysis of the GZCOM director module $Module.DLL ($Hint). Read CLAUDE.md and re/analysis/MODULE_MAP.md first.

CRITICAL SETUP FACTS - do not re-derive these, and do not report the exports as missing:
- The decompiled C export directory ``re/$dir/functions/`` EXISTS and contains $count files named ``0x<addr>_<Name>.c``. A previous worker wrongly returned NEEDS_EXECUTION claiming the exports were absent, based on a directory listing. DO NOT trust directory listings. Just Grep with path ``re/$dir/functions``. An empty grep result is a real negative, not a missing directory.
- YOU CANNOT WRITE FILES (Read/Grep/Glob only). Do NOT return NEEDS_EXECUTION and do NOT ask the orchestrator to run a write command. Return your entire deliverable as MARKDOWN INLINE IN YOUR FINAL MESSAGE. The orchestrator will write it to disk.

RULES (from CLAUDE.md, non-negotiable):
- NO-GUESSING. Report only what the decompilation literally shows. Never write probably/likely/seems/appears.
- Cite an exact RVA for every constant, offset and formula, as [CONFIRMED @ 0xADDR].
- Unknown meaning -> report the raw hex/decimal. Unknown purpose -> describe mechanically (reads X, calls Y, writes Z).
- Uncertain -> mark [UNCERTAIN] and state exactly what evidence is missing.
- An honest "not determined" beats a plausible-sounding guess. Your claims will be checked against the binary.

THE GZCOM MODULE RECIPE (holds for every module - use it to orient fast):
  GZDllGetGZCOMDirector (PE export) -> guarded static director ctor -> N x register_class(director, GZCLSID, factory, 0) inserting into a map at director+0x14 -> each factory does operator_new(size) + ctor, and may return object+N for a sub-interface.
  TRAP: factory stubs are reached only via that registration table (a DATA ref), so Ghidra often leaves them as bare LAB_* with no exported body. If a factory looks missing, say so rather than inventing it.

DELIVER, as inline markdown for ``re/analysis/$Module.md``:
1. **Purpose** - one paragraph on what this module does, grounded in its strings and class names.
2. **Director + registrations** - the GZDllGetGZCOMDirector chain, the director ctor RVA, how many classes it registers, and a table of every GZCLSID you can recover with its factory RVA and allocation size. Note which class-name strings appear (e.g. SC3FireLayer, SC3DisasterLayer).
3. **Key subsystems** - for the 5-15 most important functions: what they mechanically do, their callees, the constants/tunables they read, any message ids they send.
4. **Data/tunables** - exemplar or property keys, .IXF/resource keys, magic constants, tables. Give raw hex.
5. **Cross-module edges** - which other modules/services it calls into (by GZCLSID or IID).
6. **Classification table** in CSV form, one row per function you read well enough to classify:
   rva,subsystem,confidence,new_name,evidence
   Confidence ladder: C1 = subsystem-classified + one-line purpose from strings/xrefs; C2 = decompilation read, mechanically described, callees identified, named. Do NOT claim C3+ (needs runtime or a second witness, which you cannot do). Name functions sc3_<subsystem>_<verb>_<noun>.
   Aim for 25-60 rows of genuine quality over a large shallow list.
7. **OPEN** - what you could not determine and the exact missing evidence for each.

Optional cross-references:
- ``re/ghidra_export_ios/functions`` (20,051 files) is the iOS build of the same engine, UNSTRIPPED, with real C++ names (cSC3..., goPowerLayer, goCitySimulator...). Algorithms and magic constants DO transfer; STRUCT OFFSETS DO NOT (proven: 0 of 5 goPowerPlant offsets matched). Label iOS-derived claims [iOS-HINT] and never present an iOS offset as fact.
- ``re/data/ixf_text.csv`` = 71,924 extracted localized strings.
"@

# This wraps an external read-only delegation helper that is not included in this repo.
# Point REPO_FLEET_DELEGATE at your own delegate.ps1 (a headless read-only Claude runner).
$delegate = $env:REPO_FLEET_DELEGATE
if (-not $delegate) { throw "Set `$env:REPO_FLEET_DELEGATE to your read-only delegation helper (delegate.ps1); it is not part of this repo." }
& pwsh -NoProfile -File $delegate -Repo Simcity -Prompt $prompt
