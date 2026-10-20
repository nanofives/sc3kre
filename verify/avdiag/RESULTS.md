# avdiag results: diagonal avenues on one-way halves (2026-10-19)

Plan: `verify/avdiag/PLAN.md`. Base: avcore's AVL (child/avcore 4c7e510, merged into child/avdiag). Test tree
`Simcity_stock_avdiag`, instance `re\harness\inst_avdiag`, packages avenue_lanes (avcore) + diagonal_avenue, lab city
copy `d1.sc3`.

## 1. Lanes (offline, `re/tools/netmod/avdiag_build.py`)

The builder draws each scene's planned lanes as world lines (one direction per carriageway, right-hand), cuts them
per cell, keeps one lane set per piece, checks it everywhere the piece is used, and writes the curves and specs.

| check | result |
|---|---|
| border joins (every lane end on a border meets a lane of the next cell, same point, same direction): the 48 drag footprints, the 8 merge cases, 32 junction scenes, 8 crossing kinds x 4 turns, both bends x 4 turns | 19,336 joins, 0 problems |
| turns per kind | road crossing 8, avenue ending on a road 4, road meeting one carriageway 2 (right in, right out), diagonal x straight 8, diagonal x diagonal 8, either T 4 |
| lane graph (interior nodes with a way in and a way on) | 0 problems |
| curves | 1,016 lane segments on stock curves (within 12 lane units of the planned path), 352 new shapes 23800..25251; 0 conflicts. A lane whose end points a stock curve of another path already has is split at a via node |
| `netpack validate` diagonal_avenue | OK, 0 warnings (96 variants, 96 lane specs, every language) |
| avcore `avlanes.check`, bend joins with 21700 | clean in ENGLISH and English-UK |
| hwave diagonal transition 21604..21609 | no crossing; 32 new shapes 25400..25431; package compiles, 0 warnings |

Changes from the plan sheet, seen while building: the end U-turn fits inside the last middle cell (two semicircles
on the median line, tangent to the diagonal lanes), so the cap cells past it carry no lanes; a drag one step longer
ends the same way, its extra step is a dead stub; a road that meets one carriageway gets right in / right out (the art
has no opening in the median there). Owner sheet of the built lanes: `MAIN\verify\avdiag\owner_shots\avdiag_built.png`.

## 2. Block (`sc3netmod_dav.c`, marked lines in `sc3netmod_rbt.c`, `sc3netmod.c`, `netpack.py`, schema)

- Table lines `davu 21800 21801`, `davn <piece> <variant>` (21802..21805), `davt <piece> <variant>` (21806, 21807)
  from the package's `auto_diagonal_avenues[0].oneway`; the T crossing ids 21810..21816 come in the crossing templates.
- Writer roles: at a free end (no bend, crossing, junction, merge) the last middle cell's 20500 becomes the U-turn
  variant and the band cells past it their no-lane variants; a junction cell whose road arrives from one side only
  becomes its T variant. Same rule as the twin `avdiag_build.roles`.
- A diagonal that bends into or crosses a straight avenue converts only if `avl_band_ok` says that straight band
  converts (before writing); the AVL_POST_DAV hook re-runs the pass with `avl_dir` and puts a band back to the stock
  tiler if AVL left its straight avenue two-way. Stats line: `left two-way for a straight avenue=`.
- 14 `avlj` lines in the package's `avenue_lines` (bend and XS / TS crossing faces).

## 3. In game (lab, PIDs 41696 then 22120)

| case | log / grid |
|---|---|
| two joined diagonal drags (44,14)-(54,24), (45,14)-(55,24) | `dav: edit: band axis 0, 10 row(s) ... 32 written`; top end 21803 (cap, no lanes) / 20501 (U-turn) / 20505; bottom end 21801 (20500 U-turn) / 21802, caps 21804 |
| road across the band at z 17 | 20510.2 / 20512.0 / 20510.0 |
| road from the east ending on the band at z 20 | 21806.0 (one-sided T) |
| save | `save: 32 variant tile(s) written as base`; the save file holds stock ids only in the band area (29, 35, 43, 1999, 18004, 11225: 0 variant ids) |
| reload | `load: all 32 variant tiles restored`; DAV load pass 0 written |
| two straight drags (54,24)-(54,32), (55,24)-(55,32) from the band's bottom end | `dav: ... bends 0/2`; `avl: edit: band along z from (54,24) rows 0..7 -> one-way (ends: join or edge / U-turn)`: 21700.1 (runs N, beside the diagonal's north-going side) / 21700.3, U-turn 21701 |

| rebuilt with `dav_band_ok` (PIDs 23024, 54544, 11896): the bend drawn on the reloaded city, saved, reloaded | save `48 variant tile(s) written as base` (30 DAV + 18 AVL); the file holds 0 variant ids (43 / 35 at the joint, 11204.1 / 11204.3 and 11203 on the straight band); reload `load: all 48 variant tiles restored`, DAV load pass `bends 0/2 ... 0 written`, `avl: load: band along z from (54,24) rows 0..7 -> one-way (ends: join or edge / U-turn)` |

Screenshots: `MAIN\verify\avdiag\owner_shots\avdiag_game_band.png`, `avdiag_game_bend_junctions.png`.

Trap: `nr_drive.py save` returns before the game writes the city file; stopping the game right after the DLL's
`save:` line left the previous file. Wait for the file's time stamp to change.

## 4. For bvlanes / DBV: `dav_band_ok`

    static int dav_band_ok(int x, int z);   /* sc3netmod_dav.c, included before sc3netmod_dbv.c: call it directly */

Would the diagonal avenue band through cell (x, z) convert to DAV's one-way pieces, on the current road grid with the
full DAV rule (junctions, crossings, merges, ends, bends, and their straight avenues through `avl_band_ok`)? A dry pass
over the cell's surroundings (+-40 cells, the whole map if the band reaches that box): nothing written, nothing
reverted, no state kept. 1 = converts; 0 = it would be left to the stock tiler, or DAV is off, or (x, z) is not a cell
of a diagonal band (a lone diagonal, a cell DBV claims). A DBV-claimed cell is never a band cell (DAV ends the band
there, bend kind 3), so ask with a cell of the avenue part past DBV's claim, e.g. its first full row. Valid at any
time (it reads the grid through g_rb_mgr); during DBV's own pass, cells DBV has not written yet read as they are.
Not exercised in game yet (no DBV caller).

Not done yet: animated cars and routing in a populated city (the lab has no traffic), crossings with another avenue
in game, a game without the mod (checked offline on the save file only), hwave transition and the DBV edge in game.

## 5. Owner rule: no left turn of radius <= 80 lane units (2026-10-19, avjunc's Seoul bisect)

Measured on the planned lane lines (dense, before integer rounding) of every scene, before the fix:

| lanes | smallest left radius |
|---|---|
| end U-turn inner lane (20501..20504, 21800, 21801): a semicircle on the median line | 55 |
| median-opening left turns at a road crossing (20512, 20513) | 70 |
| diagonal x straight avenue lefts (20556, 20557, 20560, 20561, 20569..20572) | 70 |
| diagonal ending on a diagonal (TX0 / TX1) | 77..78 |
| hwave diagonal transition 21604..21609 | none (no left turn) |

Fix (`avdiag_build.py` LEFT_MIN = 88, UTURN_RHO):
- end U-turn: the outer lane stays a semicircle of 124 (the end cell allows no wider one); the inner lane is a reverse
  curve (a right arc away from the median, then a left arc of 84.2 round the end, then a right arc back), the widest
  whose apex stays inside the outer lane (14 units apart) and inside the cell. 21701's inner lane is not copied.
- turns: a left turn is first tried as a circular fillet of radius 92 at the lanes' crossing point, else as cubic
  curves whose left stretches stay above 88; a left that fits neither is not built. Only one does not fit: at an avenue
  ending on a road, the arriving carriageway's sharp (135 degree) left. Its inner lane then shares the right turn of
  the outer lane (and on the other axis the leaving inner lane is fed from the road like the outer one), so no lane
  is a dead end. Turns per kind otherwise unchanged (road crossing 8, diagonal crossings 8, T's 4).
- smallest planned left radius now: 84.1 (the U-turn inner lane); every turn >= 88.
- curve points: no two closer than 6 lane units (integer rounding on close points made the heading jitter).

Not measured on the stored curves with a trustworthy metric: a 3-point or least-squares radius over the integer
curve points reads stock 11203 curve 1024 (radius 175) as 54..144 depending on the window, so it cannot rank 84 vs
80. avcore's geometric check (avlanes.py) is to be run on the package once merged.

Update, same day: the rule was RETRACTED (avjunc's hang was its own Frida probe). LEFT_MIN is 0 again: the sharp
135-degree left at an avenue ending on a road is built again (stem 4 turns, no shared right); 92-unit fillets are still
tried first and the wider U-turn (inner reverse curve 84, outer 124) stays. Rebuilt after avcore's hwlanes extra_for
(3559939): new flat curves carry sort id 0 like stock. 19,304 joins 0 problems, 394 new shapes 23800..25293,
validate OK; `avlanes tightleft` flags lefts up to 88 (informational now).

## 6. Lab run on 9737e13 (avcore 49ddf65 merged), final lane rebuild

Packages avenue_lanes + diagonal_avenue + highway_avenue, DLL from 9737e13 + one line in `sc3netmod_hwave.c`
(PIDs 18824, 70272, 48280; no Frida).

| case | result |
|---|---|
| diagonal highway (122,4)-(130,12) into a diagonal avenue (130,13)-(138,21) + (131,13)-(139,21) | first DLL: `hwave: ... refused (the avenue's end cell beside the cap is taken)`: the avenue's end now holds DAV's no-lane cap 21803, not stock 18004. Fix: `hwavd_dav_road` also accepts DAV's role pieces (`dav_is_role`, marked line). Then: 21604..21609 built, `stats: hwave ... diagonal built=1`, the avenue's far end a U-turn (21801 / 21802 / 21804) |
| diagonal x diagonal (96,80)-(112,96) + (97,80)-(113,96), (113,80)-(97,96) + (114,80)-(98,96) | `dav: edit: band axis 0 ... 1 crossing(s), 52 written` and the same for axis 1: crossing 20540..20548, U-turn ends on all four arms (20501 / 20503 / 21800 / 21801, no-lane caps 21802..21804) |
| save | `save: 125 variant tile(s) written as base`; the file holds 0 variant ids |
| reload | `load: all 125 variant tiles restored`; DAV load passes 0 written (the transition band as bend kind 3) |

Screenshots: `MAIN\verify\avdiag\owner_shots\avdiag_game_crossing_xx.png`, `avdiag_game_hwave_diag.png`.

## 7. Owner call: median opening where a road meets one carriageway (estimate)

Today: the T row has one junction cell (the near carriageway's, 21806 / 21807): right in, right out.
An opening = the road goes on across the median and stops at the far carriageway's outer curb:
- near cell: the existing crossing piece 20510 / 20511 (the road goes on into the median cell);
- median cell: the existing 20512 / 20513 (road across the median, no trees);
- far cell: NEW, the far half (35) with its outer curb kept and road 29 only up to that curb. 2 pieces (row road,
  column road), 20 frames each (as every DAV piece), 40 frames.
Art: `diagave.junction_frame` cannot draw the far cell (it lays road 29 across the whole cell and keeps a curb only
along the road's side). `diagave_paint` (the world-scene painter the merges and crossings use) can, with one addition:
clip the road element at the far curb line. No hand drawing. Rule: two junction descriptors and the T row's median
and far cells marked as junction cells in `sc3netmod_dav.c` and its twin; the lane builder then gives 4 movements
(the lefts through the opening) with no new lane code. Estimate: half a day including a lab check.

## 8. Median opening (owner: "Build the median opening", 2026-10-19)

A road that meets one carriageway now goes on across the median and stops at the far carriageway's outer curb.
Right in / right out (21806 / 21807, `davt`) is retired: the ids and their specs are removed, the C `davt` path stays
for a package without `davo` lines.

- Pieces: far cell 20506 (row road, far curb E at state 0) and 20507 (column road, far curb N), art on 35's frames by
  `diagave_paint.Opening` (35 half kept, outer curb kept, road 29 clipped at the curb), 20 frames each. Role variants
  `davo 20510 21817`, `20511 21818` (near cell), `20512 21819`, `20513 21820` (median cell), lanes only differ.
- Rule (`sc3netmod_dav.c` and the twin `diagave.py`, `OPENING`): a row arm on one side marks the row's 3 band cells
  as junction cells, the far one with its outer curb (axis-space E / W, mirrored on axis 1); a column arm from N or S
  marks 3 cells, the far one with curb S / N. Refused (the band is left to the stock tiler): a one-sided road in the
  avenue's first or last row, a column opening that reaches the last two rows. The median cell's state turns by 2 when
  the far end is not on its own local +x (21819) / +z (21820). Any `davo` line turns the rule on.
- Offline: 19,512 joins, 0 problems; turns at an opening 4 (right in, right out, both lefts through the median);
  418 new shapes 23800..25317, 0 conflicts. `netpack validate` diagonal_avenue: 0 errors. Warnings are of the same
  kinds the committed package already had (each base piece's two-way road matrix against one-way lanes:
  22 road-matrix warnings in the committed package, 27 now, the 5 new ones on 21817..21820; "no rule
  RESULT places" 8 before, 10 now: the DLL places the role variants, no tiler rule does, by design). Correction to section 1:
  the "0 warnings" line there was wrong, the committed package had warnings of these kinds too.
- In game (lab, PIDs 61276 then 8124, no Frida): band (44,14)-(54,24) + (45,14)-(55,24), roads from the E at z 20,
  from the W at z 22, from the N at x 48:

  | opening | near | median | far |
  |---|---|---|---|
  | row z 20 (from E) | (52,20) 21817.0 | (51,20) 21819.2 | (50,20) 20506.2 |
  | row z 22 (from W) | (52,22) 21817.2 | (53,22) 21819.0 | (54,22) 20506.0 |
  | column x 48 (from N) | (48,16) 21818.0 | (48,17) 21820.0 | (48,18) 20507.2 |

  `dav: edit: ... 9 junction cell(s), 6 arm cell(s)`. All 47 avenue cells (piece and state) equal the twin's
  `roles()` run on the game's own road grid; the 3 differing cells are the side roads' stock dead-end stubs 11225.
  Save `32 variant tile(s) written as base`, the file holds 0 variant ids; reload `load: all 32 variant tiles
  restored`, DAV load pass 0 written, the cell box (40,6)-(62,28) identical before save and after reload.

Screenshot: `MAIN\verify\avdiag\owner_shots\avdiag_game_opening.png`. Not done: cars through the opening (no traffic
in the lab).

## 9. Seoul car run (2026-10-20, orchestrator cleared it; build b483236)

Tree `Simcity_stock_avdiag`, packages avenue_lanes + diagonal_avenue + highway_avenue, `SC3NETMOD_LANEDENSITY=all`.
Safe order: load, P + 2 by keys, nothing attached until the sim ran.

Spot picked offline with the twin on Seoul's own roads (`seoul_pick.py` / `seoul_one.py` in the session scratchpad):
axis-1 band from drags (22,220)-(11,231) + (23,220)-(12,231) in the city's south-west corner, crossing row road
z 222 and met by street x 15 (a dead end at (15,225) before), 6 houses demolished at (16..18, 223..225).

| step | result |
|---|---|
| first game (PID 72108) | DEADLOCK before any DAV piece existed: sim running 40 s, then `rb_lab.py cam` (Frida) with a zoom change returned `Error: system error` on the zoom job; routing evaluations froze at 1,884,114 and stayed there 8 min, CPU time flat, window not responding. The camera tool on a running game, not the pieces. Killed (own process) |
| second game (PID 51664) | view moved by a minimap click and zoomed with the minimap + button (no scripted zoom change); `rb_lab.py cam` only at the zoom already in use. Responsive throughout, about 19 min, 10.8 M routing evaluations |
| band | `dav: edit: band axis 1, 11 row(s) from (23,220), 35 cell(s), 6 junction cell(s), 6 arm cell(s) ... 38 written`; crossing at z 222 20511.3 / 20513.1 / 20511.1; opening from street x 15: near (15,226) 21817.3, median (15,227) 21819.1, far (15,228) 20506.1 (first axis-1 opening in game); U-turn ends 20503 (top), 21800 (bottom). All 35 avenue cells equal the twin on the live grid |
| car tracks, zoom 3, box (8,214)-(28,234), 180 s (`hwcars_tracks.py`) | 75 tracks: 63 road cars (height 18176 = 71 x 256), 10 subway, 2 class-0 tracks at height 23296 flying straight over empty cells (not road traffic). 36 road cars on DAV pieces |
| direction | road cars on the carriageway pieces, per cell visit (>= 1/4 cell along the band): NE-going 40 visits / 14 cars, all on the NW side of the median line (x + z < 243); SW-going 38 / 14, all on the SE side; 0 the other way. Seen on screen, SW-going cars move right with the SE side below them: right-hand |
| save | `save: 35 variant tile(s) written as base`; city kept as `inst_avdiag\seoul_avdiag_band.sc3` for the fix |
| failed trips (third game, PID 32892: the saved band city, `load: all 35 variant tiles restored`, P + 3 by keys, then `hwtraffic_probe.py` attached, no --start) | per sim month, game counters: month 1 (partial, not counted) 67 / 3,677 = 1.82%; month 2 72 / 3,681 = 1.96%; month 3 74 / 3,715 = 1.99%; month 4 85 / 3,985 = 2.13%; months 2..4 231 / 11,381 = 2.03% against the 1.95% baseline (avjunc's Seoul months 1.59..2.12%). Data `verify/avdiag/data/seoul_traffic.json` |

Against the orchestrator's pass bar: cars keep their half's direction through the band (0 of 78 visits wrong) and
cars use the crossing and the opening; failed trips 2.03% for months 2..4, inside the baseline's monthly spread. The
stalls below are not caught by the trip counter: a car removed after a stall is not a failed route.

**Defects found (not fixed):**

1. **Cars stall at the crossing and in the opening, and the game removes them after about 40 s.** Road-car stalls of 5 s
   or more: 7 at the row-222 crossing (head car of each queue, at the border of the median cell (20,222) 20513.1, from
   both sides: (21.17, 222.68) westbound, (19.83, 222.31) eastbound), 3 in the opening's median cell 21819.1 (two at
   the same point (15.23, 227.09)). Cause in the specs: in 26 of the 100 DAV lane specs a border point is both the end
   of an exiting lane and the start of an entering lane, always at the road's lane positions 80 / 175. A 45-degree band
   lane crosses the perpendicular road lane exactly on the cell border, so the compiled node graph merges the two lanes
   there, and the compiled lanes stop matching the turn matrix. The pieces: 20510..20513 (crossing, committed since
   8e44a0e), 20541 / 20543..20545 / 20547 / 20555 / 20556 / 20561 / 20562 / 20566 / 20569 / 20572 / 20575 / 20589,
   21814 / 21815, and the opening's 20506 / 20507 / 21817..21820. `netpack validate` reports exactly these as
   "matrix allows ... but no car lane drives it" / "a car lane drives ... which the matrix does not allow". My section 8
   reading of those warnings as harmless was wrong. My offline join check never tested for this.
2. **The U-turn ends do not turn cars.** Bottom end 21800.3: 4 road cars arrived from the SW-going side. 3 stopped at
   about (12.35, 230.68) for about 40 s and were removed, 1 was removed after 6 s; none came out NE. Top end 20503.3: 1
   arrived, stalled 40 s, removed. The 2 tracks that start in 21800 heading NE are cars that appeared there. These
   specs have no merged border node, so the cause is different and is [UNCERTAIN]. avcore's 21701 U-turn turned 17
   cars in its Seoul run.

Proposed fix: (a) in `avdiag_build.py`, keep lane crossings off cell borders (move the cut, or nudge one lane's border
point consistently on both sides), plus a check that no border point is both an entry and an exit, which should
clear the matrix warnings; (b) U-turn: a lab city with traffic plus car tracks at zoom 4, compared with avcore's
21701 lane graph. Then repeat this run on `seoul_avdiag_band.sc3`. Data (gitignored, 4 MB):
`verify/avdiag/data/seoul_tracks.json`, `seoul_grid.json`, `seoul_tracks_an.json`.
