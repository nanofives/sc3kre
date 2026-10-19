# hwcap: a highway ending inside an interchange's joining zone (2026-10-18)

Owner request: "Fix the end-cap case so the fourth cloverleaf corner builds." Case: `verify/hwtraffic/RESULTS.md`, open
item "Seoul quadrant A1". Build: main f21b9fc + this branch. Test tree `Simcity_stock_highways`, instance
`re\harness\inst_hwcap\`. Owner sheet: `MAIN\verify\hwcap\owner_shots\hwcap_sheet.png`.

## Verdict

- **Seoul's fourth corner builds.** Same save, same drag as hwtraffic ((238,102) -> (251,115) across the row-108/109
  highway): `hwdx: edit: new crossing O (245,109) case A r 0, quadrants A1 A2 O1 O2`, 154 cells (hwtraffic: A2 O1 O2,
  131 cells). Saved and reloaded: `load: all 154 variant tiles restored`, `hwdx: load: kept crossing O (245,109) case A
  r 0, quadrants A1 A2 O1 O2`, 0 written, 0 reverted.
- **Cause confirmed.** The drag's last cell (251,115) holds the stock end cap 14999.2, and HWDX wanted the plain band
  piece on that joining cell.
- **Two fixes, in this order:**
  1. **Carry the arm on** (all four blocks, fresh builds): the block extends the arm with stock plain pieces up to one
     row past its last joining row and moves the arm's own cap there. It uses no new pieces. A save loads in a game
     without the mod as a highway that is a few cells longer.
  2. **Capped join** (hwdx, diagonal arms only): when the land past the end takes no highway and the cap sits on the
     arm's last joining cell, that cell gets a capped join instead (4 new pieces). This is what Seoul needed: the
     cell past the cap, (251,116), is lake water by the game's own test.
- **The same problem existed in hwx, hwdd and hwt. All three are fixed with (1).** None of them was fine. Each needs
  plain highway on its arm cells, and the game caps a drag ON its last cell, so an arm dragged exactly to the last
  junction cell was refused: hwx and hwdd fell back to the flyover, hwt left the T stock.

## Stock ends (measured in game, lab, 2026-10-18)

| drag | cells | end caps |
|---|---|---|
| straight along x, (58,25) -> (66,25) | lanes z 24 = 15051.2, z 25 = 15051.0, x 57..66 | x 57 (one PAST the start): 15053.0 / 15054.0; x 66 (ON the end cell): 15054.2 / 15053.2 |
| straight along z, (70,28) -> (70,38) | lanes x 69 = 73.2, x 70 = 73.0, z 27..38 | z 27: 11237.2 / 11235.2; z 38: 11235.0 / 11237.0 |
| diagonal x - z, (44,14) -> (52,22) | band 11223.2 / 11224.0 / 11223.0 | (43,13) 14999.0 with (44,13) 11223.0; (52,22) 14999.2 with (51,22) 11223.2 |
| diagonal x + z, (56,40) -> (64,32) | band 15052.2 / 15106.0 / 15052.0 (middle line x + z = 95, one off the drag line) | (55,40) 15059.2 with (56,40) 15052.0; (64,31) 15059.0 with (63,31) 15052.2 |

So an arm's end row is: straight = both lanes capped; diagonal = the middle cell capped (a half-cell triangle cut on
the cell's diagonal across the band), the two outer cells between it and the previous middle plain, the two past it
empty. The cap's (id, state) names the outward direction (8 combinations, `hwcap.CAP_DIR`). Which drag end gets the
extra cell depends on the drag direction. That is why hwdx's table, which is symmetric about O, worked from one end of
a drag and not from the other.

Stock caps are U-turns: 14999 prop 310 = 0x08004000 (z+ => x+ and back), 15059 = 0x10000008 (x- => z+ and back)
(`lanekit show`).

## Design (picture: the sheet's top row)

```
 before (Seoul)              fix 1: carried on              fix 2: capped join
 . J J .                     . J J .                        . J J .
 . J J J                     . J J J o                      . J J J ~
 . . J C   C = 14999.2       . . J J o   o = 11223.x added  . . J K ~   K = 21532.2
 . . . .   on join (6,6)     . . . o C   C = cap moved      . . ~ ~ ~   ~ = lake
```

- **Fix 1 (`re/harness/src/sc3netmod_hwcap.c`, twin `re/tools/netmod/hwcap.py`).** `hwcap_need(cell, outward step)`
  is called by a block where it needs whole highway and finds a cap or nothing. It walks back along the arm to the
  arm's cap (the right family and direction, inside the band), then checks every cell the arm needs up to one row
  past that cell. Each must be inside the pass box, unclaimed, and take a highway: no highway there, flat
  (FUN_10016ccd), not water (FUN_10016d69), and either no surface occupant or trees. `hwcap_commit` then writes the
  arm (rows up to the farthest need, the cap copied one row out) before the block writes its own pieces over it.
  - **Fresh builds only.** An interchange that is already built never grows its arms, so a player who cuts an arm
    still loses that side.
  - **hwcap_free does not run hwy_free.** hwy_free adds the On-ramp tool's terrain test (vt+0xd0). This was meant to
    let the arm onto lake-shore cells the Highway tool builds on: a stock drag (249,117) -> (249,121) beside Seoul's
    lake built normally. It did not help at Seoul, because (251,116) failed the water test itself. The diagnostic
    line read: `hwcap: edit: (251,116) refused: highway 0, flat 1, water 1, occupant type -1`.
  - **Its own writer.** hwy_put refuses any cell that fails hwy_free, so hwcap writes with the same piece writer
    FUN_10008919. hwcore's file is unchanged.
- **Fix 2 (hwdx).** Pieces 21532 (x - z family, flavour 0), 21533 (x + z, 0), 21534 (x - z rep turned, flavour 1)
  and 21535 (x + z, 1).
  - **Base and state.** The base is the stock cap. The piece is placed at the cap's own state: it is painted at the
    crossing turn where that cap is state 0.
  - **Art.**
    - The hwdx scene is painted with the diagonal stopped on the cap line (`hwdx_paint.py`, `scene(capped=True)`).
    - The ramp that joins there has merged before that line. R4's centreline ends at x + z = 12.80; the line is 13.
    - The end face is then taken pixel for pixel from the stock cap frames (`hwcap_art.py compose`): a pixel that
      lies past the cap line at deck height comes from 14999 / 15059, the rest from the painting. The result shows
      the stock facade.
  - **Turn matrix.** The stock cap's: a U-turn. The ramp enters from the same side as the carriageway. No lanes: the
    carriageway lanes end inside the cell.
  - **Block logic.** `hwdx_quad` accepts the stock cap on a joining cell when the arm cannot be carried on and the
    class has a capped join. It keeps an existing capped join on every later pass. `hwdx_write` puts the capped join
    where the cap is.
  - **When the arm is extended later.** If the player extends the diagonal, the stock retile re-places the cap with
    band (the base is not Protected). The next pass then finds the plain piece and writes the normal join there.
  - **Older packages.** If a package without these pieces is installed, the capped joins switch off, with a log line.
  - **Straight arms get no capped join.** Frame 0 of the straight caps 15053 / 15054 is a flat 60 x 31 tile whose
    geometry was not decoded. A straight arm that cannot be carried on still drops its quadrant.
- **Why "carried on" is the first choice.** It is literally what a drag that much longer leaves: stock pieces, stock
  seams, the normal join. A capped join only works when the cap is on the last joining cell. An arm that ends a row
  or two earlier leaves join cells empty, and only extending the arm fixes that.

### Per block

| block | where an arm ending early broke it | fix |
|---|---|---|
| hwdx | joining cell holds the cap or nothing -> that quadrant dropped | per quadrant: carry the arm on (needs under the quadrant's tag, farthest wins), else capped join on the last diagonal joining cell, else drop as before |
| hwx | arm cells dx / dz 2..5 / -6..-3 not plain straight -> clean flyover | carry the arm on, then the full cloverleaf. Arm stopping at the 4x4 = hwt's stub X, unchanged |
| hwdd | JOIN rows accepted a cap, BAND rows (2 rows past) refused it -> flyover, or nothing | JOIN / BAND rows with a cap or nothing are carried on (cloverleaf and flyover). Existing interchanges: refused as before |
| hwt | through highway one past the T and stem to one past its last cell must be straight -> T refused, stem keeps caps | through highway (not at dx 0..1, where the stem meets it) and stem carried on |

## Checks

Offline twins (stock caps placed on drag footprints with `hwcap.stock_ends`, as the game does):
- `py -3.12 -m netmod.hwdx check`: 0 failures.
  - The 8 drags and the table checks are unchanged.
  - 27 end-cap cases, all ok: each arm and all four arms together capped on the last joining cell, case A / B, r 0 /
    1, carried on (157 cells, 3 stock).
  - An arm 2 rows shorter: carried on 3 rows.
  - The cell past the cap taken: capped join (A r0 +d / -d, B r1 +d / -d).
  - Shorter and blocked: A1 refused, O1 still built.
  - Straight arm blocked: A1 refused.
- `py -3.12 netmod/hwx_twin.py rule <lab.sc3>`: all ok, including "+x arm capped on its last junction cell -> carried
  on 1 row, new cloverleaf" and "the cell past it taken -> new clean flyover".
- `py -3.12 netmod/hwdd.py check`: all checks pass, including "north arm capped 4 cells past O -> built clover (arm
  carried on +6)" and "the cell past the cap taken -> none" (the same as before the fix).
- `py -3.12 netmod/hwt_twin.py selftest`: PASSED, with 8 new cases (through highway capped at dx 8 or -3, stem
  capped at dz -5, turns 0 and 1, built after carrying on; dx 9 taken: refused).
- Seoul twin with stock caps: it predicts all 4 quadrants by carrying the arm on, while the game uses the capped
  join. The twin's water map disagrees with the game at (251,116) (open item 1).

In game (instance inst_hwcap):

| check | log / cells | shot |
|---|---|---|
| Seoul, drag (238,102) -> (251,115) | `hwcap: (251,116) refused: ... water 1`, `quadrants A1 A2 O1 O2`, (251,115) = 21532.2 | seoul_after_z3 / z4 / z4_r2 |
| Seoul save + reload | 154 restored, kept A1 A2 O1 O2 | sheet, top middle |
| Seoul save read without the mod (tiler.City.load) | (251,115) = 14999.2, (250,114) = 11224.2, ramp (252,110) = 15127.0 | - |
| lab hwdx: S (43,28) -> (73,28), D (44,14) -> (64,34) | `arm end 14999.2 at (64,34) carried on 1 row(s): cap now at (65,35), 4 cells written`, `quadrants A1 A2 O1 O2`; (64,34) 21276.0, (65,34) 11223.0, (64,35) 11223.2, (65,35) 14999.2 | lab_a0_z3 |
| lab hwx: z (105,79) -> (105,99), x (95,89) -> (110,89) | `arm end 15054.2 at (110,88) carried on 1 row(s)`, `cloverleaf at (105,89): 96 cells written`; (111,88) / (111,89) = 15054.2 / 15053.2 | labx_a0_z3 |

hwdd and hwt were checked offline only (their twins mirror the C line by line). The lab hwdx and hwx builds were not
saved: the reload check was done on Seoul, where the new piece is.

## Limits and open items

1. **Twin water vs game water [UNCERTAIN].** At Seoul the game's terrain water test says (251,116) is water. The
   tiler (`City.is_water`, any corner at or below the water level) says it is dry, and that water starts at
   (251,117). This one data point is consistent with a one-row z offset in the tiler's water grid. Not checked
   elsewhere. Until then the twin over-predicts free land at shores.
2. **Unrequested highway.** Carrying an arm on adds highway the player did not drag: 1 row in the cases above,
   6 rows in hwdd's "arm only 4 cells past O" case. Cost: none (the writer is free, as for all interchange pieces).
3. **Straight arms have no capped join** (see Design).
4. **What hwcap_free skips [UNCERTAIN].** It skips terrain vt+0xd0, and what vt+0xd0 refuses besides shore cells is
   not decoded.
5. **A stalled launch.** One launch (seoul4) stalled before the city load, while other projects' batch jobs loaded the
   machine: 2 s of CPU in 12 minutes, "not responding". The relaunch on the same build and files loaded normally. Not
   reproduced. In another slow start sc3resize gave up waiting for SIMSPR ("mod inactive"), and screenshots failed in
   that game.

## Files

New:
- `re/harness/src/sc3netmod_hwcap.c`: ignored by `/re/*`, needs `git add -f`
- `re/tools/netmod/hwcap.py`
- `re/tools/netmod/hwcap_art.py`
- `verify/hwcap/RESULTS.md`

Changed:
- `re/harness/src/sc3netmod.c`: +1 include
- `re/harness/src/sc3netmod_rbt.c`: +2 lines, stats
- `re/harness/src/sc3netmod_hwdx.c`
- `re/harness/src/sc3netmod_hwdx_tab.h`: regenerated, additions only (`g_hwdx_cap`)
- `re/harness/src/sc3netmod_hwx.c`, `sc3netmod_hwdd.c`, `sc3netmod_hwt.c`
- `re/tools/netmod/hwdx.py`, `hwdx_paint.py`, `hwx_twin.py`, `hwdd.py`, `hwt_twin.py`
- `re/tools/netmod/examples/highway_diagonal_cloverleaf/manifest.json` and `README.md`
- `re/tools/netmod/examples/highway_diagonal_cloverleaf/lanes/21532..21535.json`: gitignored, needs `git add -f`

Art stays out of the repo, as for every package. Rebuild with `hwdx_paint.py art <pkg> 21532 21533 21534 21535`,
`hwcap_art.py compose <pkg>`, `hwdx_paint.py pad <pkg>`. The other pieces' art is hwseam's.
