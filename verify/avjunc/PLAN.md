# avjunc: junctions on one-way avenues (plan, milestone 1, 2026-10-19)

Stream `avjunc` of the avenue lane rework (`re/sessions/CHILD_PROTOCOL_2026-10-19_avlanes.md`, plan
`verify/avlanes/PLAN.md`). Owns: road x avenue, road T on one side, T on both halves, avenue x avenue, avenue T,
the AVX pieces' lanes (20800..20804, 20810, 20811), the stock junction shapes AVX refuses today. Ids 21750..21799 +
AVX 20805..20849, lane curve shapes 23700..23799. Owner sheet: `MAIN\verify\avjunc\owner_shots\avjunc_plan.png`
(drawn by `re/tools/netmod/avjunc.py plan`, from the same lane code the build will use).

Direction rule used throughout (avlanes PLAN section 2, avcore's base): an 11204 half in state s runs toward world side
(s - 1) mod 4 in N E S W terms: band along x, the z- row (state 2) runs +x, the z+ row (state 0) runs -x; band along
z, the x- column (state 1) runs -z, the x+ column (state 3) runs +z. Right-hand traffic in the ENGLISH lane frame
(NET_LANES.md 8: road 29's lane at z 80 runs +x; +x -> +z is counter-clockwise on screen).

## 1. What stock and AVX do today (offline, 15 shipped cities)

Tools: `re/tools/netmod/avjunc_segments.py` (every run of non-straight pairs between straight 11204 | 11204 pairs, and
whether AVX's twin boxes it), `avjunc_scan.py` (the rule below, piece counts), `avjunc_nosebug.py`. Data
`verify/avjunc/data/`.

- **3,046 segments** on straight avenue bands (a segment = consecutive positions along a band where the pair across is
  not two straight 11204 halves). **AVX's rule boxes 1,208** (Berlin 210 of 587, London 216 of 672, Seoul 128 of
  214). The rest: avcore's pieces (rail 69 | 69 alone 69, slopes, highway crossings), ends and corners, and junction
  shapes AVX refuses.
- Why AVX refuses junction shapes (`avx.check` on examples of the uncovered segments, 2 per shape): **"arm has road
  beside it"** (a second junction within 2 cells: staggered T's, a road T next to a crossing; 61 plain road x avenue
  crossings `43 | 43` are uncovered, both examples checked had a road beside an arm), the avenue
  ending on a road (`39|39` at the band end, 148 + 31 `43|39` + 22 `39|43` ...), runs of 3..4 positions
  (`39|11204 39|39 11204|39` 33 + its mirror 33: two T's offset by one cell, the stock tiler joining the halves in
  between). Rare stock pieces at the junction: 11211 / 11213 / 11214 / 14030 / 11208 / 35 (diagonal road) / 15139 in 26
  segments.
- **AVX bug found (offline twin; the C block has the same rule, `sc3netmod_avx.c avx_check`):** the median-nose piece
  (base 11204) is written on the first cell of every avenue arm whatever that cell holds, as long as its id is < 20000.
  In the shipped cities a load pass would put it over **72 rail crossings (69), 4 highway crossings (11258) and 44
  slope cells (31 / 32 / 11201 / 11202)** next to a box (`avjunc_nosebug.py`; plus 704 T 39 arm cells, which is
  intended). It saves as 11204, so the saved city would lose those crossings. Not seen in game (no AVX game ran on
  those cities). The rework writes noses only on 11204 cells.

## 2. The model: box cells with one mode per edge

A junction becomes one paved box across both halves (the AVX box, extended to the shapes above). Every box cell is a
small crossroads; each of its four edges carries one mode:

| mode | lanes on that edge (slots 80 / 175, NET_LANES.md 2.4) | where |
|---|---|---|
| N | two lanes in | a one-way half running into the box, or the box cell upstream on the same one-way row / column |
| O | two lanes out | the same, leaving |
| T | one in + one out, the stock road slots | a road arm, a two-way (unconverted) avenue half, an edge across the median (the opening) |
| C | none | closed: curb |

Lanes inside a cell (`avjunc.py cell_lanes`): every in-lane joins the exits on the other three edges. Straight 2 -> 2
lane by lane, 2 -> 1 merge, 1 -> 2 the lane feeds both; right turn from the right-hand lane to the right-hand lane;
left turn from the left-hand lane to the left-hand lane; an in-lane with no exit takes the nearest one keeping lane
order (a dual turn where the avenue ends on a road). No U-turn inside a cell; a U-turn is left + left through the
opening. Right-hand side of heading h = side h - 1 (dir order x- z- x+ z+), so a T edge's in-lane is the stock road
lane (x- edge: z 80 runs +x).

Turn matrix (props 310): low half = the (entry, exit) pairs that carry a lane, high half its transpose (the stock rule,
NET_LANES.md 1.2). LANEDENSITY (default mode) honours it because every box cell is a variant (`g_base != 0`).

Modes come from two flows per box cell: ROW = the one-way half the cell lies on (none if two-way), COLUMN = the crossing
avenue's one-way half (none if a road crosses or that avenue is two-way). Internal edge along the row -> row flow,
along the column -> column flow, none -> T; outside edge -> the neighbour (one-way half N / O, road or two-way half
T, nothing C).

What it gives (sheet, panels):

| shape | box | how every turn works |
|---|---|---|
| road x avenue | 1 x 2 (one cell per half) | right turns in the near cell; left turns and U-turns cross the opening (T edge between the halves) |
| road T on one side | 1 x 2, far cell closed outside | the same, the far side has a curb |
| T on both halves / two T's offset by one cell | one 1 x 2 box per road, a short median (one-cell island with two noses) between | each box as above |
| two roads at adjacent positions, runs of 3..4 | one box over the run, every cross edge an opening | as above, per cell |
| avenue x avenue (both one-way) | 2 x 2, both flows set: the four cells form a one-way ring (in, around, out) | straight through, right in the first cell, left after one more cell, U-turn after three |
| avenue T (both one-way) | 2 x 2, ring with the far side closed | as above |
| avenue ends on a road | the road cells at the avenue's end (1 x 2 across the road), column flow = the avenue's halves | the arriving half turns right or left (dual turn), the road feeds the leaving half |
| one-way avenue x two-way avenue (mixed) | 2 x 2, row flow only, two-way columns | as road x avenue on each row |

Curves: the model needs **11 lane geometries modulo rotation** (`avjunc.py curves`: from the x- edge at 80 or 175 to
the z- / x+ / z+ edge at 80 or 175). Each is one new VPathAtt shape (4 rotations each), **shapes 23700..23710**,
Bezier, straight lanes 2 points like the stock straights, turns 9 points. No stock curve key is used, see 6.2.

## 3. The rule (rework of the AVX block, `sc3netmod_avx.c` + `avx.py` twin)

1. avcore decides which bands convert (all-or-nothing). For that it asks this block, per segment on the band, whether
   it boxes it (6.1).
2. On a converted band, per segment: positions with an outside arm (a road or a crossing avenue leaving either half)
   form runs; each run of 1..4 positions is one box. Positions between two runs or between a run and the straight
   halves (stock links `39 | 39`, plain 11204) become one-way half cells with the median nose toward each box next to
   them (nose E / W / both). avcore's own pieces (69, 11258, 15098, slopes) stay avcore's: no nose over them.
3. Box modes from the flows (section 2); a crossing avenue's column flow is its own band's direction if that band
   converted, else none (mixed box).
4. Cells are written with the game's piece writer as today; box cells save as their base (43, or 11204 for a far half
   with a closed outside edge, as AVX), noses as 11204, so a game without the mod loads the stock junction.
5. **Two-way bands keep today's AVX** (its 5 kinds, its pieces, unchanged lanes), with the nose fix.
6. Refused -> the junction stays stock and the whole band stays two-way (avcore's rule): rare stock pieces in the
   segment (26 segments in 15 cities), runs over 4 positions (10), a box cell pattern with no declared piece, another
   block's piece in a cell.

## 4. Pieces and ids (counts from `avjunc_scan.py`, all 15 cities, `data/scan_pieces.txt`)

3,063 boxes, 9,058 box cells. Distinct box cells (outline x modes, modulo rotation):

| case | distinct pieces | note |
|---|---|---|
| every band one-way | 30 | the 6 most common cover 73% of cells, 22 cover 98% |
| every band two-way | 12 | 5 = today's AVX 20800..20804; 7 new outlines (only in boxes AVX refuses) |
| mixed (one band one-way, the crossing one two-way) | 26 | |
| union | 52 | |

Allocation: one-way box cells and the three one-way noses (nose E, nose W, both) in AVX 20805..20849; mixed box cells in
21750..21799; today's AVX pieces keep 20800..20804 / 20810 / 20811 for two-way bands. 52 + 3 = 55 ids of the 95
granted; patterns below ~10 cells in 15 cities can be dropped (refused) if art time says so.

Art: box outlines (I another box cell, A an arm, C closed): the 5 AVX outlines + **7 new**: CCII (two closed edges
meeting: a curb corner), AIII, CIII (inner cells of longer runs), AAIC / AACI (a mirror pair: avenue ending on a road),
ACCI, AICC. The AVX painter (43's asphalt folded, crosswalk on A, curb on C, corner block) per edge; the curb corner is
new. Pieces with the same outline share the art (copied per id folder). Box cells have no lane lines (as AVX); noses
keep `lanelines.py` dashes (now between the two lanes of a half, avcore's marking check).

## 5. Lanes per piece

`avjunc.py` generates each piece's lanekit spec from its mode string: car nodes at the stock slots, one edge per lane
with its new curve key, `"mirror_uk": false` (owner: right-hand in English-UK too), `"connects"` = the matrix above,
pedestrians = 43's crosswalk walks on A edges (two-way walks, no direction). Speed 64,000 (stock road). Noses: avcore's
one-way 11204 lanes with the nose art.

## 6. Asks of avcore (base API) and of the orchestrator

6.1 **Band decision hook.** avcore's band rule needs "does avjunc box this segment" before it decides a band, and
avjunc needs "which way does this half run" after. Proposal: `int avj_segment_ok(RbBuf *b, int axis, int x, int z,
int len)` exported by the AVX file (pure, no writes), and `int avl_half_dir(int x, int z)` from avcore (travel side
0..3, -1 = not on a converted band). Pass order: avl decides bands -> avl writes its cells -> AVX writes boxes + noses
(AVX cells are claimed: avl leaves box and nose ids alone, `avx_own()` already exists for that).

6.2 **English-UK and curves.** With `"mirror_uk": false` lanekit writes the ENGLISH lanes, with the same curve keys,
into English-UK, but English-UK's VPathAtt.IXF holds every curve reversed under the same key (NET_LANES.md 2.2), and
`hwlanes.curve_set` writes new shapes into English-UK reversed too. So under English-UK a right-hand lane on a stock key
or on a new shape follows its curve backwards. Needed in the shared tooling (avcore's call, it hits the one-way straight
first): new shapes written the same way round into every language when the spec says `"mirror_uk": false`, and no
stock curve key in one-way lanes. avjunc's 11 shapes follow whatever avcore picks.

6.3 **Avenue corners have no owner.** An avenue turning 90 degrees (stock: an outer 11203, two straight halves, an inner
11203; `11203|11204 11204|11203` 60 + its mirror 30 band ends in 15 cities, more with a road meeting the outer corner:
`39|11204 11204|11203` 35, `11203|11204 11204|39` 31, ...). One-way: the outer cell is a two-lane LEFT bend (the same
piece as avcore's end U-turn half), the inner cell a two-lane RIGHT bend. Without a one-way form every band with a
corner stays two-way. Suggestion: avcore takes pure corners (its bend family), avjunc takes corners with a road at the
outer cell (a box cell). Orchestrator's call.

6.4 Diagonal joins (`11203` staircases and 35 diagonal roads meeting a straight avenue, many of the `[end]` segments):
avdiag's. avjunc refuses them.

## 7. Build (milestone 2) and check

1. `avjunc.py build PACK`: specs, curves, art (AVX painter + new outlines) into `examples/avenue_junctions`.
2. Block: AVX file reworked (segments, runs, flows, modes -> piece + state lookup by canonical pattern, nose fix),
   avx.py twin in step; `avx.py check --tiler` + new shapes; offline: every box cell's lanes line up with its
   neighbours (positions and directions on shared edges), every in-lane has an exit.
3. One game (Seoul copy, light): boxes written on converted bands, cars keep their lanes through a road x avenue and an
   avenue x avenue (hwcars tools), router probes for failed trips / wrong-way fails, save + reload, a game without the
   mod loads stock junctions. Sheet `avjunc_sheet.png`, `verify/avjunc/RESULTS.md`.
