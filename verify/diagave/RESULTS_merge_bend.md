# diagave: merges, bends, crosswalks (2026-10-17)

Owner request: "now work on the merge of an avenue into a single road, the change of diagonal avenue into a straight
avenue, the sidewalk crossing". Light test: one lab game per change, screenshots, a save and reload.

Test tree `Simcity_stock_diagave`, instance `re/harness/inst_dav` (sc3netmod.dll built from this branch, 209,920
bytes), package `diagonal_avenue` 0.5.0 installed as overlay. Lab city: copy of `roadless.sc3` (flat patches at
alt 82). Screenshots stay in the instance's `shots/` (game art, not committed).

## Art: one painter for every piece

`re/tools/netmod/diagave_paint.py` paints each piece as one cell of a WORLD scene. Every output pixel is unprojected
to world coordinates and coloured from the stock pieces' own frames at the same screen position (35 for the diagonal
strips, 29 for a crossing road), so a scene pixel equals the stock pixel wherever the scene shows plain stock road and
neighbouring pieces meet exactly. Where a marking, curb or sidewalk has to become asphalt (the lanes of a carriageway
that ends, a crossing road's centre line), the fill reflects the road's cross-section about the nearer lane edge,
measured once per piece, zoom and view (a fixed sideways shift landed on the darker tyre tracks and left streaks).

## Crosswalks

Junction pieces 20510..20519 are now painted from the Junction scene: road 29 with the avenue's halves as asphalt,
two white lines (lane units 8..15 and 32..38 from the edge, stock 43's metrics at zoom 4) across the road where it
meets the avenue's outer edge, and across the avenue along the road's edges (not on a stem's far side). Zoom 2 and
up (below that the lines are under a pixel).

| Check | Result |
|---|---|
| Road crossing the avenue, zoom 4 (`m1_z4.png`) | crosswalks on both avenue edges and both road edges; centre line gone inside the junction |

## Merge: avenue into a single road

Rule (`diagave.py merge_cont`, `sc3netmod_dav.c` ends loop): at a band end, when only one staircase's two cells go on
for the next two rows, that staircase's next 3 rows join the band, the row after is path (in the lone masks, not
written: the stock tiler joins the single road on), and a case table (`davm` lines, 8 cases: axis x end x which
staircase goes on) places five taper pieces. The ending carriageway's outer curb moves linearly across the cut over
three rows and ends exactly on the other carriageway's inner sidewalk; the median stops with a concrete nose.

Pieces 20520, 20530 and 20533 hold both roads and save as 43 (`davs` lines); the other merge pieces save as 35.

| Check | Result |
|---|---|
| B shorter at the bottom + a crossing road (`m1_z3/z4.png`) | `band axis 0, 6 row(s) from (102,92), 24 cell(s), 3 junction cell(s), 4 arm cell(s), 1 merge(s), 23 written`; 20520..20524 placed |
| A shorter at the bottom and B starting later at the top (`m2_z3/z4.png`) | `band axis 0, 4 row(s) from (104,94), 22 cell(s), ... 2 merge(s), 12 written`; both tapers, a short median island between |
| Art table | first build used road 29's table: the cut-away corner of the taper showed cyan at zoom 3 (no ground drawn under). Back on 35's table: ground drawn, no cyan |

Owner review of the sheet: "crossings are fine but merging lanes are off, there should be yellow lines for lane
divider" (images 1 and 2; the bends, images 3 and 4, "perfect"). The first build turned the ending carriageway's
markings into asphalt, so its yellow line stopped at the median nose. Now the taper keeps two dividers, both made of
stock 35's own centre-line pixels moved across the cut (measured per zoom and view, `centre_line`; at zoom 4 the
stock line is a double yellow and the copy is too; none at zoom 0 or 1, where the line is under a pixel):

- the ending carriageway's centre line runs down the middle of what is left of it, (1 + edge) / 2, and meets the
  curb where the taper closes;
- a yellow line takes the median's place between the two carriageways, from the median nose to the curb.

| Check | Result |
|---|---|
| Same two layouts, rebuilt art (`m3_z4.png`, `m4_z4.png`) | both dividers drawn at every taper; DAV log unchanged (1 merge, then 2 merges) |

Second owner review, a sketch over image 2: both lines of that version marked red (remove), one green line to add
from the continuing road's centre line to the median nose. Now the taper has that single line: it branches off the
continuing carriageway's centre line where the taper closes (q_e) and runs straight to the nose (p 1 at q_s); the
ending carriageway's own centre line stops at the nose.

| Check | Result |
|---|---|
| Same two layouts, rebuilt art (`m5_z4.png`, `m6_z3/z4.png`) | one branching line at each taper, as sketched; DAV log unchanged |

## Bend: diagonal avenue into the straight avenue

Two parallel straight roads side by side are the stock avenue 11204. When both drags go on that way, the band's end
is a bend (`bend_kind`): along x (the last two rows run on past their right cell) or along z (two columns below). The
carriageways' edges meet the straight avenue's on one cell line (x - z = k meets z = m at x = k + m for all three
edges), so no bend art is needed: the diagonal cells get their middle-of-band pieces (two virtual rows of both
staircases past the end make their masks) and the straight cells stay stock.

| Check | Result |
|---|---|
| Stock before the rule (`b1_z3.png`) | the ladder (11203 / 43) into 11204; DAV gave up: "road beside the avenue is not a straight arm" |
| North at the top, east at the bottom (`b2_z3.png`, `b2_north_z4.png`, `b2_east_z4.png`) | `band axis 0, 7 row(s) from (11,46), 18 cell(s), ... bends 2/1, 17 written`; 20505 / 20500 up to the joint, 11204 from it; curbs, median trees and lane lines continuous |

## Save and reload

| Check | Result |
|---|---|
| Save (menu 0x10009002) | `save: 30 variant tile(s) written as base, section 0x4E56 written` |
| Reload with the mod | `load: all 30 variant tiles restored`; load pass `0 written` on both bands |
| Offline twin | `diagave.py plan dav8_lab.sc3`: wanted pieces equal the live cells for both bands |

0 exceptions in sc3netmod.log across the three games.

## Open

- Not seen in game this round: axis 1 merges and bends (same code with x mirrored), a bend at the top going west or at
  the bottom going south, merges loaded without the mod.
- The bend joint shows the diagonal's and the straight avenue's own lane markings meeting at the joint line.
- Avenue x avenue, turning lanes at junctions, bulldozing a junction cell: unchanged from RESULTS_junctions.md.
