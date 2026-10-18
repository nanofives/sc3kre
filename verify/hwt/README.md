# hwt plan: a highway T that connects (milestone 1, 2026-10-18)

Picture: `MAIN\verify\hwt\owner_shots\hwt_plan.png` (drawn by `re/tools/netmod/hwt_plan.py`).

## 1. Stock aftermath, measured in game

Instance `Simcity_stock_hwt\re\harness\inst_hwt`, city `t1.sc3` (copy of `lab.sc3`), stock DLLs (no sc3netmod.dll in
the instance), pid 69128. Drags with `hw_lab.py hway ... --alt 82`, cells read with `hw_lab.py cells`, turn matrices
with `nr_drive.py conn`.

Through highway along x, drag (46,28) -> (70,28): rows **z 27 and 28**, x 45..70 (the drag row plus its -z neighbour).
z 27 = `15051.2`, z 28 = `15051.0`, caps `15053/15054`. `15051` prop 310 = `0x40100`: low half bit 8 = enter x+, leave x-
(NET_LANES.md 1.1), so state 0 runs -x and state 2 runs +x. **z 27 (the -z row) runs +x, z 28 runs -x.** Stems along z:
the lower-x column is `73.2` (runs -z), the higher-x column `73.0` (runs +z). Right-hand traffic both ways.

| drag | stock result |
|---|---|
| stem (50,16) -> (50,26), ends one cell short of the side | x 49..50, z 15..26, caps `11235.0 / 11237.0` at z 26 beside the through highway. No connection. |
| stem (64,16) -> (64,28), ends on the far carriageway | same: the stem stops at z 26 with its caps |
| stem (55,18) -> (55,27), ends on the near carriageway | same: caps at z 26 |
| stem (67,28) -> (67,38), starts on the far carriageway, goes +z away from it | x 66..67, z 29..38, caps `11237.2 / 11235.2` at z 29 beside the side. No connection. |
| stem (109,88) -> (109,79), starts on the far (+z) carriageway, goes -z across the near one | x 108..109, z 78..86, cap at z 86 beside the side. No connection. |
| stem (101,87) -> (101,98), starts on the near (-z) carriageway, goes +z across the far one (clean area) | **a stock 4x4 X**: centre (100..101, 87..88) `15113.2 15114.0 / 15114.2 15113.0`, x arms `15107.0 15108.0` (x 99), `15108.2 15107.2` (x 102), z arms `15150.2 15153.2` (z 86) and `15153.0 15150.0` (z 89), stem 73 z 90..97, caps z 98. **The -z arm is a 1-cell stub with nothing beyond it.** No ramps. |
| stem (53,27) -> (53,38), same gesture, 1 cell from another stem (x 54..55) | **`15149` blocks**: (52..55, 27), (52..53, 28), (52, 26), (54, 26); (53, 26) = `15051.2`. The X did not fit. |
| stem (59,18) -> (59,31), crosses both carriageways | a full 4x4 X (hwx's shape) |

So stock reaches a T two ways: **gesture 1 = the end cap beside the side** (drag stops at the side, or starts on the far
carriageway) and **gesture 2 = the stub X** (drag starts on the near carriageway). Gesture 2 next to other highway
leaves 15149. Owner sheet shots: `inst_hwt\s04.png` (gesture 1 and the 15149 case), `s05.png` (stub X).

## 2. Layout: a trumpet with the stem bridging over

Why a trumpet: in a T with right-hand traffic the two left-turn flows (stem -> far carriageway, far carriageway ->
stem) cross each other once whatever the geometry, unless one of them is a loop. A directional T needs three levels
(one left ramp over, one under). In SC3 the two carriageways touch (no median), so a ramp that crosses the near
carriageway has no room to come back down before the far one: it has to cross both and join the far carriageway
from outside. The trumpet does exactly that with two levels (the through deck, and the stem one level above it, as
the stock X), and every ramp leaves and joins on the right.

State-0 frame (stem from -z; SB column x 0, NB column x 1; EB row z 0 runs +x, WB row z 1 runs -x):
- NB -> EB: NB exits right at (1,-2), one-lane ramp (2,-2) curve, (2,-1), joins EB at (2,0).
- EB -> SB: EB exits right at (-1,0), ramp (-1,-1), (-1,-2) curve, joins SB at (0,-2).
- NB -> WB: the stem rises at (1,-1), bridges over EB and WB at (1,0), (1,1), comes down at (1,2), loops clockwise
  (1,3) -> (2,3) -> (2,2) and joins WB from the north at (2,1), then passes under the bridge.
- WB -> SB: WB exits right at (3,1), outer ramp (3,2), (3,3), (3,4) curve, (2,4), (1,4), (0,4) curve, (0,3), rises at
  (0,2), bridges over WB and EB at (0,1), (0,0), comes down at (0,-1) into SB.
- Through EB and WB stay level and straight.

Order on every carriageway is exit before entry (no weaving): EB exits at x -1, joins at x 2; WB exits at x 3, the loop
joins at x 2; NB exits at z -2 then rises; SB comes down then takes EB's ramp at z -2.

Footprint: box x -1..3, z -2..4 (5 x 7). New cells: 4 on the stem side ((-1,-1), (-1,-2), (2,-1), (2,-2)), 12 on the
far side (x 0..3, z 2..4). Rewritten highway cells: 8 through-highway cells, 4 stem cells (the caps and the cell behind).

Pieces (13 ids, 21200..21212; a 180-degree pair shares an id): 21200 through exit, 21201 / 21202 through under the
bridge (two lane pairings), 21203 through entry, 21204 / 21205 stem level change, 21206 / 21207 far-side level change
(down to the loop / up to the bridge), 21208 stem entry, 21209 stem exit, 21210 one-lane ramp straight, 21211
one-lane curve right turn, 21212 one-lane curve left turn. Ids and states per cell are on the picture.

## 3. Rule

Triggers (both gestures give the same layout, in 4 rotations):
1. a stem cap pair `11235 / 11237` whose cap row touches the side of a straight 2-cell through highway
   (`15051` along x or `73` along z), with the stem straight for 3+ cells behind the caps.
2. the stub X: stock X centre `15113 / 15114` whose arm on one side (`15150 / 15153` or `15107 / 15108`) has no highway
   beyond it, and whose other three arms continue as straight highway. Same test as hwx (agreed 2026-10-18): look at
   the two cells just outside the 4x4 on each arm. hwt takes the X when exactly one arm has no highway there, and hwx
   takes it when all four arms do, so no X goes to both.

Why both: which one the player gets depends on which carriageway cell the drag starts on, which cannot be told apart at
zoom 1-2. Reacting to both means a T drawn either way connects.

Refused (stock result stays): a footprint cell that is not free (building, zone, other network; trees are cleared) or
not plain straight highway; slope cells; diagonals (not this wave); an X whose four arms all continue (hwx); a stem
shorter than 3 cells; another junction or T inside the footprint; 15149 blocks.

Fallback when the far side is blocked but the stem side is free: a right-in / right-out T (NB -> EB and EB -> SB only,
4 new cells), the stem keeps a cap. `[UNCERTAIN]` whether the owner wants that or plain stock there.

## 4. Rule twin (offline, `re/tools/netmod/hwt_layout.py`)

Orchestrator 2026-10-18: keep the loop size a parameter (2x2 default, 3x3 also builds) and plan for the right-in /
right-out fallback (the orchestrator's recommendation to the owner). `hwt_layout.py` is the single source the plan
sheets, and later the package builder and the C block tables, come from:

- `layout(loop, rio)`: every cell's id, state and role in the stem frame. Loop L: the loop ring takes columns 1..L and
  rows 2..L+1, and the outer ramp column L+1 and row L+2. That gives a box of x -1..L+1, z -2..L+2, with 16 new cells
  for L 2 and 22 for L 3. In rio the stem keeps its stock caps at z -1, and its z -2 cells become 21213 / 21214 (stem
  entry / exit with the through arm closed), with 4 new cells. Ids are now 21200..21214.
- `CONNECTS`: the turn matrix of every piece at state 0 (enter side -> leave side). `reach()` routes every movement
  through the layout. The selftest checks that NB reaches {EB, WB}, EB reaches {EB, SB} and WB reaches {WB, SB} for
  loops 2 and 3, and that rio gives NB {EB}, EB {EB, SB}, WB {WB}.
- `find(grid)`: the rule (section 3), in every rotation (world = A + R^r(cell), R(x, z) = (-z, x), state + r).
  The selftest runs it on the stock grids measured in section 1:
  - gesture 1 from -z gives anchor (49,27) r 0, and from +z gives (67,28) r 2.
  - gesture 2 on the stub X gives (101,88) r 2.
  - each of the 4 rotations of a synthetic cap scene is found once.
  - a full X, a blocked stem side, a stub X with its far side blocked, and a stem shorter than 3 cells are all
    refused. A cap T with its far side blocked falls back to rio.
- `match CITY.sc3`: the same rule on a save's surface layer, its buildings and its flat cells (tiler.City.load). It ran
  without error on the unedited lab city and found no T there, which is correct for that city. Zones and flora are
  not read: whether a cell is "free" is decided by hwcore's claim rule in the DLL, and the twin only approximates it.

Sheets: `owner_shots/hwt_plan.png` (loop 2 with the stock shots) and `owner_shots/hwt_layouts.png` (loop 2, loop 3,
rio).

## 5. Default loop = 3x3 (orchestrator, 2026-10-18)

hwx's cloverleaf loop has radius 1.25 cells (deck 0.44 wide, a 3x3 block; hwx needs R >= 1.25 for its S tapers next to
the stock 4x4 arms, `Simcity_wt_hwx/verify/hwx/README.md` section 2). So that the X and the T match, the T's default loop
is now 3x3 (`--loop 3`), and 2x2 is the switch (`--loop 2`). Loop 3: box x -1..4, z -2..5 (6 x 8), 22 new cells. The
two eye cells inside the ring, (2,2) and (2,3), are not claimed: a building there does not block the T. The ring's
centreline drawn on the plan passes through cell centres, about 1 cell from the eye. The painted radius (1.25, as hwx)
is set at the mockup by hwpaint.

Ramp geometry constants come from hwx (`hwx.py`: deck half width W 0.22, outer lane 0.57 from the median, loop
centreline R 1.25 tangent 0.25 outside the carriageway edge, S tapers 0.5..0.6 cell, 0.19 cell of ground between ramp
decks). `hwt_layout.GEOM` imports them from `hwx.py` when it is importable, which it will be on main after the merge.
Until then it falls back to the values hwx sent on 2026-10-18.

## 6. Painted geometry (milestone 2, `re/tools/netmod/hwt_paint.py`, hwpaint copied verbatim from hwcore)

The scene is built from hwpaint's API in the stem frame (cell units; through highway median z 1, stem centre x 1):
- **Through highway.** It is stock: level at H (31.75) and straight. Ramps leave and join it at its outer edges, after
  S tapers of 0.65 that run 0.25 outside the carriageway edge, as hwx does.
- **Stem.** Both carriageways end at z -2 (Z_SPLIT, a cell edge) and continue as one-lane ramp decks, 0.44 wide
  (2 W from hwx).
- **The two straight ramps.** NB -> loop runs at x 1.315 and WB -> SB at x 0.685, 0.63 apart (deck 0.44 + gap 0.19).
  They climb on walls from z -1.8 to z -0.15, up to H_TOP = H + (H_HIGH - H_LOW) = 63.25. That is the stock X's
  separation of 31.5 between its two decks, so the clearance over the through deck is the stock X's. They cross both
  carriageways on slab bridges from z -0.15 to z 2.15.
- **Loop.** NB's ramp loops clockwise, R 1.25 (hwx) about C = (2.565, 3.5). It is tangent to z = 2.25, which is 0.25
  outside WB's edge. It descends from H_TOP to H along the loop on pillars and joins WB through an S taper at x ~2.
- **Outer ramp.** WB -> SB leaves WB at x ~6 (taper out, then a right turn of radius 0.75 to the north). It runs
  concentric with the loop at R + 0.63 = 1.88 and comes down its west leg, which is exactly the SB bridge ramp at
  x 0.685. It climbs from H to H_TOP along the way, on pillars.
- **Near side.** NB -> EB and EB -> SB are quarter turns of radius 1.0, at H, on walls.

**Turn matrices come from the geometry.** `hwt_paint.py routes` walks every lane centreline through the cells and
takes (enter side, leave side) per cell. Routing them reaches NB -> {EB, WB}, EB -> {EB, SB} and WB -> {WB, SB}.
`hwt_paint.py export` writes the footprint table (cell, decks, connects, new or rewritten highway). These replace the
hand layout of `hwt_layout.py` for the build.

**Revised footprint** (loop R 1.25): box x -2..6, z -2..5 (9 x 8). It has 38 cells with their own art: 23 new (the
T claims them) and 15 highway cells rewritten. The near ramps take x -2..3, the outer ramp's exit takes x 5..6. That
is larger than the 6 x 8 hand estimate, because hwx's tapers and spacing need room. 38 ids fit in 21200..21259.
The 2x2-loop switch and the rio fallback each need their own art, though. Loop R 1.25 + rio fits in the 60 ids; a
second loop size does not without more ids.

## 7. Lanes and joins (second build, 2026-10-18)

hwcore's `hwlanes.py` cuts lanes per cell from the decks and links neighbouring cells by border position. So every
ramp now starts and ends ON a carriageway lane at a cell border:
- the stem's carriageways end at z -3 (Z_SPLIT). The inner lanes (x 0.761 / 1.239) go on as the bridge ramps, the
  outer lanes (x 0.431 / 1.569) as the right-turn ramps, all with S tapers.
- the through highway's outer lane (0.431 from its outer parapet) feeds the exits and takes the entries at the
  borders x -2, 4 (EB) and x 7, 1 (WB).

The NB ramp is one lane deck for hwlanes. It is still painted as two decks, because a lane cut that ends inside a
cell is dropped. Parapets open automatically (`hwt_paint.auto_gaps`) wherever two decks driven the same way touch at
the same height. The stem's two ramps at the median are driven opposite ways, so they keep their parapets.

New footprint: x -2..7, z -4..5. Full T 50 cells (30 claimed, 20 rewritten highway), fallback 18 (2 of its own).
Ids 21200..21253, curve shapes 22800..22883.
