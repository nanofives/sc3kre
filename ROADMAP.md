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

### P1 — EXIT-GATE ASSESSMENT (2026-08-15) — ❌ **GATE NOT MET. DO NOT ADVANCE.**

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
(62,552/62,552 **byte-identical re-encode**), FEZC/GVF. **The city save format is the notable
gap** — and it is the single biggest remaining modding unlock.

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
**Exit:** 100% of `FUN_*` at ≥ C1 (subsystem + one-line purpose); subsystem map committed
to `re/analysis/SUBSYSTEMS.md`; **end-state decision gate** (port vs toolkit) taken.

### P2 — Asset & data formats
Reverse the on-disk formats with round-trip parsers: city save format, the `.dat`/library
archives, graphics/sprite format, audio, and the `Scripts\`/`Apps\`/`Buildings\` data.
Cross-reference `alandoherty/opensc3` and community docs (Simtropolis) as leads only —
verify against real bytes.
**Exit:** parsers validate real game files; format docs with byte-offset tables in
`re/analysis/formats/`.

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
Either declare P-DoD (annotation complete) or, if the P1 gate chose it, open a
source-port / toolkit sub-roadmap seeded by the mapped surface.

## Sizing reality check
4,932 C0 functions; the game-logic core is a subset. No prior exe RE exists for SC3, so
type/format knowledge is built from scratch — expect P2/P4 (formats + sim) to be the long
poles. Measure progress in classified functions and documented subsystems, not dates.
