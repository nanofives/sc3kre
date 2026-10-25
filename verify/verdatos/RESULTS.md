# verdatos: the Ver datos data maps drawn by the game at the dialog factor (child/verdatos, 2026-10-25)

Owner request: the "Ver datos" data maps (views flyout -> Ver datos: aura, crime, pollution...) drawn natively at the HUD
scale, not upscaled, the same way the minimap now is (uiaudit RESULTS row 3).

## Cause and how the dialog works

- The dialog (SIMUI+0xa4d64, 424x440, container ctor `FUN_10044021`) holds one panel per data view (10 panels, ids
  0x5fa..0x603). Each panel has its own map view (vt `0x100a7e68`, 379x379 at panel-local (2,6), made once in
  `FUN_10045df2`). A view switch hides one panel and shows another (`FUN_10044aa6`). 11 map-view objects were alive in the
  dialog, measured live.
- The native texture is already at the game's cap: side `379 x 0.7071 = 268` -> 256 (`FUN_100436b4`). DLGSCALE then
  resamples the whole dialog by 2.25x (2560x1351) or 3.3x (3840x1984), so the map came out a 379 px picture enlarged.
- The view draws into the client-sized UI composite at client coordinates, not into a raster of its own as the
  minimap's does. The legend, compass and option boxes are sibling windows drawn after it, and the legend box overlaps
  the diamond.
- The map takes no clicks (view+0xd0 stays 0, and a posted click on it moved nothing). It follows the city rotation
  (minimap rotate buttons). Clicking the compass did nothing.

## Fix (sc3resize.c, VERDATOS block, `SC3RESIZE_VERDATOS_NATIVE=0` turns it off)

- A twin of the view that draws inside an enlarged dialog (the game's Clone, as MININAT), sized
  `2*round(189 x factor)+1` (851 at 2.25x, 1251 at 3.3x) with its own raster.
- The game draws the twin after the native view drew, only when the native view's pixels, its state or the factor
  changed. A still view redraws 16 times a second with the same pixels.
- Texture past the game's 256 cap, up to twice the city's cells: 512 for a 256-cell city, 1024 for a 1024-cell city
  (`SC3RESIZE_VERDATOS_TEX=<side>` caps it).
- DLGSCALE pastes the twin 1:1 right after it draws that dialog. It goes only where the twin drew and the frame's native
  pixel is still the view's own, as row runs, also written into DLGSCALE's enlarged cache.
- Freed when the view shuts down (the dialog destroys its views on close), on a view switch or rotation, and after 1 s
  unused.

The MININAT draw hook is shared (the vt+0x144 wrapper now hands non-minimap views to VERDATOS, and it is installed even
with `SC3RESIZE_MINIMAP_NATIVE=0`). `rz_hd_draw` publishes the dest box it recomputed. Doc:
`re/analysis/HUD_SCALE.md` last section.

## Check (Simcity_stock_verdatos, all 7 mods + version.dll from the worktree, windowed, HUD scale Auto)

Arms: A = main b93b77c build (Europolis only), B = this build, C = this build with `SC3RESIZE_VERDATOS_NATIVE=0` (Seoul,
Europolis 1024). Posted input only (sc3io PostMessage, SetWindowPos without z-order change, SetWindowPlacement), pictures
from `SC3RESIZE_FRAMEDUMP`.

| case | result | picture (`owner_shots/`) |
|---|---|---|
| Europolis 256, 2560x1351, aura | twin 851x851, texture 512. Cells are hard-edged diamonds and roads 1 px lines, where the old map was soft | `01_europolis_aura_2560_before_after.png`, `01b_..._zoom3x_...` |
| legend corner over the diamond | legend box, text and bevel stay the resampled dialog's, map up to the box | `01c_europolis_legend_corner_2560_zoom2x_before_after.png` |
| Europolis, maximized 3840x1984, crime | twin 1251x1251. Coverage circles are thin lines (were blurred bands) and the crime cells are crisp. The "after" here is the first prototype build (texture 1024); the final build uses 512 for 256 cities, which looks the same (512 vs 1024 compared on aura) | `02_crime_3840_before_after.png`, `02b_..._zoom3x_...` |
| all 10 data views, 2560 | each switch: old twin freed, new clone, one twin draw (44 to 183 ms), then skipped | tour frames `fdB/u_*.png` |
| rotate (minimap rotate buttons) | rotation 135 -> 225 -> 135: twin re-cloned each time, map and compass turned | `03_rotated_2560_after.png` |
| drag the dialog | dialog moved, twin followed with it | `04_dragged_2560_after.png` |
| close | twin freed by the view's Shutdown, no leftover on the city | `05_closed_no_leftover_2560_after.png` |
| Seoul 256, 2560 and 3840, arms C/B | same result on aura, density, fire coverage and crime | `seoul_*_before_after.png` |
| Europolis 1024, 2560, arms C/B | texture 1024 for the 1024-cell city: every road ring and block of each district is visible, the old map showed blobs | `e1024_zones_2560_zoom3x_before_after.png`, `e1024_crime_*` |
| `SC3RESIZE_VERDATOS_NATIVE=0` | no VERDATOS lines, map resampled as before (arm C) | `seoul_*` left halves |

Cost, from the `VERDATOS>` 10 s lines:
- Still dialog: 0 px copied, 0.23 to 0.41 ms per frame (2560) for the compare of the map rect.
- Twin draw: once per open, switch or rotation, and with the sim running about every 20 s (a data refresh). It takes
  29 to 183 ms with texture 512 and 172 to 324 ms with texture 1024 (1024 city).
- The whole HUD pass was 17 to 34 ms per frame in both A and B, with two games sharing the CPU.

## Texture size vs cost (orchestrator follow-up, 2026-10-25)

The rule asked for (smallest of 256/512/1024 at or above the on-screen size) is the one the build already uses:
- It is measured on the texture axis, which runs along the diamond's edge (602 px at 2.25x, 885 px at 3.3x). The
  diamond's width (851 / 1251 px) is its diagonal.
- So a 1024-cell city gets 1024 at both sizes: 1 cell per texel, not 4.
- The one extra cap, at twice the city's cells, only changes 256-cell cities (512 instead of 1024). There the layers
  repeat each cell, and 512 and 1024 gave the same picture.

Measured on Europolis 1024 with `SC3RESIZE_VERDATOS_TEX=256 / 512` and the default, two games at once:

| texture | twin draw at 2560 (open, view switch, rotation, data refresh) | at 3840 | still dialog, ms per frame | picture (`owner_shots/`) |
|---|---|---|---|---|
| 256 | 44 to 49 ms | 44 to 101 ms | 0.36 to 0.72 | road rings of whole districts missing (4 cells per texel) |
| 512 | 81 to 120 ms | 88 to 104 ms | 0.33 to 0.46 | rings visible but broken into dashes |
| 1024 (default for a 1024-cell city) | 172 to 366 ms | 311 ms | 0.27 to 0.44 | continuous rings, every block |
| 512 on a 256-cell city (default there) | 29 to 183 ms | 44 to 101 ms | 0.23 to 0.41 | same as 1024 |

Comparison pictures:
- `e1024_zones_2560_tex_compare_zoom3x.png` (256 | 1024)
- `e1024_aura_3840_tex_compare_zoom3x.png` (256 | 512 | 1024)

The per-frame cost does not depend on the texture: it is the compare of the 379x379 native rect.

**1024 is not too slow on a 1024 city:**
- Its 0.2 to 0.37 s redraw happens only on open, view switch or rotation. With the sim running (speed 3) it happened
  once (222 ms) in about 50 s.
- In that run the game itself ran at 0 to 15 fps, with frames up to 21.9 s, with the dialog open and after closing it.
  That is the 1024-cell sim with two such games on one PC, and it dwarfs the redraw.
- `SC3RESIZE_VERDATOS_TEX=512` is the cheaper setting if a hitch on view switch is unwanted.

**Minimap twin (report only, MININAT unchanged):**
- Its twin is 289 px at 2.25x and 425 px at 3.3x, so its texture axis is 204 px and 300 px against a 256 texture.
- At 2.25x the texture is already denser than the screen. At 3.3x it is 1.17 px per texel.
- 512 texels would be sampled at 1.7 per screen pixel, so at most 300 / 256 = 1.17x more detail can show, for about 2x
  the texture build.
- A raise only pays on a much larger minimap. Not worth it at today's factors.

Seen in these runs, not caused by VERDATOS:
- One `TEX=256` game crashed while loading Europolis 1024 at 800x600, before any HUD pass or VERDATOS hook:
  `VEH FAULT 0xC0000005 at SIMSPR.DLL+0x47B70, READ addr=0`. That is the same address uiaudit logged entering the
  terrain editor (log `logs/B_tex256_e1024_load_crash_SIMSPR47B70_sc3resize.log`).
- 7 first-chance faults in `KERNEL32+0x1CA9E` at 0.4 s, from `sc3netmod.dll+0x4DC08` / `+0x257A8` (startup probes).

## Stall when opening Ver datos (uiaudit side finding)

Not reproduced, so no stock / sc3resize-only A/B could place it:
- With all mods: 3 opens on Europolis (2560 twice, 3840 once), 3 more on Seoul in each of two arms, 1 on Europolis 1024
  in each arm. Also all 10 views and "Usar mapa", which puts the data view on the minimap.
- Worst case was a single 1.6 to 2.1 s frame at an open or a maximize, the same in the arm with VERDATOS off. Then the
  game ran at 30 to 100 fps.
- The audit's 144 s with 0 presents remains `[UNCERTAIN]`: its trigger is not known, and the audit's sc3perf log of
  that run was not kept.

## Seen, not changed

- VERDATOS takes any map view inside an enlarged dialog, not only Ver datos. Only Ver datos was checked.
- During a drag, a few frames log `map view ... is not inside its dialog - not taken`: the dialog rect has moved before
  the view redrew. Those frames keep the previous twin at the new place.
