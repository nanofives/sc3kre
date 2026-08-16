# HANDOFF.md — SimCity 3000 RE (state @ 2026-08-16)

## 🔴 READ THIS FIRST — two corrections landed 2026-08-16 (late)

1. **The city-save section offset base is `0`, not `+0x0C`.** The `[CONFIRMED, 59/59]` claim for
   `+0x0C` was circular and is **FALSIFIED**. The body header is **8 bytes**; what was read as
   header fields at `+0x08`/`+0x0c`/`+0x10` is the first section's own content. Proof: the
   SIMCITY object frame `{u16 version, u8 flags, u8 extra, u32 0xDEADBEEF}` lands exactly on a
   section start for **2,330 of 3,451 sections at base 0** — and 2,330 is the **total** number of
   `0xDEADBEEF` occurrences in all 59 bodies. At base 12 only 319 line up.
   **Every byte-level observation previously recorded at base 12 is off by 12** and the ones in
   `CITY_SAVE.md` have been re-measured. `re/tools/city_parse.py` is fixed; 59/59 still parse.
2. **The archive DOES frame sections** — frame class `SIMCITY.DLL` `0x10010315` (read) /
   `0x10010531` (write) / `0x1001066c` (dtor) / `0x100106ab` (accessor), vtable
   `PTR_FUN_10013fc0`. It is **opt-in per class**; `SC3ZoneLayer` does not use it.
   Also found: `SIMCITY.DLL FUN_1000351e` is the **city load driver** — layer array at
   `citySim+0x94..+0x98`, each layer's load is **vtable slot `+0x1c`**, called `(citySim, archive)`.
3. **Zone grammar: attempt 7 failed too, forward AND backward from the known end.** Do not
   attempt an eighth. But the section's shape is now measured: `3·N²` + a `900 + 6k` tail, with
   the first `N²` bytes a 1-byte-per-tile raster and `N ∈ {128, 192, 256}`. See `U-029`.
4. **Group `0x21737de5` is named**: the SIMDIRT terrain layer, saver `0x10004d90`, loader
   `0x10004a00`, payload delimited by literal `DirtBag_Start` / `DirtBag_End`. It is the **first
   section of every city file**. Its grammar is chunk-keyed, not the `vt+0x38`/`vt+0x88` mirror
   pair — so the mirror-pair test does **not** find every serialiser.
5. **C0 clusters merged** for the five modules that had never had one: SIMSPR, GZWinD, GZWWWD,
   SIMDIRT, AUDIO (`re/analysis/<M>_CLUSTER1.md`, 124 rows). Tracker now **1,167 of 31,991 =
   3.6%** classified (C1 6 · C2 1,134 · C3 20 · C4 7). The C1 tier is no longer empty.
6. **⭐ THE P1 GATE IS RE-SCOPED** (owner call, 2026-08-16). *"100% of `FUN_*` at ≥ C1"* is
   **retired** — do not measure against it. The gate is now: everything **enumerated** (met,
   31,991 rows) + **≥ C1 across the eleven core-sim modules** + subsystem map (met) + the
   end-state decision (**still open**). UI / audio / tooling / framework modules stay
   "enumerated, unclassified" **by design**.

   **The core-sim set (11 modules), and the only progress number that counts:**

   | module | backlog | ≥C1 | % |
   |---|---|---|---|
   | SIMRCI | 1,536 | 238 | 15.5% |
   | SIMDSTR | 1,191 | 190 | 16.0% |
   | SIMUTIL | 763 | 144 | 18.9% |
   | SIMSERV | 713 | 138 | 19.4% |
   | SIMVARIABLES | 350 | 68 | 19.4% |
   | SIMNTWRK | 809 | 161 | 19.9% |
   | SIMCITY | 587 | 120 | 20.4% |
   | SIMGEOM | 1,148 | 240 | 20.9% |
   | SIMMISC | 1,200 | 252 | 21.0% |
   | SIMECO | 659 | 139 | 21.1% |
   | SimTransit | 619 | 136 | 22.0% |
   | **TOTAL** | **9,575** | **2,384** | **24.9%** |

   The set is **levelled** (15.5%–22.0%), so "attack the worst" is not a useful selector. Pick by
   value, not by percentage.

   **7,191 to go.** Stop quoting the all-binaries 9.3%; it is dominated by 20,670 functions the
   gate does not ask for. SIMCITY / SIMNTWRK / SIMVARIABLES were added to the set on the owner's
   call 2026-08-16 — the original eight were listed before SIMCITY was identified as the tick
   driver.

   > **8.6% → 24.9% of that came from `re/scripts/classify_families.py`, not from reading.**
   > 1,558 rows merged at **C1 only** — a regex did not read anything, and C2 in this project
   > means the decompilation was read. Do not raise those rows to C2 without reading them.
   > Every merged row carries a `[classify_families]` prefix in `notes`, so they are trivially
   > separable from human/worker work.

   > ### The tail now has a tool: `re/scripts/classify_families.py`
   >
   > Bulk-classifies small functions by structural family. **`--validate` first, always** — it
   > scores the classifier against functions humans and workers already labelled, per family,
   > and that number is the only reason to trust the rest of the output. Measured precision:
   > `vtable_install` 100% (8/8), `lazy_singleton` 100% (4/4), `ctor_or_dtor` 92% (12/13, and
   > the single miss was hand-checked — `sc3_cal_today` really is a constructor, the harness
   > just does not recognise a domain name).
   >
   > **The biggest single family is `deleting_dtor` — 475 functions.** It is the MSVC scalar
   > deleting destructor, `dtor(this); if ((flags & 1) != 0) operator_delete(this);`, and the
   > `& 1` guard is the compiler's own signature, so this is an identification rather than a
   > heuristic. It came with a free result: in **all 11 modules the guarded call resolves to
   > exactly ONE target, 100% share** — that target is the module's `operator delete`, an
   > 11-byte `free(param_1)`. All 11 are now named at **C2** (`sc3_<module>_operator_delete`).
   > The 1-target/100% convergence is also the strongest available check on the family: a
   > sloppy pattern would have produced scattered targets.
   >
   > **`forwarder` (35%) and `vcall_wrapper` (0%) are deliberately NOT merged.** They are
   > structurally true and semantically empty: `sc3_powerplant_tick` genuinely is a forwarder,
   > and calling it one tells a reader nothing. Those 990 functions stay C0 so somebody picks
   > them up properly later. Merging them would have bought ~10 more points of "coverage" and
   > destroyed the signal about what still needs reading.
   >
   > **Three bugs in this tool were caught by sampling its output, not by reading the code**, and
   > all three produced plausible-looking numbers while being wrong:
   > 1. the function's own name in the signature line counted as a call, so the zero-call branch
   >    never ran and getters/setters/stubs scored a flat zero;
   > 2. `puStack_c = &LAB_...` (the SEH handler, present in every EH function) was read as a
   >    vtable install;
   > 3. `stub` was tested before the vtable check, so 45 vtable installers were filed as empty.
   >
   > If you extend it: run `--validate`, then hand-read ten random hits per new family.
   >
   > ⚠️ **The size heuristic behind `delegate_cluster.ps1` is nearly exhausted in these two
   > modules, and the "~360 runs" estimate is misleading.** Measured after cluster 3:
   >
   > | | SIMRCI (1,429 C0 left) | SIMMISC (1,102 C0 left) |
   > |---|---|---|
   > | ≥ 500 bytes | ~46 | ~25 |
   > | ≥ 200 bytes | ~212 | ~120 |
   > | **under 100 bytes** | **~70%** | **~74%** |
   >
   > Cluster 1 read 1447-814 byte functions, cluster 2 ~800-700, cluster 3 ~700-500. By cluster
   > 5 a run is deep-reading 300-byte helpers, and the last ~70% are sub-100-byte accessors and
   > forwarding stubs. **Grinding those 25-at-a-time is the wrong tool.** What they need is a
   > bulk classifier that groups by vtable slot / single-caller / size signature and labels whole
   > families at once. Design that before spending another 300 cluster runs.

---

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
  **Real backlog: 31,991 `FUN_*` across all 31 binaries. Classified: 1,034 = 3.2%.**
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

> **GZResourceD's DB was also mutated 2026-08-16**: 3 stream-primitive functions carved (`0x1000c157/69/ad`); export 1,458 -> 1,461, +3 / 0 removed / 1,461 ok / 0 fail.
>
> ⭐ **THE GZCOM STREAM WRITE PRIMITIVES ARE PINNED** (`re/analysis/formats/CITY_SAVE.md`) and they apply to EVERY serialiser in the project, not just the city save: stream `vt+0x64` and `vt+0x84` = `Write(ptr,len)` raw block, `vt+0x68` = write u8, `vt+0x88` = write u32, all forwarding to `vt+0xac`. The stream is IID `0x199627`, QI'd in 18 of the 31 modules; its QueryInterface is GZResourceD `0x1000b88a` and returns `this` at offset 0.
>
> **SIMRCI's Ghidra DB was MUTATED 2026-08-16** and re-exported. `MakeFunctions.java` force-created
> 4 functions Ghidra's auto-analysis had left uncarved: `0x1000e837`, `0x1001599d`, `0x1002115d`
> (8-byte `CALL <ini loader>; RET 4` stubs) and `0x10030369` (the SC3ZoneLayer base-class write
> thunk, slot 10 of `PTR_FUN_1004d274`). **`re/ghidra_export_simrci/` is now 3,267 files (was
> 3,263)**, verified as +4 added / 0 removed / 3,267 ok / 0 fail.
> Lesson: after any `MakeFunctions` run, **re-export that module** — workers grep the text export,
> and a stale export makes a newly-carved function look absent, which reads as "this vtable slot
> leads nowhere" rather than "the export is out of date".

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
| ⭐ **city save family** | `.sc3`/`.sct`/`.snr`/`.st3` — **59/59 files** | `re/tools/city_parse.py` — IXF container + 24-byte header + **QFS payload**, 59/59 decode, 21.9 MB -> 92.7 MB. See `formats/CITY_SAVE.md` |
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


---

## READY-TO-PASTE KICKOFF PROMPT (new orchestrator session, in the Simcity folder)

> You are the parent orchestrator for the SimCity 3000 RE project (understand-first). Read, in
> order: `HANDOFF.md`, `CLAUDE.md`, `COORDINATION.md`, `ROADMAP.md` (the **P1 exit-gate
> assessment** at the top), `re/analysis/formats/CITY_SAVE.md`, `UNCERTAINTIES.md`.
>
> **State.** The sim is not in `SC3U.exe` — it is 29 GZCOM director DLLs in `Apps\`, all imported
> and exported to `re/ghidra_export_<module>/`. `functions.csv` enumerates **all 31 binaries**:
> **31,991 real `FUN_*`, 1,034 classified (3.2%), C1 tier empty, 7 C4 rows.** Do NOT quote the raw
> 56,754 export count — 22,495 of those files are `Unwind_*` fragments.
>
> **P1's gate is NOT met and `ROADMAP.md` says so.** Do not advance phases. It also recommends
> re-scoping the gate, since "100% at ≥C1" over 31,991 functions is not realistic by hand.
>
> **Formats are done except one thing.** SYS.PAK, `.IXF`, QFS (63,691/63,691), the sprite pixel +
> anchor formats (62,552/62,552 **byte-identical re-encode**), and the whole **city save family**
> (`.sc3`/`.sct`/`.snr`/`.st3`, 59/59, `re/tools/city_parse.py`) all parse. The GZCOM **stream
> primitives are pinned** and apply to every serialiser: read `vt+0x14`/`0x34` raw, `0x18` u8,
> `0x38` u32; write `vt+0x64`/`0x84` raw, `0x68` u8, `0x88` u32; archive `vt+0x20`/`0x30` =
> open-section-by-`{type,group}`.
>
> **The one open format item — read `CITY_SAVE.md` before touching it.** The zone section's
> internal grammar is confirmed from BOTH the saver (`0x100320e7`) and the loader (`0x10031c85`)
> and still does not fit the bytes. **Six sweeps have failed; do not attempt a seventh.** The
> untested assumption is *above* the grammar: `OpenSection` (archive `vt+0x30`) may frame each
> section with a header inside its byte range. Read the **archive class**, which nobody has
> looked at — every finding so far came from its callers.
>
> **Rules.** You are the single writer of `functions.csv`/`STUBS.md`/`UNCERTAINTIES.md`/
> `DEFERRED.md`. Delegate read-only analysis to your read-only worker (see the workspace CLAUDE.md, which is not in this repo) — use
> `re/scripts/delegate_cluster.ps1 -Module <M> -Top 25` for C0 work (pass 2 is obsolete: the C1
> tier is empty), then `re/scripts/merge_worker_module.py <out> <M> --suffix CLUSTER<N> --merge`.
> **Set `$env:REPO_FLEET_DELEGATE`** or those scripts throw. Keep Ghidra runs and all writes local.
> Do not report worker $ cost.
>
> **Hard-won rules, all of which cost real time this session:**
> - **Verify worker claims against the binary.** Several were wrong: a sprite row-record field
>   split contradicted a C4 result, and two SIMUI names encoded guesses the code did not support.
> - **Check the denominator.** `functions.csv` enumerated only SC3U for weeks, so every
>   percentage was ~5x flattering. `re/scripts/enumerate_functions.py` fixed it.
> - **Read the shipped bytes before naming a format after code that reads *a* format.** A
>   `FORM/ALTM/XTER` chunk reader in SIMINIT is a SimCity 2000 importer, not the SC3 save.
> - **Near-miss ids are different ids.** `0x029ca804` is not `TrafficLayer` `0x029ca806`.
> - **After any `MakeFunctions.java` run, re-export that module** — workers grep the text export,
>   and a stale export makes a carved function look absent.
> - **Identify classes by construction, not by vtable pattern-matching.** Searching vtables by
>   slot occupancy produced a false stream candidate; following QueryInterface found it at once.
> - The repo `github.com/nanofives/sc3kre` is **public**: tools + notes only, never assets. The
>   `.gitignore` is deny-by-default and its `re/analysis` rule must stay per-directory — the
>   `**/*.md` form leaks. Verify with `git ls-files`, never by eye.
>
> **Suggested next moves, highest value first:** (1) the archive class / per-section framing
> above; (2) C0 clusters on the untouched modules — SIMSPR, GZWinD, AUDIO, SIMDIRT, GZWWWD have
> had none; (3) name the 7 unnamed persisted CLSIDs (`CITY_SAVE.md` lists exactly what was tried
> and why each attempt failed); (4) `U-001` (HTML consumer) now has a live lead — SIMUI
> `0x1009499e` is an IRC numeric-reply dispatch, i.e. the CityExchange chat client.
>
> Commit at boundaries; keep `.happy/project-info.json` current. Confirm your plan before large runs.
