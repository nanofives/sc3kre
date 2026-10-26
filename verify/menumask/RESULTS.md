# menumask: main-menu button edges on a different picture (child menumask, 2026-10-26)

Owner report: "is it possible to fix the transparency mask behind the elements in the main menu? since the background
image is different there's some mask issues". Shot: `MAIN\verify\menumask\owner_shots\img1_salir_shadow_patch.png`.

Verdict: fixed. A stair-step fringe in the stock picture's colours ran along every button edge. It came from two
sources, and both are gone on the owner's picture. The grey slab under the Salir door is part of the button art (the
same in the stock game) and is unchanged: no data in the game separates it from the background.

## What the menu frame is made of (stock frame, no menu_bg.bmp, dump at 1200x900)

| class | pixels |
|---|---|
| equal to the stock background (`MAIN.IXF 0x22729921`) | 379,996 |
| exact button-sprite pixels | 90,629 |
| other (label text, plus some sprite overlap) | 9,375, of which 1,698 lie outside every sprite rect |

- Buttons = 9 sheets in `MAIN.IXF`, `0x22729930..38`, 4x2 frames, RGB565, hard magenta key, no alpha. Frame-0 positions
  by exact match: Salir 91x94 at (600,427) (+ the door-closing sheet `..31` at the same spot), Cargar (413,216), MAXIS
  (90,462), Preferencias (260,373), Terreno (399,391), Nueva (111,197), Inicial (274,133), Escenario (433,70). Hover
  and animation frames sit at the same spot (all 8 buttons matched in every hover dump).
- No separate shadow sprite, no shadow pass: outside the sprite rects nothing but labels differs from stock.
- Salir's grey slab: high-pass correlation with the stock picture 0.019, and no match blurred (box 1..15) or shifted by
  up to 12 px. It is opaque art.
- Edge ring, by distance from the background:

| ring | px | mean diff from stock (/255) | blend fit `p = a*art + (1-a)*stock` |
|---|---|---|---|
| 1 | 7,585 | 69 | alpha mean 0.49, 75% within 16/255 |
| 2 | 5,351 | 148 | alpha mean 0.89, 32% within 16 (art) |
| 3 | 4,287 | 143 | art |

  So ring 1 was anti-aliased against the stock picture and shows its colours on any other picture.
- MSOPEN (2026-10-25) made it worse. Its 3x3 opening dropped 2,878 raw-background pixels in the jagged sprite edges,
  which then showed the exact stock colour (the dark tower beside the Salir frame in the owner shot).

## Fix

`MENUMASK` block in `re/harness/src/sc3resize.c` (`rz_mk_*`, `g_mk_*`), off switch `SC3RESIZE_MENUMASK=0`.
- Build at the first menu present: decode the 9 sheets from the game's `MAIN.IXF` (no shipped art). For each ring
  pixel of each frame, estimate alpha from the stock pixel and the 5x5 mean of art 2+ px deep. Result: 38,010 entries
  at 15,671 positions (log `MENUMASK> 9 of 9 sheets, 38010 ring entries (33654 blend with the picture, 4356 kept as
  drawn)`). Ring pixels with no interior art that are within 48/255 of stock take the picture.
- A frame pixel uses an entry only if its 565 value equals the entry's at that position and one of its 8 neighbours is
  raw background. Output = `p + (1-a) * (picture - stock)`.
- MENUSCALE (scaled menu): applied per bilinear tap, with the picture at the dest pixel. MSOPEN keeps a raw-background
  pixel that is a sheet's own border background next to a matched ring pixel.
- 1:1 / native 800x600: written into the frame. Our writes are tracked, so they are re-blended from the sprite value on
  the next present and never classed as background.
- Not changed: labels (their dark edge is their outline; re-blending it offline thinned the text), the Escenario
  smoke (translucent beyond 1 px), and the Salir slab (art).

## For the owner: what was the slab, what changed

`owner_shots\salir_stock_vs_before_vs_after.png`, Salir at the 2560x1351 size class, left to right:
1. the stock game with no `menu_bg.bmp` (its 800x600 frame scaled up, so the background is aligned as Maxis drew it).
   The grey slab under the door is already there. It is the button's own art.
2. the owner's picture, before (`SC3RESIZE_MENUMASK=0`): the same slab, plus a dark stair-step fringe on the door
   frame's top and right edges and along the slab's edges. That fringe is the stock picture's dark tower, baked into
   the button's edge pixels and left by MSOPEN in the gaps between them.
3. the owner's picture, after: the fringe is gone and the slab is as in the stock game.

`owner_shots\escenario_smoke.png`, Jugar escenario, same three panels. The green smoke plume and the fire are drawn
translucent over the stock picture across many pixels, not only at a 1-px edge. On the owner's picture a blue-grey haze
of the stock buildings stays around the plume and the flames, before and after alike. The ring fix cleans the sheet's
edges but not this haze. Removing it would need the plume's alpha, which the sheet does not carry (no alpha channel).
An estimate per pixel from the stock picture alone cannot tell smoke colour from transparency, so it is left as drawn.

## Checks (test tree `Simcity_stock_menumask`, all 7 mods, A/B = two games at once, one with `SC3RESIZE_MENUMASK=0`)

| case | result |
|---|---|
| owner picture, 2560x1351, idle + hover on 7 buttons | fringe gone on every button (`owner_shots\2560_*_idle.png`, `2560_*_hover.png`). Idle: all 44,691 client px that differ lie within 3 frame px of a matched ring pixel |
| owner picture, maximized 3840x1984 | same (`max_full.png`, `max_salir_hover.png`). 0 of 3,985,358 client px fed by unchanged non-ring source differ |
| owner picture, native 800x600 (FRAMEDUMP) | same treatment written into the frame (`800_full.png`, `800_salir_hover.png`). Outside the sprite rects 0 px differ |
| no menu_bg.bmp, native 800x600 | pixel-identical to the off arm (0 px differ outside the FPS text) |
| no menu_bg.bmp, 2560x1351 | edges change. MENUSCALE cover-scales the stock picture to the whole client, so even the stock picture is not frame-aligned behind the buttons and the off arm shows the same fringe (`stockpic_2560_salir.png`) |
| New City, Load City, Preferencias open (2560x1351) | dialogs unchanged. Inside the dialogs 0 px differ. Matched ring px with a dialog up: 3, 11 and 7, all background specks. An earlier build matched white Load City list pixels as anchors; the neighbour rule removed that (`dlg_*.png`) |
| dialogs closed with posted Escape | menu back, all buttons matched again |

Cost (MENUSCALE heartbeat, same minute, MENUMASK on vs off): static present compose 0.020 vs 0.021 ms. On recomposes,
about 20 vs 12 ns per recomposed rect pixel (0.53 vs 0.31 ms average per present while hovering). Table build 78 ms
(328 and 391 ms on the first runs with cold files), once per game. Memory about 5.8 MB.

Pictures: `MAIN\verify\menumask\owner_shots\` (27 PNG, left = before / `SC3RESIZE_MENUMASK=0`, right = after; the two three-panel ones put the stock game first).
Needs owner check: a look at the menu on the owner's PC with the owner's picture. The slab under Salir stays as Maxis
drew it.
