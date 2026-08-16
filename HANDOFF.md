# HANDOFF.md — SimCity 3000 RE (state @ 2026-08-15)

Snapshot for a fresh orchestrator session. Everything below is on disk; boot from the docs,
not from any prior transcript.

## Where we are
- **Phase:** P0 DONE. **P1 (surface map) ACTIVE.** End-goal: understand + annotate first
  (source-port-vs-toolkit decision deferred to the P1 exit gate). See `ROADMAP.md`.
- **🔴 THE STRUCTURAL FACT:** the simulation is **not** in `SC3U.exe`. That binary is the GZCOM
  shell. The game is **29 GZCOM director DLLs** in `Apps\` (6.2 MB). All are imported and
  exported. See `re/analysis/MODULE_MAP.md` + `MODULE_INVENTORY.md`.
- **Tracker `functions.csv`** now has a **`module` column** (first field).
  ⚠️ **THE DENOMINATOR WAS WRONG UNTIL 2026-08-16.** The tracker enumerated only `SC3U.exe`, so
  every percentage measured ~18% of the binaries. `re/scripts/enumerate_functions.py` fixed it.
  **Real backlog: 31,983 `FUN_*` across all 31 binaries. Classified: 1,016 = 3.2%.**
  (C1 tier is EMPTY — everything anyone has read is ≥ C2.)
  Note the raw export count of 56,754 is **misleading**: 22,495 of those files are `Unwind_*`
  exception fragments, plus 1,118 `Catch_*`, 516 thunks, 662 library-named. Do not quote it.
  Per-module coverage: SIMCITY 10.2% · SIMDSTR 5.7% · SIMGEOM 5.1% · SIMUI 4.3% · SIMMISC 3.8% ·
  SIMRCI 3.1% · SIMBABLD 1.9%. See the P1 exit-gate assessment in `ROADMAP.md`.

## The GZCOM module recipe (holds for every module)
```
GZDllGetGZCOMDirector  (PE export)
  → guarded static director ctor
  → N × register_class(director, GZCLSID, factory, 0)     # inserts into a map at director+0x14
  → factory: operator_new(size) + ctor                    # may return object+N (sub-interface)
```
Registration counts: SIMUI 40 · SIMSPR 40 · SIMRCI 37 · SIMMISC 36 · SIMUTIL 15 · SIMGEOM 14 ·
SimTransit 5 · SIMBABLD 2.

**Trap:** factory stubs are reached only via the registration table (a DATA ref), so Ghidra often
leaves them as bare `LAB_*` with **no exported body**. Recovered 12 in SIMUI + **51 across 17
modules** with `re/scripts/MakeFunctions.java`. Detect with `re/scripts/find_stub_gaps.py`, but
**only trust the registration-signature filter** — a blanket `LAB_*` sweep matches basic-block
labels inside functions and will corrupt the databases.

## Classes pinned (real GZCLSIDs — NOT the `0x41F836xx` ids in CitySim.ini)
`SC3PowerLayer` `0x20afdf44` · `SC3WaterLayer` `0x82bf0042` · `SC3ValveLayer` `0x60a42f32` ·
`SC3ZoneLayer` `0x409ff3ba` · `TrafficLayer` `0x029ca806` · `SC3BuildingLayer` `0xe150e7bb` ·
`SC3BudgetLayer` `0xc11bcc75` · `SC3WorldLayer` `0xe11bddf6` · sprite manager `0xa411112f` ·
**9 power plants** (`0x?14a10??` cluster, Coal `0x814a0fbd` … WasteToEnergy `0x2302193a`).

## Sim models reversed
- **Power** (`POWER_GRID.md`): masked **bitmap dilation flood-fill**, 32 tiles/dword, **cap 600**
  (`0x258` @`0x10004ee2`), over a conductive mask raster + a byte-per-tile demand raster.
  Plant output = `cap − (age − declineAge)·cap/(maxLife − declineAge)`, 0 past maxLife.
- **RCI/zoning** (`SIMRCI.md`): valve effect tables are module-global; 23-slot zone-developer table.
- **Traffic** (`SIMUTIL_SIMTRANSIT.md`): trip/cell-cost commute model, 4 per-zone destination tables.
- **Budget/ordinances/aura/neighbor deals** (`SIMMISC.md`): bonds, the tax "transmogrifier"
  coefficients, the 40-byte ordinance record with prerequisite links.
- **Buildings** (`SIMGEOM.md`): occupant property schema, ids `0x65`–`0x7c`.

## Data formats cracked (all with parsers or full specs)
| format | where | tool |
|---|---|---|
| `SYS.PAK` | 51 ini files | `re/tools/syspak_parse.py` |
| **`.IXF` GZ segment** | localized text, building exports, **all 40 sprite archives** | `re/tools/ixf_parse.py` |
| **QFS / RefPack** | sprite pixel data | `re/tools/qfs.py` — **C4, 63,691/63,691 streams round-trip** |
| **plain-bitmap sprite** | 1,139 effect/UI records | `re/tools/sprite_render.py` — **C4**, 8bpp 5-bit coverage mask |
| **span sprite** | 62,552 records = the main art | `sprite_render.py` + `sprite_encode.py` — **C4, 62,552/62,552 re-encode BYTE-IDENTICAL** |
| **sprite anchor** (type-1) | 62,387 records | `sprite_render.parse_anchor` — **C4**, 4×i16 `{spanL,spanT,spanR,spanB}`, witnessed by `.SII` |
| ⭐ **city save family** | `.sc3`/`.sct`/`.snr`/`.st3` — **59/59 files, 992 records** | `ixf_parse.py` **unchanged** — see `formats/CITY_SAVE.md` (container only; payloads open) |
| FEZC / GVF | iOS assets | `fez_extract.py`, `gvf_dump.py` |

The sprite block's producer is **`GZGraphicD.dll`'s image class** (GZCLSID `0xa487535d`,
IID `0x0487534f`), not SIMSPR: encoder `0x100017de`, consumer `0x10001700`. See `formats/QFS.md`
and `formats/SPRITE_SII.md`.

`.IXF`: magic `0x80C381D7`, 20-byte index `{group, instance, type, offset, size}`, end = key
triple zero, tombstone = `offset`/`size` == `-1`. Reader (GZResourceD `0x1000ca78`) **and** two
writers (SIMBABLD `0x1204f2e7`, SIMSPR `0x100583cf`) all agree.
Extraction: **537 files, 71,924 text records** → `re/data/ixf_text.csv`; sprites: **40 archives,
127,971 records** (63,691 type-0 + 62,387 type-1) → `re/data/sprite_records.csv`.
⚠️ A previous figure of "72 archives / 253,838 records" was **double-counted** (exactly 2x over the
36 `.DAT` files, missing the 4 `.IXF`); corrected 2026-08-15 by the full `qfs.py` sweep.

## Public repo

Tools + notes are published to **https://github.com/nanofives/sc3kre** (public, MIT for our code).
The repo is a **subset** of this working tree, not a mirror: `re/tools/*.py`,
`re/scripts/*.{py,ps1,java}`, `re/analysis/**/*.md`, the root trackers and `functions.csv` — 61
files, ~1.4 MB. **No game binaries, no `re/ghidra_export*`, no `re/data/`, no extracted assets.**
`.gitignore` is deny-by-default (`/*` then an explicit allowlist), with a per-directory deny for
each `re/analysis` subdirectory so a NEW subdir fails safe.

> ⚠️ Do NOT "fix" that `.gitignore` into the tidier `!/re/analysis/**/*.md` form. It was tried and
> it **leaks**: git's `**/` directory re-include exposes the subdirectory's non-md contents, which
> let `re/analysis/formats/gvf_keys.csv` (961 KB of extracted iOS game data) become tracked.
> Verify any change with `git check-ignore -v` and `git ls-files`, never by eye.

> ⚠️ `re/scripts/delegate_module.ps1` no longer hardcodes the worker path (it was scrubbed for
> publication). It **throws unless `$env:REPO_FLEET_DELEGATE` is set** — point it at your
> read-only delegation helper, i.e. the workspace's
> `.claude\skills\repo-fleet\scripts\delegate.ps1` (path is machine-local; see the workspace
> `CLAUDE.md`, which is deliberately not in this repo).

**Not backed up anywhere:** `re/data/` (63,691 rendered sprites), `re/ghidra_export*/` (31 dirs)
and the Ghidra projects are local-only and unversioned.

## Tooling added this session
```
re\scripts\ghidra_headless.ps1 -Module <NAME.DLL> -Import|-Export   # per-module projects
re\scripts\delegate_module.ps1           # fan one module analysis at a read-only worker
re\scripts\merge_worker_module.py        # land a worker's markdown + merge its rows
re\scripts\DumpDisasm.java               # raw instruction listing (when decomp fails)
re\tools\qfs.py                          # QFS/RefPack decompressor
re\tools\sprite_render.py                # sprite -> PNG (both pixel classes + anchors)
re\scripts\import_all_modules.ps1        # bulk import, resumable
re\scripts\recover_all_stubs.ps1         # + find_stub_gaps.py + MakeFunctions.java
re\scripts\VtableProbe.java              # method -> vtable slot -> installing ctor
re\scripts\VtableDump.java               # dump a vtable's slots  (vtables are DATA, ungreppable)
re\tools\ixf_parse.py                    # .IXF/.DAT index + text extraction
re\tools\pe_read.py                      # read .rdata constants straight out of a PE, no Ghidra
```

## The cross-RE rule (hard-won, two results)
**iOS algorithms and magic constants transfer; iOS struct layouts do NOT.**
Confirmed: the `Bit1_SelectionGrow` cap of 600 is literally in SIMUTIL. Refuted: **0 of 5**
`goPowerPlant` field offsets match the PC build. Use iOS to predict *what code does and which
constants to look for* — never *where fields sit*. See `SIM_LAYERS_XREF.md`.

## Uncertainties
Resolved this session: **U-005** (modules), **U-007** (GZCOM resource key), **U-008** (`.IXF` text,
C4 round-trip), **U-009** (power vs water), **U-010** (ValveLayer id), **U-011** (plant field map),
**U-012** (power flood-fill). **Falsified: U-006** — no `0x41F836xx` GZCLSID exists in *any*
shipped binary; building types are pure data. Do not re-attempt.
Open: **U-001** (HTML consumer; lead `0x004a3f0c`), **U-002** (FEZC field0), plus the per-module
open lists at the foot of each analysis doc.

## Next moves (ranked)

> **DONE 2026-08-15:** the whole sprite pipeline. `re/tools/qfs.py` (QFS, 63,691/63,691 streams)
> and `re/tools/sprite_render.py` (both pixel classes) turn all 63,691 records into PNGs.
> Building property ids `0x65`–`0x7c` are in `re/analysis/SIMGEOM_PROPERTIES.md`.

> **ALSO DONE 2026-08-15:** all 7 previously unanalysed sim modules now have a first-pass
> analysis doc — `SIMNTWRK.md` `SIMDSTR.md` `SIMADV.md` `SIMSERV.md` `SIMECO.md` `STRTSIM.md`
> `SCENARIO.md` — via `re/scripts/delegate_module.ps1` + `re/scripts/merge_worker_module.py`.
> Findings are C1/C2 only (workers cannot verify, so C3+ claims are capped on merge).
> Spot-checked against the binary: SIMNTWRK's 2 GZCLSIDs + TilingRules strings, SIMECO's
> pollution-layer factory (`new(0x4d0)`, returns `+0x1c`, CLSID `0xc0a81498`) — all correct.

> **ALSO DONE 2026-08-15 (later):** pass 2 on SCENARIO / SIMADV / SIMECO / SIMDSTR via
> `re/scripts/delegate_pass2.ps1` → `re/analysis/<MODULE>_PASS2.md` (a SUPPLEMENT; the pass-1
> doc is not overwritten). **C1 108 → 46.** And **U-023 + U-024 are resolved** — the sprite
> block's producer is `GZGraphicD.dll`'s image class, and every header field is now named.
> Backups: `re/scripts/backup.ps1` mirrors ~1.2 GB to `D:\Backups\Simcity-RE`.

1. **Remaining C1 (46)**: SC3U 26, SIMUI 13, SIMUTIL 4, GZResourceD/SIMNTWRK/STRTSIM 1 each.
   SC3U and SIMUI are the two big un-passed surfaces.
2. **U-023** — the class behind IID `0x0487534f` (sprite-block consumer). Names the last
   unexplained span-sprite header fields. Needs `VtableProbe.java`, not grep.
3. **SIMGEOM `0x76`–`0x7a`** — 5 of the 7 resource-variant slots have no proven consumer, and
   the purpose-bit names (1/2/4) are still unknown. See `SIMGEOM_PROPERTIES.md` OPEN list.
4. **The `.SII` text mirrors** (10 files beside the sprite `.DAT`s) may name sprite records —
   a cheap cross-check now that the images exist.
4. **Queued live-Ghidra data xrefs** (text export cannot resolve these): config-loader vtable slot
   indices per layer; the scale float `_DAT_1003c644`; the writers of the power mask/demand
   rasters; SIMSPR's post-QFS pixel path.

---

## READY-TO-PASTE KICKOFF PROMPT (new orchestrator session, in the Simcity folder)

> You are the parent orchestrator for the SimCity 3000 RE project (understand-first). Read, in
> order: `HANDOFF.md`, `CLAUDE.md`, `COORDINATION.md`, `re/analysis/MODULE_MAP.md`,
> `re/analysis/MODULE_INVENTORY.md`, `UNCERTAINTIES.md`. We are in **P1 (surface map)**.
>
> Key facts: the sim is NOT in `SC3U.exe` — it is 29 GZCOM director DLLs in `Apps\`, all already
> imported and exported to `re/ghidra_export_<module>/`. `functions.csv` has a `module` column and
> stands at C0 4,843 / C1 44 / C2 319 / C3 8, 340 named. The GZCOM module recipe, the pinned
> GZCLSIDs, the cracked formats (`.IXF`, QFS) and the tooling are all summarised in `HANDOFF.md`.
>
> Rules: you are the **single writer** of `functions.csv`/`STUBS.md`/`UNCERTAINTIES.md`/`DEFERRED.md`;
> delegate read-only analysis to a **headless read-only worker**
> (a delegation helper that runs Claude read-only over this repo; not included here)
> and merge their `rva,subsystem,confidence,evidence` tables; keep Ghidra runs/edits local; do NOT
> report worker $ cost. Tell workers the export directory EXISTS with its file count and to grep
> for addresses rather than trust directory listings (one worker wrongly returned NEEDS_EXECUTION
> claiming the exports were absent). Verify worker claims that contradict what is on disk, and
> use `re/tools/pe_read.py` when an answer is a `.rdata` constant and `re/scripts/VtableDump.java`
> when it is behind a vtable slot.
>
> **First task: build `re/tools/qfs.py`** to the spec in `re/analysis/formats/QFS.md` and decode
> the sprite archives (`ixf_parse.py` already reads them; 253,838 records, type 0 = pixels,
> type 1 = anchor). Validate by checking each stream's declared uncompressed size. Then chase the
> post-decompression pixel encoding (`FUN_1001e086`, bitmap `+0xc8` colour key) so a sprite can be
> written out as an image. In parallel, fan a worker at the building property ids `0x65`–`0x7c`
> (`re/analysis/SIMGEOM.md`) to name each field.
>
> Commit at boundaries; keep `.happy/project-info.json` current. Confirm your plan before large runs.
