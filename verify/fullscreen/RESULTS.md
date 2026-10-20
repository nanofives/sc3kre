# Borderless fullscreen (Alt+Enter), window memory, no resolution dropdown — 2026-10-20

Owner request 2026-10-20: "remove the screen resolution dropdown selector, resolution is driven by size of the
window and alt + enter should enter fullscreen and keep current refresh rate". Design calls the same day:
borderless (not exclusive), remember size and fullscreen like the HUD scale, leave a gap where the dropdown was.

All in `re/harness/src/sc3resize.c`, branch `child/fullscreen`. Each block has an env opt-out.

| block | what | opt-out |
|---|---|---|
| FULLSCREEN | Alt+Enter: frame styles off, window covers its monitor (`rcMonitor`), display mode never changed, so the desktop resolution and refresh rate stay. Alt+Enter again restores style + `WINDOWPLACEMENT` (maximized included). No sizing edges, no Win+Up / move / size while on | `SC3RESIZE_FSKEY=0` |
| WINMEM | `sc3resize.ini [window]` left/top/right/bottom (restored rect), maximized, fullscreen. Saved at drag end, maximize/restore, toggle. Applied once at the subclass | `SC3RESIZE_WINMEM=0` |
| RESROW | Preferencias: label `0x02F95AE3` and dropdown `0x02F95AEA` hidden (GZWIND vt+0xf4(1,0)), gap left | `SC3RESIZE_RESROW=1` shows it |
| STARTRES | GZGraphicD `FUN_10010ed1` (SetResolution) forced to 800x600, so a resolution saved by an earlier dropdown pick cannot come back | `SC3RESIZE_STARTRES=0` |

Why not the game's own fullscreen: it is exclusive mode through DD1 `SetDisplayMode(w,h,bpp)`, which has no
refresh-rate argument [GZGraphicD `FUN_10011f73`], and it has never been run as a runtime toggle.

## Session run, 3840x2160 monitor at 240 dpi, mods_launch + sc3resize only

1. Intro screen, no ini: `STARTRES> game asked 800x600x16 -> 800x600`, `WINMEM> no saved window`.
   Alt+Enter: `FULLSCREEN> on: style 0x94CF0000 -> 0x94000000, monitor [0 0 3840 2160], display mode untouched`,
   client 3840x2160. Alt+Enter: back to 800x600 at the same place, ini written.
2. Fullscreen on, quit, relaunch: `WINMEM> restored [1504 676 2336 1364], fullscreen`, client 3840x2160 from the
   first frame.
3. Europolis, maximized (ini `maximized=1`). Preferencias opened by `hudclick_arm.py --only pref`:
   `RESROW> resolution row: 2 of 2 hidden`. In-process frame dump (`pref_dialog.png`, not committed): the row
   under "Otras animaciones" is empty, every other control in place.
4. Same city, Alt+Enter twice: fullscreen 3840x2160, then back to maximized 3840x1984. Leaving passes two
   transient WM_SIZEs (3808x2072, 800x600) within 11 ms; one resize pass ran, at the final size. City and HUD
   render in both frames (`fs_pair.png`, not committed). No fault.

Not covered: owner hand test, multi-monitor (fullscreen goes to the monitor the window is on), the main menu while
fullscreen, terrain editor.
