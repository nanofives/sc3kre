# STATUS bldlook (round 2026-11-18c)

## goal
Rendered buildings (re/tools/bldimport/bldrender.py) look like stock art by default: measure stock art (resolution,
pixel doubling, palette, light, outline, texture) on 20+ stock buildings, add named render styles (`stock` default,
`clean` = the 2026-11-18b look), metrics table, side-by-side sheets z3/z4, test models growing in Sacramento.

## verdict
Styles built and measured (stock default, stock_sharp, clean = old look byte for byte). DONE: test models grew in Sacramento in the default style (531 / 517 / 94 lots at the first autosave).
Deciding facts: stock frames <= 255 colours (1,200/1,200), lit wall follows the model axis (right/left 0.81/1.27/0.81/1.23 by slot), zoom 4 = zoom 3 doubled, darker front lawn band. BUILDING_ART.md 4.1.

## built
- bldrender.py: STYLES (stock, stock_sharp, clean), style= on render_model/render_frame, $SC3BLD_STYLE, axis light, palette_cut, grain, front-edge lawn band, vibrance, luminance contrast, zoom-4 doubling
- verify/bldlook/work/: extract_stock.py, metrics.py, measure_stock.py, ours.py, tune.py, sheets.py, final.py

## proven game-side vs static only
- static: metrics vs 75 stock buildings, calibrate 0/160 frames differ, clean == old 40/40 frames, bldimport check 3/3 ok
- game-side: bld_lab run1 (verify/bldlook/runs/run1): grown 531/517/94, 9 dumps, only the known pre-load fault SC3U.exe+0x84122

## blocked on
nothing. Test buildings left installed in dev/bldlook/tree (bldimport.py restore --game dev/bldlook/tree removes them).

## files owned
- dev/bldlook/wt/re/tools/bldimport/bldrender.py
- dev/bldlook/wt/re/analysis/BUILDING_ART.md
- MAIN verify/bldlook/RESULTS.md, verify/bldlook/owner_shots/*.jpg (10), verify/bldlook/work/*.py + *.json + final_table.md (stock/ PNG dumps, try*/, sheets/, old/, testmodels/sc3build are scratch: EA pixels in stock/, do not commit)
- MAIN re/sessions/STATUS_bldlook.md
- verify/bldlook/runs/run1 (counts.json; fd PNGs and saves are run output)

## game-harness need
one windowed run of dev/bldlook/tree (Sacramento)

## asks of other sessions
- bldfile (bldimport.py owner): pass `x_bldrender.style` per model to render_model(style=) and add it to render_key; docstring line 17 'zoom 4 drawn natively' is now style-dependent
