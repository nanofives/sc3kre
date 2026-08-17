# SimCity 3000 RE — Roadmap

**North star (current):** a complete, RVA-cited *understanding* of SC3U.exe — every
game-logic function classified and the sim's core systems (RCI demand, budget/tax,
utilities, traffic, pollution, land value) documented — plus round-trip parsers for the
on-disk formats. The **end-state choice** (greenfield source port vs modding/format
toolkit) is a decision at the **P1 exit gate**, made with the mapped surface in hand.

Phases are gates. Do not advance until the current phase's Definition of Done holds.
No fuzzy exit criteria.

## Definitions of Done

**F-DoD (function):** RVA pinned in `functions.csv` against the anchor SHA-256;
confidence ≥ C2 (named + mechanically described + callees resolved); no `[UNCERTAIN]`
left unlogged; inline RVA citations on cross-references.

**S-DoD (subsystem):** every function the subsystem's behavior touches is F-DoD; shared
structs documented field-by-field in `re/analysis/structs/` with RVA citations; any
custom data format has a round-trip parser+writer in `re/tools/`; the subsystem's
`STUBS.md` section is empty.

**P-DoD (project, annotate-first):** every `FUN_*` classified to a subsystem (C1+); every
core-sim subsystem S-DoD; all formats parse; trackers hold only `wontfix`/`deferred` rows
with rationale; a written architecture overview of SC3's simulation.

## Phases

### P0 — Bootstrap  ✅ (2026-08-14)
Scaffold, SHA-256 anchor, own Ghidra 12.1.2 install, headless no-MCP driver + query
helpers, first auto-analysis (9,730 functions), `functions.csv` seeded (4,932 C0 backlog).
**Exit:** ✅ `re/ghidra_export/` greppable; tracker seeded; docs in place.

### P1 — THE GATE, RE-SCOPED (owner decision, 2026-08-16)

The original exit — *"100% of `FUN_*` at ≥ C1"* — was written when the target was one
9,730-function exe. The real target is **31,991 `FUN_*` across 31 binaries**, ~6.5x larger, and
that gate is not reachable by hand. **Re-scoped on the owner's call to the two-tier form the
assessment below recommended.** The old text is preserved further down as the record of why.

**P1 exit (current, binding):**

1. **Every `FUN_*` in all 31 binaries enumerated in `functions.csv`.** ✅ **MET — re-closed
   2026-08-17, 38,092 rows.** It went stale earlier the same day when the Ghidra exports were
   regenerated mid-session; `re/scripts/enumerate_functions.py` added the **129** `FUN_` bodies
   that had no row (SIMRCI 90, SIMMISC 39) and a direct check now finds **0 `FUN_` bodies without
   a tracker row across all 30 binaries**. The script is additive by construction — it appends
   missing rows and never touches an existing one — so no analysis work was at risk.

   > ⚠️ **The gap was first reported here as 271, and that figure was WRONG — mine, not the
   > tool's.** My check matched `'_FUN_' in filename`, which also matches `thunk_FUN_*`; 142 of
   > the 271 were import/jump thunks, which this criterion deliberately excludes. Two methods
   > disagreed (my grep said 271, `enumerate_functions.py --dry-run` said 129) and **the loose
   > one was mine.** Same failure family as the rest of the day: a filter that matched more than
   > it was asked to.
2. **⭐ RE-SCOPED 2026-08-17 (owner's call): ≥ C2 across the TOOLKIT-NECESSARY set.**
   ✅ **MET 2026-08-17 — 530 of 530 = 100%, nothing left to read.**

   Read in 17 delegated clusters across two rounds (301 functions on the day the gate was
   adopted, from 251/513 = 48.9%). Every cluster was checked by
   `re/scripts/verify_worker_rows.py` against the binary before merging; two batches were held
   back on flags and re-read rather than merged.

   > **"Met" means met AT THIS MEASUREMENT.** The set is derived from the export, and the export
   > grew from 513 to 530 members while the reading was in progress. A re-export can add
   > members, so re-run `scope_toolkit.py` rather than quoting 530.

   The old form of this criterion (*"≥ C1 for every function in the eleven core-sim modules"*,
   2,312 / 9,575 = 24.1%) is **retired** — do not measure against it. It was written while the
   end-state was undecided; the end-state is a toolkit, and a toolkit does not need the 7,263
   remaining functions, 71% of which are sub-100-byte accessors.

   **The set is defined by measurement, not by judgement**, and is re-derivable at any time:
   `re/scripts/scope_toolkit.py`. Four criteria — pinned GZCOM stream-slot users (349), section
   TYPE literal writers (138), functions naming a class id that occurs as a section `group` (95),
   `.INI` loaders (71). Union 513 = 5.4% of the core-sim set. **Recall against
   `find_section_producers.py`, an unrelated method: 50/50 = 100%**, and the answer holds across
   a 6x range of the one threshold it has (119–427 to read at min-slot-calls 2..12).

   **Why C2 and not C1:** C1 can be a regex label — 1,473 of the old count were exactly that,
   written by `classify_families.py` with nothing read. A format needs the decompilation read, so
   the set shrank 19x and the bar went up one notch. Only 839 core-sim functions had ever been
   read at all.

   Full analysis, the four options considered and their costs: `re/analysis/GATE_RESCOPE.md`.
   Work list: `scope_toolkit.py --todo <MODULE>` feeds `delegate_cluster.ps1 -RvaFile`.

   > Precision of the set is explicitly NOT measured (a slot offset only means "stream" if the
   > object is one), so the true set is likely smaller than 530, never larger. That cuts the
   > right way for a met gate: the functions read are a superset of the ones strictly needed.
3. UI / audio / tooling / framework modules: **"enumerated, unclassified" is acceptable** — 16
   modules, 20,670 functions, no per-function requirement.
4. Subsystem map committed to `re/analysis/SUBSYSTEMS.md`. ✅ MET.
5. **End-state decision (port vs toolkit) taken.** ✅ **MET — 2026-08-17. The end-state is a
   MODDING / FORMAT TOOLKIT.** Owner's call. See below.

### ⭐ END-STATE DECIDED: modding / format toolkit (2026-08-17)

**The source-port option is closed.** Not deferred — closed. Anyone reopening it should have to
argue against the evidence here, not merely prefer it.

*Why not a port:* 31,991 functions across 31 interdependent GZCOM binaries, with the simulation
spread over eleven of them. At the honest current rate that surface is not reimplementable by
one person, and nothing found since has changed that arithmetic.

*Why a toolkit is reachable now:* the format layer is not a plan, it is working code.

| format | status |
|---|---|
| QFS / RefPack | **C4**, 63,691/63,691 streams round-trip |
| sprite pixel + anchor | **C4**, 62,552/62,552 re-encode **byte-identical** |
| `.IXF` GZ segment | **C4** round-trip |
| `SYS.PAK` | parsed, 51 ini files |
| **city save family** | **59/59** — container, 24-byte header, QFS, section archive, per-section frame, **all 44 section groups traced to their serialisers**, zone layer decoded to tile level |
| FEZC / GVF (iOS) | parsed |

The content is also overwhelmingly **data-driven** — `U-006` proved there are no per-building
classes in code, and `SC3Tune.INI` / `SYS.PAK` drive the taxonomy — so a toolkit reaches real
modding capability without reimplementing the sim.

**What this changes about the remaining RE work.** The annotate-first goal stands, but the
*purpose* of further function analysis is now narrower: read what a toolkit needs, not
everything. Concretely, deprioritise anything that only matters to a reimplementation
(per-tick sim math, render internals, UI behaviour) unless it blocks a format.

~~**P1's gate criterion 2 should be re-examined against this decision.**~~ **DONE — re-scoped on
the owner's call 2026-08-17 and then MET the same day, 530/530.** See criterion 2 above and
`re/analysis/GATE_RESCOPE.md`.

**Toolkit scope, as the evidence currently supports it:**

1. **Read/inspect** every shipped format — done, `re/tools/`.
2. **Round-trip write** for the formats proven reversible: QFS (**both directions now**, the
   compressor transcribed from GZResourceD `FUN_1001694d`), sprites, `.IXF`, and the **city save
   family — 59/59 byte-identical end to end** (2026-08-17).
3. **City-save editing** — the reachable new capability: the section directory is fully mapped
   and the zone layer decodes to per-tile developer slots.
4. **Asset extraction/replacement** — 63,691 sprites already decode and re-encode identically.

~~`[UNCERTAIN]` city-save **writing** is not yet demonstrated.~~ **DEMONSTRATED 2026-08-17: the
writer round-trips all 59 shipped city-family files byte-identically at every layer**
(`re/tools/city_roundtrip.py`, and the QFS compressor transcribed from GZResourceD
`FUN_1001694d`). Two things that claim does NOT cover, kept explicit: a **modified** file has not
been fed to the game, and the zone section still has semantic unknowns (the `u16` permutation's
purpose, the `3000/5000/8000` keys — `U-029`).

**The core-sim set and where it stands.** ⚠️ **THE TABLE BELOW IS SUPERSEDED** — it is the
early-2026-08-16 snapshot (568 / 5.9%), taken before the `classify_families.py` merges. The
current per-module figures are **2,299 / 9,575 = 24.0%** in `HANDOFF.md`; use that one. Kept here
only so the "9,007 remaining / ~360 runs" reasoning below stays readable.

| module | backlog | ≥C1 | % | remaining |
|---|---|---|---|---|
| SIMRCI | 1,536 | 57 | 3.7% | 1,479 |
| SIMMISC | 1,200 | 48 | 4.0% | 1,152 |
| SIMUTIL | 763 | 62 | 8.1% | 701 |
| SimTransit | 619 | 35 | 5.7% | 584 |
| SIMECO | 659 | 55 | 8.3% | 604 |
| SIMGEOM | 1,148 | 59 | 5.1% | 1,089 |
| SIMSERV | 713 | 58 | 8.1% | 655 |
| SIMDSTR | 1,191 | 68 | 5.7% | 1,123 |
| SIMCITY | 587 | 71 | 12.1% | 516 |
| SIMNTWRK | 809 | 24 | 3.0% | 785 |
| SIMVARIABLES | 350 | 31 | 8.9% | 319 |
| **TOTAL** | **9,575** | **568** | **5.9%** | **9,007** |

**The set is 11 modules.** SIMCITY, SIMNTWRK and SIMVARIABLES were added on the owner's call
2026-08-16: the original eight were listed before `SIMCITY.DLL` was identified as the city
simulator / tick driver, so their absence was an accident of timing, not a judgement.

- **SIMCITY** — the per-tick dispatch and the 33-entry layer roster live here.
- **SIMNTWRK** — the road/rail network layer.
- **SIMVARIABLES** — the tunables store every sim constant resolves through.

That is the honest cost of the gate: **9,007 functions**, roughly 360 more `delegate_cluster.ps1`
runs at 25 each. Large, but under a third of the un-scoped number and finite.

**Progress metric:** classified functions in the core-sim set, not dates and not the
all-binaries percentage (which is dominated by 22,416 UI/framework functions the gate does not
ask for).

---

### P1 — EXIT-GATE ASSESSMENT (2026-08-15) — the assessment that produced the re-scope above

> **HISTORICAL — kept for the reasoning, not the numbers.** The counts in this section are the
> 2026-08-15 snapshot (674 classified, 31,963 backlog) and are superseded by the re-scoped gate
> above (1,167 classified, 31,991 backlog). Its recommendation was adopted 2026-08-16.

The stated exit is *"100% of `FUN_*` at ≥ C1"*. Measured honestly, that is **not close**, and
the headline tracker numbers have been flattering because **the denominator is wrong**.

| measure | value |
|---|---|
| rows in `functions.csv` | 10,315 |
| of which real backlog (not `lib`/`thunk`) | 5,517 |
| classified ≥ C1 **within the tracker** | 674 = **12.2%** |
| exported bodies across the 31 target binaries | 56,754 |
| — of which `Unwind_*` stubs / `Catch_*` / thunks / library-named | 24,791 (**not functions**) |
| **real `FUN_*` backlog across all 31 binaries** | **31,963** |
| classified ≥ C1 **against the real surface** | 674 = **2.1%** |

> The 56,754 figure is the raw export count and is **misleading** — 22,495 of those files are
> `Unwind_*` exception fragments, plus 1,118 `Catch_*`, 516 thunks and 662 library-named. The
> honest backlog denominator is **31,963 `FUN_*`**. (SC3U alone contributes 4,929 of them, which
> matches the long-standing 4,932 figure.)

**The core problem: `functions.csv` fully enumerates only `SC3U.exe` (9,730 rows).** For the
other 30 binaries it holds just the rows we hand-added while analysing them — SIMUI has 109 rows
against **3,109** `FUN_*`, SIMRCI 21 against **1,530**, SIMBABLD 12 against **1,871**, and
SIMINIT / GZWinD / AUDIO have **zero** rows against 1,150 / 1,171 / ~900.

So "C1 tier cleared, C2 657" is true but measures a set covering ~18% of the binaries. Against
the actual surface it is **2.1%** classified. **This must be corrected before P1 can be judged**,
otherwise the gate is measuring the wrong thing. First action of the next phase of work:
enumerate all 31,963 FUN_ into the tracker so progress has an honest denominator.

**What P1 *did* achieve** (substantial, and none of it is invalidated):
- 🔴 The structural discovery that reframed the project: the sim is **not** in `SC3U.exe`, it is
  29 GZCOM director DLLs. All 31 binaries imported, analysed and exported.
- The GZCOM module recipe, and 20+ classes pinned to real GZCLSIDs.
- Sim models reversed: power grid, RCI/zoning valves, traffic, budget/ordinances, buildings.
- 18 modules with analysis docs; **every function anyone has read is ≥ C2** (C1 tier empty).

**Scope change to acknowledge:** the gate was written when the target was one 9,730-function
exe. The real target turned out to be 31,963 FUN_ across 31 binaries — ~6.5x larger. The
gate text below is preserved, but "100% at >=C1" over 31,963 functions is not a realistic gate for
a hand-analysis project. **Recommend re-scoping it** to: *100% enumerated in the tracker, plus
≥C1 for every function in the core-sim modules* (SIMRCI, SIMMISC, SIMUTIL, SimTransit, SIMECO,
SIMGEOM, SIMSERV, SIMDSTR), leaving UI/audio/tooling modules at "enumerated, unclassified".

**P2 overtook P1.** Formats were supposed to be the *next* phase, but the highest-value work kept
being format work, and P2's exit ("parsers validate real game files") is now effectively met:
`SYS.PAK`, `.IXF` (C4 round-trip), QFS/RefPack (63,691/63,691), the sprite pixel + anchor formats
(62,552/62,552 **byte-identical re-encode**), FEZC/GVF, and — as of 2026-08-16 — **the city save
family** (`.sc3`/`.sct`/`.snr`/`.st3`, 59/59 files, container + QFS payload, `city_parse.py`).
**P2's exit is now met at the container/compression level for every shipped format.** What
remains is *record-level* structure inside the city payload, which is P4-shaped work (it needs
the sim-side serialisers), not another container to crack.

**End-state decision (port vs toolkit) — evidence, not a verdict.** This is the owner's call.
What the mapped surface now says:
- *Against a source port:* 31,963 functions across 31 interdependent GZCOM binaries, with the sim
  spread over ~10 of them. That is an order of magnitude beyond a one-person reimplementation.
- *For a toolkit:* the format layer is already **C4-verified with working parsers**, the data is
  overwhelmingly data-driven (`SYS.PAK`/`CitySim.ini` drives the entire building taxonomy —
  U-006 proved there are no per-building classes in code), and 63,691 sprites already decode and
  re-encode byte-identically. A modding/asset toolkit is reachable *now*; a port is not.

### P1 — Surface map  ◀ ACTIVE (taxonomy built 2026-08-14 → `re/analysis/SUBSYSTEMS.md`)
**Done:** 18-subsystem taxonomy (S1–S18) from the iOS named classes + SC3U string anchors +
25-largest-`FUN_*` priority list + classification methodology. Power subsystem cross-RE
demoed (`re/analysis/POWER_SUBSYSTEM.md`).
**Remaining:** walk the size list + string-anchored clusters, seed `functions.csv`
`subsystem`/`confidence` per function.

Split library vs game code; classify every `FUN_*` to a subsystem; triage strings +
imports; build the subsystem inventory and skeleton call graph from the entry point.
- Import table + `strings.csv` triage → seed subsystem guesses.
- Cluster by call graph; label the big functions (the 15 KB / 9 KB / 3 KB+ ones first).
- Locate: WinMain/entry, the message loop, the per-tick sim update, the save/load path.

**Exit:** see **"P1 — THE GATE, RE-SCOPED"** at the top of this file. In short: everything
enumerated (met), **≥ C1 across the eleven core-sim modules** (5.9%, the open item), UI/audio/
tooling left unclassified by design, subsystem map committed (met), end-state decision taken
(open). The literal "100% of `FUN_*` at ≥ C1" wording is **retired** — do not measure against it.

### P2 — Asset & data formats
Reverse the on-disk formats with round-trip parsers: city save format, the `.dat`/library
archives, graphics/sprite format, audio, and the `Scripts\`/`Apps\`/`Buildings\` data.
Cross-reference `alandoherty/opensc3` and community docs (Simtropolis) as leads only —
verify against real bytes.
**Exit:** parsers validate real game files; format docs with byte-offset tables in
`re/analysis/formats/`.

> ⭐ **CITY SAVE CONTAINER SOLVED (2026-08-16) — see `formats/CITY_SAVE.md`.**
> `.sc3` / `.sct` / `.snr` / `.st3` are **`.IXF` containers**. **59 of 59 shipped city-family
> files parse with the EXISTING `re/tools/ixf_parse.py`, no changes** (992 records).
> **PAYLOAD ALSO SOLVED:** the bulk record is a 24-byte header + a **QFS** stream (same QFS as the sprites), so `qfs.py` decodes it unchanged. **59/59 files, 21.9 MB -> 92.7 MB.** Tool: `re/tools/city_parse.py`. Body carries a `0xDEADBEEF` marker at +0x0c in all 59. Still open: the layout INSIDE the decompressed body.
> ⚠️ Nearly recorded backwards: `SIMINIT` `0x10001ada` reads an IFF chunk format with tags
> `XZON XBLD XTER ALTM MISC SCDH FORM` — those are **SimCity 2000 `.sc2`** tags, i.e. a legacy
> importer, NOT the SC3 format. Checking the first bytes of a real `.sc3` is what caught it.
>
> **LEAD ON THE PAYLOADS** — the serialiser route:
> SIMGEOM has a confirmed **serialiser mirror pair**: `FUN_1001e516` = LOAD, `FUN_1001e226` =
> SAVE, over the identical field set `[CONFIRMED @0x1001e516, 0x1001e226]`. LOAD calls the
> stream's `vt+0x38` on field **addresses**; SAVE calls `vt+0x88` on field **values**; both walk
> `+0x04`, `+0x08`, `+0x0c`, `+0x18`, … in the same order.
> **So `vt+0x38` / `vt+0x88` are the GZCOM stream read/write primitives.** The field order in
> each serialiser *is* the on-disk record layout, which is the way into the city save.
>
> A grep for `vt+0x88` call sites hits **285 files across 22 modules** (SIMRCI 26, SIMUI 33,
> SIMDSTR 22, SIMMISC 20 …). `[UNCERTAIN]` — that is a **candidate count, not 285 confirmed
> serialisers**: any vtable whose slot 0x22 is called matches the same pattern. To qualify a
> candidate, require the **pair** (a `+0x38` reader over the same field offsets in mirror order)
> and check the object is a GZCOM stream. Next step: script that pairing test rather than
> trusting the raw grep.

### P3 — Boot & main loop
Map entry → subsystem init → main message/sim loop → shutdown end-to-end; locate and
name the master game state and the per-tick update dispatch.
**Exit:** boot/tick call-graph documented; key global state located and named.

> **PARTIAL, ahead of schedule (2026-08-16) — the per-tick dispatch is FOUND.**
> `SIMCITY.DLL` is the city simulator / tick driver (`re/analysis/SIMCITY.md`, 60 functions).
> Layer modules **register periodic-update callbacks into buckets**, and the driver walks the
> buckets in order per day: bucket1 (sub-tick) → bucket2 → bucket3 (daily) → …
> Tick tiers: `FUN_1000a915` (tier 1, fastest) → `FUN_1000a9b1` (tier 2) → `FUN_1000aa4d`.
> Clock `[CONFIRMED @0x10009b35]`: speed = **ticks-per-day, default `0x5a0` = 1440**
> (`param_1[0x14] = 0x5a0`), and **ms-per-tick = `86400000 / speed`** with derived sleep
> thresholds at `/24` and `/60`. So one sim day = 1440 ticks = one tick per simulated minute.
> Also found: `SIMVARIABLES.DLL` is the **tunables store** — it reads `SYS.PAK [Tunables]` and
> `SimTune.INI [tuneup]`, hashes each key name to a 32-bit id, and holds id→value pairs
> (`re/analysis/SIMVARIABLES.md`). That is the lookup path for every tunable constant.
> Still needed for the P3 exit: boot/entry → init ordering, and shutdown.

### P4 — Core simulation (the heart)
RCI demand model, budget/tax/ordinances, power/water networks, traffic/transport,
pollution, crime, land value, growth. Each: named, mechanically described, constants
cited by RVA, structs documented.
**Exit:** S-DoD for each core-sim subsystem.

### P5 — UI / render / audio / events
Isometric renderer, tool & menu UI, the news/advisor event system, audio.
**Exit:** S-DoD per subsystem.

### P6 — Close (annotate-first) / branch to chosen end-state
**Branch chosen 2026-08-17: the modding / format TOOLKIT.** The source-port option is closed
(see the P1 gate). P6 is now: declare P-DoD for the annotation that a toolkit needs, and open a
toolkit sub-roadmap.

**First deliverable of the toolkit branch — ✅ MET 2026-08-17.** The **city-save writer**
round-trips shipped `.sc3` files **byte-identically, 59/59 at all five layers** (container,
24-byte record header, section archive, QFS, whole file with lengths recomputed):
`re/tools/city_roundtrip.py`. The QFS compressor turned out to be *in the game* — GZResourceD
`FUN_1001694d` — so it was transcribed rather than inferred (`re/tools/qfs_encode.py`,
`formats/QFS.md`). That matches the sprite precedent (62,552/62,552).

Scope limit on record: section payloads are re-emitted verbatim, so this is an
**edit-and-rewrite** pipeline, not city authoring from scratch.

**Next in the toolkit branch, unranked until the owner calls it:**
1. An editing API over the writer (`re/tools/city_write.py`): mutate a decoded field — the zone
   raster is the obvious first target, one byte per tile — and emit a file the game loads. The
   round-trip proves the container survives; **that a MODIFIED file loads is a separate claim and
   has not been tested.**
2. Apply the same layered round-trip to the other write-capable formats (`.IXF`, `SYS.PAK`).
3. `U-029` semantics (the `u16` permutation's purpose, the `3000/5000/8000` keys, the
   `this+0x3c` 23-vs-92-byte mismatch).

## Sizing reality check
4,932 C0 functions; the game-logic core is a subset. No prior exe RE exists for SC3, so
type/format knowledge is built from scratch — expect P2/P4 (formats + sim) to be the long
poles. Measure progress in classified functions and documented subsystems, not dates.
