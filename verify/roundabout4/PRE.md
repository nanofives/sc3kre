# roundabout4: pre-registration (2026-10-14)

Owner request 2026-10-14 (after hand-testing round/1012, screenshot at zoom ~3): "we need a separate texture for 3 road
roundabout". On a 3-arm automatic roundabout the unused fourth mouth is drawn as an open asphalt stub up to the block
edge (roundabout3 RESULTS, limit). Branch `child/roundabout4` from `round/1012` 5eae8e6 (roundabout2 + roundabout3).
SIMNTWRK / SIMSPR addresses are Ghidra VAs (image base 0x10000000).

## What was built

**The second piece is a quarter, not a whole block.** A block is four cells, one per exit (pinwheel states 3,0 / 2,1,
MULTITILE.md 5). On a 3-arm block exactly one cell's exit holds no road. That cell gets the new variant **20401**
(base 39, ROAD, same state as the cell); the other three stay 20400. "Rotated so the closed mouth faces the missing
arm" is then automatic: a cell's state already fixes which side its arm is on.

- **Art** (`paint_closed.json`, `netpaint.py` `closed_mouth`): the 20400 quarter's ring and island unchanged (same code
  path, `PinwheelRoundabout.ring`); no arm strip, entry band, exit band, splitter island or give-way dashes. Outside the
  ring asphalt (r >= 212 units from the block centre) the ring's outer profile of stock road 29 (white edge line
  212-219, gutter, sidewalk) runs on round the block centre to r = 258; beyond that the frame is transparent.
  Reference: stock curve 11203 state 0 draws the same thing about the same centre (corner x 0, z 256): sampled along
  45 deg, edge line at r 212-219, sidewalk 224-256, transparent from r 260; its opaque pixels reach r 259.3 (zoom 4,
  slot 0, measured on the stock frame). 20400's 20 frames are byte-identical before and after the netpaint refactor
  (measured: 0 of 20 differ).
- **Terrain under the piece** (static, the brief's NO-GUESSING point). SIMSPR `FUN_100192aa` (occupant -> view
  cell) reads the frame table's draw flags (`frameTable->vt+0x20`, header +0x12) and, when bit **0x40** is set, calls
  `FUN_1001a303(cell x, z)`, which returns the terrain object of that cell (`this+0x40`->vt+0x6c and the per-mode
  helpers), and attaches it to the occupant with `vt+0x5c` before the cell is queued [CONFIRMED @ SIMSPR 0x100192aa,
  0x1001a303]. Stock flags (NET_ART.md 8): T 39 and road 29 0x80, curve 11203 **0xC0**. That is why grass shows in
  11203's transparent corner and the back buffer shows in 20400's (roundabout2 "Island fill"). netpack gets
  `art.ground_under` (sets / clears 0x40); 20401 ships it set. Installed tables read back: 20400 `0x80`, 20401 `0xC0`.
  20400 keeps 0x80 (every pixel is painted).
- **Lanes** (`closed.lanes.json`): cars only on the ring, x- (0,80) -> z+ (175,255) path 1024 (20400's ring lane, which
  is also stock 11203 state 0's lane); pedestrians on the outer sidewalk (15,15) -> (240,240) path 768 (11203 state
  0's walk), exits (15,15) code 0 (x-) and (240,240) code 24 (z+), the points where the neighbouring 20400 quarters'
  walks end. No vehicle lane and no pedestrian exit on the arm side (z-, code 8). Turn matrix auto: road `0x10000008`
  (x- -> z+ only).
- **Rule** (`sc3netmod_rbt.c`): table line `rbt 20400 3 20401` (manifest `auto_roundabouts[].closed_piece`). Same
  qualification as roundabout3; in (a) 20401 counts as either stock tile, like 20400. Per cell the converter writes
  20400 when the cell's exit holds road and 20401 when it does not; a block is (re)written when any cell differs from
  that. Revert: a non-qualifying block holding 20400 or 20401 in the right state gets the stock rect retile (as
  before). Save: 20401 is always written as curve 11203 (it only sits on an arm-less cell), 20400 as before. A table
  line with two numbers keeps roundabout3's behaviour (every quarter 20400).
- `rb_auto.py scan` prints the per-cell pieces.

Static: `netpack.py validate examples/roundabout` OK (4.0.0, two variants, `auto roundabout: piece 20400 ... arm-less
quarter 20401`, no warning); `netpaint.py seams` 20400 1320 / 1320; lanekit build of the closed spec: no warning.
`netpack.py selftest`: 1 failure, U1 (tree byte-identical after install / uninstall), the diff lists
`verify/menuscale/A_sc3resize.log` and `verify/menuscale/state.json`: files another child writes into MAIN during the
run; re-run before RESULTS.

## Build under test

Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_roundabout4`: hard links of MAIN `Apps`, `Buildings`, `Cities`,
`Scripts` (release mod files skipped), `Apps\GZGraphicD.dll` / `SIMSPR.DLL` = the `.shipped` copies, `*.ini/*.cfg/*.txt`
in Apps de-linked. SHA-256 prefixes: SC3U.exe 49dd55e1 (anchor), SIMNTWRK 693f6572, GZGraphicD 48201f47, SIMSPR
eec71500 (stock). Package roundabout 4.0.0 in overlay mode. Instances `re\harness\inst_rb4` (sc3resize + sc3netmod +
mods_launch from this branch) and `inst_rb4_nomod` (sc3resize + mods_launch). Every game started with
`mods_launch.exe -multi`, stopped by its own PID.

## Predictions

Block rows below are `(X,Z) (X+1,Z) / (X,Z+1) (X+1,Z+1)` as id.state.

**L, install.** Log: `rbt: ... automatic 2x2 roundabout = piece 20400, at least 3 arm(s), arm-less quarter 20401`,
`hooked ... arm-less quarter 20401`, `### READY`. No `### rbt` line in any run.

**GR, terrain under 20401 (gate).** Lab save (below), both games load it, same camera calls (`rb_lab.py cam`), sim
paused, frames by sc3resize DUMP; zoom 2, 3, 4 x rotation 0..3 on each of the four 3-arm lab blocks. `rb_ground.py`:
G = closed-cell pixels farther than 262 units from the block centre. Mod frame vs stock frame (stock curve 11203 on
that cell, also transparent there): equal (5/6/5) on >= 0.95 of G and black on <= 0.01 of G, in every view with
|G| >= 20. If not met: STOP, the art is not shipped as is (fallback is painting that area, decided with the owner).

**A, stock cities on load** (shipped saves, copies). Load pass `3 qualify, 3 converted` (Berlin, Moscow), `1 qualify,
1 converted` (Craterville). Pieces (from `rb_auto.py scan`):
- Berlin (29,86) `20400.3 20401.0 / 20400.2 20400.1`; (57,167) `20400.3 20400.0 / 20401.2 20400.1`; (145,102)
  `20401.3 20400.0 / 20400.2 20400.1`.
- Moscow (30,54) `20400.3 20400.0 / 20401.2 20400.1`; (92,141) `20401.3 20400.0 / 20400.2 20400.1`; (122,130) all 20400.
- Craterville (132,148) all 20400.
- Every other cell of a 10x10 box round each block reads as in the save (`rb_grid.py`).

**B, lab** (Roadless Paradise copy, flat sites at altitude 82 picked from the save's height map, Road tool through
`rb_lab.py road`, grid read after each stroke). Strokes per block (X,Z): (X,Z)-(X+1,Z), (X,Z+1)-(X+1,Z+1), then the
arms W (X-1,Z)-(X-3,Z), N (X+1,Z-1)-(X+1,Z-3), E (X+2,Z+1)-(X+4,Z+1), S (X,Z+2)-(X,Z+4), each 3 cells.
- B-W (56,8), arms N E S: `20401.3 20400.0 / 20400.2 20400.1`.
- B-N (56,20), arms W E S: `20400.3 20401.0 / 20400.2 20400.1`.
- B-E (56,32), arms W N S: `20400.3 20400.0 / 20400.2 20401.1`.
- B-S (68,20), arms W N E: `20400.3 20400.0 / 20401.2 20400.1`.
  Each converts on the stroke that completes its third arm and logs `-> roundabout, 3 arm(s): <the four ids>`.
- B-G grow / shrink (68,32): arms W N S -> `20400.3 20400.0 / 20400.2 20401.1`; add E -> all four 20400 (log `4 arm(s)`);
  demolish the E exit cell (70,33) -> `20400.3 20400.0 / 20400.2 20401.1` again (log `3 arm(s)`); demolish the S
  exit cell (68,34) -> 2 arms: stock `39.3 39.0 / 11203.2 11203.1` (roundabout3 B8), no 20400 / 20401 left.
- Then save (menu command 0x10009002) = the lab save for GR and V.

**BK, two-number table** (the "before" pictures). Same lab save, `SC3NETMOD_TABLE` = a copy of the installed table with
the line `rbt 20400 3`: log `arm-less quarter 0 (none ...)`, the four lab blocks read 20400 on all 4 cells (as
roundabout3).

**V, pictures.** The four lab blocks, zoom 2, 3, 4 x rotation 0..3, mod game (and BK and stock for the same views).
Expected: on the closed side the ring's outer edge line, gutter and sidewalk run on unbroken from one neighbouring
quarter to the other; no asphalt stub, no give-way dashes, no splitter island on that side; terrain outside the curb;
the other three arms unchanged from roundabout3. This arm is judged on the pictures (owner shots), not a number.

**T, traffic.** Moscow after the load conversion, sim running, `rb_island.py 30,54 --secs 480` (closed quarter (30,55),
state 2, its mouth = exit code 24 towards (30,56), which holds no road). Predicted: 0 transitions `30,55,24,*`
(nothing leaves the closed quarter through the mouth) and 0 transitions from (30,56); ring with the order (ccw) > 0,
against = 0 (`rb_ring.py ... ccw`); moves into the ring from the three road arms > 0. Scope: rb_island counts movers at
STRTSIM `FUN_1001c750` (the exit-step lookup that pedestrian exit codes also go through, NET_LANES.md); which
movers it sees is reported from the codes in the run (diagonal codes 4, 12, 20, 28 only come from pedestrians).

**S, saves.** Save the converted Moscow. Log `save: 12 variant tile(s) written as base`. `netvariant.py scan`: 0 raw
variant tiles, 12 entries; the saved ids of (30,55) and (92,141) are 11203 (the 20401 cells), the other 10 are 39.
- S0 (inst_rb4_nomod): the save opens; the 12 cells read the shipped tiles; 0 other differences in the 10x10 boxes.
- S1 (mod): `12 to restore`, `all 12 variant tiles restored`, load pass `3 qualify, 0 converted, 0 reverted`; (30,55)
  and (92,141) read 20401.2 / 20401.3.

**O, owner pictures.** `MAIN\verify\roundabout4\owner_shots\` + `captions.md` (Spanish): before / after at zoom 3
(like the owner's screenshot) and zoom 4, the four orientations, a shipped-city block converted on load, the
grow / shrink sequence.

Anything not met is reported as not met; changes after this file are listed in RESULTS with the reason.
