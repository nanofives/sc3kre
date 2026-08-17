# HANDOFF.md — SimCity 3000 RE (state @ 2026-08-17)

## ⭐ WHERE THE PROJECT IS

**End-state: a MODDING / FORMAT TOOLKIT.** Decided 2026-08-17; the source-port option is
**closed** (`ROADMAP.md`, P1 gate).

**⭐ P1 criterion 2 was RE-SCOPED 2026-08-17 (owner's call). The gate is now ≥ C2 across the
513-function TOOLKIT-NECESSARY set — 279/513 = 54.4%, 234 left to READ** (was 251/513 when
the gate was adopted; SIMRCI cluster 4 read 25 of them). The old form (≥C1
across all 9,575 core-sim functions, 24.1%) is **retired — stop quoting it.** P1 is met except
this one criterion.

The set is derived from the binary, not chosen: pinned GZCOM stream-slot users, section-TYPE
literal writers, functions naming a class id that occurs as a section `group`, and `.INI`
loaders. 513 = 5.4% of the core-sim set, **recall 50/50 = 100%** against the unrelated
`find_section_producers.py`, and threshold-insensitive (119–427 to read across a 6x range).
Re-measure, never quote: `py -3.12 re/scripts/scope_toolkit.py [--validate|--todo <MODULE>]`.
Analysis and the four options considered: `re/analysis/GATE_RESCOPE.md`.

Two numbers behave differently and it matters: **513 is stable** (binary-derived); **the
remaining count is a snapshot** (tracker-derived) — it was 262 at adoption and is 234 now. Why C2 rather than C1: 1,473 of the old count were
`classify_families.py` regex labels with nothing read, and only **839** core-sim functions had
ever actually been read. The set shrank 19x and the bar went up a notch.

The work list feeds the existing delegation path directly:
```
py -3.12 re\scripts\scope_toolkit.py --todo SIMRCI > slice.txt
pwsh -NoProfile -File re\scripts\delegate_cluster.ps1 -Module SIMRCI -RvaFile slice.txt
```
`-RvaFile` is new; the size heuristic is no longer the only selector, and the gate no longer asks
for the sub-100-byte tail that heuristic was down to.

**Cluster 4 (SIMRCI, 25 rows) is merged and it is the template for the remaining ~9 runs:**
delegate → `re/scripts/verify_worker_rows.py <out> <MODULE>` → merge only what survives →
hand-read every flag. All 25 rows passed; three produced findings recorded in `CITY_SAVE.md`
(a mechanical witness on the `0x16` tile value, a THIRD independent copy of the frame reader at
SIMRCI `0x1003fb73`, and field-for-field confirmation of the `u16`-permutation reader
`0x1004350e`). Two rows collided with the concurrent session's unverified C3 rows and the merge
kept C3 — so two toolkit-set functions now count as done on evidence nobody has checked.

**`verify_worker_rows.py` is new and it is not optional.** `merge_worker_module.py` scrubs leaks
and caps C3+, but checks no claim. The verifier resolves every cited constant against the body
(as integer values, across hex / decimal / `FUN_` symbols / **C character escapes**), requires a
serialisation name to be backed by a stream slot or an INI string, and rejects hedging words.
Calibrate before trusting it: on the already-merged `SIMRCI_CLUSTER3.md` it flags 4 of 25.

> ⚠️ **A CONCURRENT SESSION IS WRITING `functions.csv`.** During 2026-08-17 it added 127
> `[GZ-IID]` annotation rows and then **17 rows at C3**, and that shifted a gate number between
> two runs of the same script (SIMRCI 57 → 55 to read). Nothing was lost — row count is
> unchanged at 36,790 and my merges preserved its notes — but this file is supposed to have a
> single writer, and **C3 means behaviour confirmed by runtime, a second witness or data-file
> validation**, so those 17 rows should be checked against the binary before they are trusted.

**⭐ DONE 2026-08-17 — the city-save WRITER round-trips shipped `.sc3` files BYTE-IDENTICALLY,
59/59 at every layer.** The toolkit branch's first deliverable, and it passed the sprite bar.

```
py -3.12 re/tools/city_roundtrip.py "Cities"
L0 container 59/59 · L1 record 59/59 · L2 archive 59/59 · L3 QFS 59/59 · L4 whole file 59/59
```

Every layer is re-emitted **from parsed structure**, nothing copied through, and L4 recomputes
both length fields from the bytes it emitted. Full write-up: `formats/CITY_SAVE.md` ("THE WRITER")
and `formats/QFS.md`.

**The expected blocker was not one. The QFS COMPRESSOR is in the game** — GZResourceD
`FUN_1001694d` via `FUN_100168cb` `[CONFIRMED]`, transcribed in `re/tools/qfs_encode.py`, and it
reproduces all 59 shipped streams exactly. It selects matches by **net gain**
(`matchLen - tokenCost`), not by length, and the shipped files used its `quick = 1` mode
(`quick = 0` compresses 4.7% better and is therefore provably not what shipped).

> **The method lesson is the transferable part.** A probe of the shipped streams measured the
> encoder taking the longest available match only 82.0% of the time and the nearest such offset
> 67.8% — which looks precisely like an unreproducible heuristic, and "byte-identical QFS is
> unattainable, here is the weaker bar" was one step from being written down. It was wrong: the
> probe had no cost model. What broke it was a question rather than a measurement — *the game
> writes `.sc3` files, so where is its compressor?* **Before concluding a behaviour cannot be
> reproduced, check whether the code that produces it shipped.**

**Scope limit, stated plainly:** section payload bytes are re-emitted verbatim, so this is an
**edit-and-rewrite** pipeline (parse, change bytes at a decoded offset, emit a valid file), not
authoring a city from scratch — that would mean reimplementing the layer savers.

**The city save is READ-solved.** Container, 24-byte header, QFS, section archive, per-section
frame, **all 44 section groups traced to their serialisers**, map dimension `N` readable, zone
layer decoded to per-tile developer slots with R/C/I/Landfill named. Tools: `re/tools/city_parse.py`,
`re/tools/city_sections.py`, `re/scripts/find_section_producers.py`.

### Method lessons from 2026-08-16/17 — these cost real time, read them

1. **Silent tool failures were the dominant time sink — four in one session.** Every one
   produced plausible output with no error: a regex needing 8 hex digits when Ghidra strips
   leading zeros; an assumed store order; a call-listing regex that skipped slot-0 calls
   entirely; a classifier counting a function's own name as a call. **Every one was caught by a
   disagreement between two methods, never by re-reading the code.** Cross-check tools against
   readers, and hand-sample output.
2. **Don't reason backwards from a discrepancy to a cause.** Four inferences about one ~138-byte
   gap were all wrong (`vt+0x98` non-scalar; blocks as 4-byte elements; saver/loader asymmetry;
   the alignment contradiction). Each made the arithmetic close and each was falsified by
   reading. Measure the cause.
3. **Re-read the function, not the summary of it.** `CITY_SAVE.md`'s grammar was derived from
   the saver twice and the loader once and was still missing two writes.
4. **A validation harness can go circular.** After the classifier's first merge it began scoring
   its own rows and "improved" from 12/13 to 626/627. Ground truth must exclude your own output.
5. **A coverage number that only ever rises is not measuring anything.** The classifier reverted
   85 of its own rows on re-run; core-sim went 24.9% → 24.0% and that was correct.
6. **2026-08-17 added FOUR more silent zero-match regexes, so treat this as the default failure
   mode, not an anomaly.** (a) `\.ini` matched nothing because Ghidra renames dots to underscores
   (`s_Sys_SC3ComLayer_ini_...`) — reported 0 INI loaders across 11 modules; (b) a gate-cost line
   compared two different denominators and printed 9,388 where an independent count said 7,263;
   (c) writing a regex through a bash heredoc turned `\b` into literal BACKSPACE bytes, and
   `print(pattern)` rendered them invisibly, so the pattern LOOKED right while matching nothing;
   (d) the row verifier had no case for **C character escapes**, so a correct claim citing `0x16`
   — present in the body as `'\x16'` — was reported as a fabricated constant. **(d) is the one to
   remember: when a checker accuses a claim, check the checker first.** Edit regex code with a
   real editor, and give every checker a `--selftest` against strings whose answers you know.

## 🔴 What landed 2026-08-16 (still current unless corrected above)

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
3. ~~**Zone grammar: attempt 7 failed. Do not attempt an eighth.**~~ **SUPERSEDED 2026-08-17 —
   the zone section is now decoded.** The grammar starts at `N*N` and parses in 59/59; all eight
   earlier sweeps failed for one reason, they required it to consume to the section end and it
   never does. The `3·N²` reading was also wrong: only the first `N*N` is a raster, the rest is
   a `u16`-per-tile permutation written by a sub-object at `this+0x268` (slot 1 writes, slot 0
   reads), and the loader's second arm is a **failure fallback** that recomputes a histogram,
   not a format variant. `N` is readable from the SIMGEOM tile-grid section. See `CITY_SAVE.md`
   and `U-029`; open items there are semantic (the permutation's purpose, the `3000/5000/8000`
   keys, a `this+0x3c` 23-vs-92-byte mismatch).
4. **Group `0x21737de5` is named**: the SIMDIRT terrain layer, saver `0x10004d90`, loader
   `0x10004a00`, payload delimited by literal `DirtBag_Start` / `DirtBag_End`. It is the **first
   section of every city file**. Its grammar is chunk-keyed, not the `vt+0x38`/`vt+0x88` mirror
   pair — so the mirror-pair test does **not** find every serialiser.
5. **C0 clusters merged** for the five modules that had never had one: SIMSPR, GZWinD, GZWWWD,
   SIMDIRT, AUDIO (`re/analysis/<M>_CLUSTER1.md`, 124 rows). (tracker figures superseded — see the gate table below).
6. **⭐ THE P1 GATE IS RE-SCOPED** (owner call, 2026-08-16). *"100% of `FUN_*` at ≥ C1"* is
   **retired** — do not measure against it. The gate is now: everything **enumerated** (met,
   31,991 rows) + **≥ C1 across the eleven core-sim modules** + subsystem map (met) + the
   end-state decision (**still open**). UI / audio / tooling / framework modules stay
   "enumerated, unclassified" **by design**.

   **The core-sim set (11 modules), and the only progress number that counts:**

   | module | backlog | ≥C1 | % |
   |---|---|---|---|
   | SIMDSTR | 1,191 | 221 | 18.6% |
   | SIMRCI | 1,536 | 315 | 20.5% |
   | SIMUTIL | 763 | 177 | 23.2% |
   | SIMSERV | 713 | 168 | 23.6% |
   | SIMVARIABLES | 350 | 83 | 23.7% |
   | SIMCITY | 587 | 140 | 23.9% |
   | SIMECO | 659 | 167 | 25.3% |
   | SimTransit | 619 | 164 | 26.5% |
   | SIMGEOM | 1,148 | 310 | 27.0% |
   | SIMNTWRK | 809 | 222 | 27.4% |
   | SIMMISC | 1,200 | 332 | 27.7% |
   | **TOTAL** | **9,575** | **2,299** | **24.0%** |

   The set is **levelled** (18.6%–27.7%), so "attack the worst" is not a useful selector. Pick by
   value, not by percentage.

   **7,276 to go.** Stop quoting the all-binaries 17.0%; it is dominated by 20,670 functions the
   gate does not ask for. SIMCITY / SIMNTWRK / SIMVARIABLES were added to the set on the owner's
   call 2026-08-16 — the original eight were listed before SIMCITY was identified as the tick
   driver.

   > **8.6% → 24.0% of that came from `re/scripts/classify_families.py`, not from reading.**
   > 4,009 rows merged at **C1 only** — a regex did not read anything, and C2 in this project
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
   > **Run across all 31 binaries with `--all-modules`** (2026-08-16): 4,009 rows at C1,
   > all-binaries coverage 9.3% → **17.0%**. The gate is still measured over the core-sim set
   > only, so those extra rows do not inflate it — they are free coverage for whoever opens a
   > UI or framework module later.
   >
   > ⚠️ **The core-sim number went DOWN in that run, 24.9% → 24.0%, and that is correct.**
   > Widening the validation set exposed two more pattern bugs, and re-running **reverted 85
   > rows it had previously written**. The tool now re-examines its own output on every run and
   > actively resets verdicts that no longer hold, rather than freezing a bad label in place.
   > A coverage number that only ever rises is not measuring anything.
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

7. **⭐ END-STATE DECIDED (owner call, 2026-08-17): a MODDING / FORMAT TOOLKIT.** The
   source-port option is **closed**, not deferred — 31,991 functions across 31 interdependent
   binaries with the sim spread over eleven of them. `ROADMAP.md` carries the full rationale.
   **P1 gate criterion 5 is now MET.**

   Consequence for RE work: annotate-first still holds, but the *purpose* narrows to **what a
   toolkit needs**. Deprioritise anything that only matters to a reimplementation (per-tick sim
   math, render internals, UI behaviour) unless it blocks a format. The core-sim ≥C1 target
   (24.0%) should be re-scoped against this — a toolkit likely does not need all 9,575.

   **First deliverable, and it is falsifiable: a city-save WRITER that round-trips a shipped
   `.sc3` byte-identically.** Reading 59/59 is not the same as writing one the game accepts.
   The bar to match is the sprite work: 62,552/62,552 byte-identical re-encode.
---

> ⚠️ **EVERYTHING BELOW THIS LINE IS THE 2026-08-15 SNAPSHOT AND IS PARTLY SUPERSEDED.**
> Kept for the parts that are still the best record (module recipe, pinned classes, sim models,
> cross-RE rule, tooling). Do **not** trust these specifically:
> * the **`3.2% classified`** figure and any per-module percentage — see the gate table above;
> * **"C1 tier is EMPTY"** — it is now the largest tier (4,015 rows, mostly `classify_families`);
> * anything about the **city save** — the container section base was `+0x0C` and is **0**, and
>   the zone section is decoded; `CITY_SAVE.md` is the only current source;
> * **"the grammar is confirmed from BOTH the saver and the loader"** — true only up to block C;
> * the **next-moves list** at the foot — superseded by the toolkit decision in `ROADMAP.md`.
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

> You are the parent orchestrator for the SimCity 3000 RE project. Read first, in order:
> `HANDOFF.md` (the head — "WHERE THE PROJECT IS" — is current; everything under the
> ⚠️ banner is a 2026-08-15 snapshot and partly dead), `ROADMAP.md` (the P1 gate and the
> **END-STATE DECIDED** block), `re/analysis/formats/CITY_SAVE.md`, and `U-029` in
> `UNCERTAINTIES.md`. Boot from those, not from any transcript.
>
> **STATE.** End-state is a **modding / format toolkit**; the source-port option is **closed**
> (owner call 2026-08-17). P1's gate is met except criterion 2 — ≥C1 across the eleven core-sim
> modules, **2,299 / 9,575 = 24.0%** — and that criterion should itself be re-examined now that
> the end-state is a toolkit, since a toolkit likely does not need all 9,575.
>
> **THIS SESSION'S GOAL: the first toolkit deliverable — a city-save WRITER that round-trips a
> shipped `.sc3` BYTE-IDENTICALLY.** Reading 59/59 is not writing. The bar to match is the sprite
> work (62,552/62,552 byte-identical re-encode). Until that passes, "the city save is solved"
> means solved for reading. Start by re-emitting an unmodified file through
> container → 24-byte header → QFS → section archive → per-section frame, and diff. Expect QFS
> re-compression to be the hard part; `re/tools/qfs.py` decompresses but a byte-identical
> *compressor* has never been demonstrated. If it cannot be bit-exact, say so early and define
> the weaker bar (game accepts the file) explicitly rather than sliding into it.
>
> **WHAT IS ALREADY DONE — do not redo it.** City save: container, header, QFS, section archive,
> per-section frame, **all 44 section groups traced to their serialisers**, map dimension `N`
> readable from the SIMGEOM tile-grid section, zone layer decoded to per-tile developer slot
> indices with **Residential / Commercial / Industrial / Landfill named from their `SC3Tune.INI`
> sections**. Tools: `re/tools/city_parse.py`, `re/tools/city_sections.py`,
> `re/scripts/find_section_producers.py`. Also settled: the `+0x188`/`+0x18c` conflict was
> multiple inheritance (both readings correct), and the loader's second arm is a **failure
> fallback**, not a format variant.
>
> **DEAD ENDS — do not reopen without new evidence.** The eight zone-grammar sweeps (the grammar
> is at `N*N`; they all failed because they required it to consume to the section end). The
> `3·N²` three-plane reading (only the first `N*N` is a raster). The `+0x0C` section base (it is
> **0**). `U-006` (no `0x41F836xx` GZCLSID exists in any shipped binary). "Dimensions are in
> SC3WorldLayer" (they are not; they are in the tile-grid section).
>
> **METHOD RULES — these cost the most time in the last session, all five are in `HANDOFF.md`.**
> (1) **Silent tool failures were the dominant time sink — four in one session**, every one
> plausible-looking with no error, every one caught by a *disagreement between two methods* and
> never by re-reading code. Cross-check tools against readers and hand-sample output.
> (2) **Never reason backwards from a discrepancy to a cause** — four inferences about one
> 138-byte gap were all wrong. Measure the cause. (3) **Re-read the function, not the summary of
> it** — `CITY_SAVE.md`'s grammar was derived three times and still missed two writes.
> (4) A validation harness can go **circular** once it scores its own output. (5) A coverage
> number that only ever rises is not measuring anything.
>
> **PROJECT RULES.** You are the single writer of `functions.csv` / `STUBS.md` /
> `UNCERTAINTIES.md` / `DEFERRED.md`. Delegate read-only analysis to the account2 worker
> (`re/scripts/delegate_cluster.ps1 -Module <M> -Top 25`, then
> `re/scripts/merge_worker_module.py <out> <M> --suffix CLUSTER<N> --merge`); **set
> `$env:REPO_FLEET_DELEGATE`** or those scripts throw. Keep Ghidra runs and all writes local. Do
> not report worker $ cost. **VERIFY worker claims against the binary before merging** — several
> were wrong. `re/scripts/classify_families.py` bulk-labels the small-function tail at **C1
> only**; run `--validate` first and never promote its rows to C2 without reading them.
>
> **PUBLIC REPO.** `github.com/nanofives/sc3kre` is public: tools and notes only, never assets.
> `.gitignore` is deny-by-default and its `re/analysis` rule must stay per-directory (the
> `**/*.md` form leaks). Grep every diff for `C:\Users\`, the worker account name and the owner's
> email before committing. ⚠️ **Known unresolved:** the local Windows username is already in the
> repo's *history* from a delegation footer; scrubbed going forward, a history rewrite is the
> owner's call.
>
> **OPEN ITEMS, ranked.** (1) the save writer above; (2) `U-029` semantics — what the `u16`
> per-tile permutation is for, what the `c1` keys `3000/5000/8000` index, and a `this+0x3c`
> 23-byte-vs-92-byte mismatch; (3) re-scope core-sim ≥C1 against the toolkit decision;
> (4) **windowed mode — ROOT CAUSE now found** (`LAUNCH_CONTROL.md` §16-§21, `U-039`): windowed
> surfaces are created 32bpp while the engine renders 16bpp, so 16bpp output never lands in the
> presented surfaces (black client). One defect also explains U-024 and U-025. Two fixes landed
> in the harness (`-nokeysrc` clears a 100%-failing `DDBLT_KEYSRCOVERRIDE`; U-033 path bug), but
> both are in `re/harness/src`, which is gitignored. Cheap confirmation pending: set the desktop
> to 16bpp and launch windowed. LAUNCH_CONTROL.md is uncommitted (§16-§21 added this session).
>
> **ASK ME** rather than deciding: whether to exclude `re/harness` (1.2 GB of regenerable
> framebuffer BMPs) from `backup.ps1`, and whether to rewrite the public repo's history.
>
> Commit at boundaries; keep `.happy/project-info.json` current; confirm before large delegation
> runs.