# Undo-by-snapshot spike: in-process save and reload while paused (2026-10-20)

Question: can a mod snapshot the city after each action and restore it, in-process, while paused?
Verdict: **yes on a stock 256 city (London)**. Save to a path and load over the open city both run
from the game thread with no dialog, the game stays paused, and the restored city matches the
snapshot in every named layer section.

## How it was driven

Two new `-gzseq` steps in `re/harness/src/sc3probe.c` (inert unless used):

- `savepath:<abs path>`: game Save command, CLSID `0x410438DD`, one string variant. Same recipe as SC3U `0x004108f3`.
- `loadpath:<abs path>`: game Load command, CLSID `0x610438A4`, variants {uint `0x83172ad7` type 3, bool false, string}. Same recipe as SC3U `0x0043e718`.

Both are timed around `cmd->vt+0x2c` Execute with QPC. Variants are allocated on the game heap
(`operator_new` thunk `0x004b4890`) because the command releases them.

Two probe fixes were needed and are in:

1. `SC3PROBE_GZSEQ` buffer 512 -> 4096. A longer spec made `GetEnvironmentVariableA` return
   without filling the buffer and the probe parsed one empty click step.
2. Re-entry guard `g_undo_busy`. Execute pumps frames, so the game-thread hook re-entered from
   inside it and restarted the save step about 40 times, nested, with no return.

Install state for every run: `GZGraphicD.dll`, `SIMSPR.DLL` MODIFIED (pre-existing, not touched).
Probe sha256 `6ED84028...8B62C3`. Switches `-nocom -windowed -origin -fix16 -fitclient -nointro -quiet`.

## Run 1: London, England (799,502 B stock save), city loaded paused (pause depth 1)

| step | Execute | ms | city ptr | pause depth |
|---|---|---:|---|---|
| save snapA | 1 | 1176.9 | same | 1 -> 1 |
| save snapA2 | 1 | 1035.0 | same | 1 -> 1 |
| save snapA3 | 1 | 1036.2 | same | 1 -> 1 |
| load madison.sc3 (other city) | 1 | 2475.2 | 0x102E9EC0 -> 0x16777510 | 1 -> 1 |
| load snapA (back) | 1 | 2366.3 | 0x16777510 -> 0x108A6A20 | 1 -> 1 |
| save snapAfter | 1 | 995.1 | same | 1 -> 1 |

- snapA, snapA2, snapA3 are byte-identical (799,126 B). A paused city serialises deterministically.
- Loading over an open city works through the Load command: the city object is replaced, no prompt.
  This closes the gap the static read left open (CreateCity refuses when app+0x48 is set).
- The post-reload screenshot shows London, "Simulacion en pausa", date 5/20/1991, pop 304,900, $23,788.

### snapA vs snapAfter (save, reload, save)

Payload size identical (2,276,470 B). 51 of 61 sections identical, including every named layer
(zone, building, power, water, traffic, budget, world). 10 sections differ by 3 to 7 bytes each,
45 bytes in total. Raw observations, meaning not decoded:

- 7 sections `013dee82:*`: u32 fields that were 0 hold sequential values 0x28..0x45 after reload.
- `206c6e7c:c0a81498` (395,790 B): a run of 7 values at +395732 is in reverse order.
- `206c6e7c:e0afdf68`: leading u32 2 -> 3, a 12-entry array shifted one slot, last u32 0x149989 -> 0x14b234.
- `206c6e7c:21f6abca`: u32 at +20 `0x0336e998` -> `0x0f0f0f0f`.

[UNCERTAIN] whether any of these change gameplay after an undo. Missing evidence: a decode of
those sections, or a run that undoes, unpauses and compares against a run that never reloaded.

## Run 4-6: a real action. Bulldoze, then undo by reload (London, paused)

Sequence: `savepath A; fire:0x10002006 (Demolish); drag:250,200,400,320; savepath B; [cleartool]; loadpath A; savepath C`.

The bulldoze lands: the screenshot shows the block cleared, money $23,788 -> $23,298. A vs B: 10
sections differ, including `SC3ZoneLayer` (7 B), `e0faadc7:a0ab89f0:1` (169,759 B differ) and
`2147c2dd:1` (42,323 B differ).

**Reloading with the tool still selected breaks the game.** Run 4 (after the drag) and run 5
(Demolish selected, no drag) both: Load Execute returns 1, then the next engine Blt fails
`0x80070057` and `rasthw_throw` fires, and the game thread logs nothing more. Run 1 (no tool) did not.

**Fix: put the tool down first.** New step `cleartool` calls the city view's SetTool(NULL),
primary vt+0x58 = SIMSPR `0x10048a08` -> vt+0xa0(0,0) = `0x10048a2d` (slot checked in the PE of
both the installed and the original SIMSPR). Run 6 log: mode(+0x220) 4 -> 0, tool(+0x228)
0x1037EFC8 -> 0. The reload then completes, the sequence completes, and the final screenshot
shows the block restored, $23,788, paused, 5/20/1991.

| step (run 6) | ms |
|---|---:|
| save A | 953.7 |
| save B (after bulldoze) | 949.8 |
| load A (undo) | 2326.0 |
| save C | 969.9 |

**A vs C:** 50 of 61 sections identical. Every section the bulldoze changed is back to A, with two
exceptions:

- `20a7ae7f` (SIMSERV layer, unnamed): 82,501 B in A, 82,510 B in both B and C. Its last 48 bytes
  in C are identical to B, not A. So part of the bulldozed state SURVIVED the reload.
- `c0a81498` (SIMECO pollution layer): 395,790 B in A, 395,808 B in both B and C.

The other 9 differing sections are the same reload residue as in run 1.

### Run 7: full unload before the reload does not change it

The lead above was wrong as written. The Load command (SIMINIT `0x10008bf8`) already calls
cISC3App vt+0x28 before CreateCity, and that slot is the end-session function: vtable SC3U
`0x004CF59C` (installed at app+0x30 by the app ctor `0x00402e74`), slot +0x28 = `0x00407f25`,
which Sends `0x311FDAE5` [CONFIRMED in the PE and the decompilation; the runtime hit count is
missing because the `-fnlog` table for SC3U did not install under this switch set].

Run 7 adds an explicit `endsession` step (new probe step, calls that slot) after `cleartool`.
Pre-registered prediction: no change. Measured: end-session 731 ms and the city pointer goes to 0
(it is a full teardown), then the load creates a new city in 1873 ms, still paused. The undo save
`es_C.sc3` is **byte-identical** to run 6's `bd_C.sc3`. Prediction held.

### Where the leftover state lives [CONFIRMED @ addresses below]

Both leftover sections are written from **module globals**, not from the layer object, and those
globals outlive any city:

- SIMSERV `20a7ae7f`: save `0x100073b0` writes its tail from the global map `DAT_10024968`
  (count `DAT_1002496c`). Load `0x100071d5` reads the tail into the OBJECT map at this+0x90 and never
  touches the global. The global is built once by a static initializer (`0x10005f64`), filled from
  the INI (`0x1000689e` sc3_serv_load_building_modifier), and grows at run time in `0x10007d35`
  (sc3_serv_stamp_building_modifier): on a miss for a building id (`vt+0x88`) it scans every entry
  for the nearest (`vt+0x20` distance), copies that entry's two modifier bytes and inserts the id.
  So it is a lookup cache. The bulldoze added entries, and no unload removes them.
- SIMECO `c0a81498` (pollution): save `0x10006abb` writes the global map `DAT_10020818` (count
  `DAT_1002081c`), u32 key + short per entry, a global also used by sc3_pollution_load_tuning
  `0x100046bb`. Same shape. Its insert path was not read.

Consequence: this is stock behaviour. Any load through the game's own Load command keeps these two
caches. Undo-by-reload does not add it.

[UNCERTAIN] whether it affects gameplay. Cached entries take part in later nearest-match scans in
`0x10007d35`, so a leftover entry could change which modifier a future new id inherits. Missing
evidence: a run that undoes, unpauses and compares the crime/pollution layers against a control
that never placed or bulldozed.

Fix options for the mod, untested: (a) accept it as stock behaviour; (b) at snapshot time record
the key set of both global maps, and after the undo erase keys that were not present (SIMSERV
already has an erase-by-key, `FUN_100087b2`, used on the object map in `0x10007635`).

## Runs 8-10: unpause after an undo, a game year, against controls

Arms, each a fresh launch from snapshot `bd_A.sc3`, speed 4, resume, 60 s wall, pause, save:

- C1, C2: control, no action.
- U: Demolish + drag, `cleartool`, `loadpath bd_A`, then the same run.

Days run (clock cursor +0x4c): C1 313, C2 313, U 309.

**The sim is not deterministic between launches.** C1 vs C2 after the same 313 days: 23 sections
differ, among them crime `20a7ae7f` 43,150 B, pollution `c0a81498` 94,724 B, `SC3ZoneLayer`
130,677 B. A whole-layer byte comparison cannot show a few cache entries, so the comparison was
done on the two cache tables, which are deterministic data.

Cache table formats, read from the files (both are sorted maps, `count` u32 then records):

- crime, at +82119 in `20a7ae7f`: 9 B = u32 id, i32 modifier, u8. It ends at the section end.
- pollution, at +394290 in `c0a81498`: 18 B = u32 id, i32, i32, u8, u8, i32. 221 B follow it.

| file | crime n | pollution n | vs C1 |
|---|---:|---:|---|
| A (snapshot) | 42 | 76 | identical |
| C2 | 42 | 76 | identical |
| B (bulldozed) | 43 | 77 | + id `0x3e80`, all zero, in both |
| C (undo, paused) | 43 | 77 | + id `0x3e80`, all zero, in both |
| U (undo + a year) | 44 | 77 | + `0x3e80` in both, + crime id `0x12c` -> (0, 0) |

- No id present in two arms ever had a different value. The undone bulldoze leaves exactly one
  entry, id `0x3e80`, with every field zero, in each cache.
- Neither control inserted any id in a year of play. U inserted one, `0x12c`, value (0, 0).
  [UNCERTAIN] whether `0x12c` comes from the leftover entry or from U's different year; two
  controls are not enough to call it. Missing evidence: more control arms, or a read of the
  nearest-match distance (`0x10007d35`, `local_20[0x24]->vt+0x20`) for ids `0x12c` vs `0x3e80`.
- A zero entry gives a zero modifier for its own id. `0x10007d35` applies the modifier only when
  it is non-zero, so `0x3e80` itself has no effect. A leftover entry can only matter if it is
  the nearest match for a later new id.

Render: U logged one `Blt FAILED 0x80070057` + `rasthw_throw` right after the reload, WITH the tool
already put down (`cleartool` mode 4 -> 0). The game kept rendering and simulating. Runs 6 and 7
logged none. Count so far: tool held 2/2 stalled; tool cleared 0/3 stalled, 1/3 logged one failure.

## Run 2/3: Big One (4,401,780 B) - not loadable on this install, says nothing about undo

- From the command line: the game exits about 4 s into the load, no crash dump. A control run with
  no save/load steps did the same, so the new steps are not the cause.
- In-session from London via `loadpath:`: Load raised `0xC0000005` 2.66 s in (caught), every later
  step faulted on the half-loaded city.
- Cause not investigated. Large-city timing is therefore NOT measured.

## What this means for an undo mod

- Cost per action on a 256 city: about 1.0 to 1.2 s to snapshot, about 2.4 s to undo.
  The snapshot pause after every action is the cost a player would feel most.
- The mod must put the active tool down (SetTool(NULL)) before every undo reload.
- Undo is not byte-exact: two module-global lookup caches (SIMSERV crime modifiers, SIMECO
  pollution) keep entries added by the undone action. A full unload does not clear them (run 7).
  The stock Load does the same. Measured size of it: one zero entry per cache (runs 8-10).
- Not deterministic sim, so an undo cannot be checked against a control by comparing saves after
  play. The cache tables are the deterministic check.
- Not measured: 1024 maps (need the `sc3bigcity` setup), and behaviour after unpausing a restored city.

Logs: `run1_probe.log` (London), `run2_probe.log` / `run2c_probe.log` (Big One cmdline + control),
`run3_probe.log` (Big One in-session). Probe source backup before the change: `re/harness/spike_undo_backup/`.
