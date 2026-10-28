# STATUS edgeload (2026-10-28)

## goal
Owner crash: "Big One" 1024 autosave loaded from the main menu on MARIANO-PC (maximized, client 2560x1351, 120 dpi,
HUD scale 1) dies at once: VEH FAULT 0xC0000005 WRITE at GZGraphicD+0x253E, one page past a surface.

## verdict + deciding RVA
FIXED. Reproduced, fixed, A/B in the same build (switch off = same fault). verify/edgeload/RESULTS.md.
- GZGraphicD FUN_1000239d (zoom-scaled 16bpp sprite blit), 2x branch, 0x1000253C / 0x1000253E: each source row goes to
  dest rows y and y+1. For an odd dest height the last pass writes the row at the dest bottom, one past the rect.
- At zoom 4 the iso Init SIMSPR FUN_10005b42 makes the view origin even (param_5/6 & ~1 when zoom > 3), so a doubled
  sprite clipped at the surface bottom has an odd height exactly when the surface height is odd. 1351 is odd. 600 and
  1984 (the autosave3 test geometry) are even, which is why LIVING-PC never reproduced it.
- sc3resize pads the surfaces it recreates with 8 guard rows (2026-08-30). A city made while the window is already at
  size gets its render target from the game's Init (call [eax+0xc](w, h) at SIMSPR 0x10005cf8 or 0x10005df1, the load
  took 0x10005df1), unpadded. sc3resize's layout pass would pad it, but the readiness gate holds it 3 s, and the load's
  first full repaint draws in that window.
- Fix INITSLACK (sc3resize.c, own block, SC3RESIZE_INITSLACK=0 off): both Init create sites add RZ_SURFACE_SLACK rows
  to the height, except at native 800x600.

Second crash, found while testing, not reported by the owner: sc3perf.dll+0x6D9F (ov_copy, src NULL) 50 s after the
load (run 1). A present nests: sc3resize's Blt hook (chained after perf_blt) issues full-client Blts inside it (RCI
repaint, src NULL), and the nested perf_blt restored the outer call's overlay pixels through the global g_ov_saved.
FPS overlay is on by default (owner log: overlay=1). Fix OVNEST (sc3perf.c, SC3PERF_OVNEST=0 / perf.ini ovnest=0):
only the outermost Blt draws the overlay, and each call restores only what it saved.

## built
dev\edgeload\inst: sc3resize.dll, sc3perf.dll (rest from 0585798). Builds clean.

## proven game-side vs static only
Game-side, LIVING-PC, restored window client 2560x1351 at 240 dpi, owner's bigcity.ini, HUD scale 1, zoomextra 1:
- before: Big One.autosave2 (-City) -> LCENTER #2 (584,22) -> GZGraphicD+0x253E WRITE 0x139AB000, regs as the
  owner's. Frida probe on 0x1000239d: dest [336 1250 520 1351] into a 2560x1351 raster, region 0x699000 bytes,
  row 1351 unmapped past x=492.
- after: INITSLACK> #1 2560x1351 -> 2560x1359; raster 1359 from the first blit; 0 blits reach the last row; alive.
- main menu Load City (dialog navigated to the tree's Cities by posted keys): Big One.autosave2 and plain Big One
  both load, INITSLACK #1, no fault.
- control SC3RESIZE_INITSLACK=0, same build: the same fault (WRITE 0x1C203000).
- even-height control, INITSLACK=0 at client 2560x1350: unpadded surface, same camera (584,22), no fault, alive 60 s.
- main menu autosave2 load alive 76 s after the load.
- Big One.autosave1 lands at (574,30) (sparse land at the bottom edge) and did not fault before the fix either.
- OVNEST: static fix + the run 1 stack. The nesting did not recur in runs 4-7, so the fixed path was not seen live.
Static only: why the load took the 0x10005df1 path (the 0x118/0x20 checks in Init).

## blocked on
nothing

## files owned
- re/harness/src/sc3resize.c (INITSLACK block after REPAINT8, env read next to SC3RESIZE_REPAINT8)
- re/harness/src/sc3perf.c (OVNEST in perf_blt, cfg "ovnest")
- verify/edgeload/RESULTS.md (in dev/edgeload/wt)
- re/sessions/STATUS_edgeload.md (written in MAIN, per CHILD_PROTOCOL)
Pictures (not for git): verify/edgeload/owner_shots/

## notes
- `cp` of the owner's Big One.sc3 into tree\Cities wrote over its hard link to the base. Bytes identical (same
  SHA-256 in base, MAIN and evidence), so nothing changed. Use netpack-style delete-then-copy next time.
- A csrss "SC3U.exe - Error del sistema: no se encontro UV.dll" box from another launch sits on screen. Not mine, left.

## game-harness need
own tree only (dev\edgeload\tree). No re/harness claim needed.

## asks of other sessions
none
