# dbvx49: junctions 49 / 51 / 53 with short arms (2026-11-17)

Workspace dev/dbvx49 (main b547c93 + the 2026-11-17c release stage). Code: `re/harness/src/sc3netmod_dbv.c` (blocks
DBVCAPNEAR, DBVXENDCAP), `re/harness/src/sc3netmod_dav.c` (block DAVSHORTBOX). Package: diagonal_boulevard 0.3.1
(8 crossing template variants, ids 23..30), installed in dev/dbvx49/tree only. Every C change has an off switch:
`SC3NETMOD_DBVCAPNEAR=0`, `SC3NETMOD_DBVXENDCAP=0`, `SC3NETMOD_DAVSHORTBOX=0`. Debug: `SC3NETMOD_DBVCAPDBG=1` logs the
rows past every end that stays ragged.

"Before" below = the released table + the three switches off (= release 2026-11-17c behaviour), "after" = the
0.3.1 table + switches on, same build, same sandbox slots (runs `b0*` and `a7*`).

## 1. What was wrong (reproduced in dev/dbvx49, run a0 / b0)

- **49 and 53 at 3 and 4 rows had no junction box at all**, in both draw orders: the diagonal boulevard ran through as
  plain band pieces and the other band was cut with notches (`owner_shots/sandbox_49_4.jpg`, `sandbox_53_4.jpg`). The
  "3 rows already reach the baseline (5 / 5 / 4 stock cells)" of the brief was a count match only: those layouts had
  no box either (`sandbox_49_3.jpg`, `sandbox_53_3.jpg`). 53 without a box is not even repeatable: b0 and a0 (same
  build, same slots) differ in 6 / 8 cells at 3 / 4 rows.
- **51 has no crossing template at any length** (none in the package). Its 6-row look is the boulevard running through
  and the avenue stem ending at its edge. In the sandbox 51 at 3 / 4 / 6 rows reads the same before and after.
- Showcase city (`showcase_built_pristine.sc3`, read-back `c0/rb.json`): 49 / 51 / 53 = 13 / 12 / 12 stock cells, as
  diagarm reported.

## 2. Causes (code paths)

a) **Template windows too long for short arms.** The 49 / 53 templates (diagonal_boulevard 0.3.0 ids 1 2 / 9 10, 9x9
   and 9x10) were cut from 6-row arms and check about 4 rows up each arm. With 4-row arms one cell next to a written
   cell differs (49: template 1 off by 1 cell, canonical (-1,-2), inside DBVSHORT's 1-cell near ring, so the relaxed
   pass does not take it either, `nearmiss.py`). At 3 rows the 6-row anchor row is also not a row of the band's chain
   (templates are only tried on chain rows), so one band of 53 got no template and later passes wrote plain band pieces
   over the box (the draw-order flicker of the first try).
b) **Cap tests read 9-wide rows.** `dbv_end_kind` needs the row after a cap's stamp rows empty over d -2..6. On axis 1
   those rows are real columns, so the showcase street two rows past the end ((129..148,111), below 51's end rows
   107..109) crossed every one of them (`..rrr.r..`): RAGGED, stock 11203 / 39 / 11225 end, with an empty real row
   between it and the street (51 and 53 in the showcase: 6 extra stock cells each, `endkind.py`).
c) **Ends inside a template's rows were skipped** (`if (jxrow[z_e - z0]) continue;`, meant for a T / L stem that ends
   in the box). With short arms a cross's far end lies inside the window too: 49 at 4 rows lost its boulevard end cap
   once the box matched, and the end's partial rows then touched the band and stayed stock.
d) **The box splits the diagonal avenue.** The box claims every cell of the avenue's rows at the crossing, so those
   rows end the avenue's chain (`dav_full`). Past the box a 4-row arm keeps 1..2 clean rows, under `DAV_MIN_ROWS` 3:
   the stub stayed the stock ladder (49 at 4 rows, 7 cells).

## 3. Fix

1. **diagonal_boulevard 0.3.1** (`verify/dbvx49/shortx.py`): per 49 / 53 template, a variant with the same window,
   writes and art, where every window cell whose road state depends on an arm's length (each of the 4 arm ends 3..7
   rows, independently, all 8 symmetries) is `-` (any), writes on cells that are not road at every length are dropped
   (band pieces in partial rows), and the anchor is moved along the band to a row that is a chain row at every length.
   At 6 rows the released template still matches and is more specific, the variant's writes are a subset with the same
   pieces, so 6-row results do not change through the package. No new art.
   Offline check in the same script (an emulation of DBV's strict / relaxed template choice per band chain): every
   diagonal-boulevard chain of 49 / 53 gets a strict match at every length and symmetry (the 2..3-row chain inside the
   DA x DB overlap has none, before and after, and is refused quietly in the game), and on every other diagonal pair
   case (arms 2..7, 8 symmetries) the chosen templates are the same with and without the variants.
2. **DBVCAPNEAR** (`sc3netmod_dbv.c`, only where the cap tests say RAGGED): each cap shape is tried by its cells. Its
   cells are road, the two cells beside the end row are empty, and every cell of rows 1..4 that is 8-adjacent to the
   shape or the end row is empty. Cells DBVTOUCH masked count as road in these tests (first try missed that: in Berlin
   it capped a boulevard end that joins an avenue junction at (159,151)).
3. **DBVXENDCAP** (`sc3netmod_dbv.c`): an end inside a matched template's rows is judged as usual when its kind is a cap,
   all its stamp cells are road and none is a cell a matched template writes. Otherwise skipped as before (first try
   with a row-distance test stamped 49's top end at 6 rows onto template 1's band-piece write, and the band was refused,
   "junctions or ends too close together").
4. **DAVSHORTBOX** (`sc3netmod_dav.c`): an avenue chain with at least 1 clean row is judged when the row just past one of
   its ends is a row the boulevard holds (the box). Tried and dropped: also chains of 1..2 rows with no clean row (49 at
   3 rows needs that). It took the boulevard's ragged end rows as avenue stubs and broke 43 at 4 rows (run a5).

## 4. Results

Sandbox (`xsect_sandbox_clear.sc3`), own diagonal drag cells holding a stock piece, and junction box cells (22721..22798)
in the 21x21 window. Forward and reverse draw order give cell-identical results after the fix (within 8 cells of the
centre, every spec), so one line per case:

| case | arms | before stock / box | after stock / box | note |
|---|---|---|---|---|
| 49 DA x DB cross | 3 | 5 / 0 | 9 / 7 | box drawn. The avenue's 1-row stub above the box stays stock (4 cells, open, see 6) |
| 49 | 4 | 13 / 0 | 6 / 7 | box, avenue arm with its U-turn end, boulevard end cap. The 6 = the boulevard's far ragged end, as at 6 rows |
| 49 | 6 | 5 / 7 | 5 / 7 | 0 cells differ |
| 51 DA x DB T2 | 3 / 4 / 6 | 5 / 6 / 0 | 5 / 6 / 0 | 0 cells differ. At 3 / 4 rows the stock cells are the boulevard's end next to the avenue stem's first row (the T sits at the boulevard's end in the turned frame, a road beside the end row) |
| 53 DB x DB cross | 3 | 4 / 0 | 4 / 8 | box drawn |
| 53 | 4 | 6 / 0 | 6 / 8 | box drawn |
| 53 | 6 | 4 / 8 | 4 / 8 | 6 cells differ: the axis-0 band's top-left end gets the cap stamp its other end already had (DBVXENDCAP) |

Showcase city (`showcase_built_pristine.sc3`, load read-back of the undamaged built save, `c0` before, `c2` after):

| case | before stock / box | after stock / box |
|---|---|---|
| 49 D9_DAxDB_cross | 13 / 0 | 6 / 7 |
| 51 D9_DAxDB_T2 | 12 / 0 | 6 / 0 (the lower-left end cap, DBVCAPNEAR) |
| 53 D10_DBxDB_cross | 12 / 0 | 6 / 8 |

The 6 left in each are the same cells: the axis-1 boulevard's top-right end, its drags' partial rows (3 + 2 + 1 cells at centre + (2..4, -4..-2)). The released 6-row sweep keeps that end stock in 49 and 51 too (5 / 6 cells).

Pictures (zoom 4, rotation 0, before | after, 1400 px JPEG) in `owner_shots/`: `sandbox_<case>_<rows>.jpg` (+ `_rev`
for 49 / 53 at 3 and 4 rows), `sandbox_53_6_end.jpg`, `city_<case>_<block>.jpg`.

## 5. Changed besides 49 / 51 / 53

Same mechanisms, all from a stock or bare boulevard end becoming the package's cap stamp. Pictures `owner_shots/side_*`.

| layout | cells | what changes | block |
|---|---|---|---|
| 50 / 52 / 54 / 55 at 4 rows (sandbox, both orders) | 10 / 10 / 16 / 22 | the stem's (and 55's other arm's) far end: stock ladder (6 stock cells) -> cap | DBVXENDCAP |
| 54 / 55 at 6 rows (sandbox, sweep) | 6 / 12 | the through band's far end inside the T's tall window: bare band rows -> cap, as its other end | DBVXENDCAP |
| 53 at 6 rows (sandbox, sweep) | 6 | top-left end, bare band rows -> cap | DBVXENDCAP |
| showcase 50 / 52 / 54 / 55 | 10 / 11 / 22 / 22 | far ends, 6 stock -> 0 | DBVXENDCAP |
| showcase 42 / 44 (B x DB) | 6 / 6 | the boulevard's end with a grid street not touching it: bare band rows -> cap | DBVCAPNEAR |
| sweep 51 | 10 | the boulevard's top-right end, stock -> cap (a road of the next slot 2 rows past it, not touching) | DBVCAPNEAR |

19 34 43 45 at 4 rows (DBVSHORT's short-arm layouts): 0 cells differ, both orders.

## 6. Regression

- **80-case sweep** (fresh sandbox, sweep order, final read-back, `s2/cmp_stage.txt` against `verify/final1117/s1`):
  **73 of 80 identical**. 31 / 32 / 33 differ by 27 / 26 / 15 cells, exactly as diagarm's m3 run of the released
  code (s2 against `verify/diagarm/m3`: 31 32 33 identical), so that is the baseline's drift, not this branch. 51 / 53 /
  54 / 55 differ by 10 / 6 / 6 / 12 cells, all boulevard end caps (section 5; log lines DBVCAPNEAR for 51, DBVXENDCAP
  for 53 54 55). Against m3 only 51 53 54 55 differ. s1 (the build before the Berlin fix) and s2 (final) are identical.
- **Berlin** (`rotleak Berlin.sc3`, every road cell read after load): 19,220 cells, **0 differ** with the fix on and off
  (`berlin/on4.json`, `berlin/off.json`). The first build differed in 6 cells (DBVCAPNEAR read a masked touching
  road as empty, fixed, section 3.2).
- DBVSHORT short-arm layouts: see section 5.

## 7. Open

- **49 at 3 rows: the avenue's 1-row stub past the box stays the stock ladder** (4 cells, top of
  `sandbox_49_3.jpg`). Its only row has the boulevard's arm beside it, so it has no clean row. Letting DAV take chains
  with no clean row broke other layouts (section 3.4). A fix would be a template variant for exactly 3 avenue rows that
  writes the stub's end pieces itself (21803 / 20501 / 20505 / 20505.2, per symmetry), or a DAV rule that tells this
  stub from a boulevard's ragged end rows.
- 51 at 3 / 4 rows: the boulevard's end beside the avenue stem's first row stays stock (5..6 cells), unchanged.
- The boulevard's far ragged end (the drags' extra row, 5..6 stock cells) is unchanged everywhere, as at 6 rows.

## Files

- Code (dev/dbvx49/wt, branch child/dbvx49): `re/harness/src/sc3netmod_dbv.c`, `re/harness/src/sc3netmod_dav.c`,
  `re/tools/netmod/examples/diagonal_boulevard/manifest.json` (0.3.1: version + 8 crossing entries).
- Full package with art for stage/src: `dev/dbvx49/packs/diagonal_boulevard` (the stage copy + the 0.3.1 manifest;
  `netpack.py build` of it gives the tested table byte for byte, game files unchanged).
- Tools (verify/dbvx49, untracked): `shortx.py` (variants + emulated check), `nearmiss.py`, `overlay.py`,
  `endkind.py`, `enddist.py`, `summary.py`, `grid.py`, `finalread.py`, `shots2.py`, `compose.py`, `launch.py`,
  `runset.sh`, `picrun.sh`, `cityrun.sh`, `sweeprun.sh`, `berlin.sh`, copies of diagarm's `armlab.py` `shots.py`
  `run.py` `cmp_stage.py` `readback.py` `cityshots.py` `mapread.py` `savecells.py` `sheet.py`.
