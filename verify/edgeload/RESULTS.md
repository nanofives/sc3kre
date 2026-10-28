# RESULTS - edgeload (2026-10-28): 1024 autosave crashes on load from the main menu

Child of "SC3 mods page layout + autosave rotation + load crash". Worktree `dev/edgeload/wt` (branch `child/edgeload`,
from main 0585798 = sc3mods-2026-10-28b), tree `dev/edgeload/tree`. Posted input only, pictures from the in-process
dump (the PC's monitor was asleep, desktop composition stale at 8:12, so desktop grabs were useless).

## Verdict

Reproduced on LIVING-PC and fixed. Cause: GZGraphicD's 2x sprite blit writes one row past an odd-height render
target, and a city created at the current window size gets its render target from the game, without the guard rows
sc3resize adds to the surfaces it creates.

## Cause

- GZGraphicD `FUN_1000239d` is the zoom-scaled 16bpp sprite blit. Its 2x branch writes each source row to dest rows y
  and y+1 (`0x1000253c mov [edx],esi` / `0x1000253e mov [edi+edx],esi`). For an odd dest height its last pass still
  writes row y+1, which is the dest bottom, one row past the rect. [CONFIRMED @ GZGraphicD 0x1000239d]
- At zoom 4 the iso Init `FUN_10005b42` clears bit 0 of the view origin (param_5/6 & ~1 when zoom > 3), so doubled
  sprites start on even rows. A sprite clipped at the surface bottom has an odd height exactly when the surface height
  is odd. Owner: 2560x1351, 1351 is odd. 600 (stock) and 1984 (the autosave3 test, 3840x1984) are even, so neither
  ever writes past the end. That is why autosave3 could not reproduce it. [CONFIRMED @ SIMSPR 0x10005b42]
- sc3resize pads every surface it recreates with `RZ_SURFACE_SLACK` = 8 guard rows (zoom-crash fix, 2026-08-30).
  When the window is already at size before Load City, the game's Init creates the render target iso+0x74 itself at
  2560x1351 (`call [eax+0xc](w, h)` at SIMSPR `0x10005cf8`, or `0x10005df1` on the path this load took). sc3resize's
  layout pass would pad it, but the readiness gate holds it 3 s. The load's first full repaint draws in that window.
- The write faults only when the next page is unmapped. 2560x1351x2 = 0x698C00 bytes, rounded to a 0x699000 region,
  so row 1351 fits in the region tail up to x = 511 and faults from x = 512.

## Evidence (LIVING-PC, restored window client 2560x1351 at 240 dpi, owner's bigcity.ini, HUD scale 1, zoomextra 1)

| run | build / switch | city, path | result |
|---|---|---|---|
| 1 | 0585798 | Big One.autosave1, `-City` | LCENTER #2 (574,30), no fault in the load. Died 50 s later in sc3perf (section B) |
| 2 | 0585798 | Big One.autosave2, `-City` | LCENTER #2 (584,22), VEH FAULT GZGraphicD+0x253E WRITE 0x139AB000, regs ebx=4185 esi=41854185 edi=1400 as the owner's |
| 4 | fix | Big One.autosave2, `-City` | `INITSLACK> #1 ... 2560x1351: allocated 2560x1359`, no fault, alive 77 s |
| 5 | fix | Big One.sc3 (plain), main menu Load City | INITSLACK #1, LCENTER #2 (566,41), alive |
| 6 | fix | Big One.autosave2, main menu Load City (dialog navigated to the tree's Cities) | INITSLACK #1, LCENTER #2 (584,22), no fault, alive 76 s after the load |
| 7 | fix, `SC3RESIZE_INITSLACK=0` | Big One.autosave2, `-City` | `INITSLACK: disabled`, VEH FAULT GZGraphicD+0x253E WRITE 0x1C203000 |
| 8 | fix, `SC3RESIZE_INITSLACK=0`, client 2560x1350 (even) | Big One.autosave2, `-City` | render target unpadded (h 1350), LCENTER #2 (584,22), no fault, probe: 0 odd-height 2x blits at the last row, alive 60 s |

Frida probe on `0x1000239d` entry, run 2 (before the fix): dest raster vtable GZ+0x1E894, 2560x1351, a 2x call with dest
[336 1250 520 1351] (height 101), surface bits 0x13312028 in the region 0x13312000 size 0x699000, row 1351 unmapped at
the rect's right end. Fault 0x139AB000 = region end. Run 4 (fixed): the same raster reports h = 1359 from the first
call and no 2x call reaches its last row.

Run 8 is the parity control: the same camera on an unpadded surface one row shorter, even height, does not fault.

The owner's log matches run 2 line for line: "fresh city view already at 2560x1351", DEFER (< 3000 ms), LCENTER #2
(584,22), REPAINT8 #2, DIRTCLIP x10, then the fault. Autosave1 puts the camera at (574,30): no doubled sprite
crosses the bottom edge past x = 511 there, so it loads without a fault. The owner's 13:47 crash was most likely
autosave2. The file name is not in the log.

## Fix A: INITSLACK (sc3resize.c, own block after REPAINT8)

Both Init create sites (`SIMSPR+0x5ced`, `+0x5de6`, the same 14 bytes, checked before patching) jump to a stub that
adds `RZ_SURFACE_SLACK` rows to the height, except at the native 800x600. The guard rows are never presented (the view
rect stays w x h), and the poll's settle check already accepts h..h+8. This matches the state every resized surface has
been in since 2026-08-30. Log: `--- INITSLACK: ...` at start, `INITSLACK> #n ... allocated WxH+8` per city.
Off switch: `SC3RESIZE_INITSLACK=0`.

## B. Second crash found while testing: sc3perf overlay restore on a nested present

Run 1, 50 s after the load, no input: 0xC0000005 READ 0 at sc3perf.dll+0x6D9F = `ov_copy` with src NULL (`mov eax,
[esi]`). Stack: sc3perf+0x79D5 twice (return from the chained Blt) and +0x79F0 (return from ov_copy), VEH
in_rci_repaint=1. perf_blt chains to sc3resize's Blt hook, and that hook issues its own full-client Blts inside it
(RCI corner repaint, src NULL). Those come back through perf_blt, which read the outer call's global `g_ov_saved` and
restored the overlay onto a NULL surface. The FPS overlay is on by default (owner's sc3perf.log: overlay=1), so the
owner can hit this too. It was not in the owner's report, and it is not what crashed at 11:35 / 13:47.

Fix OVNEST (sc3perf.c, perf_blt): only the outermost Blt draws the overlay, and each call restores only the pixels it
saved, on its own src. A nested final Blt logs `OVNEST> #n ...` (first 3). Off switch: `SC3PERF_OVNEST=0` or
perf.ini `[perf] ovnest=0`. Static fix plus the stack above. The nesting did not recur in runs 4-7 (no OVNEST line), so
the fixed path has not been seen live.

## Pictures (`verify/edgeload/owner_shots/`, not for git)

- `autosave2_mainmenu_2560x1351_fixed.png` (+ `_half`): the owner's case, main menu Load City, fixed build
- `autosave2_2560x1351_loaded_fixed.png` (+ `_half`): same file by `-City`, fixed build
- `bigone_plain_mainmenu_2560x1351.png` (+ `_half`): plain Big One from the main menu

## Not covered

- MARIANO-PC itself, maximized (here: restored window with the same client size). The owner check: load
  "Big One.autosave2" from the main menu, maximized.
- Other odd heights and the device surface iso+0x4ec (also created by the game without guard rows). No 2x blit into
  it was seen, so it is left alone.
- The OVNEST path live (B).

## Test notes

- Reproduce without the owner's display: put a `[window]` rect in `inst\sc3resize.ini` that gives the client size,
  launch without `SC3RESIZE_WINMEM=0` (`sc3dev run` sets it), so the window is at size before the city is created.
  Then `-City "Big One.autosave2.sc3"`.
- The game's Load City dialog ignores typed paths ("no es valido"). Navigate with posted keys: click a list row,
  Down to the folder, Enter opens it (posted double clicks do nothing). The list sorts in ASCII order (uppercase first).
- The in-process DUMP can catch a frame before the HUD pass; take a second one.
- `cp` over a hard-linked file in the tree writes the base in place. `Big One.sc3` was copied over its link here. The
  bytes were identical (same SHA-256 as the base and MAIN), so nothing changed.
