# hwx: straight highway x straight highway (cloverleaf, clean flyover fallback)

Task `hwx` of the highway program (protocol `re/sessions/CHILD_PROTOCOL_2026-10-18_highways.md`, ids 21120..21199).
Milestone 1 (plan), 2026-10-18. Geometry and tables: `re/tools/netmod/hwx.py` (`cells`, `plan`). Owner picture:
`MAIN\verify\hwx\owner_shots\hwx_plan.png` (not committed).

## 1. What stock leaves

Offline tiler (`tiler.Tiler.retile(4, ...)` on the lab city, two straight drags across each other, both drag
orders) gives the 12-cell plus shape of `STOCK.md`, cell for cell the same as Berlin's core at 213..216 x 118..121.
Frame of this note: the highway along z holds x = -1 (73.2, traffic -z) and x = 0 (73.0, traffic +z), the highway
along x holds z = -1 (15051.2, traffic +x) and z = 0 (15051.0, traffic -x) (lanes: `lanekit describe`).

| cell | piece | cell | piece | cell | piece |
|---|---|---|---|---|---|
| (-2,-1) | 15107.0 | (-1,-1) | 15113.2 | (0,-1) | 15114.0 |
| (1,-1) | 15108.2 | (-2,0) | 15108.0 | (-1,0) | 15114.2 |
| (0,0) | 15113.0 | (1,0) | 15107.2 | (-1,-2) | 15150.2 |
| (0,-2) | 15153.2 | (-1,1) | 15153.0 | (0,1) | 15150.0 |

The four corners of the 4x4 stay empty. Lane heights (lanekit): the z highway climbs 1024 -> 1536 in its arm cells
(15150 / 15153) and 1536 -> 1792 in the centre; the x highway drops 1024 -> 512 (15107 / 15108) and 512 -> 256.
So the z highway always goes over and the x highway under, whatever the drag order. The stock lanes are straight
(61 / 145 through the centre), but the art pinches: the upper deck jogs inward and the lower one narrows into a
small tunnel (`stock_x` offline render). Highway trips at the stock X only go straight on.

Berlin's 6x6 (212..217 x 117..122) adds corner pieces 15121..15128 that connect each arm to the next one by a
right turn, with one-lane ramp lanes at height 1024 (15121 splits a lane off to x- at 80, 15122 merges one in from
x+ at 80, 15123..15128 are one-lane quarter curves). No left turns there. How Berlin's ring was made is still open
(`STOCK.md`). The rule refuses an X that has that ring.

## 2. The cloverleaf

Right turns leave a carriageway toward its outer side. Left turns would cross the opposite carriageway, so they
take loops. Per quadrant: one outer ramp (right turn) and one 270-degree loop (left turn). Quadrant Q0 = (+x, -z):
- loop `+x -> +z`: leaves the +x carriageway after the X (cell (2,-1)), turns 270 degrees, joins the +z carriageway
  before the X (cell (0,-3));
- outer ramp `+z -> +x`: leaves the +z carriageway at (0,-6), right turn, goes around the outside of the loop (left
  turn), right turn, joins the +x carriageway at (5,-1).

Q1, Q2, Q3 are Q0 turned 90, 180 and 270 degrees about the X centre, cell (i, j) -> (-j-1, i) per step. Each step
maps every carriageway onto the next one with its direction, so the four quadrants are the same pieces in
successive states. On each carriageway, in driving order: outer exit, loop entry, X, loop exit, outer entry (the
usual cloverleaf weave between a loop entry and the next loop exit, across the X).

All 12 movements connect: 4 through (the X), 4 right (outer ramps), 4 left (loops). No U-turns.

Heights: every ramp is one lane on a deck at 1024 on walls, the same level as the highways. No ramp crosses another
ramp or a carriageway, so nothing new bridges. The only bridge is the X core (z over x, as stock).

Loop size is a parameter (`hwx.py --loop-r R`, default 1.25); every table below is computed from the geometry.
Minimum 1.25: the loop is tangent to the lines 0.25 outside both carriageways, so its ends sit at x = z = 1.25 + R,
and each S taper needs about 0.5 cell outside the stock 4x4 arm cells (it leaves +x at x >= 2, joins +z at z <= -3).
A 2x2-block loop (R 0.75, ends at 2.0) would put the taper on the arm cells where the decks change height, so it
cannot be built at the X. The T's 3x3 option (hwt) is the size that matches the X default.

Geometry (cell units, Q0, R 1.25; revised at the mockup to hwpaint's measured ramp width): one-lane ramp deck 0.62
wide (`hwpaint.RAMP_W`). Loop centreline radius 1.25 around (2.5, -2.5), tangent to the lines 0.25 outside both
carriageways, so its deck (0.94..1.56 from the centre) fills the 3x3 block x 1..3, z -4..-2 (overlapping its
neighbours by 0.06) around a hole about 2 cells across (cell (2,-3) stays free ground). The outer ramp's middle arc
has radius 2.06 about the same centre (0.19 of ground between the two decks). Its two right-turn arcs have radius
0.75 (1.0 would push the joins out to a 14 x 14 box). S tapers of about 0.5 to 0.6 cell join each ramp to the
carriageway's outer lane (0.57 from the median). Ramps are slab decks (10.25 thick, as hwcore's fit of stock 15127)
on pillars, parapet on the right of travel (the inner side of the loop, as 15127).

Cells per quadrant (computed from the centrelines by `hwx.py cells`, turn = entering side -> leaving side):

| cell | id | what | turns |
|---|---|---|---|
| (2,-1) | 21150 (x hwy) | loop diverge, base 15051.2 | through x- -> x+, loop x- -> z- |
| (2,-2) | 21120 | loop | z+ -> x+ |
| (3,-2) | 21121 | loop | x- -> z- |
| (3,-3) | 21122 | loop | z+ -> z- |
| (3,-4) | 21123 | loop + outer | loop z+ -> x-, outer z- -> x+ |
| (2,-4) | 21124 | loop | x+ -> x- |
| (1,-4) | 21125 | loop | x+ -> z+ |
| (1,-3) | 21126 | loop | z- -> x- |
| (0,-3) | 21156 (z hwy) | loop merge, base 73.0 | through z- -> z+, loop x+ -> z+ |
| (0,-6) | 21157 (z hwy) | outer diverge, base 73.0 | through z- -> z+, outer z- -> x+ |
| (1,-6) | 21127 | outer | x- -> z+ |
| (1,-5) | 21128 | outer | z- -> x+ |
| (2,-5) | 21129 | outer | x- -> x+ |
| (3,-5) | 21130 | outer | x- -> z+ |
| (4,-4) | 21131 | outer | x- -> z+ |
| (4,-3) | 21132 | outer | z- -> z+ |
| (4,-2) | 21133 | outer | z- -> x+ |
| (5,-2) | 21134 | outer | x- -> z+ |
| (5,-1) | 21151 (x hwy) | outer merge, base 15051.2 | through x- -> x+, outer z- -> x+ |
| (1,-2) | 21135 | deck edge only (the loop's taper ends), no lanes | |
| (4,-5) | 21136 | deck edge only (the outer ramp's arc), no lanes | |
| (2,-3) | none | enclosed ground (the loop's hole): left to the player, not claimed | |

The one shared cell (3,-4) carries the two ramps on different entry sides, so its turn matrix keeps them apart.

Pieces:
- 21120..21149: ramp cells (written into empty cells), states 0..3 = the four quadrants (nominal: the engine's
  state turn direction against `rot_cell` is checked at build time). 17 used at loop radius 1.25 (21120..21136),
  more at radius 1.75. Numbered in driving order (loop, then outer ramp, then deck-edge-only cells) by `hwx.py`.
- 21150..21157: 8 mainline cells (loop diverge, outer merge, loop merge, outer diverge), each in an x-highway kind
  (base 15051) and a z-highway kind (base 73), states 0 / 2. Each id is used in two opposite quadrants.
- 21160..21165: clean X core, one per stock core piece (15113, 15114, 15107, 15108, 15150, 15153), same states and
  lanes as stock, art redrawn straight. Used by the cloverleaf and by the fallback.
- 21170..21189 reserved for the X on a slope, 21190..21199 spare.
- Lane curve shape numbers (hwlanes, one new curve per lane cut): 22500..22799 (protocol range for hwx).
- Sharing a ramp id across the four quadrants by state: netart slot r is slot 0 turned 90 degrees CCW on screen,
  (u, v) -> (v, 1 - u), and `rot_cell` (x, z) -> (-z, x) is the same turn in u = -x, v = z, so state q = quadrant q.
  HWY_BASE.md places shape pieces at state 0 with one id per cell; that would take 96 ids here (range 80), so hwx
  keeps state sharing and checks the lanes of states 1..3 at build time.

Per X: 68 ramp cells + 16 mainline cells + 12 core cells; the 4 loop holes stay the player's (no road access, so
a zone there does not develop). Footprint 12 x 12 (cells -6..5
on both axes). The 8 cells in each outer corner of the box, outside the outer ramp, stay the player's.

Program rule (orchestrator 2026-10-18): these constants are the shared highway-program geometry (W 0.31, ramp
deck 0.62, loop R 1.25, outer ramp radius 2.06, turn arcs 0.75, gap 0.19); hwt imports them from `hwx.py`. Keep the
names stable. Every ramp join opens the carriageway's outer parapet (hwpaint `Deck.gaps`, computed in `hwx.py`).

## 3. The rule

A net-4 pass on RBT's hooks (`sc3netmod_hwx.c` on hwcore's `sc3netmod_hwy.c` dispatch). A NEW cloverleaf is placed
only in an edit pass (`rb_pass`) that creates or touches the X. The load pass (`rb_load_pass`) only restores
cloverleafs and clean flyovers that the save already holds (by their saved ids); it never claims land:
- **trigger**: the stock 12-cell X (the table in section 1) on flat dry ground, with all four arms continuing: both
  cells just outside the 4x4 on every arm ((2,-1)/(2,0), (-3,-1)/(-3,0), (-1,2)/(0,2), (-1,-3)/(0,-3)) hold highway.
  A stock X with a 1-cell stub arm and nothing beyond it (a drag that starts on the near carriageway of a
  through highway, measured by hwt, `Simcity_wt_hwt/verify/hwt/PLAN.md` 1) is a T: refused here, hwt owns it;
- **cloverleaf** when all of these hold: the 12 x 12 box is inside the map, flat and dry; the arms are plain straight
  highway (15051 / 73 pairs in the stock states) on cells 2..5 and -6..-3 of every arm; all 68 ramp cells pass the claim
  rule (empty or trees, no building, zone or other network); no other highway piece,
  on-ramp or interchange in the box (another X closer than 12 cells, a T, a diagonal);
- **else the clean flyover**: the 12 core cells become 21160..21165;
- **refused, left stock**: an X with a stub arm (hwt's T), an X on a slope (15149; slope task later), an X with Berlin's ring (15115..15128 in its
  6x6), any X pattern that touches a diagonal (stream hwdx / hwdd).
- **revert** (as built, `sc3netmod_hwx.c`): a bulldozed ramp cell is rebuilt on the next pass (as hwt does: a pass
  reads only the retile box + 8, so it may see part of the cloverleaf, and an all-or-nothing ramp rule could not be
  decided per pass). When an arm cell stops being plain highway, the ramps are removed, the junction cells go back to
  15051 / 73 and the core stays the clean flyover. When the X itself goes (a core cell or a cell past the 4x4), the
  core goes back to the stock pieces and the stock tiler takes over; a core cell is never more than 8 cells from any
  cell of the 12x12, so that pass sees the whole cloverleaf.

## 4. Owner decisions (orchestrator defaults 2026-10-18, until the owner answers)

1. Loop radius 1.25 (12 x 12), kept as a parameter (`--loop-r`; 1.75 = 14 x 14 drawn as an option). hwt's trumpet
   loop uses the same 3x3 size.
2. A new cloverleaf only when the X is built or edited (an edit pass that creates or touches the X). At a city load,
   only restore what exists, never take land.
3. All four quadrants or the clean flyover, no partial cloverleaf.
4. Loop holes and the corners beside the X are left to the player, no piece and no claim.

## 5. Open (other streams)

- hwcore (2026-10-18): every painted piece needs `"ground_under": true` in its art block (bases 73 / 15051 / 15099 have
  draw flags 0, so the engine draws no terrain under the piece and transparent pixels show stale back-buffer). This
  matters here: loops and ramps are slabs on pillars over open ground. Required but not sufficient: some views still
  show patches depending on frame geometry; hwcore is tracing the frame rule (will land in HWY_BASE.md). Check every
  view of the in-game shots for it.

- hwcore: base piece for the empty-cell ramp variants, their save ids, and one-lane ramp lanes / matrices.
