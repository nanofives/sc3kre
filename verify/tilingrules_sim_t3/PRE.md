# T3 — simulation-level tiling test — PRE-REGISTRATION (DRAFT, held)

Session `roadtypes`. Drafted 2026-08-27. **This is a DRAFT held for two gates and is NOT yet the
committed pre-registration of a run.** It is committed now (by path, `.gitignore` whitelists
`verify/*/PRE.md`) so the design is on record before any lease. Before firing, this file must be
finalized (oracle locked, fixture pinned with hashes, ticks/speed pinned) and re-committed. I am
priority 2 for the lease behind `resize`; the writer work is done, so I hold here.

## The question T3 answers, stated so it can be wrong

Every road-tiling result so far (T1 destructive, T2 constructive) is fenced **render/build-path
only**. T3 asks the first **simulation** question: **does a network tiling-rule edit reach the
simulation** — does breaking or changing which piece a road tile resolves to change how the sim
**routes traffic / develops zones along that network**, separably from the sim merely running?

The honest null hypothesis is that tiling piece-selection is **render-only** and the sim's transport
graph is independent of it. T3 is designed to distinguish that null from its alternative, not to
assume either.

## Why this is only testable now, and the trap it must avoid

- **Unpause is game-verified:** post GZ message `0xc2a35d80,0,0,0` → `FUN_10002fa6` → `vt+0x210`
  = `FUN_10005773`, decrementing suspend-depth `+0x140` and resuming the clock. Witnessed: `+0x140`
  1→0, tick cursor advanced (BIGGER_CITIES.md / PROMPTS.md §3). Probe verb `msg:0xc2a35d80,0,0,0`.
- ⚠️ **A confirmed unpause path is not a confirmed unpause.** This project lost two leases to
  `0x231e2493`, which clears a pause bit that was **already 0 at load**. So T3 MUST **measure the
  clock actually advanced** this run (sim date and/or the tick cursor read before and after), and
  **abort loudly** if it did not. An unpause capability is not a simulation result.
- ⚠️ **Keep the render-path fence in every doc until THIS run has actually produced a sim result.**
  Drafting T3 does not lift the fence.

## Design — the destructive-connectivity 3-arm test (primary)

Reuses the **T1 destructive lever** (`ROAD_GRND_Set.txt` → `{99999}`), whose blast radius is
game-known: every road tile fails the render validity scan `FUN_1001a7f7(netType,pieceId)`
`[CONFIRMED @0x1001a7f7]` and **does not draw**, while rail (own untouched Set) draws normally, with
**no crash, no error** (`verify/tilingrules_read_test/RESULTS.md`). What is unknown, and is exactly
the T3 question: does that same validity failure also remove those tiles from the **transport graph
the sim routes over**?

Three arms, **same fixture, same everything except the one edit and the pause state**:

| arm | rules | sim | isolates |
|---|---|---|---|
| **A** | stock | **unpaused** N ticks | baseline: this fixture develops/carries traffic when served + running |
| **B** | `Set.txt`→`{99999}` (roads invisible) | **unpaused** N ticks | whether invisible roads still route for the sim |
| **C** | stock | **PAUSED** N ticks (no unpause post) | control: the signal needs the sim to RUN, not just load |

**Discriminator (all three read on the SAVED FILE, camera- and pixel-independent):**
1. **A moves, C does not** — confirms the metric responds to the sim running and not to load/save
   alone. If A == C (no movement in A either), the fixture or tick budget is inadequate → **abort,
   re-pick fixture / raise N**, this is not a result about tiling.
2. Given (1) holds, **B vs A**:
   - **B moves like A** ⇒ the tiling/piece-validity edit is **RENDER-ONLY**; the sim routes over
     roads that do not draw. Tiling does NOT reach simulation. **T3 met (null confirmed), fence
     liftable to "tiling is cosmetic to the sim."**
   - **B is flat like C** ⇒ the piece-validity scan gates the sim's transport too; breaking tiling
     broke connectivity. **Tiling reaches simulation. T3 met (alternative), fence lifted.**

Both B outcomes are a genuine first simulation-level finding. The confounds a residential develop
check early-returns on — demand `0xd`, radioactivity `0xa`, power `0xe`, transport `0x10`, land value
`0xb/0xc`, family `0xf/0x12` `[CONFIRMED @ SIMRCI 0x10028f12, iOS 0x0026e7c8]` — are **held identical
between A and B** (same fixture, same save, only `Set.txt` differs), so any A/B difference is
attributable to the tiling edit's reach, and the paused arm C isolates "the sim ran."

## ✅ GATE 1 CLOSED — the oracle is the SimTransit live-density grid

**Locked 2026-08-27.** The metric is a whole-map (or rect-around-the-test-network) **SUM of a
SimTransit live-density grid**, read off the saved file — camera- and pixel-independent, per the T2
precedent ("score on the file, never pixels").

- Tool: `re/tools/transit_layer.py --sum surf_live` (and `rail_live`), decoded and validated 2026-08-27
  (`formats/CITY_SAVE.md`, group `0x029ca804`, 0/68 validation failures). ⚠️ the save layer is
  `0x029ca804` (SimTransit), **not** `0x029ca806` (TrafficLayer, never saved).
- **Why this grid:** the `*_live` grids are the within-month traffic accumulators — `FUN_10006edd`
  adds each trip's contribution along its assigned route every sim step `[CONFIRMED @0x10006edd]`, and
  the monthly pass decrements them `[CONFIRMED @0x100093e9]`. **They respond to the sim ticking** — a
  paused save's grid does not move, an unpaused one's does. That is exactly the A>C separation the
  design needs. Static routing costs are NOT grids (they are `STTraffic.INI` scalars), so there is no
  static-cost confound in the readout.
- **Metric:** `surf_live` total (surface = road+hwy traffic) is the primary; `rail_live` is the
  cross-network control (breaking ROAD tiling must not move rail traffic). Density is not confined to
  network cells, so use the SUM (whole-map or a rect over the served corridor), not a per-tile match.
- **Not-moved guard:** the SimTransit grid also gives a second, independent read of the anti-`0x231e2493`
  clock check — if the sim truly did not tick in an unpaused arm, `sum(surf_live)` will not differ from
  the paused control C beyond noise. So oracle and clock-advanced assertion must agree.

**Re-derive N and any byte count yourself** — do not adopt a tick count from the orchestrator.

## ✅ GATE 2 CLOSED — fixture pinned: Liverpool, England (N=192)

Chosen 2026-08-27 for substantial LIVE surface traffic (so the oracle has a large signal to move) on a
mid-size map (faster sim than the N=256 cities), with rail traffic present as a built-in cross-network
control. Load camera is irrelevant — the oracle is the saved file.

- Fixture: `Cities\Liverpool, England.sc3`, **sha256 `59bdc7c6…`, 445,812 B, N=192.**
- Baseline oracle (read now, pre-run): **`surf_live` total = 621,831** (7,623 cells, road=9,579
  tiles), **`rail_live` total = 2,381** (85 cells), `surf_snap` = 410,237. These are the frozen-at-load
  values; arm C (paused) must reproduce them, arm A (unpaused) must diverge.
- `Apps\Res\TilingRules\ROAD_GRND_Set.txt` stock sha256 `9926948a…` (arm B edits this, restores after).

## FROZEN RUN SPEC (committed before the lease)

Three arms, each an independent `capture.ps1` launch (self-acquires the FIFO lease). Same fixture
baseline restored before each; the only differences are the `Set.txt` edit (arm B) and the unpause
(A/B yes, C no). Oracle read on the saved file with `transit_layer.py`. Runner:
`re/harness/t3_run.ps1` (gitignored execution artifact; logs every step, restores in a finally).

Per-arm `capture.ps1 -Owner roadtypes -GamePath 'Cities\Liverpool, England.sc3' -AtSec 200 -GzSeq`:
- **Arm A** (stock rules, UNPAUSED): `msg:0xc2a35d80,0,0,0;msg:0xc2684065,3,0,0;wait:90000;fire:0x10009002;wait:12000`
  → unpause (game-verified msg, NOT the inert `0x231e2493`), set speed 3, run 90 s, Save, let the
  write finish. Copy saved fixture → `liv_A.sc3`; restore fixture from backup.
- **Arm B** (`ROAD_GRND_Set.txt`→`{99999}`, the T1 destructive edit; UNPAUSED): identical GzSeq.
  Copy → `liv_B.sc3`; restore fixture AND `Set.txt`; verify both hashes.
- **Arm C** (stock rules, PAUSED — no unpause msg): `wait:90000;fire:0x10009002;wait:12000`.
  Copy → `liv_C.sc3`; restore fixture.

Oracle read (`transit_layer.py --sum surf_live` / `rail_live` on each `liv_*.sc3`):
- **Gate (must pass first): `surf_live(A)` ≠ `surf_live(C)`** and `surf_live(C)` ≈ baseline 621,831.
  This is the clock-advanced assertion via the oracle — if A ≈ C the sim did not run (or N too small)
  → **VOID, not a result** (raise the wait or the speed, re-fixture).
- **Discriminator, given the gate holds:** compare `surf_live(B)` to `surf_live(A)`:
  - **B ≈ A** ⇒ traffic still routes over roads that no longer render ⇒ **tiling is RENDER-ONLY, does
    not reach the sim.** Fence lifts to "tiling cosmetic to the simulation." T3 met.
  - **B collapses toward C-minus-decay** (surface traffic not replenished) ⇒ the piece-validity scan
    gates the sim's transport too ⇒ **tiling reaches the simulation.** Fence lifted. T3 met.
- **Cross-network control:** `rail_live(A)` ≈ `rail_live(B)` — breaking ROAD `Set.txt` must not move
  RAIL traffic. If rail moves, the edit's blast radius exceeded roads → attribution fails, investigate.

Install: runs on the owner's live modified build UNTOUCHED — the oracle is the saved sim state, which
is render-independent, so SIMSPR/GZGraphicD skin mods do not affect it. The runner does **not** touch
either DLL, so no restage is owed (standing rule not triggered). Only `Set.txt` and the fixture save
are mutated, both restored + hash-verified in the runner's finally.

## Pre-committed outcomes (to be frozen at finalization; drafted here)

1. **NULL (tiling is render-only):** A and B both move, C flat. ⇒ the sim routes over invisible roads;
   piece-validity is render-only. T3 met, fence lifts to "tiling cosmetic to sim."
2. **REACH (tiling gates the sim):** A moves, B flat like C. ⇒ the validity scan gates transport;
   the tiling edit reached the simulation. T3 met, fence lifted.
3. **PLAUSIBLE-BUT-WRONG SUCCESS to reject:** B is flat and it is read as "tiling reached the sim,"
   **but the clock never advanced in B** (unpause silently no-op'd, the `0x231e2493` failure mode) or
   **A was also flat** (fixture/N inadequate) — then B-flat proves nothing. Guard: the
   clock-advanced assertion (measured, both A and B) and the A>C separation gate MUST pass first, or
   the run is void and named as such, not scored.
4. **CRASH / OVER-BROAD / rail affected:** breaking `Set.txt` did more than remove road render (rail
   moved, a crash, filetrace absent). Investigate; not a result.

## Controls
- **C (paused, stock)** isolates sim-ran from load/save.
- **RAIL** untouched across all arms (cross-network control; its own metric must be identical A/B/C).
- **Same fixture save** for A and B → every develop-gate confound but transport held equal.
- **Clock-advanced assertion** (measured each unpaused arm) — the anti-`0x231e2493` guard.
- Loader witness: TilingRules filetrace line count identical across arms (re-derive the number).

## Protocol (to be finalized)
`SC3_SESSION=roadtypes`; `capture.ps1` self-acquires/releases the lease — do NOT wrap in an outer
acquire. Keep `-AtSec` under ~800 s. Back up `Apps\Res\TilingRules` (68 files) and the fixture; restore
both in a `finally` and re-verify sha256 (`Set.txt` `9926948a…1358`, TilingRules 68/68 == backup).
**Never commit `TilingRules.bak/` or any game content or captured frames.** The owner's install is
deliberately modified (SIMSPR / GZGraphicD) — restore shipped modules for the measurement and re-stage
the owner's standing build as the final action, reading the gated command from `BOARD.md`. Never kill a
process I did not start.

## Status
DRAFT. Gate 1 (oracle) CLOSED 2026-08-27 — `transit_layer.py` `surf_live`/`rail_live` grid sum,
decoded and validated. Remaining before firing: (2) fixture pin + tick budget N (must show
`sum(surf_live)` moves in arm A vs the paused arm C), (3) the lease (priority 2 behind `resize`). No
lease taken. Render-path fence stays until this run produces a sim result.
