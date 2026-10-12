# PRE.md, toolicon (2026-10-12), written before any game run

Owner report: "el ícono de la herramienta seleccionada está renderizando sobre el valor de lo que estoy construyendo".
Owner config: round build inst_round1012b, sc3resize.ini [hud] scale=0 smooth=1, DPI-aware per-monitor v2 on a
dpi 120 (125%) monitor, often maximized 2560x1351.

## Static facts known before the run
- SC3 has two cursor paths. Software: a 32x32 BMP with a hotspot appended after the BMP data, loaded into a GZ image and
  handed to a cursor manager `vt+0x7c` [CONFIRMED @ SC3U 0x0047cf0f, SIMSPR 0x10056c29/0x10056e73]. Hardware:
  LoadCursorFromFileA + SetCursor (same functions, else-branch). GZGraphicD hides the Windows cursor (ShowCursor(0))
  when a "cursor" option is set [CONFIRMED @ GZGraphicD 0x100114b8].
- Which path the tool cursor uses at runtime is NOT known yet.

## Measurements (each arm: same city copy, same tool, same posted drag, grab, crop around the cursor)
- M1 stock-equivalent: no mods (launcher with no DLLs, or stock tree), 800x600.
- M2 owner build, all defaults (DPI-aware on), 800x600 and maximized.
- M3 owner build with SC3RESIZE_DPIAWARE=0.
- M4+ further opt-outs only if M2 != M1: HUDPERF=0, HUDFIX=0, HUDSCALE=0, VIEWFIX=0, sc3overscroll removed.

## Predictions (pre-registered, not assumptions)
- P1: in M1 the cost value and the tool icon do NOT overlap (owner would have reported it before otherwise). If they
  DO overlap in M1, the defect is stock and the fix is a new offset, owner design call needed.
- P2: if the tool cursor is a hardware cursor, the overlap depends on DPI awareness: under per-monitor v2 the cursor
  is drawn at the monitor's cursor scale while the label offset is in game pixels. Then M3 (DPIAWARE=0) removes it.
- P3: if the tool cursor is software (drawn into the frame), DPI awareness does not change cursor size in frame
  pixels, and the cause is a draw-order or offset difference introduced by a frame-compositing mod (HUDPERF/HUDSCALE).
- Grabs are desktop-DC BitBlt: a hardware cursor is NOT in them. So "icon visible in grab" is itself evidence for P3.

## Addendum, written after M2/M3 and before the first run of the fix (TIPCURSOR)
- P5: fix on, DPI-aware, CursorBaseSize 80, dpi 120: log "anchor box 92", hooked anchor [mx my mx+92 my+92], label top
  my+94 (physical), clear of the 80 px icon (opaque rows 2..77).
- P6: fix on, SC3RESIZE_DPIAWARE=0: box ceil(80/1.25)+12 = 76 game px, label top 78 game px = 97.5 physical below.
- P7: SC3RESIZE_TIPCURSOR=0: anchor box 44 (shipped), log says disabled.
- P8: SC3RESIZE_TIPCURSOR_PX=32: box 44, "(shipped)" in the log (the default-pointer layout is unchanged).
- P9: cursor within the box size of the view's right or bottom edge: anchor [mx-92 my-36 mx my-20], label above-left.
