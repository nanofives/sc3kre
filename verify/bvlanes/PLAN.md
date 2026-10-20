# bvlanes: plan for 3-wide boulevards with 3 lanes each way (2026-10-19, milestone 1)

Stream `bvlanes` of the avenue lane rework (`re/sessions/CHILD_PROTOCOL_2026-10-19_avlanes.md`, program plan
`verify/avlanes/PLAN.md` section 9). Owns every boulevard piece: BV 20700..20768, BVX 20900..20911, DBV 20950..21063.
Owner calls that bind it: right-hand traffic everywhere (English-UK too, no mirrored lane set), an avenue the mod cannot
convert whole stays stock two-way, boulevards become 3 lanes each way.

Sheets: `MAIN\verify\bvlanes\owner_shots\bvlanes_plan.png` (straight, caps, single-road junctions, narrowing, tapers,
diagonal) and `bvlanes_plan_boxes.png` (junction boxes). Both are drawn by `re/tools/netmod/bvlanes.py sheet` from the
same lane geometry the build will cut, and every grey cell carries the piece and state the BV / BVX rule writes there
today (`boulevard.runs()`), so the sheet shows the real placements, not a mock-up.

## 1. Rule of direction and lane slots

- Right-hand traffic, the median on the driver's left (as avcore's half rule and the highways). Straight boulevard
  along x, rows z 0 / 1 / 2: row 0's side runs +x, row 2's side runs -x. Along z the same turned one state: the x+ side
  runs +z. This follows from the geometry, so every placement that is a rotation of the canonical one is right. All BV,
  BVX and DBV placements are rotations (no mirrored placement exists in the rules).
- Lane slots do not move (lane units, 255 per cell, across the band): +x at 80, 175 (row 0) and 255 + 14 (row 1);
  -x at 255 + 241 (row 1), 510 + 80, 510 + 175 (row 2). Each side = the outer cell's 2 lanes + the middle cell's lane
  beside it; the grass median between the two middle-cell lanes. The painted lane lines already match (white dashes
  between all three lanes of a side, `boulevard_paint.py`), so **no art changes** for the straight, caps, tapers,
  narrowings, junction columns or boxes (the median already ends in a nose at every junction: the opening exists).
- Diagonal (DBV): the same cross-section across p = x - z (`diagbv.py`). Strip A (p 0..1) runs -q, strip C (p 2..3)
  runs +q (q = x + z) on axis 0, the median in strip B. A lane at offset f in a cell is a 45 degree chord between the
  stock slots: f = 80 / 175 give the stock 35 node positions, the middle-strip lanes give the 14 / 241 chords. So the
  diagonal band meets the straight boulevard at a bend and the diagonal avenue at its narrowing on the same slots.

## 2. Pieces, new lanes, turn matrices

Turn matrices = the turns the new lanes drive (`connects: auto`), measured by `bvlanes.py check` on the rule's own
placements (state-0 frame of each piece, `x-=>z+` = entering by x-, leaving by z+).

| piece | today | new lanes | matrix (low half) |
|---|---|---|---|
| 20700 outer | +x at 80, -x at 175 (two-way) | both lanes one way, as avcore's one-way 11204 half | `x+=>x-` |
| 20701 / 20702 / 20703 middle | +x at 241, -x at 14 | both flip: 14 runs +x (with row 0), 241 runs -x | `x-=>x+ x+=>x-` (one each way, no sideways exit) |
| 20704 / 20705 / 20706 cap (rows 0 / 1 / 2) | none (road 29 fallback) | 3-lane U-turn, outer to outer, middle to middle, inner to inner; 20705 also carries 2 routing branches (below) | 20704 `x-=>z+`; 20705 `x-=>x- x-=>z+ z-=>x- z-=>z+`; 20706 `z-=>x-` |
| 20710 junction, entry row (crossing) | 43's | straight 3, right from the 2 outer lanes into the arm, the road's right turn in, the far side's left turns passing | `x-=>z- x-=>x+ x-=>z+ z-=>x+ z-=>z+ z+=>z-` |
| **20707** junction, entry row of a T (NEW) | (was 20710) | 20710 without the far road arm's lanes | `x-=>z- x-=>x+ z-=>x+ z-=>z+ z+=>z-` |
| 20711 junction, middle row (crossing) | 43's | 3 + 3 straight, every left turn through the opening | `x-=>x+ x-=>z+ z-=>x- z-=>z+ x+=>x- x+=>z- z+=>z- z+=>x+` |
| **20708** junction, middle row of a T (NEW) | (was 20711) | as 20711 for one road arm; placed state 0 for a T from z-, state 2 for a T from z+ (checked: same lanes turned) | `x-=>z- x-=>x+ z-=>x- x+=>x- x+=>z- z+=>x-` |
| 20712 junction, far row of a T | 39's | straight 3, left turns from the near side's inner lanes into the arm | `x+=>x- x+=>z-` |
| 20720..20748 tapers to a single road (row 1 / 0 / 2) | none | 3 -> 1: per side the outer lane closes onto the middle by half way, the middle onto the inner by the end, the inner moves to the road's lane (the side coming out of the road splits the same way) | per cell, 1..4 turns; 6 corner cells carry no lane (see 4) |
| 20750..20768 narrowing to an avenue (rows 0, 1 / 1, 2) | none | 3 -> 2: the side going into the avenue merges its middle-cell lane; the side coming out slides one row with its carriageway (linear, as the paint) and opens its third lane from its inner one | per cell, 1..3 turns |
| BVX boxes 20900..20905 | 43's / T 39's copied, shared by edge pattern | every movement of the box (section 3) | per cell |
| BVX noses 20910 / 20911 | copy of stock 11204 (two-way) | one-way, as avcore's half | `x+=>x-` |
| DBV 20950..21063 | copy_base (two-way 35 / 43), 20951 own spec | band: 3 one-way chords per side and cell; ends, bends and junctions by the same rules as the straight pieces | per cell |

Routing (LANEDENSITY honours variants, so all of these): outer cells one-way, the middle row two-way with one lane each
way, no sideways exit anywhere along a stretch, so a trip keeps its row until a junction, a cap or an end.

Caps and the router: the router never re-enters a cell during a trip (visited grid, LANE_DENSITY.md 1), so the inner
U-turn (middle cell, in by x- and out by x-) cannot be used by trips: they would re-enter the middle-row cell they came
from. Cars still drive it (cars follow lanes, not trips, CAR_TRIPS.md 2). So 20705 gets two branch lanes: the inner
lane can leave by the far row (into its middle lane), and the near row's middle lane can come out on the middle row's
-x lane. Without them a trip on the middle row heading into a cap would backtrack the whole stretch.

## 3. Junctions (single road column and BVX boxes): one movement rule

Every junction (BV junction column, BVX box) uses one rule, written once (`bvlanes.box_lanes`):
- straight on every lane, to the opposite arm's lane of the same rank;
- right turns from the outer lane(s), left turns from the inner lane(s) through the median opening: 2 each from a
  3-lane boulevard side, 1 from an avenue side or a road; targets outer-first (right) / inner-first (left); where the
  target has fewer lanes the extra one merges at the box edge;
- the crossing road turns right into the near side's outer lane, left into the far side's inner lane;
- no U-turns inside a junction (the caps carry them).

**Box pieces need splitting.** Today 20900..20905 are chosen by edge pattern (N E S W of I / A / C), so one id serves
the corners of an avenue crossing, of a boulevard crossing and of both T's. With one-way lanes those corners drive
different lanes (`bvlanes.py check`): 20900 is placed with 9 different lane sets, 20903 with 8, 20901 / 20902 with 3,
20904 / 20905 with 2. The box cells therefore get ids by (box kind, cell): **21 more ids** (same art as the pattern
piece they replace). The BVX rule chooses by box kind and position instead of pattern (offline twin `bvx.py`, block
`sc3netmod_bvx.c`); the box kinds stay those of today (boulevard x avenue, avenue ends on it, it ends on an avenue,
boulevard x boulevard, boulevard ends on a boulevard). Single-road columns: 2 more ids (20707, 20708, table above).

## 4. Shapes that need a word

- **6 taper corner cells carry no lane** (20726, 20728, 20735, 20738, 20743, 20746: the corners the closing curb
  cuts off). An all-zero matrix means "unconstrained" to LANEDENSITY, but no neighbour's matrix leads into them
  (by construction: every matrix is its lanes' turns and no lane enters these cells), so trips never enter them; a lot facing only such a cell cannot start a road trip there
  (its first step is refused by the neighbours). Same as a curb.
- **Narrowing / BVX avenue arms / DBV into a diagonal avenue meet another stream's cells.** These ends are one-way at
  the shared edge. If the avenue beyond is not converted (avcore's band rule refused it, owner rule 2), its two-way
  half would meet one-way lanes: cars strand at the border (arrival node found by position, NET_LANES.md 2.3).
  Recommendation: treat that as an unconvertible end, so the boulevard run is left to the stock tiler as a whole
  (owner rule 2 applied to boulevard + avenue together; rare: it needs an unconvertible piece on an avenue attached to
  a boulevard). Alternative: keep a two-way copy of every end piece, about 40 more ids. **Needs an orchestrator /
  owner call.** For BV to decide it needs avcore's predicate "does the avenue band starting at this cell convert"
  (ask below).
- **Pieces shared between DBV stamps.** 26 DBV ids are used by more than one stamp or position (for example 20953 /
  20954 / 20957 in both the crossing and the T, 20965..20969 in both column junctions, 21027..21030 in three caps). Each
  is checked the same way at build time (one lane set per id); the ones that differ get ids from 21900..21949.

## 5. Ids, curve shapes, records

| what | count | range |
|---|---|---|
| BV new ids (T junction entry row, T middle row) | 2 | 20707, 20708 (BV free 20707..20709 / 20713..20719) |
| BVX box splits | 21 | 20912..20932 (BVX free 20906..20909 / 20912..20949) |
| DBV splits | up to 50 (counted at build) | 21900..21949 |
| lane cuts (curves) for BV + BVX, distinct up to rotation, before matching stock curves | 132 | shapes 24000..24199 |
| DBV curves | not counted yet (114 pieces + splits; BV + BVX gave 132 for 62 pieces) | **ask: reserve 24200..24399** |

Records: one TrBlkAtt record per (id, state used, language). Pieces placed in fewer than 4 states (tapers, narrowings,
caps: states 0 and 2) list only those states. The index grows by itself (`ixf_insert`, avenue program).

## 6. Dependencies on the other streams (asks)

- **avcore** (base, publishes `AVENUE_LANES.md`):
  1. the one-way straight curves of a half (state-0 frame (255, 80) -> (0, 80) and (255, 175) -> (0, 175)): BV 20700
     and the BVX noses use avcore's curves, not new ones, so the halves and the boulevard's outer rows are one set;
  2. the English-UK rule for one-way lanes (UK's VPathAtt runs every stock curve backwards under the same key, so a
     `mirror_uk: false` lane on a stock key drives backwards there; hwlanes writes reversed UK copies for new curves):
     BV follows whatever avcore publishes;
  3. claims: avcore's band block leaves BV / BVX / DBV cells alone (as DAV's `dbv_claimed`), and counts a BV narrowing,
     a BVX box arm (20910 / 20911) and a DBV narrowing as an authored one-way end of the avenue band beyond;
  4. a predicate other blocks can call before writing: "the avenue band through this cell converts" (for section 4's
     fallback);
  5. confirm the half's lanes stay at the 80 / 175 slots in the state-0 frame.
- **avjunc**: the same movement rule for AVX boxes (straight every lane, right from outer, left from inner through the
  opening, 1 turning lane per side on an avenue, no U-turns), so an avenue arm reads the same at an AVX and a BVX box.
  If avjunc picks a different rule, BVX follows it.
- **avdiag**: the DBV narrowing (narrow-C 20972..20982, narrow-A 20983..20992) meets the diagonal avenue: on axis 0
  the half on the smaller-p strip runs -q, the other +q, at the stock 35 slots (80 / 175 chords) on every shared cell
  edge; the same fallback as section 4 if the diagonal avenue stays two-way. To agree through the orchestrator.

## 7. Build (milestone 2, after avcore's base is merged)

1. `bvlanes.py`: turn the plan's lane geometry into lanekit specs per piece (cut per cell, curves deduplicated up to
   rotation, stock curves where the points match, `connects: auto`, `mirror_uk` per avcore), the check that every id
   has one lane set, and the new ids' manifest entries (art copied from the piece they split from).
2. Rules: BV picks 20707 / 20708 for T columns (`boulevard.py` + `sc3netmod_bv.c`), BVX picks box ids by box kind and
   cell (`bvx.py` + `sc3netmod_bvx.c`), DBV stamps list the split ids (`diagbv.py` manifest stamps), the fallback of
   section 4 once decided.
3. Offline: `bvlanes.py check` 0 split left, every spec compiles in every language (`lanekit`), DBV / BV / BVX twins
   unchanged in what they convert (`diagbv.py check`, `bvx.py check`).
4. One in-game check: a copy of Seoul (traffic) with a boulevard drawn along an existing avenue plus a crossing road and
   a cap; cars keep their lane through the pieces (hwcars tools), the probes show no trip routed against a lane; save,
   reload, a game without the mod loads stock pieces. Sheet `bvlanes_sheet.png`, `verify/bvlanes/RESULTS.md`.
