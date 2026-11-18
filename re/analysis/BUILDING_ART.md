# BUILDING_ART.md: how a stock building's art is laid out, and how a 3D model becomes one (task bldrender, 2026-11-18)

Owner request (round 2026-11-18b): a folder of 3D models becomes zoned buildings that grow next to the stock ones. This
file is the art spec, measured on the stock files and read in the SIMSPR draw code, and the manual of the tool that
renders an OBJ into that art (`re/tools/bldimport/`). The packaging recipe is the proven one of
`BUILDING_PICK.md` 6 C and `re/tools/batgrow.py`. Results in game: `verify/bldrender/RESULTS.md`. SIMSPR.DLL
addresses are Ghidra VAs, image base 0x10000000. Census numbers come from every stock building exemplar
(`{0x207EDC0E, 0x57E, id}` over `Apps\Res\Occupant\*.IXF`) whose prop 0x67 names a `0x6300` table.

## 1. A building's art in one paragraph

The exemplar's prop 0x67 names a `BIN\r` frame table of 20 frames (5 zooms x 4 rotation slots). Frame k is zoom
`k // 4`, slot `k % 4`; the engine draws frame `zoom * 4 + ((state + viewRot) & 3)`, state = the sprite instance's
`+4 >> 30` [CONFIRMED @ SIMSPR 0x1005aeab, vtable 0x10068ca8 slot 0x68, reached from slot 0x14 0x1005ad34].
Frames 0-15 are 4 zooms of own art; frames 16-19 re-use the zoom-3 records at scale 2. Each record is a format-1
sprite (RGB565, colour key 0xF81F) plus an 8-byte anchor `{L, T, R, B}`; the anchor's (L, T) pixel lands on the
footprint's LEFT ground vertex. The picture carries everything: the lot ground, the building, trees, fences and a
soft shadow, all baked into one bitmap. No mask, no separate shadow, no night or animation frames on a plain house.

## 2. Measured layout (census of the stock buildings)

Example: Meek Cr. (115, class 3300, 1x1) and Ike's House (3077, class 3500, 2x2), both in `CSATTRIB.IXF`, pixels
in `00000002_Residential.DAT`:

| zoom | 115 sizes (slots 0-3) | 115 anchor (L, T, B) | 3077 sizes | 3077 anchor (L, T, B) |
|---|---|---|---|---|
| 0 | 8x6, 8x7, 8x6, 8x6 | (0, 3-4, 3) | 16x10, 16x9, 16x11, 16x11 | (0, 4-6, 5) |
| 1 | 16x12 .. 16x13 | (0, 7-8, 5) | 32x18 .. 32x21 | (0, 9-12, 9) |
| 2 | 32x22 .. 32x24 | (0, 13-15, 9) | 64x35 .. 64x42 | (0, 18-25, 17) |
| 3 | 64x42 .. 64x46 | (0, 25-29, 17) | 128x70 .. 128x84 | (0, 37-51, 33) |
| 4 | = zoom 3, scale byte 2 | = zoom 3 x 2 | = zoom 3, scale byte 2 | = zoom 3 x 2 |

Rules, over the 221 stock R/C/I buildings with a 20-frame one-layer table (3,536 frames at zooms 0-3):

- **Width = n x (8 << zoom)**, n = lot size: 3,536 of 3,536. **L = 0**: 3,536 of 3,536. The horizontal clip of a
  cell is the footprint, `n * (8 << z)` px from the left vertex [CONFIRMED @ SIMSPR 0x1000be25: width
  `cell+10 << (zoom + 3)`], so the art never leaves the lot sideways.
- **B = n x W / 4 + 1** (the bottom vertex of the lot plus the 1 px rim): 3,476 of 3,536; the rest 0, +2 or +4 px.
- **T** = how far the art rises above the left vertex; free. `R == w - L`, `B == h - T` on 7,744 of 7,744 frames.
- **Zoom 4**: frames 16-19 name the records of 12-15 with frame byte +1 (scale) = 2: 1,908 of 1,936 frames. The
  scale doubles the size and the anchor at draw time [CONFIRMED @ SIMSPR 0x10001272, 0x100014e7, 0x1000138b]. A
  frame with scale 0 and its own zoom-4 record draws natively (network art does it on 8,924 of 8,940 frames, NET_ART 4).
- **Header**: 474 of 611 building tables are `BIN\r` v1, SprInstCLSID 0x7300, ZoomCount 5, RotCount 4, +0x0e 4,
  +0x0f 20, AnimFrames 1, RegRects 0, draw flags 0, 20 frames (field names: SIMSPR reader 0x10001c90, NET_ART 8.1).
  The rest: 0x7302 tables with 144 / 576 frames (3 zooms x 48: larger animated sets), 0x7310 with 16-192 (2 zooms,
  animation frames). Draw flags 0 = no first-pass bit and no terrain-under bit (0x40, `0x100192aa`), so the engine
  draws no terrain under a building: the art must paint the whole lot diamond, which every stock frame does.
- **Pixels**: record header d0 0x107, d1 0x80000, d2 / d3 = width / height on every frame read; RGB565, key 0xF81F
  (SPRITE_MODDING.md; the alpha cut is at 128, opaque magenta is nudged one step blue).

## 3. Where the art lands (draw point, multi-cell lots, slots)

- Projection (NET_ART 2): cell draw point `x = (vz - vx) * (4 << z)`, `y = (vx + vz) * (2 << z) - alt * (1 << z)`
  [CONFIRMED @ 0x1000be25]. The sprite's (L, T) pixel goes on that point [CONFIRMED @ 0x1000138b].
- An occupant of size n is inserted once with its size byte: `InsertCellAlignedSprite` (cISC3CitySpriteManager slot
  0x4c, 0x100192aa) reads the occupant's position (vt+0xb8) and size (vt+0xd4) and calls the cell map's `Insert`
  (0x10007b4d) with them. Insert writes the same sprite into all n x n cells with the frame's T / B (cell +4 / +6)
  and stores in each cell (`+8`, `+9`) = (x + n - 1, z), and marks the four corner cells (flags 0x20 / 0x40 / 8 /
  0x10) [CONFIRMED @ 0x10007b4d].
- The display-list builder takes a cell with size >= 2 through `FUN_1000c678`: view coordinates of (x + n - 1, z)
  (`FUN_1000a62c`), then per view rotation r1 `vz += 1 - n`, r2 `vx += n - 1, vz += 1 - n`, r3 `vx += n - 1`
  [CONFIRMED @ 0x1000c678]. That is the cell with the largest vx and the smallest vz of the footprint: its left
  vertex is the footprint's left vertex. So for every lot size the registration point is the left vertex of the
  whole lot diamond, consistent with L = 0, width n W and B = n W / 4 + 1 above.
- Slot r + 1 is slot r turned 90 degrees counter-clockwise on screen, measured on network art (NET_ART 6); the
  rendered test models drawn in the four view rotations in game match the stock houses around them
  (`verify/bldrender/owner_shots/03`).
- **Grown buildings do not turn to their road.** In a Sacramento autosave 16,322 of 16,450 buildings are saved with
  rotation 0 (occupant record bits 30-31, occupant_layer.py), 13,392 of 13,573 in shipped Berlin; for 1x1 lots
  with one road neighbour the road is on each of the four sides in about equal numbers (stock 435 / 380 / 384 / 386,
  imported 88 / 74 / 84 / 77). So the face a player sees depends only on the view rotation. [The developer code that
  gives state 0 was not read; the evidence is the saves.] This tool puts **the model's front on the lower-right face
  in slot 0**, the side the stock shopfronts of 156 and the entrance of 3020 show in slot 0.
- `FUN_100159e2` (the occupant sprite's slot 0x14) adds per-(zoom, rotation) offsets from the tables at
  `0x10062ae0` / `0x10062b30` when byte +0x11 is set [CONFIRMED]. The byte is set from flag 0x20000000
  (`FUN_100158ef`), which `0x100192aa` passes to the attached second-layer sprite only (`vt+0x60` child, `vt+0x50
  (0x20000000)`) [CONFIRMED]. A one-layer building table has no child, so the offsets do not apply to it
  [UNCERTAIN at runtime: not watched live].

## 4. The renderer (`re/tools/bldimport/bldrender.py`)

No Blender: Blender is not installed on LIVING-PC, and the engine's projection is a closed formula, so a small numpy
rasteriser draws in the game's own geometry. Same frame as netart (NET_ART 9.2): tile coordinates of slot 0, u
towards the top vertex, v towards the bottom vertex, h up, 1 cell = 1 unit,

```
x = (u + v) * W / 2,   y = (v - u) * W / 4 - h * W * cos(30 deg) / sqrt(2)        W = 8 << zoom
```

(the 30 degree camera that makes the 2:1 diamond; one altitude unit = 0.20412 cells, netart_blender ALT). Depth for
the z-buffer = the camera forward of netart_blender. Each frame: 4 x 4 supersampling (8 x 8 at zooms 0-1), box
filter, alpha cut at 50 % coverage, RGB565 quantisation exactly as the exporter expands it, magenta nudged.

**Calibration** (`bldimport.py calibrate`): the lot diamond of an empty lot against the stock frames below the
registration row (always lot ground). With a sub-pixel offset of the registration point per zoom and a growth of
the lot per zoom and lot size (`bldrender.CALIB`), **0 differing pixels on 160 of 160 frames**: 1x1 115 / 3065 /
126, 2x2 3077 / 3020 / 141, 3x3 3011 / 176, 4x4 3028 / 3071, zooms 0-3, every slot, and the flat tile 39 at zooms
0-4. Stock lots of 2x2 and larger are one pixel wider per side at zooms 1-2 than 1x1 lots: the growth is per size.

**Zoom 4** depends on the render style (section 4.1). `stock` (the default since 2026-11-18c) writes the zoom-3 frame
pixel-doubled, anchor x 2, as its own scale-0 record: the same pixels the stock scale-2 frames draw, so the lot edge
has the stock 2 px steps. `clean` and `stock_sharp` render zoom 4 natively (128 px per cell): sharper, and the lot
edge is tile 39's native zoom-4 edge (exact), the edge stock roads draw next to houses.

**Model axes** (classifier page convention, Blender's OBJ export default): metres, Y up. OBJ +X -> u, +Z -> v,
+Y -> h. The footprint's bounding box is centred on the lot, the lowest vertex sits on the ground. `scale` multiplies,
`rotate_deg` turns the model counter-clockwise seen from above before it is placed. **Front = +Z** (what faces the
viewer in Blender's front view after an OBJ export) -> lower-right face in slot 0 (section 3).

**Size**: 16 m per lot cell (classifier page convention). The engine has no metre unit (no "metre" / "feet" string
or tuning parameter found in SC3U strings or SYS.PAK). Checked by eye against stock: a 10 x 8 m cottage with a 7.8 m
ridge fills a 1x1 lot like Meek Cr. (115) and Pitched Roof Cottage (3065) do, and a 22 x 12 m, 13 m block sits on a
2x2 lot like the stock 2x2 houses (`verify/bldrender/owner_shots/`). Change it per model with `x_bldrender.cell_m`.
[UNCERTAIN: an engine-side meaning of the cell size does not exist to measure; the value is a visual match.]

**Light** (style `clean`): sun direction (v, u, h) = (0.30, -0.80, 1.25) normalised, ambient 0.50, diffuse 0.62:
roof brightest, the lower-left face lit, the lower-right face in shade in every slot. Shadows from an orthographic
shadow map along the sun, a shadowed sample keeps 35 % of its direct light. Ground: procedural lawn (no game pixels),
base colour from the measured stock lawn (mean RGB 86 / 118 / 70 over 5,540 green pixels in the lower quarter of nine
stock 1x1 / 2x2 lots). The `stock` style replaces most of this (section 4.1).

**Materials**: OBJ `usemtl` + MTL `Kd` colours, `map_Kd` textures (PNG / JPEG, nearest texel, wraps). Vertex
normals are not used: faces are flat-shaded, two-sided (a face turned away from the camera is lit from its back).

### 4.1 What makes stock building art look the way it does, and the render styles (task bldlook, 2026-11-18c)

Measured on 75 stock growables (every growable class x lot size, the first two plain 20-frame members of each
class's rule families), 16 frames each (zooms 0-3, slots 0-3), 1,200 frames. Tools and full tables:
`verify/bldlook/RESULTS.md`, scripts in `verify/bldlook/work/` (`extract_stock.py`, `metrics.py`). "Structure" =
opaque pixels that are not lawn green (G > R + 8 and G > B + 8 of 255).

| what | stock | clean (2026-11-18b) |
|---|---|---|
| colours per frame | <= 255 on 1,200 of 1,200 frames (zoom 3 median 248, max 255) | up to 343 |
| zoom 4 | zoom 3 doubled (1,908 of 1,936 census frames); 2x2 blocks equal 100 % | native, 45 % |
| zoom 3 native? | 2x2 blocks equal 4 %: real zoom-3 detail, not zoom 2 doubled | 38 % (flat faces) |
| lit side, zoom 3 right / left luminance, slots 0-3 | 0.81 / 1.27 / 0.81 / 1.23 | 0.88 / 0.88 / 0.76 / 0.91 |
| structure contrast (p90 - p10) / p50, zooms 3 / 2 / 1 / 0 | 1.23 / 0.94 / 0.70 / 0.51 | 0.65 / 0.63 / 0.53 / 0.39 |
| structure saturation, zoom 3 / 0 | 0.225 / 0.106 | 0.132 / 0.031 |
| texture (mean abs luminance - 3x3 mean), zoom 3 | 0.045 | 0.019 |
| dark lawn share (< 0.7 x lawn median), zooms 3 / 2 / 1 / 0 | 0.18 / 0.10 / 0.04 / 0.00 | 0.02 / 0.01 / 0.00 / 0.01 |
| lit lawn RGB, zoom 3 / 0 | 94/136/73 / 114/137/104 | 97/128/76 / 88/118/70 |

Findings:

1. **The lit wall follows the model's axis, not the screen.** In slots 0 and 2 the lower-left face is the light one,
   in slots 1 and 3 the lower-right. With the slot rule (u, v) -> (v, n - u), that is the model's +-u walls light and
   +-v walls dark in every slot: the same world-axis rule as the stock highway walls (memory
   project-wall-lighting-lit-twins). Grown lots keep state 0 (section 3), so in view rotations 1 and 3 every stock
   house is lit on its lower-right face. The `clean` style lights the lower-left face in every slot, the opposite
   of its neighbours in two of the four views.
2. **8-bit palette per frame.** No stock frame holds more than 255 colours (plus the key): the art went through a
   per-frame palette before the RGB565 export.
3. **The lawn is darker along the two front edges of the lot** (heat map of dark lawn pixels over every 1x1 and
   2x2 lot, all slots), not in a cast shadow beside the building. Measured as the dark-lawn share above.
4. **The roof is not the brightest surface**: on 3020 and the 1x1 houses the lit wall is lighter than the roof.
5. Stock contrast, saturation and dark-lawn share fall at the smaller zooms; the lawn gets lighter (zoom 0
   114/137/104 against zoom 3 94/136/73).
6. Smaller zooms are not box filters of the next one: zoom z against zoom z + 1 box-halved differs by 13-14 of 255
   (mean abs, all three pairs); separate renders per zoom, as bldrender does.

**Styles** (`bldrender.STYLES`, `render_model(..., style=)`; None = `$SC3BLD_STYLE`, else `stock`):

| style | light | zoom 4 | colour | surface |
|---|---|---|---|---|
| `stock` (default) | axis light: ambient 0.47 + roof 0.42 x up + 0.37 x abs(n.u) + 0.20 x abs(n.v); screen sun only for cast shadows, which fall on surfaces facing it; shadow strength 0.25 / 0.40 / 0.55 / 0.70 at zooms 0-3 | zoom 3 doubled | vibrance 2.6 / 2.2 / 2.0 / 2.0 (less on already saturated colours), luminance contrast 1.4 / 1.2 / 1.3 / 1.35 about 0.42, 255-colour median-cut palette per frame, lawn per zoom fitted to the stock lit lawn | smooth two-octave grain (6 px and 2 px) 0.12-0.30, front-edge lawn band 0.3 cells deep, 0.10-0.62 dark |
| `stock_sharp` | as `stock` | native | as `stock` | as `stock` |
| `clean` | screen sun (above) | native | as 2026-11-18b | flat |

`clean` renders byte for byte what the 2026-11-18b renderer did (40 of 40 frames compared). `calibrate` still gives
0 differing pixels on 160 of 160 frames (the styles do not move the lot diamond). The fitted values come from the 6
test and sample models measured the same way as the stock set; the table per style is in `verify/bldlook/RESULTS.md`.
What the styles do not reach: stock p10 (dark detail: windows, eaves, porches) is 0.20 at zoom 3 against 0.24, and
the stock texture comes from painted detail the test models do not have, so the measured texture stays 0.032
against 0.045. More model detail closes both; a global filter would not.

How to choose a style today: `bldimport.py` (owned by bldfile this round) does not pass one, so the default
`stock` applies, or set `SC3BLD_STYLE=clean|stock|stock_sharp` for the run. The render cache key covers
`bldrender.py` but not the variable, so after changing it run `bldimport.py build --force`.
[Proposed for bldimport: an `x_bldrender.style` key per model, passed to `render_model` and added to the cache key.]

## 5. Packaging (`re/tools/bldimport/bldimport.py pack`)

Same containers as batgrow (proven in game, verify/batconvert): exemplar copied from the class's stock base building
of the same lot size (batgrow.class_table) and re-keyed to the new id (38000-38999), frame table (the base's header,
20 own entries, scale 0) in the overlay `CSAttrib_Korea.IXF`, 40 pixel + anchor records in a new
`Res\Sprites\B1D10001_bldimport.DAT` (group 0xB1D10001, keys `id << 16 | frame`), the name in every overlay
`SC3StringsNetpack.IXF`, and a weighted `Key:` line first in every family the class grows from. Ids are kept per
model file in `<folder>\sc3build\ids.json`, so a saved city keeps finding its buildings after a rebuild.

## 6. Commands

```
py -3.12 re/tools/bldimport/bldimport.py build   <folder> --game <game>    # render (cached) + pack + install
py -3.12 re/tools/bldimport/bldimport.py check   <folder> --game <game>    # read the installed files back
py -3.12 re/tools/bldimport/bldimport.py restore --game <game>             # take them out again, byte for byte
py -3.12 re/tools/bldimport/bldimport.py preview <folder> --game <game> --out x.jpg [--zoom 4]
py -3.12 re/tools/bldimport/bldimport.py calibrate --game <game>           # section 4, exit 1 on any difference
py -3.12 re/tools/bldimport/make_testmodels.py <folder>                    # the three test models + models.json
```

## 7. Open items

- Non-square lots (the classifier writes [n, n] only; every stock base is square): not supported.
- glTF / FBX: OBJ only this round.
- Grown lots keep state 0 (section 3): read from saves, the developer's placement code not read.
- Zoom 4 native edge vs stock zoom-3-doubled lots: a 1 px step can show between neighbouring lots at zoom 4 with
  `clean` / `stock_sharp`; `stock` (default) doubles zoom 3 like the stock lots.
- Per-model render style in `models.json`: needs a bldimport change (section 4.1).
