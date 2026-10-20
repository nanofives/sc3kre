# avdiag: the diagonal avenue family on one-way halves (plan, milestone 1, 2026-10-19)

Stream `avdiag` of the avenue lane rework (`re/sessions/CHILD_PROTOCOL_2026-10-19_avlanes.md`, program plan
`verify/avlanes/PLAN.md`). Owns: DAV pieces 20500..20594 (middle, outer, end combos, junctions, merges, crossings),
`sc3netmod_dav.c` + `diagave.py`, the hwave diagonal transition 21604..21609. Ids 21800..21849 + DAV free
20506..20509 / 20525..20529 / 20535..20539, lane curve shapes 23800..23899.

Owner sheets: `MAIN\verify\avdiag\owner_shots\avdiag_plan.png` (band, ends, merge, bend, road junctions, hwave
transition) and `avdiag_plan_crossings.png` (diagonal x straight avenue, diagonal x diagonal, both T's). Each pair shows
today's lanes (drawn from the package specs and the stock records, pieces placed by the offline twin `diagave.py`) and
the plan. Tool: `re/tools/netmod/avdiag.py` (`scene KIND [--proposed]`, `sheet OUT [--kinds ...] [--hwave]`).

## 1. The direction rule on a diagonal (right-hand, as the highways and avcore)

A diagonal avenue is two diagonal drags joined: staircase A (d 0, 1 of each band row) and B (d 1, 2); the middle cell
holds A's and B's halves of stock 35 (`diagave.py` docstring). Each lone diagonal carries one lane each way, on the lines
z - x = 80 and 175 of the state-0 frame (`lanekit describe 35`: (0,80) -> (175,255) key 2304, (80,255) -> (0,175) key
2560), so across the avenue the order is R B | R B, as on stock 11204.

Rule: a carriageway drives with the median on its LEFT. With left(t) = (-tz, tx) and r the offset from the median
line: r > 0 drives -t, r < 0 drives +t (the program's rule, `verify/avlanes/PLAN.md` 2).

- Axis 0 (band along +x +z): A (x- / z+ side) drives -x -z, B drives +x +z.
- Axis 1 (band along -x +z): A (x+ side in real coordinates) drives -x +z, B drives +x -z.
- Check against hwave's frame (`hwave_build.py`: the highway's exit carriageway at high p = x - z drives +x +z): B is
  the high-p side and drives +x +z. Same.

**Measured (avdiag.py, 7 scenes, 686 lanes along the band):** the curb-side lane of every stock diagonal already runs
the right-hand way and the median-side lane runs the other way: outer lanes keep 349 / 349, inner lanes reverse
337 / 337. So the rework of a diagonal carriageway is: reverse the median-side lane, keep the curb-side lane. The lane
END POINTS do not move (the slots 80 / 175 on every border stay), so neighbouring pieces still meet by position (the
street sim's arrival lookup, `NET_LANES.md` 2.3).

Curves: in the state-0 frame the 35 halves of a converted band use 4 lane shapes: stock 2304 and 2560 (the curb-side
lanes and the outer cells' halves) and their two reverses, which do not exist in the stock curve set (`Paths.find`: (175,255) -> (0,80) and
(0,175) -> (80,255) give no key; the forward ones give 1024 / 2304 / 50176 / 50688 and 768 / 2560 / 50432 / 50944) and become new shapes in 23800..23899. English-UK: see section 7, open with avcore.

## 2. Inventory and what changes per piece

Art changes nowhere except where noted (markings already show the lanes). Lanes = new `*.lanes.json` specs with
`"mirror_uk": false`, `"connects": {"road": "auto"}` (low half = the one-way lanes, high = transpose).

| piece(s) | today | plan |
|---|---|---|
| 20500 middle (35 + 35, median) | 4 lanes, two-way per carriageway | each carriageway one-way, 2 lanes (inner lane reversed) |
| 20505 outer cell (copy_base of 35) | stock 35's two-way lanes | own lanes spec: 35 one-way (the outer cell's median side is its CORNER side, so the reversed lane is the (80,255)-(0,175) one, unlike the middle cell) |
| 20501..20504 (middle + start / end cap, end rows only) | lanes of the parts, each road U-turns in its own cap | lanes of the two-lane U-turn (section 3) |
| stock 18004 / 1999 caps and 35 in end rows (written by DAV) | stock lone-road caps | U-turn end variants, art from the stock piece, saved as the stock piece: NEW ids from 21800 |
| 20510..20519 junctions (road 29 + avenue halves) | parts' lanes; turns only where two parts share a node | one-way through lanes + every turn through the median opening, inside the junction cells (arms stay stock 29) |
| 20520..20534 merges | the ending road caps (U-turn in its own carriageway) | taper lanes: the ending carriageway's 2 lanes join the single road's lane of their direction, the single road's other lane widens to 2 |
| 20540..20594 crossings (XX0, XX1, XSX, XSZ, TSX, TSZ, TX0, TX1) | straight through only, two-way | one-way through lanes on both avenues + turns: 8 at an X, 4 at a T, inside the crossing cells |
| 21604..21609 hwave diagonal transition | the exit's inner lane and the avenue's leaving lanes cross the median (shapes 23420..23435) | no crossing: each highway lane drops onto the carriageway lane of its side and rank (exit outer p 0.560 -> 0.686, inner 0.240 -> 0.314, mirrored for the entry) |
| bends into straight 11204 | diagonal and straight cells meet on one cell line | no new pieces. Measured geometry: a diagonal lane at offset r meets the joint line r * sqrt 2 from the median, which is exactly the 11204 lane (0.221 * 1.414 = 0.3125 = 80 / 256, 0.483 * 1.414 = 0.684 = 175 / 256), so lanes join outer to outer, inner to inner, and the rule gives both the same direction |

Pre-existing fault found while drawing (offline, `avdiag.py`): in the junctions where the avenue ENDS on a road
(20515, 20518, both stem cases) the avenue's lanes run on through the road and exit its far border into a cell with no
road (4 lane ends per stem). The rework replaces those lanes with the turns.

## 3. Ends

Measured: 24 distinct end shapes over the 48 drag footprints (`diagave.footprints`, both axes, both phases, both
offsets, drags of equal length or one step apart). Under rotation (which keeps right-hand traffic) they fall into:

- **Even end** (both drags end in the same row, or one phase apart): two-lane U-turn around the median nose, outer lane
  to outer lane, inner to inner, placed where today's caps are. Cells: the end row's cap cells and the middle cell with
  a cap.
- **Tail** (one drag one step longer; 10 of the 24 shapes have road cells two or more rows past the end row that are not
  merge pieces): the shorter carriageway ends; the longer
  one goes on as a short two-way stub ending in its stock cap, joined with the merge lanes (the arriving side's 2 lanes
  join the stub's lane of that direction, the stub's other lane widens to 2). Art unchanged.
- **Merge** (one carriageway ends and the other goes on as a single road, existing 20520..20534): as the tail, over
  the existing three-row taper.
- **Ends handled elsewhere:** on a road (junction pieces), on another avenue (crossings), into a straight avenue
  (bend), at a highway (hwave transition), into a diagonal boulevard (DBV, bvlanes' pieces).

New ids: the U-turn and tail cells that today hold stock caps / stock 35 or a piece also used mid-band (20505) need
their own lane sets, so their own ids (art from the piece they replace). The count per role is made at build time from
the 24 shapes; the estimate is 10 to 20 ids in 21800..21829.

## 4. Junctions and crossings: the turn rule

Every movement through the median opening, right-hand: right turn from the outer lane into the outer lane, left turn
from the inner lane into the inner lane. Road 29 stays two-way (one lane each way). The drawing counts per kind (all
kinds, `avdiag.py scene`): road crossing 8, road from one side 4, avenue ending on a road 4, diagonal x straight
avenue 8, diagonal x diagonal 8, either T 4.

Rules for the build:
- turning lanes stay inside the junction / crossing cells (lane ends on their borders at the slots), so the 29 arms
  and the band cells around keep their pieces; where a turn cannot fit in the cells, a reserve id (21830..21849);
- lane points on one border never closer than the 72-unit buckets of the arrival lookup unless they coincide (hwave's
  rule, `hwave_build.py`);
- the turn matrix (props 310) follows the lanes ("auto"). LANEDENSITY's default mode honours variants' matrices, so
  every DAV piece being a variant makes the one-way rule real for trips with no code change.

## 5. The rule block (sc3netmod_dav.c) and the edge with avcore

Agreed base: avcore's `re/analysis/AVENUE_LANES.md` (child/avcore d5dddf1, merged into child/avdiag). A straight band
converts in `sc3netmod_avl.c` (AVL, runs LAST in every road pass and the load pass) when both ends are accepted: its
U-turn, the map edge, or two pieces declared `avlj <piece> <NESW>`.

**Diagonal bands do not go through AVL.** DAV owns them whole: its rule (`diagave.bands` / `wanted`, `sc3netmod_dav.c`)
already converts a diagonal band all or nothing, and after this rework every DAV piece's lanes are one-way, so a DAV band
that converts IS one-way. Its halves are declared by geometry (section 1: the side whose offset from the median is
positive drives -t), not per cell. The only coupling with AVL is where a STRAIGHT band meets a diagonal one:

5.1 **The straight band ends on DAV pieces: `avlj` letters.** At a bend the straight band's end row holds a DAV
   20500 + 20505 pair; at an XS / TS crossing it holds the crossing's first pieces on each half. `avdiag.py joins`
   derives each piece's letters from the planned one-way lanes (every through lane that crosses a side) and runs a port
   of `avl_end` on every scene where a straight avenue meets the diagonal (bend along z, bend along x, XSX, XSZ, TSX,
   TSZ, each at 4 turns): **40 straight-band ends, 40 accepted, 0 refused, letters consistent across every use**, with
   14 declarations (a side crossed both ways is written `.`, never a face):

       avlj 20500 IOIO   avlj 20505 ..OI   avlj 20555 O..I   avlj 20558 .I.O   avlj 20559 .I.O
       avlj 20562 .IO.   avlj 20566 O..I   avlj 20567 .I.O   avlj 20574 .I.O   avlj 20575 .IO.
       avlj 20577 OO.I   avlj 20582 .I.O   avlj 20583 O.II   avlj 20588 I.O.

   The lane nodes on those faces are the 35 / 11204 slots, which section 2 of AVENUE_LANES.md requires (a diagonal lane
   at offset r meets a cell line at r * sqrt 2 from the median: 0.221 * 1.414 = 0.3125 = 80 / 256 and 0.483 * 1.414 =
   0.684 = 175 / 256, inner to inner, outer to outer). To be checked with `avlanes.py check` on the built specs.
   AVL_MAXJ is 64 in `sc3netmod_avl.c` for ALL packages; this stream needs 14.

5.2 **The diagonal band needs the straight band one-way: a post-step.** A DAV band that bends into or crosses a straight
   avenue is one-way, so it can only stay when AVL converted every straight band it touches (else the joint mixes
   one-way and two-way lanes and cars vanish there). AVL decides after DAV in the same pass, so DAV checks afterwards:

       road pass:  ... DAV ... AVL  ->  dav_post(box)  ->  if dav_post reverted a band: AVL again on its box  (repeat, max 4)

   `dav_post` reads `avl_dir(x, z)` (valid right after AVL's run: AVL writes its band map during the walk) for the
   straight cells beside each DAV bend and inside each XS / TS crossing; if any is -1 the DAV band goes back to the
   stock tiler (rect retile: the stock two-way ladder, the owner's "cannot convert whole stays stock two-way" applied to
   the diagonal). Reverting can leave a straight band AVL already converted ending on stock pieces, so AVL runs again on
   that box and reverts it; that can in turn refuse another DAV band at its other end, hence the loop (each round
   reverts at least one band, so it ends). Same in the load pass. The result is all or nothing per connected group of
   straight and diagonal bands.
   Until avjunc's pieces are declared most straight avenues end on stock junctions and stay two-way, so a diagonal that
   bends into one of them shows the stock ladder meanwhile.

5.3 **DAV leaves AVL's cells alone:** where DAV's crossing templates write plain stock 11204 on the straight avenue,
   DAV skips a cell that holds AVL's straight variant (21700) or that `avl_claimed` reports (AVL converts the stock
   cells it writes in the same pass anyway).

5.4 **Other block changes:** the end cells get the U-turn / tail variants instead of the stock caps; save ids: the new
   variants save as their base (18004 / 1999 / 35), both-road cells as 43 as today, so a game without the mod loads
   today's stock ladder. A diagonal x diagonal crossing already converts only when both avenues do. hwave: the
   transition joins a converted (so one-way) DAV only; nothing else changes in `sc3netmod_hwave.c`.

Asked of avcore (through the orchestrator): (a) confirm `avl_dir` is valid for cells of the current pass right after
`avl_run` returns, and that calling `avl_run` again in the same pass on a sub-box is safe; (b) the order line in
`sc3netmod_rbt.c` (`dav_post` after `avl_run`, then `avl_run` again when it reverted): avdiag adds it as marked lines
unless avcore prefers to own it; (c) AVL_MAXJ 64 shared by every package (14 here).

## 6. The edge with bvlanes (diagonal boulevard narrowing into a diagonal avenue)

DAV ends at a DBV with bend kind 3 (virtual rows, nothing written past the end, `diagave.bend_kind`). Proposed edge: the
cell line where DBV's narrowing pieces (20972..20992) meet DAV's steady-state rows. On that line DAV presents its
steady-state lanes: per carriageway 2 lanes at the 35 slots (80 / 175 on the shared border), directions by section 1.
bvlanes' narrowing pieces end with the same points and directions and do the 3 -> 2 merge inside their own cells.

## 7. Open, needs another stream

| to | what |
|---|---|
| avcore | section 5 (a) to (c). English-UK curves: SETTLED by AVENUE_LANES.md 2 (no `path` keys, curves found by end points per language; where a language lacks one, a new shape whose English geometry is the reverse of the lane) |
| orchestrator | shape budget: with that rule a new lane geometry needs its own shape AND, unless stock has it, its reverse (English-UK's copy). For the 35 halves that is 2 new shapes (the reverses of 2304 and 2560). Estimate for the whole stream 150 to 250 shapes against the 100 granted (23800..23899); 24000..24999 now belongs to bvlanes, so a reserve elsewhere if free |
| bvlanes | the edge in section 6 |

## 8. Build order (milestone 2, after avcore's base is merged)

1. `avdiag.py build`: lanes from corridor curves cut per cell (as `hwlanes.build_cells`), curves de-duplicated by
   geometry, specs for every piece above; offline continuity check over all footprints and crossing kinds (every lane
   end on a border meets a lane of the neighbour at the same point, same direction; every lane has a way on; no lane
   into a cell without road).
2. DAV block: end variants, save ids, component rule.
3. hwave diagonal transition lanes without the swap.
4. One in-game check (a Seoul copy with a diagonal avenue drawn near traffic): cars keep their lane, routing probes,
   save + reload, a game without the mod.
