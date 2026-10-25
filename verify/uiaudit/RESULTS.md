# uiaudit: where HUD scale (Auto) is not done right, 2026-10-25

Report only, no code changed. Build: main `ba6cfe7`, all 7 mods + `version.dll` built from `Simcity_wt_uiaudit` into
`Simcity_stock_uiaudit`. HUD scale Auto, Suavizado on, Zoom extra on (defaults).

Two size classes, both driven with posted input only (sc3io), pictures from `SC3RESIZE_FRAMEDUMP` / `MENUSCALE_DUMP`:

| class | client | HUD factor | how |
|---|---|---|---|
| this PC maximized (3840x2160 at 250%, dpiaware) | 3840x1984 (3808x1984 restored) | 3.307 | `sc3io maximize` |
| owner MARIANO-PC | 2560x1351 | 2.252 | `sc3io resize 2560 1351` |

Raw frames: `fd/` (`a_*` menu 3840, `b_*`..`m_*` city 3840, `o_*`..`x_*` 2560). Picked crops: `owner_shots/`.
Logs: `sc3resize_run_3840.log`, `sc3resize_run_2560.log`, `sc3resize_run_2560b.log`, crash runs
`sc3resize_zoomcrash2_2560.log`, `sc3resize_zoomcrash3_hudoff.log`.

**HSCENSUS over all runs: 0 `NOT SCALED`, 0 `KEPT NATIVE` lines.** Every window the HUD pass collects was enlarged
(5 HUD classes, 14 dialog sizes, the tooltip class `SC3U+0xD3BCC` in 25 sizes, flyout `SIMUI+0xA9CC8`). So the defects
below are not "missed" windows. They are wrong copies, upscaled content the game could draw natively, and one caller
that reads the factor wrong.

## Ranked defects (most visible to a player first)

| # | element | how to reach | HSCENSUS | 3840 (3.307x) | 2560 (2.252x) | picture | likely owner code |
|---|---|---|---|---|---|---|---|
| 1 | **Tooltips on dialog controls drawn twice** (advisor names in Reunirse, any dialog tooltip) | open Reunirse, hover an advisor portrait | `SC3U+0xD3BCC 100x16: cost label, enlarged` | two copies: one enlarged with the dialog, clipped at the dialog's left edge ("oncejales finanzas"), and a second enlarged copy far away | same: second copy in the middle of the dialog | `owner_shots/01_dialog_tooltip_doubled_2560.png`, `01b_..._3840.png`; frames `t_dlgtip`, `c_dlg_tip` | COSTLABEL / task uiscale `rz_hl_add` path in `rz_hs_collect` (`sc3resize.c` ~5174). A cursor on an enlarged DIALOG is mapped by DLGSCALE, not `rz_hs_mouse`, so the tooltip reads as "cursor in the city" and is drawn as a city cost label at the stale TIPCURSOR point `g_tip_mx/my`. Log: `COSTLABEL> city label [1032 588 1132 604] -> [1128 687 1353 723] 2.252x, cursor (1200,600)`; (1200,600) was the last city cursor, not the advisor. The DLGSCALE pass also copies the native tooltip inside the dialog, so it shows twice |
| 2 | **Hide-UI leaves the enlarged minimap map on the city** | minimap "_" button (hide UI) | while hidden: `HUDSCALE> 1 window(s) enlarged` (corner widget only) | not captured (my hide click at 3808 did not take) | the minimap diamond stays drawn over the city while every other HUD part is gone, until unhide | `owner_shots/02_hideui_minimap_left_on_city_2560.png`; frames `s_hide`, `s_hide2` | MININAT `mn_compose` (`sc3resize.c` ~6518): no visibility test on `g_mn_mini`. `rz_hs_collect` skips hidden windows BEFORE it updates `g_mn_mini`, so the pointer keeps the hidden minimap and the twin is composed each frame (`MININAT> 0 twin draws, 50 frames composed`). Likely cause, not proven by a fix |
| 3 | **Ver datos (data map) dialog: the map is upscaled, pixelated** | views flyout -> "Ver datos" (Mapa de aura etc.) | `SIMUI+0xA4D64 424x440: dialog enlarged` | the 379x379 map-view resampled 3.3x, blocky stair steps, as the minimap was before MININAT | same at 2.25x | `owner_shots/03_verdatos_map_upscaled_2560.png`, `03b_..._3840.png` | DLGSCALE resample. The map is the same map-view class as the minimap's map (`SIMUI+0xa7e68`, child of the dialog at local [2 6 381 385]), so the MININAT approach (a twin drawn at the factor) would apply here too |
| 4 | **FPS / profiler overlay not scaled in the terrain editor** | New City -> terrain editor (Editar Terreno) | `SIMUI+0xA4D64 172x480: dialog enlarged`, `0 window(s) enlarged` | not checked | overlay text at native size (about 11 px tall) while the panel is enlarged; in the city it is 225% | `owner_shots/07_fps_overlay_terrain_editor_2560.png` vs `07b_fps_overlay_city_2560.png` | `sc3resize_ui_scale()` (`sc3resize.c` 6941) returns 100 unless `g_hs_n > 0`. The terrain editor has no HUD windows, only a dialog, so sc3perf's UISCALE draws at 100% |
| 5 | Load / Save city preview map | Cargar Ciudad, Guardar ciudad (in city and at the menu) | `478x353: dialog enlarged` | city preview diamond upscaled, soft and blocky | same | `owner_shots/04_load_preview_map_upscaled_2560.png` | DLGSCALE resample of the dialog's preview picture. Whether the game can draw it at another size is `[UNCERTAIN]` (for an unloaded city it comes from the save file, not read) |
| 6 | Main menu Load City list: specks of the menu picture inside the white list | main menu -> Cargar Ciudad | n/a (menu) | a few 1-3 px dark-blue specks in the white list area | not checked | `owner_shots/05_menu_loadcity_list_specks_3840.png`; frame `a_menu_load` | MENUSCALE background mask `g_ms_bg`: list pixels whose colour equals the stock background at that spot are classed as background and replaced by `menu_bg.bmp` (mask = 255 at (542,232) inside the list, measured) |
| 7 | All dialog text and art soft | every dialog (budget, graphs, ordinances, query, Preferencias, Reunirse) | `dialog enlarged` (14 sizes) | 3.3x bilinear: readable, soft | 2.25x: readable, soft | `owner_shots/06_graphs_soft_text_3840.png`, `06b_query_dialog_2560.png` | by design (DLGSCALE resamples the native dialog; native text would need option D). Listed so the owner can judge |
| 8 | Main menu and its dialogs soft | main menu, New City, Preferencias, Load City, Load Terrain, Salir | n/a | the 800x600 frame resampled 3.3x | 2.25x | `fd/a_menu_*.png`, `fd/o_*.png` | by design (MENUSCALE resamples the 800x600 menu frame; the art is 800x600) |

## Checked and right at both sizes (scaled, placed right, clicks land)

Side panel and all 9 category flyouts, sub-menus by press-hold (zones, Ver datos), HUD button tooltips (enlarged
next to the button, `floating, enlarged`), bottom bar, news ticker, date and funds, pause/play buttons, RCI, minimap
frame, buttons and the native-drawn map (MININAT, sharp), the in-minimap clock, the city cost label during a zone drag
(enlarged below the pointer, log `below the pointer`), Reunirse and an advisor page, budget and its income tab, the
budget "?" popup, ordinances (checkbox click hit), neighbour deals map, loans, graphs (Gráficas), charts (Cuadros),
Capas de la ciudad + Vista de capas (Crimen applied and reverted), query dialog (Indagar, Copiar ID), Guardar ciudad,
Cargar ciudad, the "¿Quieres guardar esta ciudad?" box, Preferencias in the city, terrain editor panel and its tooltips
area, unhide UI, Cargando box, main menu dialogs (all MENUSCALE, soft as row 8).

## Side findings (not scaling, but seen during the tour)

- **Crash: CITYZOOM x2 step at client 2560x1351.** The first zoom-in past zoom 4 ends the process silently. Last log
  line every time: `CITYZOOM> zoom in at zoom 4: step x1 -> x2 (client 2560x1351 allows x2)`. No VEH FAULT, no Windows
  Application event. 3 of 3 on Europolis, two with HUD scale Auto and one with `SC3RESIZE_HUDSCALE=0`, so it is not
  HUDSCALE. Not tried at 3840x1984. Sent to the orchestrator during the run.
- **Opening Ver datos stalls the game.** sc3perf CSV shows 0 presents for 144 s at 2560 (t=213 to 356 s) after the
  click, about 2 minutes at 3840 too. Cause `[UNCERTAIN]`, no A/B with mods off was run.
- At 3840, with the modal query dialog open, the window was minimized from outside (not by this session) and
  re-maximized; the next frames for about 30 s showed the whole HUD and the dialog native. A second restore brought the
  enlarged layout back. Not reproduced at 2560 without a minimize. `[UNCERTAIN]`.

## Not covered (needs owner check or not reached)

- Real-mouse behaviour (hover with a real cursor, minimap drag-pan, pan arrows): hard rule, posted input only.
- City zoom x2 / x3 frames: blocked by zoomcrash (the child that owns the crash).
- Newspaper, petitioner popups (none pending in Europolis), disaster trigger menu, reward / landmark menus beyond the
  flyout, message boxes other than the save question, 1024 maps, live resize drag with dialogs open.

## Correction to the audit

Row 4 understated it: in the terrain editor the PANEL itself was not enlarged either (HSCENSUS logged `dialog enlarged`,
but the pass stopped at `n <= 0` because no HUD window was up, so nothing was drawn enlarged). The audit frames
`fd/p_terrain*.png` show it native. Fixed with #4 below.

## Fixes (owner picked #1, #2, #4, #6), 2026-10-25

Worktree `Simcity_wt_uiaudit` (child/uiaudit at main `54bf548`), one file: `re/harness/src/sc3resize.c`, four blocks, each
with an off switch; doc section in `re/analysis/HUD_SCALE.md`. No edits near the CITYZOOM / ZOOMCENTER code.
Checked as an A/B: two games at once from the same build, arm A with the four switches at 0 (= current main), arm B
default. Frames `fix_A/`, `fix_B/`, logs there (`sc3resize*.log`). Posted input only, windows at the bottom of the
Z-order, never topmost or foreground.

| # | block, off switch | what changed | 2560x1351 | 3840x1984 | pictures |
|---|---|---|---|---|---|
| 1 | TIPDLG, `SC3RESIZE_TIPDLG=0` | a tooltip on an enlarged dialog is enlarged with that dialog, once | A: two copies (clipped one at the portrait, second in the dialog body). B: one whole tooltip at the portrait, log `TIPDLG> dialog tooltip [1032 588 1132 604] -> [784 515 1009 551] with its dialog [1040 470 1423 824] (2.251x)` | same: A two copies, B one (`-> [1214 769 1545 822]`, 3.305x) | `owner_shots/fix1_dialog_tooltip_2560_before_after.png`, `fix1_..._3840_...` |
| 2 | MINIVIS, `SC3RESIZE_MINIVIS=0` | MININAT twin composed only while the minimap is visible | hide UI on Europolis: A keeps the minimap diamond on the city, B shows only the city and the unhide button | same | `fix2_hideui_minimap_2560_before_after.png`, `fix2_..._3840_...` |
| 4 | DLGONLY, `SC3RESIZE_DLGONLY=0` | the pass runs when only a dialog is up; `sc3resize_ui_scale()` reports the factor while a dialog is enlarged | terrain editor: panel `[2388 435 2560 915] -> [2173 135 2560 1215]` 2.25x, FPS text 225% (sc3perf `UISCALE> overlay text at 225%`); click on "Aceptar este Terreno" in the enlarged panel mapped (`DLGSCALE> down (2380,1140) -> native (2480,881)`) and started the city | panel `-> [3272 199 3840 1786]` 3.30x, FPS text 331% | `fix4_terrain_panel_2560_before_after.png`, `fix4_fps_overlay_terrain_2560_before_after.png`, `fix4_terrain_3840_after.png` (before = audit frame `fd/p_terrain2.png`; arm A crashed entering the editor at 3840, see below) |
| 6 | MSOPEN, `SC3RESIZE_MENUSCALE_OPEN=0` | MENUSCALE composes from the 3x3 opening of the background mask | A: specks in the Load City list, B: none. 81 client pixels differ between the arms, all inside the dialog | A specks, B none (170 px differ, all inside the dialog) | `fix6_menu_loadcity_list_2560_before_after.png`, `fix6_..._3840_...` |

Regression checks in arm B: HUD tooltip on the side panel still enlarged next to its button (`COSTLABEL> floating ...
cursor on the HUD ... -> enlarged`); the city cost label during a zone drag still the enlarged label below the pointer
(`COSTLABEL> city label ... below the pointer`); the menu picture outside the dialog unchanged (pixel diff above).

### Seen during the fix runs, not caused by these changes, not fixed

- **Arm A (switches off = current main) crashed entering the terrain editor at 3840x1984** (New City, Pequeña):
  `VEH FAULT 0xC0000005 at SIMSPR.DLL+0x47B70, READ addr=0x00000000`. 1 of 1 for A, 0 of 1 for B on the same steps.
  Log `fix_A/sc3resize_crash_terrain3840.log`. Not investigated.
- **The whole enlarged HUD can stay on screen after hide UI** (bar, panel, minimap with frame and buttons), while
  `uiwin_dump` shows the HUD windows hidden. Seen in arm B after a session with resizes in the terrain editor and a
  hide/unhide in an empty city, and in the audit run at 3808x1984 after a restore/resize, with the old code. A fresh B
  launch straight into Europolis hid cleanly at both sizes. Trigger not isolated `[UNCERTAIN]`.
