# hwseam: painted highway cell | stock highway cell, made seamless (2026-10-18)

Owner feedback on the T: "make it more seamless the transition between a regular piece and the beginning of the T
piece". Fixed in the shared painter `re/tools/netmod/hwpaint.py` (+30 lines, `task hwseam`); T art rebuilt.

## Causes and fixes (hwpaint.py)
1. **Dashes.** `deck_top_colour` re-drew the lane dashes on every hw deck from the world arc length: where `dash_on`
   held on the dash band it took the stock pixel if light, else `LL.white()`, so the whole band went white for half of
   each period: short blocky double dashes where stock 73 / 15051 have a thin line. Now a STRAIGHT hw deck on an axis
   (heading within about 1 degree, the existing `smooth` test) reads the stock frame at the same share across and
   world along-coordinate, dashes included (`_axis_plain`). Curving hw decks keep re-drawn dashes; ramp decks and the
   diagonal bands are unchanged (the bands already sampled their own dashes).
2. **1 px holes across the deck at a cell's cut edge** (a dark dotted line at painted | stock borders): the stock frame
   stops short of the cell edge, the sample was transparent and the fallback only stepped across the road. It now
   steps along the road too (holes measured offline: 52 -> 0 per border).
3. The across-step is skipped on the outer parapet edge (past it the stock frame is empty on purpose). It is kept at
   the inner curb: without it the median showed 1 px beige dots in game (seen on run 3, fixed on run 4).

Tried and reverted: a 1 px vertical shift of the painted geometry at zoom 4. The offline strip said stock zoom-4
frames sit 1 px low (zoom-4 differing px 1612 -> 1041), but in game the shifted art opened a 1 px gap at the median
(double line). [UNCERTAIN] why `netart.preview` and the game differ there: the anchor conventions agree. Do not tune
vertical registration offline.

## Evidence
- Offline, `hwpaint.py proof`: straight 73 / 15051 zoom 4 near 0.970 -> 0.975, exact 0.969 -> 0.972; diagonal bands
  and curve 15127 identical to the old painter.
- Offline strip (straight highway, one painted cell between stock cells, all 4 views): zoom-4 dash pixels identical
  to stock; `MAIN\verify\hwseam\owner_shots\hwseam_offline_strip.png` (stock | old | new). That sheet was made with
  the zoom-4 shift still in; the dash and hole fixes it shows are the ones kept.
- In game (test tree Simcity_stock_highways, city lab4_saved.sc3 copies, T at (105,86) turn 2, camera 103,85, zoom 4
  views 0..3 and zoom 3 views 0..3): before = old art (PID 37360), after = final art (PID 27180). Thin stock dashes on
  the T's through-highway cells, no dotted border lines, continuous median. Sheet:
  `MAIN\verify\hwseam\owner_shots\hwseam_sheet.png`; raw shots `MAIN\verify\hwseam\game\{before,after}_z*_r*.png`.
- Not checked in game: the stem side at zoom 3 in every view one by one (covered by the full-view shots only).

## Other packages (after the T is approved)
- `hwx_cloverleaf`: through highways are straight axis hw decks (`hwx.py` 390-391): affected. Rebuild art + pad
  (`hwx_build.py art examples/hwx_cloverleaf --jobs 8`, `pad`), lanes and manifest unchanged.
- `highway_diagonal_cloverleaf`: its straight highway is two axis hw decks (`hwdx_paint.py` 93, 96): affected. Rebuild
  `hwdx_paint.py art` + `pad` (slow, all pieces).
- `highway_dd_cloverleaf`: both highways are `highway_diag` bands, no axis hw deck: the change does not reach it
  (proof on the band pieces identical to the old painter). No rebuild needed.
