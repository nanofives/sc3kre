# boulevard: three parallel straight roads become one boulevard (2026-10-17)

Owner request: "fix 3 wide avenues where the middle road is an extra lane but a bigger median". Stock tiles three
parallel roads as 11204 / 29 / 11204 (two medians facing a plain road). Light test per owner rule: one lab game,
pictures, a save and reload.

Setup: test tree `Simcity_stock_boulevard`, instance `re/harness/inst_boulevard`, sc3netmod.dll built from this
branch (218,624 bytes), package `boulevard` 0.1.0 installed as overlay. Lab city: copy of `lab.sc3` (flat patch at
alt 82, x 100..116 / z 90..106). Game art and screenshots stay in the instance's `shots/` and in
`MAIN\verify\boulevard\owner_shots\` (not committed).

## Design (working interpretation, shown to the owner in the mockup)

Cross-section, lane units of stock road 29 at zoom 4 (sidewalk 0..34, curb and gutter 34..56, lane 1 56..116, centre
line 124..132, lane 2 148..200, gutter and curb 200..224, sidewalk 224..256; car lanes at 80 and 175):

- outer rows: stock 29, yellow centre line kept. Their inner sidewalk becomes one extra lane, 104 units wide (stock
  lane asphalt folded from the lane's own dark band), then their own gutter and curb, moved over by 104.
- middle row: the two extra lanes' far parts, the two curbs, and between them 11204's median grass with 11204's two
  trees per cell on the centre line. Curb to curb about twice the stock avenue's median.
- car lanes (cosmetic, traffic uses the road grid; round 3 adds the outer piece's spec back): middle row one lane along each carriageway (zl 14 going -x next
  to the north row's -x lane, zl 241 going +x), its own TrBlkAtt spec. Junctions copy 43's record. Every other piece
  has `trblkatt: none` and gets road 29's straight lanes (NET_LANES.md section 3), which is what its spec held
  (round 2: TrBlkAtt's reserved index has 161 free slots for all packages; the first full build needed 211).
- lane lines (owner change, round 2): no yellow on the boulevard. Each carriageway's centre line and the line between
  its inner lane and the extra lane (220 units from its outer edge, between the car lanes at 175 and 270) are white
  dashes from `lanelines.py` (copied from the diagave worktree, not edited): period 0.25 cell, dash 0.375, phase from
  the world along-coordinate, footprint = 29's yellow line, white = highway 73's dashes, none at zoom 0-1. Single
  roads keep yellow; in a taper the single road's yellow line still runs to the median nose.

Painter: `re/tools/netmod/boulevard_paint.py`, world scenes as `diagave_paint.py` (every pixel samples stock 29, 43,
39 and 11204's grass at the same screen position). Scenes: Boulevard (median nose optional at either end), Junction
(stock 43 / T 39 with the boulevard's inner edges opened by reflection, so the crosswalks are 43's own two white
lines and run across the whole boulevard), Cap, Taper.

## Rule (`boulevard.py runs()`, `sc3netmod_bv.c bv_run1()`)

- column: ROAD at (s, w0..w0+2). Clean: no ROAD beside it. Junction: a straight single road arm on one or both sides.
- run: maximal consecutive columns along x or z. Each end: nothing beyond = cap (last column closes it with a half
  ellipse of curb), exactly one row going on straight = taper to that row over the last 3 columns, else refused.
- accepted: at least 3 clean columns besides the end regions, no junction in or next to an end region, no other ROAD
  8-touching the run except junction arms and the road a taper goes on into.
- refused: any run shorter than 4 columns (orchestrator ruling, 2026-10-17: an exactly-3x3 full road block is
  bigrbt's whatever its arms, including three parallel roads 3 long with avenues or roads going on at both ends).
  Twin: both 3x3 cases refused with "3-column run: a 3x3 block (bigrbt's)", the 5-column capped run still
  converts, the mockup layout unchanged; C has the same early return (BV_MIN_RUN 4), built, not run in game.
- refused, as the shape table requires: diagonals touching the run (DAV), 3x3 blocks (bigrbt, fewer than 3 clean
  columns), avenue x avenue boxes (avx, no three parallel roads), an avenue or a boulevard crossing (its arm is not a
  single road: wave 2), two roads going on at an end (avenue narrowing, not built).

Pieces (canonical: along +x, rows 0 / 1 / 2; the -x end is the +x end turned half a circle; along z = state + 1):

| id | piece | base (save) | art table |
|---|---|---|---|
| 20700 | outer row (south row state 0, north row state 2 = stock 11204's states) | 11204 | 29 |
| 20701 / 20702 / 20703 | middle, middle with a nose at +x, nose at both ends | 29 | 11204 (two layers, trees) |
| 20704..20706 | end cap, rows 0 / 1 / 2 | 43 | 11203 (ground under) |
| 20710 / 20711 / 20712 | junction entry row, middle row, far row of a T | 43 | 43 / 43 / 39 |
| 20720..20728, 20730..20738, 20740..20748 | taper to row 1 / 0 / 2 (3 * column + row) | 43 | 11203 |
| 20750..20758, 20760..20768 | narrowing to the avenue on rows 0, 1 / 1, 2 (round 2) | 43 | 11204 (median cells, trees) / 11203 |

Saves: every piece saves as its base, so a game without the mod keeps the roads joined (stock 11204 / 29 look on
straight stretches, 4-way 43 at junctions and ends).

## Offline

| Check | Result |
|---|---|
| Mockup layout (taper to row 0, boulevard, crossing, T, taper to row 1) hand-placed vs `runs()` on its road set | equal, 45 cells; the same road set turned a quarter (along z) gives the hand layout at state + 1 |
| `boulevard.py mockup` | `owner_shots/boulevard_mockup.png`: zoom 4 and 3, views 0 and 1, stock-today panel |

## Game (pid 41816, then 60428 after reload)

| Step | Result (sc3netmod.log) |
|---|---|
| three drags (101..114, z 96 / 97 / 98) | `bv: edit: boulevard axis 0, columns 101..114 at row 96, 42 cell(s), 42 written`: caps at both ends (20704..20706 states 2 / 0), noses 20702 at 102 and 113 |
| crossing road x 106 (z 92..102), T from the north x 109 (z 92..95), middle road on to x 116 | after each drag `42 cell(s)`, 30 / 30 / 15 written; grid: 20710.0 / 20711.0 / 20710.2 at 106, 20710.0 / 20711.0 / 20712.0 at 109, 20720..20728 at 112..114, 29.0 beyond |
| screenshots (`g2_z3`, `g2_z4`, `g3_taper_z4`) | as the mockup; taper's open parts show terrain, no cyan |
| save (menu 0x10009002) | `save: 42 variant tile(s) written as base, section 0x4E56 written` |
| reload | `load: all 42 variant tiles restored`; load pass `42 cell(s), 0 written`; view 1 zoom 4 correct (`g5`) |
| offline twin on the save (`boulevard.py plan lab2_saved.sc3`) | 42 wanted pieces = the live grid after reload, 0 mismatches |
| bulldoze middle cell (104, 97), rebuild it | the stock retile re-placed the cells near the hole, BV reverted the other 15 (`no longer in a run -> stock retile`): stock 11204 / 29 / 39 / 43 again (`g6`); rebuild: `42 written` |

0 exceptions in both logs.

## Round 2 (owner change: white dashed lane lines; avenue narrowing on 20750..20769)

- AvenueNarrow scene: over the last 3 columns the ending side's carriageway slides one row in (frame moves 256 units,
  linearly), both extra lanes close (104 -> 0), the median narrows to the avenue's and its centre moves 384 -> 256
  (rows 0, 1 go on) or 512; its trees follow it. The carriageways' dashed centre lines run through; the extra-lane
  dividers end where it starts. The cells past the end are stock 11204 (offline tiler: clean 11204.2 / 11204.0 pairs
  right after such an end). No median nose before an avenue narrowing (rule fix in twin and C).
- The outer-road taper's curb shape is one function, `boulevard_paint.outer_curve(t)` (t^3 now).
- A yellow pixel within 8 units of a carriageway centre line becomes dash or asphalt (a frame moving by fractional
  units brings stock yellow pixels in beside the footprint).

Game (pid 51180, then 68464 after reload), `lab3.sc3`:

| Step | Result |
|---|---|
| drags (100..113, z 96), (100..116, z 97), (103..116, z 98), crossing x 108 | `bv: edit: boulevard axis 0, columns 103..113 at row 96, 33 cell(s)`: 20760.. at both ends (state 2 at -x, 0 at +x), middle 20701 next to both narrowings, 20710 / 20711 at 108 |
| along z: drags x 15 / 16 / 17 (z 45..55), crossing road z 50 | `bv: edit: boulevard axis 1, columns 45..55 at row -17, 33 cell(s), 33 written`; caps 20704..06 states 3 / 1, outer 20700.1 / .3, junction 20710.3 / 20711.1 / 20710.1 |
| save | `save: 66 variant tile(s) written as base` |
| offline twin `boulevard.py plan lab3_saved.sc3` vs live grid | 66 / 66 equal (both axes, both narrowings) |
| reload | `load: all 66 variant tiles restored`, both load passes `0 written` |

0 exceptions (`sc3netmod_run3.log`, `_run4.log`). Owner sheet: `owner_shots/boulevard_sheet_v2.png`; mockup with
dashes and the narrowing: `owner_shots/boulevard_mockup_v2.png`. Owner sheet: `MAIN\verify\boulevard\owner_shots\boulevard_sheet.png` (the blue square in
panels 1 and 6 is the road / bulldoze tool's cursor highlight).

## Round 3: TrBlkAtt index growth (ixf_insert.py from child/diagave f92c5c9, copied unedited)

| Install | boulevard TrBlkAtt slots per language | index (all 7 language folders) |
|---|---|---|
| shipped: specs for 20700 (outer: pedestrians on its outer sidewalk only) and 20701..20703 (middle lanes), junctions copy 43, the rest `trblkatt: none` | 19 (4 x 4 + 3) | 862 -> 881 slots, first payload stays 0x5004 (not grown) |
| test only (`BV_FULL_LANES=1`): a spec for every non-junction piece | 211 | 862 -> 1073 slots, grown one block: first payload 0x5004 -> 0xa004 |

The specs left out give cars the lanes they would get anyway (road 29's straight lanes, the NET_LANES.md section 3
fallback), so the shipped package keeps the lean set. Game on the grown install (pid 37356, `lab4.sc3` = the round 2
save): sc3netmod's overlay served the grown `ENGLISH\TRBLKATT.IXF` to GZResourceD, `load: all 66 variant tiles
restored`, both load passes `0 written`, the sim ran from 1/1/2000 to 1/4/2000, 0 exceptions
(`sc3netmod_run5_grown.log`, `shots/k1_grown_running_z4.png`). The lab city has no population, so no car was seen
following a lane: this checks that the grown index loads and runs, not the lanes themselves.

## Open

- The avenue past a narrowing is stock 11204 (yellow until the orchestrator's avenue_markings reskin). My last
  column's median edge is 29's curb profile, 11204's curb sits about 8 units further in: a step of about 4 px at
  zoom 4 at the joint, not visible at zoom 3.
- Two OUTER rows going on at an end (the boulevard splitting into two roads): refused.
- Narrowing to an OUTER road: both ending drags stop on the same column, so the far curb eases in (t^3) to keep road
  in every cell of the ending rows; it reads as a rounded bulb (mockup, -x end). Not seen in game this round.
- Wave 2: boulevard x avenue, boulevard x boulevard. Extension: a junction column whose arm is a two-wide road would
  need a junction block of 2 columns (both arm columns), 43-based like the single-road junction, with the median
  nose before the first and after the last; boulevard x boulevard = a 3x3 block of opened 43 with noses on all four
  sides. Both shapes are refused today ("not a straight single road").
- The rule writes about 30 cells after each nearby edit (the stock retile re-places them first), as DAV does.
