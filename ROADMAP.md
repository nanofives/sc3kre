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
