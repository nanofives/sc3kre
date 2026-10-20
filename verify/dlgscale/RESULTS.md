# DLGSCALE: dialogs enlarged with the HUD factor, capped to fit — 2026-10-20

Owner, 2026-10-20: "when i adjust the scaling to my 4k screen, opening a dialog like "reunirse" lowers the FPS, also
the Reunirse popup is not scaled, neither any other menu". Design call the same day: scale dialogs with the HUD factor,
capped to fit, and find the Reunirse slowdown. Code: DLGSCALE block in `re/harness/src/sc3resize.c`, notes in
`re/analysis/HUD_SCALE.md` "Dialogs enlarged too". `SC3RESIZE_DLGSCALE=0` keeps dialogs native.

## Session run (Europolis, 3840x1984 maximized on a 3840x2160 monitor at 240 dpi, HUD scale Fit 3.307x, smooth on, sc3resize only)

| dialog | native | enlarged | input checked |
|---|---|---|---|
| Reunirse | 383x354 | 1266x1170 (3.305x) | advisor button (depth 0) opened "Concejales finanzas"; "Discutir" dropdown opened enlarged, "Informes" picked inside its loop (depth 1); close box closed it |
| Preferencias | 480x472 | 1587x1560 | "Ver consejos al iniciar" toggled; X (cancel) closed it; resolution gap still there |
| Indagar (query) | 423x320 | 1398x1058 | "Declarar historico" toggled at depth 1; check button closed it |

Drag by the title bar: first build moved the dialog 118 px for a 300 px drag (the game moves a dialog by the native
distance from the press, and the map caught up one frame late at 5 fps). Fixed by mapping the cursor 1:1 from the
press point once the dialog's native origin moves: (300, 200) of cursor moved the enlarged dialog exactly (300, 200).

Cost, 10-s windows: 6.2 to 6.4 ms per frame in the pre-present pass without a dialog, 9.9 to 10.6 ms with Reunirse open.

## The Reunirse slowdown

Not caused by HUD scale or DLGSCALE. Same Reunirse test, 25 s before and 25 s with the dialog open (ddraw Blts per
second, BLTBEAT):

| setup | before | Reunirse open |
|---|---:|---:|
| native 800x600, scale off | 4,883 | 1,373 |
| 4K maximized, scale off | 1,070 | 277 |
| 4K maximized, Fit | 891 | 265 |

Static read (worker report, 2026-10-20): the main pump SC3U `FUN_0046135a` never sleeps, Reunirse opens non-modal
through SIMUI `FUN_100034d4` (no `Sleep(0)` modal loop), takes no pause or UI hold, and its portraits have no timer.
Runtime (sc3perf CSV, 1-s rows, same city and window): with sc3perf loaded (`sysmem=1`, the shipped perf.ini, cap 60)
there is no drop: 60 fps with Reunirse closed and open, scale off and at Fit with DLGSCALE. What the dialog adds is
surface Locks: 60 -> 3,150 per second (scale off), 240 -> 3,330 (Fit). sc3perf's idle time under the cap went from
~650 to ~530 ms per second at Fit, and the game thread was 55% idle with the dialog open (profile `ropen`). Without
sc3perf the game draws in video memory, where each Lock waits for the GPU, which fits the Blt counts above falling while
time inside Blt fell too. The code that issues those ~55 Locks per frame is not identified yet `[UNCERTAIN]`.
An A/B with `SC3RESIZE_DIALOGS=0 SC3RESIZE_HOLD=0` was void: the dialog opened off-screen at 4K coordinates inside the
800x600 client.

Not covered: owner hand test, dialogs at the main menu (MENUSCALE path, not touched), tooltips of dialog controls that
fall outside the dialog's own rect.

## sc3perf overlay scaled too (owner hand test 2026-10-20)

Owner: "in game the profiling indicator/FPS should scale with interface too". Then: "it looks stretched out in game",
"not centered in the main menu", design call "top-left of the window on the menu too".
- `sc3resize` exports `sc3resize_ui_scale()` (HUD factor of the last enlarged present, percent, 100 when off) and
  `sc3resize_menu_rect(LONG *r)` (the scaled main menu's 4:3 rect, 0 when not the menu).
- `sc3perf` draws the FPS and busy lines with a TrueType monospace (Consolas bold) at the stock font's cell height
  times the factor, line step 16 times the factor, save area 800x92 times the factor. The stock raster font could only be
  widened, which is what looked stretched. At 100 the stock font and area are used as before.
- On the scaled main menu it draws after the present on the window DC at its top-left, at the menu factor (rect width /
  800), instead of into the 800x600 frame, which does not reach the window corner.
Owner hand test on the 3840x1984 maximized window, Fit (log: `overlay text at 330%` menu, `331%` city): overlay and
dialogs look right.

120 fps: not testable that evening. The only display is a Philips TV over HDMI; with the TV off Windows lists
3840x2160@120 from the EDID but reverts to 60 Hz, so sc3perf's cap (-1 = monitor refresh) is 60.
