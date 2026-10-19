# hwcap2: never extend, capped joins instead (2026-10-18/19)

Owner decision 2026-10-18: "Never extend: only use the end piece where possible." Build: main 73073cd + this branch
(child/hwcap2). Test tree `Simcity_stock_highways`, instance `re\harness\inst_hwcap2\`. Owner sheet:
`MAIN\verify\hwcap2\owner_shots\hwcap2_sheet.png`.

## Verdict

- **The carry-on is gone from all four blocks.** No interchange writes a highway piece into a cell the player's drag
  left empty. Checked offline in every twin (cases below assert it) and in game (lab hwx: x 111+ stays empty; Seoul:
  (251,116), (252,115), (252,116) stay empty, the north end keeps its own stock cap one past the drag).
- **Where an arm ends ON its last joining cell, a capped join is written** (the join with the stock end face, a U-turn
  turn matrix, saved as the stock cap):

  | block | arm | capped pieces | new in this task |
  |---|---|---|---|
  | hwx | the 4 arms (last junction row dx / dz 5 and -6) | 21166..21169 (one per outer junction 21151 / 53 / 55 / 57) | 4 |
  | hwt | through highway ends dx -2 / 7, stem end dz -4 (stem frame) | 21254 / 21255 / 21256 (twins of 21215 / 21227 / 21200) | 3 |
  | hwdx | straight arms (A1's last column 9, O2's last column 6, both cases) | 21536..21543 (classes 53 / 64 / 119 / 108 x 2 flavours) | 8 |
  | hwdx | diagonal arms | 21532..21535 (task hwcap), now the only path | 0 |
  | hwdd | diagonal arms | none possible (below) | 0 |

  15 new pieces in total, 3 to 8 per kind, so no kind needed an orchestrator call.
- **An arm that ends earlier drops what it cannot reach**, as before task hwcap: hwx -> the clean flyover, hwt -> no
  T, hwdx -> that quadrant (a diagonal arm one row short also drops O1 / O2, whose joining outer cell then lies past
  the stock end), hwdd -> the flyover (or nothing).
- **In game:** Seoul A1 builds with the capped join only: same save and drag as hwtraffic / hwcap,
  `hwdx: edit: new crossing O (245,109) case A r 0, quadrants A1 A2 O1 O2`, (251,115) = 21532.2. Saved and reloaded:
  `load: all 154 variant tiles restored`, `hwdx: load: kept crossing O (245,109) case A r 0, quadrants A1 A2 O1 O2`,
  (251,115) still 21532.2. Lab hwx (straight arm): z (105,79) -> (105,99), x (95,89) -> (110,89):
  `hwx: edit: cloverleaf at (105,89): 96 cells written`, (110,88) = 21166.2, (110,89) = 21167.2, x 111+ empty. Saved
  and reloaded: `load: all 96 variant tiles restored`, `stats: hwx ... kept=1`, both capped junctions kept.
- **Without the mod** (save read with `tiler.City.load`): lab (110,88) / (110,89) = 15054.2 / 15053.2 and Seoul
  (251,115) = 14999.2, the exact stock ends.

## Design

### Shared: `sc3netmod_hwcap.c` (kept, now read-only)

Its arm walking is still needed (hwt and hwdd accept cells past an arm's end), so the file stays, reduced to:
`hwcap_dir` / `hwcap_is` (a stock cap and its outward step), `hwcap_end(hp, x, z, sx, sz)` (1 = the arm's own cap is on
the cell, 2 = the cell is empty and the arm's cap lies behind it, 0 = neither) and `hwcap_cap_of(step, lower)` (the
stock cap of an end: lane-specific for straight arms). Removed: `hwcap_need`, `hwcap_commit`, the writer, the free-cell
test, `SC3NETMOD_HWCAP`, `hwcap_stats` and its two lines in `sc3netmod_rbt.c`. Twin: `hwcap.py` (`stock_ends`, `end`,
`cap_of`).

### Per block

| block | rule now |
|---|---|
| hwx | Arm cells: plain, or (last junction row only) the stock cap of that lane / the capped junction (table class 3: `hwx <capped> <cap state> <dx> <dz> 3`). `hwx_put_all` writes the capped junction where the cap is, `hwx_unput` puts the stock cap back (not plain highway) when the ramps go. |
| hwt | The through highway (dx tx0-1 .. tx1+1) and the stem may END: a cell that is not one of the T's own may hold the stock cap or lie past it; a T cell may hold the cap only when it has a capped twin (`hwtc <twin> <dx> <dz>`), which is written at the T's state r. Votes, keep and break know the twins; a broken T puts the stock cap back on a twin cell. Saves: `hwys` lines (the stock cap at each turn). |
| hwdx | A joining cell holding no highway refuses its quadrant; one holding the arm's own stock cap takes the class's capped join (`g_hwdx_cap`, now also for the straight classes), else refuses. Capped joins sit at the cap's own state, base = the cap. |
| hwdd | Plain-band rows may hold the arm's own cap or lie past it (`hwcap_end`), on fresh and on built interchanges. Joining rows holding a cap or nothing refuse the cloverleaf (the flyover is tried next). `hwdd_write` no longer turns a cap on a band row back into plain band. |

### Why hwdd has no capped join

The stock end of a diagonal drag caps the middle cell and leaves the two outer cells beyond it empty (measured,
`sc3netmod_hwcap.c` header). hwdd's last joining middle row (clover c: (-4,-4) on the up-left arm) has a joining
OUTER cell beyond it ((-5,-4)). A cap on that middle therefore always leaves a joining cell empty, and one capped cell
cannot carry the ramp that joins there. A capped join would need a second piece in a cell the drag did not reach,
which is what the owner ruled out. The twin shows the effect on the north arm (`hwdd.py check`): clover c builds the
cloverleaf when the arm ends 8 or more cells past O and the flyover at 3..7; clover h builds the cloverleaf from 7.

### Pieces and art

- **Painting.** Each capped piece is painted from its interchange's scene with that highway cut on the end cell's
  outer edge (`hwx.scene(ext=6)`, `hwt_paint.scene(extent=(-2, 8, -4, 8))`, `hwdx_paint.scene_A(capped=("S", e))`),
  at the orientation where the piece sits at state 0.
- **End face.** `hwcap_art.compose_straight` takes the stock cap's pixels for the end face: the vertical face on the
  end edge where it faces the viewer (the view ray meets that plane between ground and deck, inside the edge), and
  the deck top within 0.1 cell of the edge. The stock straight caps leave faces undrawn in some views (15053 view 0 is
  a bare deck); there the painted wall stays, so a capped piece never shows a hole. In game the result is the stock
  facade with its dark column recesses (sheet, top right).
- **Turn matrix.** The join's turns with the outward side replaced by the side toward the other lane of the row. That
  is the stock cap's U-turn (checked: 21166 `x+ => z-` = 15054.0, 21167 `z+ => x+` = 15053.0, 21168 `z- => x-` =
  11237.0, 21169 `x+ => z-` = 11235.0) plus the ramp's own turn into or out of the end. No animated lanes, as for
  hwcap's 21532..21535.
- **Base and saves.** hwx and hwdx capped pieces: base = the stock cap, written at the cap's own state, so the save
  and the stock tiler see the stock end. hwt twins: written at the T's state r (the T's vote needs it), saved through
  `hwys` as the stock cap of that end at each turn.

## Checks

Offline (all pass):
- `py -3.12 hwx_twin.py selftest examples/hwx_cloverleaf <lab.sc3>`: PASSED. New: x drag ending on dx 5 -> cloverleaf
  with 2 capped junctions, kept by a load pass; on dx 4 -> clean flyover; on dx 6 -> plain cloverleaf with the stock
  cap beside it; none writes past the drag.
- `py -3.12 hwt_twin.py selftest`: PASSED. New, at all 4 turns: through highway ends on dx 7 / -2, stem on dz -4, all
  three at once -> T with 1 / 1 / 1 / 3 capped twins; ends one past (dx 8 / -3, dz -5) -> plain T; one short (dx 6,
  dz -3) -> refused; never a cell written past a drag.
- `py -3.12 hwdd.py check`: all checks pass (the north arm ending 3..9 cells past O, both parities, no write into an
  empty arm cell).
- `py -3.12 -m netmod.hwdx check`: FAILURES 0. 20 cases with every arm (and all four) capped on its last joining cell:
  4 quadrants, every movement, the expected capped joins (diagonal and straight). 16 more: one row short (straight:
  A1 refused, diagonal: A1 and O1 refused), straight arm ending on O2's / O1's last column (capped join there, A1 /
  A2 refused). No case writes into a cell the drags left empty.
- Build: `build_mod.ps1` clean, no warnings.

In game: the two runs above (lab hwx, Seoul hwdx), each saved and reloaded once. hwt twins and hwdx straight capped
joins are offline only. hwdd changed rule only, offline only.

## Limits and open items

1. **hwt twins sit at state r, not at the cap's state** (the T recognises itself by state = turn). Without the mod
   the `hwys` lines make them load as the right stock cap. With the mod, a stock retile near the end sees the twin's
   base (15053 / 11237, from turn 0) at the T's state. Not observed to matter (hwt's other highway cells work the
   same way), not tested in game.
2. **hwdd cap on a joining row -> flyover**, never a cloverleaf (Design). A longer drag gives the cloverleaf.
3. **Capped pieces have no animated lanes** (cars do not draw a U-turn there). Trips use the turn matrix.
4. **Water map** item from hwcap (tiler one row off at Seoul's shore) is unchanged and no longer matters to these
   rules: nothing tests free land past an end any more.

## Files

New:
- `verify/hwcap2/RESULTS.md`
- `re/tools/netmod/examples/hwx_cloverleaf/hwx_21166.lanes.json` .. `hwx_21169.lanes.json`
- `re/tools/netmod/examples/hwt_trumpet/hwt_21254.lanes.json` .. `hwt_21256.lanes.json`
- `re/tools/netmod/examples/highway_diagonal_cloverleaf/lanes/21536.json` .. `21543.json`: gitignored, need
  `git add -f`

Changed:
- `re/harness/src/sc3netmod_hwcap.c` (reduced to read-only helpers), `sc3netmod_hwx.c`, `sc3netmod_hwt.c`,
  `sc3netmod_hwdd.c`, `sc3netmod_hwdx.c`, `sc3netmod_hwdx_tab.h` (regenerated, additions only)
- `re/harness/src/sc3netmod.c` (include comment), `sc3netmod_rbt.c` (hwcap_stats lines removed, `hwtc` dispatch)
- `re/tools/netmod/hwcap.py`, `hwcap_art.py`, `hwx_build.py`, `hwx_twin.py`, `hwt_build.py`, `hwt_twin.py`, `hwdx.py`,
  `hwdx_paint.py`, `hwdd.py`
- `re/tools/netmod/examples/hwx_cloverleaf/{manifest.json,README.md}`, `hwt_trumpet/{manifest.json,README.md}`,
  `highway_diagonal_cloverleaf/{manifest.json,README.md}`

Art stays out of the repo. Rebuild: hwx `hwx_build.py art examples/hwx_cloverleaf --only 21166,21167,21168,21169`
then `pad`; hwt `hwt_build.py capart examples/hwt_trumpet` then `pad`; hwdx `hwdx_paint.py art <pkg> 21536 .. 21543`,
`hwcap_art.py compose <pkg>`, `hwdx_paint.py pad <pkg>`. Up-to-date art for all three is in this worktree and
installed in `Simcity_stock_highways`.
