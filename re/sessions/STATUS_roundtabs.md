# STATUS roundtabs (2026-11-02)
goal: rounded Ver datos tabs (Graficas + Cuadros), same colours / selected look / rows / click areas.
verdict: done. Own drawn shape kept (the game's pill art not reused: it has no top-only rounding and a tab needs the joined selected look).
Shape class takes 4-point polygons only (7 and 28 point outlines drew skewed or as a chamfer), so each tab is stacked rects with a circle-derived corner stair (R=5 at 1x, inner layer R=4, 1 px border layer under a fill layer). DLGSCALE scales the page surface, so the radius scales with it.
built: dev/roundtabs/inst/sc3resize.dll. Switch SC3RESIZE_VDTABSROUND=0 = old trapezoid tabs (SC3RESIZE_VDTABS=0 still = stock).
proven game-side: one check, Berlin 2560x1351, both pages, pictures verify/roundtabs/owner_shots (antes/despues + crop). Click areas unchanged (button rects same code). Not tested: tab clicks after the change.
files owned: re/harness/src/sc3resize_vdtabs.c, re/harness/src/sc3resize_vdbars.c (env parse line), re/sessions/STATUS_roundtabs.md, verify/roundtabs/
blocked on: nothing. Lab runs landed in verify/graphaxis/runs (v1*, w1*, x1*; gitignored scratch, delete).

## second pass 2026-11-02
Radius 9 px at 1x (half the 18 px tab), 6-step corner, 2 px gaps between tabs, rule stops 4 px short of the selected tab corners (stray pixel gone). One posted click per page checked: Graficas Economia, Cuadros Salud.
