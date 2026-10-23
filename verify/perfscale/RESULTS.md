# perfscale RESULTS (2026-10-23)

Owner: de-maximizing the windowed game leaves the FPS / profiler text unscaled.

Cause (menu only): `sc3resize.c` MENUSCALE native branch (800x600 client, ~line 4262) returned without clearing
`g_ms_on`. `sc3resize_menu_rect` kept returning the last scaled 4:3 rect, so sc3perf `draw_overlay_menu` drew the
text on the window at the old 330% scale, clipped (`owner_shots/before_menu_restore_330pct_clipped.png`).

In a city the path was correct in every size tried (800x600 native, 1600x1000 at 167%, 3840x1984 at 331%): `city_*.png`.

Fix: `g_ms_on = 0` in that branch, switch `SC3RESIZE_PERFSCALE=0` restores the old behaviour.
Check, menu, maximize -> restore -> maximize: native text after restore (`after_menu_restore_native.png`), 331% after
re-maximize (`after_menu_remax_331pct.png`).
Not tested: restore to an intermediate size above 800x600 at the menu (that path already sets g_ms_on every present).

## City, second pass (orchestrator request)
Europolis, sim running, restored size set to 1200x900 client first: maximize (3840x1984, 331%) -> restore by title-bar
double-click (WM_NCLBUTTONDBLCLK) -> 1200x900, text 150% correct; maximize -> restore by SC_RESTORE (button path) ->
1200x900, text 150% correct (`city_restore_1200x900_*.png`, UISCALE log 331% / 150% alternating). The city path never
reproduced: the bug is menu-only (cause above). Limits: this PC is dpi 250% (client 3840x1984), not MARIANO-PC's dpi 120
(2560x1351), so that exact size class was not run; the factor logic is size-driven (Auto = min(cw/800, ch/600)).
