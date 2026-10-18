# hwt results: a highway T that connects (2026-10-18)

Owner sheets (game art, not committed): `MAIN\verify\hwt\owner_shots\hwt_sheet.png` (in game), `hwt_mockup.png`
(the package art drawn offline among stock highway, every view, the fallback, the top-down plan), `hwt_plan.png`
(milestone 1). Design and stock measurements: `README.md`.

## What was built

| part | file |
|---|---|
| scene (hwpaint decks), lane routes from the centrelines, footprint, mockup | `re/tools/netmod/hwt_paint.py` |
| cell table, art builder (all zooms, parallel), manifest, offline package preview | `re/tools/netmod/hwt_build.py` -> `hwt_cells.py` (generated) |
| C block on hwcore's HWY base | `re/harness/src/sc3netmod_hwt.c` (+7 marked lines in `sc3netmod.c`, `sc3netmod_rbt.c`) |
| offline twin of the C rule | `re/tools/netmod/hwt_twin.py` (`selftest` PASSED: 19 checks) |
| package | `re/tools/netmod/examples/hwt_trumpet` (54 variants 21200..21253, 51 lane specs `hwt_<id>.lanes.json`) |

Superseded but kept for the plan sheets: `hwt_layout.py` (the milestone-1 hand layout and rule), `hwt_plan.py`.

## In game, second build (2026-10-18, with hwcore's lanes; `sc3netmod_run7.log`, `run8.log`)

The package now has real lanes: 51 hwlanes specs, 84 new curves (shapes 22800..22883), turn matrices "auto" from
the lanes. Every spec compiles in every language without a warning. On every cell, the turns of its lanes equal the
routes walked from the scene's lane lines. The ramps start and end ON carriageway lanes at cell borders: the stem
splits at z -3, one ramp per lane, and the through highway's outer lane feeds the exits and takes the entries.
Parapets open where two decks meet. Ramp decks have no dash line (hwpaint dadc156). Table: 54 pieces 21200..21253,
full T 50 cells (30 claimed), fallback 18.

| step | result |
|---|---|
| the same drags as the first build | `full T at anchor (54,30) turn 0` (50 cells), `(131,19) turn 1` (50), `right-in/right-out T at anchor (130,35) turn 3` (18), `full T at anchor (104,88) turn 2 from a stub X` (50, plus 1 X arm cell back to 15051) |
| live turn matrices, the T at (54,30) (`nr_drive.py conn` over x 51..60, z 26..35) | 49 of 49 cells read = the table (the 50th lies outside the box) |
| save | `save: 168 variant tile(s) written as base` |
| restart on the save | `load: all 168 variant tiles restored`; load pass `0 written, 0 reverted`; `kept=4` |
| bulldoze (104,91), a stem cell of the stub-X T | broken: `16 written, 32 reverted`; the through highway plain 15051 again, no 15149 left, the cut stem keeps stock caps |
| the same with hwcore's `hwy_drop` (ef1d797) instead of the keep-bit trick (`sc3netmod_run9.log`) | the stub cells `dropped by a block -> removed, 3x3 retile` (one had become 15149 in the stock retile before the pass); same clean result: through highway plain 15051, cut stem capped 11235 / 11237 |

## In game, first build (lanes copy_base; `sc3netmod_run1..6.log`)

DLL log lines quoted from `sc3netmod.log` (copies `sc3netmod_run1..6.log` in the instance).

| step | result |
|---|---|
| through highway (44,31)-(72,31), then stem (55,18)-(55,29) up to its side | `hwt: edit: full T at anchor (54,30) turn 0 from the stem's end caps: 50 cells written`, `0 reverted` |
| live turn matrices (`nr_drive.py conn`) on the 6 bridge cells | low halves = the table: (54,30) x- -> x+ and z+ -> z-, (55,30) x- -> x+ and z- -> z+, (56,31) x+ -> x- and z+ -> x- (the loop joining), ... |
| through highway along z (131,4)-(131,44), stem (141,20)-(132,20) along x | `full T at anchor (131,19) turn 1`, 50 cells |
| a highway (136,31)-(136,40) on the far side, then stem (120,35)-(129,35) | `right-in/right-out T at anchor (130,35) turn 3 ... 19 cells written`; the T at (131,19) next to the new highway's pass: kept |
| through (96,88)-(114,88), drag (104,87)-(104,99) from the near carriageway | `full T at anchor (104,88) turn 2 from a stub X: 50 cells written` (+1 X arm cell back to plain 15051) |
| save (menu 0x10009002) | `save: 169 variant tile(s) written as base, section 0x4E56 written` (50 + 50 + 50 + 19) |
| restart on the saved city | `load: all 169 variant tiles restored`; load pass `0 written, 0 reverted`; `kept=4` |
| bulldoze a stem cell of the stub-X T (104,91) | `T at anchor (104,88) turn 2 is broken (stem cut: the stub against the through highway goes too)`; land cells removed; through highway straight 15051 again, the cut stem keeps stock caps 11235 / 11237 |
| draw the stem again (104,87)-(104,96) | the T comes back: `full T at anchor (104,88) turn 2 from a stub X: 50 cells written` |

Fixed on the way (all in `sc3netmod_hwt.c`):
- **Stock leftovers after a break.** A broken T left to the stock retile left 15149 "Highway Construction" on the
  through highway and the stem stub. That is the stock side-hit result. `hwt_break` now writes plain stock pieces back
  and removes the stub between the through highway and the cut.
- **Cascading breaks.** The first break version took its own freshly written cells for more Ts and broke five of
  them. Built Ts are now found by vote: at least 4 pieces must agree on an anchor, and claimed cells don't vote.
- **Self-overlapping deck.** The NB ramp's tail passes under its own bridge, and hwpaint takes a point's height from
  the nearest segment of its path. One self-crossing deck cut a notch in the bridge, so it is now two decks.

## Without the mod (the save-id path)

First run (`t18_nomod.sc3`, saved before hwcore's save table): every piece came back as its base, but at its OWN
state. In the T at turn 0, the through row that runs +x read 15051.0 (stock: 15051.2) and the stem's SB column 73.0
(stock: 73.2), so those cells pointed the wrong way.

Fixed with hwcore's per-state save table (6ff62ab, merged as 6c2038e). Every rewritten highway cell now has a
`hwys <piece> <id0> <st0> .. <id3> <st3>` line (`hwt_build.save_table`): at each state it saves as the stock straight
highway for its heading turned by that state. Second run: the save was re-saved with the mod (`t21_saved.sc3`), then
loaded with sc3netmod moved aside (`t22_nomod.sc3`), cells read in game:
- T at (54,30) turn 0: the through rows 15051.2 / 15051.0 and the stem 73.2 / 73.0 all the way through, the same as
  the plain highway beside the T.
- turned T at (131,19) turn 1: the through highway (along z) 73.2 / 73.0 and the stem (along x) 15051.2 / 15051.0.
  No odd-state 15051 is left.
- The land cells still show as stock 15099 slope pieces, a field of stepped blocks (`nomod2_t1_z3r0.png`,
  `nomod2_t2_z3r0.png`). They load and the highway through them is whole, but they are ugly. A different land save id
  would only change which stock piece shows; cells can't be emptied through the save.

Trap found on the way: `nr_drive.py save` returns before the game has written the file. Copy the save only after its
mtime changes (my first re-save was copied before the write, so it still held the old states).

## Open

- **Ground under open decks (fixed, see below).** Under the slab ramps and in the gaps between decks, the ground of the T's land cells
  draws as a cleared-lot texture: mottled grey with small blue puddles in window 1, flat slate-blue in window 3. It
  does not draw as grass. Terrain heights are unchanged (save diffed against `lab.sc3`). It happens with land base
  15099 and with 15110, so it is not the base. hwcore could not reproduce it in its own lab: its single land pieces
  showed grass. Reload check (2026-10-18, a copy of `t8_saved.sc3`):
  - window 1 (T at (54,30)): grass after reload, so the live grey was a drawing effect after the pass writes. hwcore
    and I agree on that reading; hwcore is looking for an invalidate call to make after hwy_put.
  - window 3 (T at (131,19), turn 1): the slate patches stay after reload and after scrolling away and back and
    rotating, so that one is stored in that window of the save. Sent to hwcore with the shots `g_reload_*.png` and
    `g_scroll_*.png`.
  - Cell check, mapped from the shot with a fitted camera offset (approximate): 9 of the 10 slate cells are land
    pieces of that T, which sit at state 1. Rewritten highway cells: 0; outside the T: 1, at (120,25). The Ts at state
    0 and 2 show grass under the same kind of art. Lead, not checked: the art is declared "from 73", which stock only
    uses at states 0 / 2, so the frame entries for states 1 / 3 may lack the ground-draw flag (orchestrator's 0x40
    lead). (Superseded: it is 73's table as a whole, see below.)
  - hwcore's rule: art "from" 73 has frame draw flags 0, so the engine draws no terrain under the piece (bit 0x40).
    Fixed: `"ground_under": true` on every piece (hwt_build.py manifest). I also padded every frame to its full cell
    diamond (`hwt_build.py pad`, pixel-identical offline). Reason: many land frames were cropped narrower than the
    tile, and the terrain may be drawn only under the frame's rectangle (not proven).
  - After save + reload (`t13_saved.sc3`): grass under the slabs for the T at (54,30) (view 0) and the stub-X T
    (view 1). The turned T at (131,19) (state 1) is clean in view 0 but still shows slate patches in view 3
    (`q2_t2_reload_z3r3.png`). The untouched lab at the same spot in view 3 is grass (`q4_lab_w3_z3r3.png`). Live
    writes show grey / blue under the new cells until a reload, even after scrolling away and back. Fresh shots taken
    right after camera jumps sometimes have undrawn dark terrain far from any T (`p7_t2_wait_z3r3.png`), so part of
    this is capture timing in a paused game. Sent to hwcore.
  - FIXED (orchestrator's lead, from roundabout4; rule confirmed by hwcore, HWY_BASE.md): the land pieces now take
    their frame table "from" 15127, not 73. The frame table's draw word is one per table, not per state. 73's table
    (class 29440, flags 0) loses the terrain under the piece in some views even with 0x40 forced. 15127's table
    (class 1650, flags 0x440) draws it in all views. Why the table class matters in SIMSPR is not traced. With ground_under and the padded frames: after reload the turned T in view 3 shows grass
    (`r1_t2_from15127_z3r3.png`), the controls stay clean, and a LIVE rebuild of the stub-X T shows grass at once
    (`r4_tx_live_from15127_z3r1.png`). Spot check at zoom 4 and zoom 2 (the turned T, view 3, after reload,
    `z4_t2_r3.png`, `z2_t2_r3.png`): grass. Owner sheet rebuilt from these runs (`sc3netmod_run15.log`, `run16.log`).
- **Lanes.** The second build has the T's own lanes (hwlanes). Animated cars were not watched (the lab city has no
  population), and highway trips through the T were not measured.
- **Stem cut one cell behind the T.** The bulldoze at (103,93), with the T still whole, left 15149 on the 1-cell stem
  end next to the T. That is stock behaviour at a stem end beside interchange pieces. Not fixed.
- **Not run:**
  - zoom 4 in game beyond the one spot check above (the camera call can fail at zoom 4 with `system error`; it
    worked on a retry);
  - a stock game loading the saved city without the mod;
  - building a T next to an existing one;
  - slopes (refused by rule: the stem and through highway must be stock straight pieces).
- **Ids.** A second loop size (2x2) would need its own art and about 50 more ids, which the range doesn't have.
