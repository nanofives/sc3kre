# diagx: diagonal avenue crossings (2026-10-17)

Orchestrator brief (avenue program, child `diagx`): diagonal avenue x diagonal avenue, diagonal avenue x straight
avenue 11204, a diagonal avenue ending on a straight avenue (T), and on another diagonal avenue if it falls out of the
same rule. Light test per owner rule: offline mockup, one game check, pictures, save + reload.

Owner pictures (untracked): `MAIN\verify\diagx\owner_shots\diagx_mockup.png` (crossings, offline),
`diagx_mockup_T.png` (T, offline), `diagx_sheet.png` (game).

## What stock does (offline tiler, `tiler.Tiler.retile` on the footprints)

| Shape | Stock |
|---|---|
| diagonal avenue x diagonal avenue | the two ladders meet in a patch of 43 / 39; where the bands overlap: a plus of 5 cells or a 2x2, by the bands' offset parity |
| diagonal avenue x 11204 along x | 11204 rows hold 39.1 39.1 43.0 39.3 / 39.1 43.0 39.3 39.3 where the band crosses, the band is the ladder |
| diagonal avenue x 11204 along z | the same turned: 39.0 / 39.2 cells in the two columns |

11204 along x is row m state 2, row m + 1 state 0; along z, column n state 1, n + 1 state 3.

## Art: a crossing scene of two elements

`diagave_paint.Crossing`: two ELEMENTS, each in its own canonical frame (DiagEl: the diagonal avenue on strips
c..c+2 of x - z, drawn as the DAV pieces draw it; StraightEl: 11204 along x), placed turned k states and moved by
whole cells.

- Turning: a scene turned one state shows at view r what the unturned scene shows at view r + 1 at the point
  (wz, -wx). Measured on stock 35, 4,000 random points at zooms 2..4: 0 mismatches for that mapping (1,922 / 3,948 /
  3,976 for the other three candidates). So an axis-1 diagonal is DiagEl turned once and an avenue along z is StraightEl
  turned once, sampled from the same stock frames.
- Where both elements are: paved with stock 43's interior asphalt (lane units 48..208, folded by a triangle wave of
  the world coordinate so cells meet); corner sidewalks where both outer sidewalks meet, each side sampled from its own
  element so its curb runs on (the element whose edge is relatively farther wins); two white crosswalk lines
  (WHITE_LINES, lane units from the edge, as the junction pieces) along every edge an arm leaves through.
- Where one element is: that element as stock, its median ending NOSE_CELLS (0.085 cells, StraightAvenue.NOSE) before
  the other with a concrete nose (the diagonal's own light pixels; on 11204 stock 35's light pixels).
- A T (`stem`): nothing of the stem past the through road's far edge, the through road's far sidewalk and curb kept,
  no crosswalk there.
- 11204's layer 0 carries its trees; in slots 1 and 2 they stand in front of the road. Ground under them is read from
  the nearest point along the road that no tree covers (lane lines stay put). The opposite view draws the same ground
  point with only 10% of pixels equal (measured, 3,000 points per slot), so it is only the last resort. On the median
  the trunk bases become grass (a crossing cell carries no tree layer).

## Kinds, pieces, templates

| Kind | Layout | Special cells |
|---|---|---|
| XX0 / XX1 | diagonal x diagonal, bands meet in a plus / a 2x2 | 9 / 4 |
| XSX / XSZ | diagonal x 11204 along x / z | 12 / 12 |
| TSX / TSZ | diagonal ends on 11204 along x / z | 10 / 10 |
| TX0 / TX1 | diagonal ends on diagonal (plus / 2x2) | 8 / 4 |

Each kind turned 0..3 covers every drawing (the T from either side, either axis). Special cell = art differs from the
plain pieces at zooms 3 and 4, all views. Pieces deduplicated by frames over placement states: 55 (20540..20594).
Base 43 when a cell holds parts of both roads (saved as 43), else that part's stock piece at its state; art table from
35 (ground drawn under); lanes = every road part's stock lanes (`parts_spec`).

Rule: 32 templates (`recipe_crossings.json`, `davx` / `davxg` / `davxw` table lines). A template is anchored on a band
row with road beside it, holds the window (special cells grown by 2) as ROAD / no ROAD exactly, and the cells it
writes (its pieces, and 11204 on the straight avenue's plain cells the stock tiler turned into 39 / 43). A symmetric
kind keeps only the turns that are not an earlier turn moved (else two templates match one crossing). Window cells are
not arms and do not count as touching; a band end inside a window has no stub, merge or bend. When the window holds a
second diagonal band, that band must convert too: the DLL runs dry rounds (no writes) until no band changes, then the
write round; the Python twin runs the same fixpoint.

Refuses: straight x straight, 3x3 blocks, three parallel roads (no DAV band, or the exact window fails). RBT does not
take the XX1 2x2 (its pinwheel and closed cells do not hold).

## Offline

| Check | Result |
|---|---|
| `diagave.py xcheck` (8 kinds x 4 turns, long arms) | 32 / 32: every band converts, every special cell gets its art |
| `diagave.py combos` | unchanged (5 middle combinations, 28 / 32 junction drawings) |
| `diagave.py scan` (16 shipped cities) | no template matches; the 3 converting bands are bends from the diagave round |

## Game (Simcity_stock_diagx, inst_diagx: sc3netmod + sc3resize, package 0.6.0)

| Step | Result |
|---|---|
| Install (first runs) | TrBlkAtt rebuilt by a local opt-in fallback, since dropped for the orchestrator's ixf_insert growth (below) |
| Load (pid 19068) | READY, variants=81, no `### dav` line (all 32 templates read) |
| Drags (100,90)-(115,105), (101,90)-(116,105), then (116,90)-(101,105), (115,90)-(100,105) | `band axis 0, 15 row(s) ... 1 crossing(s), 47 written`, `band axis 1, 12 row(s) ... 1 crossing(s), 38 written`; a 2x2 meeting (XX1): 20549..20552 |
| Roads (10..24, 49) and (10..24, 50), then drags (10,43)-(23,56), (11,43)-(24,56) | `band axis 0, 13 row(s) ... 1 crossing(s), 45 written`: 20553..20564, plain 11204 beyond |
| Live grid vs `diagave.py plan` on the save | 122 band cells, 0 differ |
| Pictures zoom 3 and 4, views 0 and 1 | paved crossings, crosswalks on every arm, median trees stop at a concrete nose, curbs continuous; a pedestrian walking the crosswalk |
| Save (menu 0x10009002) | `save: 115 variant tile(s) written as base` |
| Reload (pid 59836) | `load: all 115 variant tiles restored`; load pass `1 crossing(s), 0 written` on all three bands |

Logs: no `###` line besides load / READY, no exception in either run.

## White dashed lane lines (owner change, relayed 2026-10-17)

"On avenues instead of yellow lines they should be white striped lines for every lane." The crossing scenes' arms
now dash: DiagEl turns a yellow pixel on the stock centre line's footprint (`centre_line`) into a lanelines.py dash at
(x + z) / sqrt 2 of the avenue's own frame (as the diagonal avenue scenes), else lane asphalt; StraightEl does the same
on 11204's two carriageway lines with along = x (4 centred dashes per cell, as the avenue_markings reskin). Own code in
the crossing section only (StraightAvenue / Merge / Junction untouched; their dashing arrives with child/diagave).
Rebuilt: 55 pieces, 32 templates, `xcheck` 32 / 32.

| Check | Result |
|---|---|
| Install with child/diagave's ixf_insert (index growth, no flag) | every language TRBLKATT.IXF: 1,186 slots (stock 862 + 324), first payload 0x5004 -> 0xA004 |
| TrBlkAtt slots the crossings take | 220 per language (55 laned variants x 4 states); the whole package 324 |
| Load of the saved lab city (pid 69436) | `load: all 115 variant tiles restored`, load pass `1 crossing(s), 0 written` on all three bands, no `###` line |
| Picture (`shots/dash_xs_z4.png`, `dash_xx_z4.png`) | dashes on the arms inside the crossing pieces; the plain avenue pieces of this tree are still the pre-change yellow |

## Open

- Not seen in game: XX0 (plus meeting), XSZ, the four T kinds, turns other than the ones drawn. All pass offline.
- Symmetric cells do not share pieces (stock frames differ per view, so a turned copy is not pixel-equal): 55 pieces
  where an exact-symmetry build would need about 34.
- TrBlkAtt: the crossings take 220 slots per language (55 x 4), past the stock index's 161 free; ixf_insert now grows
  the index (child/diagave f92c5c9), proven by the load above.
- Lanes go straight through on both avenues; no turns at crossings (as the junction pieces).
- Crossing cells carry no tree layer: the straight avenue's trees stop one cell before the crossing.
