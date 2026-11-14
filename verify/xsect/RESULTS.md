# xsect: every junction shape on a flat sandbox (2026-11-14)

Owner request: "test with all possible intersections in a plain sandbox world and send me screenshots". Player report
(Simtropolis): a "new avenue not showing up when 2 roads are placed orthogonal (all network pieces disappear - diagonal
seems to work)". Test pass only, nothing fixed. Mods = main 5f87c4f (dev/xsect tree, all mods loaded).

## Verdict

80 cases: **43 draw correctly, 10 refused by design (stock look, the log says so), 26 broken, 1 not built.**

- Every case made only of orthogonal pieces draws: R, A (2 roads), B (3 roads) crossings, T's, corners, ends, merges,
  A/B over rail, A/B under a highway, R and A next to an on-ramp. Where netmod refuses a band it keeps the stock
  two-way look (yellow centre line, crossing boxes) and the log says why (`stays two-way` / `left to the stock tiler`).
- **Every broken case has a diagonal avenue (DA) or diagonal boulevard (DB) in it.** On screen a diagonal band runs
  vertical or horizontal and a grid-aligned one runs slanted, so the player's "2 roads placed orthogonal" may well
  mean a road or avenue meeting a DIAGONAL avenue, which is where this sweep finds the faults.
- No case had a cell that holds a piece and draws nothing at all. The faults are wrong or missing art next to the
  junction: grass or dark diamonds inside a DB lane, lanes ending in lone crossing boxes on grass, roads ending square
  against an end cap, bands with no junction piece, stock pieces drawn as a chain of roundabouts, rail or highway cut.
- The same faults show in rotation 1 (`owner_shots/rot_*.png`), so they do not depend on the view direction.

## Broken classes (cells + log lines)

1. **Road/avenue bending 135 deg into a DA/DB (15, 19, 34).** 15: road 29 up to (86,33), then (87,33) = 21803.0 (the
   DA's U-turn end), (88,33) 20501.0, (87,34) 11203.2. Picture: road stops in a square cut, a U-turn bulb beside it,
   the avenue starts a row lower. Log `dav: edit: band axis 0 from (87,33) kept: 2 touching road cell(s) left to the
   stock tiler (DAVTOUCH, 2 tries)`. 19: road 29 to (158,33), DB end cap 21026.2/21025.2/21024.2/21023.2 at (159..162,33).
2. **Road/avenue/boulevard meeting a DB (16, 17, 18, 31, 32, 33, 42, 43, 44).** Every cell holds a piece but a grass
   (16, 33, 44) or dark slate (31) diamond is drawn in the DB's lane right beside the crossing row, or grass with trees
   (17, 18, 32, 43) where the lane should be road. 16: crossing row (105..108,33) = 20953.0/20954.0/20955.0/20956.0,
   DB lane above it (104,32) 20950.2, (106,32) 21917.0, (107,34) 20957.0. 17: T row (123..126,33) = 20963.2..20960.2,
   lane below (125,34) 21917.2. 18: (143,34) 21917.2, (142,32) 20957.2.
3. **Orthogonal A/B crossing or ending at a DA/DB (31, 32, 38, 40, 42, 44).** Only one road of the band reaches the
   diagonal; the other lanes end in lone crossing boxes on grass, or the stem is drawn by the stock tiler as one
   diagonal-looking road. 40: B stem rows 68..70, x 177..183 = 11204.2 x4 + 11203.0 / 39.3 39.3 39.0 11204.3 /
   43.0 39.1 11203.1. Log `bv: edit: run axis 0 from (177,68), 7 column(s) left to the stock tiler: avenue / boulevard
   arm shorter than 2`. 38: left side 20700..20706 (converted), right side 11204/39/43/11203 (stock).
4. **DA x DB and DB x DB crossings (49, 53).** No junction piece: the axis-1 band's 20950.3/20951.3/20951.1/20950.1
   run straight through, the axis-0 band is cut with notches on either side.
5. **DB stem or corner on axis 1 (50, 52, 54, 55).** The DB arm is not converted (no `dbv:` line for it). 50 rows
   87..93 hold stock 11203.3 / 43.0 / 43.0 / 11203.1, and the rows of 43 pieces draw as a chain of roundabout-like
   diamonds with yellow curves (`rot_50_DAxDB_T1.png`). The same DB on axis 1 as a full through band (51) draws.
6. **DA/DB over rail (68, 69) and highway (72, 73).** The rail or highway is cut. 68: rail row 123 = 44.0 up to x 140
   and from x 144, cells (141..143,123) hold 20505.2/20500.0/20505.0. 72: highway cells (32..34,140) and (33..35,141)
   hold 20505/20500 instead of 15051. Stock baseline in the same city: a plain diagonal road crosses rail at grade (74)
   and passes under the highway (75), so the cut comes from the avenue conversion.
7. **Minor (41, 48).** 41: the lowest boulevard road ends square against the DA's curb. 48 (DA x DA corner): notched
   lane edges and a short stub below the corner, no corner piece.

Not built: **80** (DA next to an on-ramp). The On-ramp tool placed nothing because the DA had cut the highway (class 6).

## Side findings (not fixes)

- **Far edits re-tile two DA bands every time.** Cases 40 (x 160..167, z 68..75) and 41 (x 16..23, z 86..93), 21 cells
  each, log `dav: edit: (160,68) avenue piece 20505 no longer in a band -> stock retile` on every later edit anywhere
  on the map (438 lines over the sweep). The read windows grow to most of the 192 map (`window grown to (0,0)-(191,112)`).
  Final read-back: 41's boulevard arm went from 20700/20701/20702 to stock 11204/29/11204 after later edits (18 cells).
- **Lab tool:** some builds (case 45 drags 1-3, 48 drag 2, 56, 58 drags 2-3) never returned to the Frida client
  although the game applied them (cells read back, `ptime: edit` 265 ms, game alive, autosaves running). `sweep.py`
  now opens a new session and carries on. Not a game hang.
- Leftover zoned land from Roadless Paradise (orange/blue squares with no-power bolts in 52, 53, 62, 63, 73) is
  unrelated: the bulldozer does not de-zone.
- 09 (R x B T): draws, but its T box is a darker speckled asphalt than the other boxes.

## How it was built

- Sandbox `dev/xsect/tree/Cities/xsect_sandbox_clear.sc3`: Roadless Paradise (192x192) flattened with
  `re/tools/city_flatten.py` (every corner 82, water 80, so no water), all trees bulldozed with posted Bulldozer area
  drags (`clear_trees.py`, `clear_boxes.py`), funds $50,000,000 (`re/tools/set_funds.py`). The built sweep:
  `xsect_sweep_built.sc3` (`pwsh re/scripts/sc3dev.ps1 run xsect -City xsect_sweep_built.sc3` to look around).
- `sweep.py`: one 18x18 slot per case from (6,6), arms 6 cells. Builds are game-thread calls of the network manager
  build (nb_drive, the call the Road/Rail/Highway tools make), one drag per lane. Diagonals are stairs as avdb_lab
  draws them (DA = 2 joined stairs, DB = 3). First kind along x / axis 0 (+x+z), second along z / axis 1 (-x+z).
  T1 = first kind through, T2 = second kind through. Read-back = piece id.state of every network cell in the slot after
  the build, re-read after the whole sweep (`final_cells.json`: 6 cases changed later, listed above). Log lines = the
  sc3netmod.log bytes written during the case, filtered to lines whose first cell lies in the slot (`logsum.json`).
- `ramp.py`: highway + crossing kind + On-ramp tool click (posted, pixel from rb_lab's formula, flat alt 82), recipe
  from verify/netramp/PRE.md.
- Pictures: in-process frame dumps (sc3resize DUMP), zoom 4 close-up on the junction | zoom 3 case view per case,
  zoom 1 overviews per slot row (`overview_row*.png`), rotation 1 for 04, 15, 16, 50 (`rot_*.png`). Sheets
  `sheet_<group>.png`, at most 12 tiles, label colour = verdict (red BROKEN, amber refused, green ok).
- No real mouse, keyboard or foreground. Full netmod log of the run: `sc3netmod_sweep.log`.

## Table

Log line = the first refusal/revert line for the case's own cells, else its first netmod line.

| case | built how | read-back | log line | verdict | picture |
|---|---|---|---|---|---|
| 01_RxR_cross | 2 drag(s) (road) | 25 cells | `(no netmod line for these cells)` | **ok**  | `owner_shots/01_RxR_cross.png` |
| 02_RxR_T1 | 2 drag(s) (road) | 19 cells | `(no netmod line for these cells)` | **ok**  | `owner_shots/02_RxR_T1.png` |
| 03_RxR_L | 2 drag(s) (road) | 13 cells | `(no netmod line for these cells)` | **ok**  | `owner_shots/03_RxR_L.png` |
| 04_RxA_cross | 3 drag(s) (road) | 37 cells | `avl: edit: band along z from (69,10) rows 0..3 -> one-way (ends: U-turn / join or edge)` | **ok**  | `owner_shots/04_RxA_cross.png` |
| 05_RxA_T1 | 3 drag(s) (road) | 25 cells | `avl: edit: band along z from (87,17) rows 0..3 -> one-way (ends: join or edge / U-turn)` | **ok**  | `owner_shots/05_RxA_T1.png` |
| 06_RxA_T2 | 3 drag(s) (road) | 31 cells | `avl: edit: band along z from (105,10) rows 0..3 -> one-way (ends: U-turn / join or edge)` | **ok**  | `owner_shots/06_RxA_T2.png` |
| 07_RxA_L | 3 drag(s) (road) | 20 cells | `avx: edit: (124,15) avenue end cap 11203.0 beside the T at (123,15) -> read as a box row` | **ok**  | `owner_shots/07_RxA_L.png` |
| 08_RxB_cross | 4 drag(s) (road) | 49 cells | `avl: edit: band along z from (140,10) rows 0..3 -> one-way (ends: U-turn / join or edge)` | **ok**  | `owner_shots/08_RxB_cross.png` |
| 09_RxB_T1 | 4 drag(s) (road) | 31 cells | `avl: edit: band along z from (158,17) rows 0..3 -> one-way (ends: join or edge / U-turn)` | **ok** draws; T box darker speckled asphalt | `owner_shots/09_RxB_T1.png` |
| 10_RxB_T2 | 4 drag(s) (road) | 44 cells | `avl: edit: band along z from (176,10) rows 0..3 -> one-way (ends: U-turn / join or edge)` | **ok**  | `owner_shots/10_RxB_T2.png` |
| 11_RxB_L | 4 drag(s) (road) | 26 cells | `bv: edit: run axis 1 from (16,33): ragged end(s), 0 column(s) at +s and 1 at -s left to the stock tiler: a junction inside an end region` | **ok** draws; 1 column left to stock tiler | `owner_shots/11_RxB_L.png` |
| 12_RxDA_cross | 3 drag(s) (road) | 49 cells | `dav: edit: band axis 0, 13 row(s) from (27,27), 39 cell(s), 3 junction cell(s), 4 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 41 written` | **ok**  | `owner_shots/12_RxDA_cross.png` |
| 13_RxDA_T1 | 3 drag(s) (road) | 31 cells | `dav: edit: band axis 0, 7 row(s) from (51,33), 21 cell(s), 3 junction cell(s), 4 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 22 written` | **ok**  | `owner_shots/13_RxDA_T1.png` |
| 14_RxDA_T2 | 3 drag(s) (road) | 43 cells | `dav: edit: band axis 0, 13 row(s) from (63,27), 39 cell(s), 3 junction cell(s), 2 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 40 written` | **ok**  | `owner_shots/14_RxDA_T2.png` |
| 15_RxDA_L | 3 drag(s) (road) | 28 cells | `dav: edit: band axis 0 from (87,33) kept: 2 touching road cell(s) left to the stock tiler (DAVTOUCH, 2 tries)` | **BROKEN** road ends square at DA U-turn cap 21803, not joined | `owner_shots/15_RxDA_L.png` |
| 16_RxDB_cross | 4 drag(s) (road) | 60 cells | `dav: edit: band axis 0, 13 row(s) from (99,27), 39 cell(s), 3 junction cell(s), 4 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 41 written` | **BROKEN** grass diamond in DB left lane at the crossing | `owner_shots/16_RxDB_cross.png` |
| 17_RxDB_T1 | 4 drag(s) (road) | 37 cells | `dav: edit: band axis 0, 7 row(s) from (123,33), 21 cell(s), 3 junction cell(s), 4 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 22 written` | **BROKEN** grass + trees in DB right lane at the T | `owner_shots/17_RxDB_T1.png` |
| 18_RxDB_T2 | 4 drag(s) (road) | 55 cells | `dav: edit: band axis 0, 13 row(s) from (135,27), 39 cell(s), 3 junction cell(s), 2 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 40 written` | **BROKEN** grass + trees in DB lane beside the road T | `owner_shots/18_RxDB_T2.png` |
| 19_RxDB_L | 4 drag(s) (road) | 34 cells | `dav: edit: band axis 0 from (159,33) kept: 1 touching road cell(s) left to the stock tiler (DAVTOUCH, 1 tries)` | **BROKEN** road ends at DB end cap 21023..21026, not joined | `owner_shots/19_RxDB_L.png` |
| 20_AxA_cross | 4 drag(s) (road) | 49 cells | `avl: edit: band along x from (172,33) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/20_AxA_cross.png` |
| 21_AxA_T1 | 4 drag(s) (road) | 36 cells | `avl: edit: band along x from (10,51) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/21_AxA_T1.png` |
| 22_AxA_L | 4 drag(s) (road) | 26 cells | `avl: edit: band along x from (28,51) rows 0..5 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/22_AxA_L.png` |
| 23_AxB_cross | 5 drag(s) (road) | 59 cells | `avl: edit: band along x from (46,51) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/23_AxB_cross.png` |
| 24_AxB_T1 | 5 drag(s) (road) | 41 cells | `avl: edit: band along x from (64,51) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/24_AxB_T1.png` |
| 25_AxB_T2 | 5 drag(s) (road) | 49 cells | `avl: edit: band along x from (87,51) rows 0..5 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/25_AxB_T2.png` |
| 26_AxB_L | 5 drag(s) (road) | 31 cells | `bv: edit: run axis 1 from (106,51): ragged end(s), 0 column(s) at +s and 2 at -s left to the stock tiler: an end on a corner (road on one side only)` | **refused** corner + avenue arm stay stock two-way (yellow) | `owner_shots/26_AxB_L.png` |
| 27_AxDA_cross | 4 drag(s) (road) | 59 cells | `avl: edit: band along x from (118,51) rows 0..3 stays two-way: band along x at (118,51): forward end (122,51) 39.1 + (122,52) 11204.0 is not a U-turn ` | **refused** avenue stays two-way (yellow), draws connected | `owner_shots/27_AxDA_cross.png` |
| 28_AxDA_T1 | 4 drag(s) (road) | 41 cells | `avl: edit: band along x from (136,51) rows 0..6 stays two-way: band along x at (136,51): forward end (143,51) 11204.2 + (143,52) 39.3 is not a U-turn ` | **refused** avenue stays two-way (yellow), draws connected | `owner_shots/28_AxDA_T1.png` |
| 29_AxDA_T2 | 4 drag(s) (road) | 47 cells | `avl: edit: band along x from (163,51) rows 0..1 stays two-way: band along x at (163,51): back end (162,51) 11204.2 + (162,52) 39.3 is not a U-turn pai` | **refused** avenue stem stays two-way stub | `owner_shots/29_AxDA_T2.png` |
| 30_AxDA_L | 4 drag(s) (road) | 34 cells | `avl: edit: band along x from (172,51) rows 0..5 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/30_AxDA_L.png` |
| 31_AxDB_cross | 5 drag(s) (road) | 69 cells | `avl: edit: band along x from (10,69) rows 0..3 stays two-way: band along x at (10,69): forward end (14,69) 39.1 + (14,70) 11204.0 is not a U-turn pair` | **BROKEN** dark triangle in DB lane; avenue lane ends in lone box | `owner_shots/31_AxDB_cross.png` |
| 32_AxDB_T1 | 5 drag(s) (road) | 46 cells | `avl: edit: band along x from (28,69) rows 0..6 stays two-way: band along x at (28,69): forward end (35,69) 11204.2 + (35,70) 39.3 is not a U-turn pair` | **BROKEN** gap in DB lane at the T; avenue lane cut | `owner_shots/32_AxDB_T1.png` |
| 33_AxDB_T2 | 5 drag(s) (road) | 58 cells | `avl: edit: band along x from (55,69) rows 0..1 stays two-way: band along x at (55,69): back end (54,69) 11204.2 + (54,70) 39.3 is not a U-turn pair, c` | **BROKEN** grass diamond in DB lane; avenue stem one stub | `owner_shots/33_AxDB_T2.png` |
| 34_AxDB_L | 5 drag(s) (road) | 41 cells | `avl: edit: band along x from (64,69) rows 0..6 stays two-way: band along x at (64,69): forward end (71,69) 11203.0 + (71,70) 39.0 is not a U-turn pair` | **BROKEN** avenue ends at DB end cap, not joined | `owner_shots/34_AxDB_L.png` |
| 35_BxB_cross | 6 drag(s) (road) | 70 cells | `avl: edit: band along x from (82,68) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/35_BxB_cross.png` |
| 36_BxB_T1 | 6 drag(s) (road) | 54 cells | `avl: edit: band along x from (100,68) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/36_BxB_T1.png` |
| 37_BxB_L | 6 drag(s) (road) | 39 cells | `bv: edit: run axis 0 from (117,68): ragged end(s), 3 column(s) at +s and 0 at -s left to the stock tiler: an end on a corner (road on one side only)` | **refused** corner left to stock tiler: boxes + yellow bend | `owner_shots/37_BxB_L.png` |
| 38_BxDA_cross | 5 drag(s) (road) | 69 cells | `bv: edit: run axis 0 from (135,68): split at a bad arm, columns 135..138 convert, the rest of 135..147 left to the stock tiler: avenue / boulevard arm` | **BROKEN** B lanes end in lone crossing boxes at the DA | `owner_shots/38_BxDA_cross.png` |
| 39_BxDA_T1 | 5 drag(s) (road) | 54 cells | `bv: edit: run axis 0 from (153,68): ragged end(s), 5 column(s) at +s and 0 at -s left to the stock tiler: avenue / boulevard arm shorter than 2` | **refused** draws connected; 5 B columns stock look | `owner_shots/39_BxDA_T1.png` |
| 40_BxDA_T2 | 5 drag(s) (road) | 52 cells | `bv: edit: run axis 0 from (177,68), 7 column(s) left to the stock tiler: avenue / boulevard arm shorter than 2` | **BROKEN** B stem drawn as one diagonal-looking road (stock 43/39) | `owner_shots/40_BxDA_T2.png` |
| 41_BxDA_L | 5 drag(s) (road) | 42 cells | `bv: edit: run axis 0 from (9,86): ragged end(s), 1 column(s) at +s and 0 at -s left to the stock tiler: an end where the roads going on are not one ro` | **BROKEN** minor: lowest B road ends square against DA curb | `owner_shots/41_BxDA_L.png` |
| 42_BxDB_cross | 6 drag(s) (road) | 78 cells | `bv: edit: run axis 0 from (27,86): split at a bad arm, columns 27..30 convert, the rest of 27..39 left to the stock tiler: avenue / boulevard arm shor` | **BROKEN** B lanes end in lone boxes; grass patch in DB lane | `owner_shots/42_BxDB_cross.png` |
| 43_BxDB_T1 | 6 drag(s) (road) | 59 cells | `bv: edit: run axis 0 from (45,86): ragged end(s), 5 column(s) at +s and 0 at -s left to the stock tiler: avenue / boulevard arm shorter than 2` | **BROKEN** grass + trees in DB lane at the T | `owner_shots/43_BxDB_T1.png` |
| 44_BxDB_T2 | 6 drag(s) (road) | 62 cells | `bv: edit: run axis 0 from (69,86), 7 column(s) left to the stock tiler: avenue / boulevard arm shorter than 2` | **BROKEN** grass diamond in DB lane; B stem one stub | `owner_shots/44_BxDB_T2.png` |
| 45_BxDB_L | 6 drag(s) (road), 3 no reply (applied) | 50 cells | `bv: edit: run axis 0 from (81,86): ragged end(s), 1 column(s) at +s and 0 at -s left to the stock tiler: road beside the boulevard is not a straight s` | **ok**  | `owner_shots/45_BxDB_L.png` |
| 46_DAxDA_cross | 4 drag(s) (road) | 73 cells | `dav: edit: band axis 0 from (99,81) kept: 4 touching road cell(s) left to the stock tiler (DAVTOUCH, 3 tries)` | **ok**  | `owner_shots/46_DAxDA_cross.png` |
| 47_DAxDA_T1 | 4 drag(s) (road) | 59 cells | `dav: edit: band axis 0 from (117,81) kept: 2 touching road cell(s) left to the stock tiler (DAVTOUCH, 2 tries)` | **ok**  | `owner_shots/47_DAxDA_T1.png` |
| 48_DAxDA_L | 4 drag(s) (road), 1 no reply (applied) | 44 cells | `dav: edit: band axis 0 from (135,81) kept: 2 touching road cell(s) left to the stock tiler (DAVTOUCH, 2 tries)` | **BROKEN** minor: notched lanes + stub at the corner, no corner piece | `owner_shots/48_DAxDA_L.png` |
| 49_DAxDB_cross | 5 drag(s) (road) | 85 cells | `dav: edit: band axis 0 from (153,81) kept: 4 touching road cell(s) left to the stock tiler (DAVTOUCH, 3 tries)` | **BROKEN** no junction: DB runs over DA, DA cut with notches | `owner_shots/49_DAxDB_cross.png` |
| 50_DAxDB_T1 | 5 drag(s) (road) | 66 cells | `dav: edit: band axis 0 from (171,81) kept: 2 touching road cell(s) left to the stock tiler (DAVTOUCH, 2 tries)` | **BROKEN** DB stem not converted: stock 43 chain = roundabouts | `owner_shots/50_DAxDB_T1.png` |
| 51_DAxDB_T2 | 5 drag(s) (road) | 72 cells | `dav: edit: band axis 0 from (15,105) kept: 4 touching road cell(s) left to the stock tiler (DAVTOUCH, 2 tries)` | **ok**  | `owner_shots/51_DAxDB_T2.png` |
| 52_DAxDB_L | 5 drag(s) (road) | 54 cells | `dav: edit: band axis 0 from (27,99) kept: 2 touching road cell(s) left to the stock tiler (DAVTOUCH, 2 tries)` | **BROKEN** DB arm not converted: roundabout chain | `owner_shots/52_DAxDB_L.png` |
| 53_DBxDB_cross | 6 drag(s) (road) | 95 cells | `dbv: edit: band axis 0 from canonical (45,99) kept: 4 touching road cell(s) left to the stock tiler (DBVTOUCH, 3 tries)` | **BROKEN** no junction: one DB cut by the other | `owner_shots/53_DBxDB_cross.png` |
| 54_DBxDB_T1 | 6 drag(s) (road) | 78 cells | `dbv: edit: band axis 0 from canonical (63,99) kept: 2 touching road cell(s) left to the stock tiler (DBVTOUCH, 2 tries)` | **BROKEN** DB stem not converted: roundabout chain | `owner_shots/54_DBxDB_T1.png` |
| 55_DBxDB_L | 6 drag(s) (road) | 63 cells | `dbv: edit: band axis 0 from canonical (81,99) kept: 2 touching road cell(s) left to the stock tiler (DBVTOUCH, 2 tries)` | **BROKEN** DB arm not converted: roundabout chain | `owner_shots/55_DBxDB_L.png` |
| 56_R_end | 1 drag(s) (road), 1 no reply (applied) | 13 cells | `dbv: edit: band axis 0 from canonical (45,99) kept: 10 touching road cell(s) left to the stock tiler (DBVTOUCH, 6 tries)` | **ok**  | `owner_shots/56_R_end.png` |
| 57_A_end | 2 drag(s) (road) | 26 cells | `avl: edit: band along x from (118,105) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/57_A_end.png` |
| 58_B_end | 3 drag(s) (road), 2 no reply (applied) | 39 cells | `avl: edit: band along x from (136,104) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/58_B_end.png` |
| 59_DA_end | 2 drag(s) (road) | 39 cells | `dav: edit: band axis 0, 13 row(s) from (153,99), 39 cell(s), 0 junction cell(s), 0 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 39 written` | **ok**  | `owner_shots/59_DA_end.png` |
| 60_DB_end | 3 drag(s) (road) | 51 cells | `dav: edit: band axis 0, 13 row(s) from (171,99), 39 cell(s), 0 junction cell(s), 0 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 39 written` | **ok**  | `owner_shots/60_DB_end.png` |
| 61_BtoA_merge | 3 drag(s) (road) | 33 cells | `avl: edit: band along x from (10,123) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/61_BtoA_merge.png` |
| 62_AtoR_merge | 2 drag(s) (road) | 20 cells | `avl: edit: band along x from (28,123) rows 0..4 stays two-way: band along x at (28,123): forward end (33,123) 39.3 + (33,124) 11203.1 is not a U-turn ` | **refused** avenue stays two-way, boxes at the narrowing | `owner_shots/62_AtoR_merge.png` |
| 63_AplusA_merge | 4 drag(s) (road) | 52 cells | `bv: edit: run axis 0 from (45,122), 13 column(s) left to the stock tiler: road more than 3 wide beside the boulevard` | **refused** 4 roads wide: stock grid of crossing boxes | `owner_shots/63_AplusA_merge.png` |
| 64_DBtoDA_merge | 3 drag(s) (road) | 46 cells | `dav: edit: band axis 0, 13 row(s) from (63,117), 39 cell(s), 0 junction cell(s), 0 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 39 written` | **ok**  | `owner_shots/64_DBtoDA_merge.png` |
| 65_DAtoDR_merge | 2 drag(s) (road) | 33 cells | `dav: edit: band axis 0, 7 row(s) from (81,117), 27 cell(s), 0 junction cell(s), 0 arm cell(s), 1 merge(s), bends 0/0, 0 crossing(s), 24 written` | **ok**  | `owner_shots/65_DAtoDR_merge.png` |
| 66_Axrail_cross | 3 drag(s) (rail, road) | 41 cells | `avl: edit: band along z from (105,118) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/66_Axrail_cross.png` |
| 67_Bxrail_cross | 4 drag(s) (rail, road) | 53 cells | `bv: edit: run axis 1 from (124,117): ragged end(s), 1 column(s) at +s and 0 at -s left to the stock tiler: an end where the roads going on are not one` | **refused** part of B stays stock two-way (yellow) | `owner_shots/67_Bxrail_cross.png` |
| 68_DAxrail_cross | 3 drag(s) (rail, road) | 53 cells | `dav: edit: band axis 0, 13 row(s) from (135,117), 39 cell(s), 0 junction cell(s), 0 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 39 written` | **BROKEN** rail cut: rail cells hold DA pieces 20505/20500 | `owner_shots/68_DAxrail_cross.png` |
| 69_DBxrail_cross | 4 drag(s) (rail, road) | 64 cells | `dav: edit: band axis 0, 13 row(s) from (153,117), 39 cell(s), 0 junction cell(s), 0 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 39 written` | **BROKEN** rail cut by the DB | `owner_shots/69_DBxrail_cross.png` |
| 70_Axhwy_cross | 3 drag(s) (hwy, road) | 57 cells | `avl: edit: band along z from (177,118) rows 0..10 -> one-way (ends: U-turn / U-turn)` | **ok**  | `owner_shots/70_Axhwy_cross.png` |
| 71_Bxhwy_cross | 4 drag(s) (hwy, road) | 67 cells | `bv: edit: run axis 1 from (16,135): ragged end(s), 1 column(s) at +s and 0 at -s left to the stock tiler: an end where the roads going on are not one ` | **refused** part of B stays stock two-way (yellow) | `owner_shots/71_Bxhwy_cross.png` |
| 72_DAxhwy_cross | 3 drag(s) (hwy, road) | 67 cells | `dav: edit: band axis 0, 13 row(s) from (27,135), 39 cell(s), 0 junction cell(s), 0 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 39 written` | **BROKEN** highway cut: highway cells hold DA pieces | `owner_shots/72_DAxhwy_cross.png` |
| 73_DBxhwy_cross | 4 drag(s) (hwy, road) | 77 cells | `dav: edit: band axis 0, 13 row(s) from (45,135), 39 cell(s), 0 junction cell(s), 0 arm cell(s), 0 merge(s), bends 0/0, 0 crossing(s), 39 written` | **BROKEN** highway cut by the DB | `owner_shots/73_DBxhwy_cross.png` |
| 74_DRxrail_cross | 2 drag(s) (rail, road) | 42 cells | `dbv: edit: band axis 1 from canonical (105,-85), 4 row(s) left to the stock tiler: fewer than 3 clean rows` | **ok**  | `owner_shots/74_DRxrail_cross.png` |
| 75_DRxhwy_cross | 2 drag(s) (hwy, road) | 56 cells | `dbv: edit: band axis 0 from canonical (45,99) kept: 10 touching road cell(s) left to the stock tiler (DBVTOUCH, 6 tries)` | **ok**  | `owner_shots/75_DRxhwy_cross.png` |
| 76_Rxrail_cross | 2 drag(s) (rail, road) | 29 cells | `dav: edit: band axis 0 from (63,117) kept: 6 touching road cell(s) left to the stock tiler (DAVTOUCH, 6 tries)` | **ok**  | `owner_shots/76_Rxrail_cross.png` |
| 77_Rxhwy_cross | 2 drag(s) (hwy, road) | 45 cells | `bv: edit: run axis 1 from (124,117): ragged end(s), 1 column(s) at +s and 0 at -s left to the stock tiler: an end where the roads going on are not one` | **ok**  | `owner_shots/77_Rxhwy_cross.png` |
| 78_Rxonramp | 2 drag(s) (hwy, road) + On-ramp click (143, 139) | 48 cells | `dbv: edit: band axis 1 from canonical (87,-175), 4 row(s) left to the stock tiler: fewer than 3 clean rows` | **ok**  | `owner_shots/78_Rxonramp.png` |
| 79_Axonramp | 3 drag(s) (hwy, road) + On-ramp click (162, 139) | 59 cells | `dbv: edit: band axis 1 from canonical (87,-175), 4 row(s) left to the stock tiler: fewer than 3 clean rows` | **ok**  | `owner_shots/79_Axonramp.png` |
| 80_DAxonramp | 3 drag(s) (hwy, road) + On-ramp click (179, 139) | 67 cells | `dbv: edit: band axis 1 from canonical (87,-175), 4 row(s) left to the stock tiler: fewer than 3 clean rows` | **not built** no ramp: the DA had cut the highway (see 72) | `owner_shots/80_DAxonramp.png` |
