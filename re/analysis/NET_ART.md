# NET_ART.md: network piece art, measured, and the kit to make new art (task artkit, 2026-10-13)

Owner intent: bring NEW art into the game for network pieces whose geometry does not exist in stock (new ramps,
junctions), not recolours. This file is the geometry spec (measured on the stock files and read in the SIMSPR draw
code) and the manual for the three authoring routes. Tools: `re/tools/netmod/netart.py` (kit),
`netart_blender.py` (runs inside Blender), `plant.py` (cells into a save copy), `netpack.py` (packaging).
Proof: `verify/artkit/RESULTS.md`. SIMSPR.DLL addresses are Ghidra VAs, image base 0x10000000.

## 1. A piece's art in one paragraph

A network piece's exemplar names a CSATTRIB frame table of 20 frames (40 for layered bridge pieces). Frame k is
zoom `(k % 20) // 4`, rotation slot `k % 4`. Each frame is a pair of records in a `Sprites\*.DAT`: a 16-bit sprite
(format 1, colour key) and an 8-byte anchor. The engine draws frame `zoom*4 + ((state + viewRot) & 3)`
[CONFIRMED @ SIMSPR 0x1005aeab, 0x10015b57], with the piece state from `piece+0x10 >> 30` [CONFIRMED @ SIMNTWRK
0x10023c14], and puts the anchor's registration point on the cell's LEFT ground vertex. Nothing else about the
picture is read: no alpha mask, no per-frame offset on this path.

## 2. Projection

Per-zoom constants set by the zoom setter `0x10006752`: tile width `8 << z`, tile height `4 << z`, `1 << z` px per
altitude unit [CONFIRMED @ 0x10006752]. Cell draw point, same formula in both draw-list builders
[CONFIRMED @ 0x1000be25, 0x1000d0f5]:

```
screen_x = (vz - vx) * (4 << z) - originX
screen_y = (vx + vz) * (2 << z) - alt * (1 << z) - originY
```

with `(vx, vz)` the view coordinates of the cell (`FUN_1000a62c`: r0 `(x, z)`, r1 `(H-1-z, x)`, r2
`(W-1-x, H-1-z)`, r3 `(z, W-1-x)`). The inverse `0x1000a33a` maps the pixel `(x + W/2, y)` back to the same cell,
so the draw point is the diamond's left vertex at its vertical centre [CONFIRMED @ 0x1000a33a]. At zoom 4 the view
origin is forced even [CONFIRMED @ 0x10006752].

| zoom | tile W x H | px per altitude unit | flat tile frame | its anchor (L, T) | rows of the diamond |
|---|---|---|---|---|---|
| 0 | 8 x 4 | 1 | 8 x 5 | (0, 2) | 5 |
| 1 | 16 x 8 | 2 | 16 x 9 | (0, 4) | 9 |
| 2 | 32 x 16 | 4 | 32 x 17 | (0, 8) | 17 |
| 3 | 64 x 32 | 8 | 64 x 33 | (0, 16) | 33 |
| 4 | 128 x 64 | 16 | 128 x 64 | (0, 31) | 64 |

Flat tile = piece 39, every slot identical (`netart.py geometry`). The stock diamond is the exact 2:1 diamond plus a
1 px rim (section 6). Elevated highway 73: frames 8x9 .. 128x128, T 6/12/24/48/95, so the deck sits 4 altitude
units up (4 << z px), which matches the altitude rule above.

Tile coordinates used by the kit (slot 0): u from the left vertex to the top vertex, v from the left vertex to the
bottom vertex. Offset from the registration point: `x = (u + v) W/2`, `y = (v - u) W/4 - e W/64` (e = height in
zoom-3 px). In view rotation 0 the slot-0 edges are: +x = SW (lower left), -x = NE, +z = SE, -z = NW (from the
draw formula: a +vx neighbour shares the left-to-bottom edge).

## 3. The anchor record

Type-1 record = 4 signed i16 `{L, T, R, B}` (SPRITE_SII.md). Over all 8,940 network frames `R == w - L` and
`B == h - T`, no exception, so only (L, T) carries information. The engine places the sprite's pixel (L, T) on the
draw point: dest rect `{x - L, y - T, x + R, y + B}` [CONFIRMED @ 0x1000138b]. T and B also become the cell's
vertical clip range (cell record +4 / +6, built into the clip rect `{left, y-T, left + n*(8<<z), y+B}`)
[CONFIRMED @ 0x10007b4d, 0x1000be25]. L and R are not used for that clip: the horizontal clip is the footprint,
`n * (8 << z)` px from the left vertex, so art must stay inside the footprint horizontally.

## 4. Frame table details

- Frame byte +1 (called "flag" in netcat) is a signed SCALE: 2 draws the referenced record at 2x with doubled
  anchors (buildings' zoom 4 reusing zoom-3 art). Applied at 0x10001272 (size), 0x100014e7 (anchors), 0x1000138b
  (dest rect), 0x100011c7 (hit test); the blit takes a stretch path (GZGraphicD 0x100022b1). Network pieces ship
  their own zoom-4 art (scale 0 on 8,924 of 8,940 frames).
- Header layout and the first-pass bit: section 8.1.
- RotCount is not consulted by the index (`zoom*4` is a literal) [CONFIRMED @ 0x1005aeab].
- Size limits: none in pixels on the decode path (stack buffer below 0xc011 bytes, heap above, 0x1001de49). T and
  B are s16. The real limit is the cell clip (section 3 and 8).

## 5. Pixels

- Format 1 only: all 8,940 network frames (QFS header d0 0x107, d1 0x80000, d2/d3 = width/height on every one).
- RGB565, key 0xF81F (magenta). The archive's key is magenta converted to the display format
  [CONFIRMED @ 0x1001da94]; a bitmap in another pixel format is converted in place [CONFIRMED @ GZGraphicD
  0x1000294c].
- Alpha masks (format 0, the 1,139 records): no network frame uses one, and the occupant blit draws exactly one
  bitmap per frame with no paired mask lookup [CONFIRMED absence @ 0x1000163a]. Network art needs none.
- Alpha is a cut at 128. Opaque magenta is nudged one step blue (sprite_patch.image_to_surface).
- The framebuffer expands 5/6/5 by shifting, the exporter by scaling: compare in 5/6/5.

## 6. Rotation slots and the stock rim

- Slot r+1 shows slot r turned 90 degrees counter-clockwise on screen, `(u, v) -> (v, 1 - u)`. Measured over the
  flat ROAD frames at zooms 2-3 (`netart.py check-rot`): 372 pairs, overlap >= 0.6 in 341, median 0.938; the
  clockwise turn gives median 0.595. The low pairs are partial pieces (ramps, bridge ends).
- The stock flat diamond covers one more pixel on its edges than a pixel-centre rasterisation of the exact diamond.
  Region masks clamp sample points onto the tile so a region that ends at an edge keeps that rim (otherwise a
  dotted seam shows between cells; seen and fixed in the first roundabout preview).

## 7. What a frame of ANOTHER size needs

Only the two records: the pixel record with header d2/d3 = the new width/height, and an anchor `{L, T, w-L, h-T}`.
`sprite_patch.record_from_image` + `anchor_payload` write them; netpack takes the registration point from
`png_dir/anchors.json` (`{"z3_r0.png": [L, T], ...}`), so any PNG listed there may have any size (selftest U11).
`.SII` files are text mirrors of 10 archives only; netpack writes its own containers, which have none, and nothing
in the draw path reads them. netpack also gives a frame its own record when its new art differs from another frame
that shared the stock record.

## 8. Taller-than-base frames: the cell clip

Arm D of the proof: a variant whose zoom-4 frame is 128x208 (T 175) instead of the base's 128x64 (T 31) draws, but
in view rotations 0 and 2 two of four cells lose the top of the sprite on a horizontal line, stable across camera
positions. Rotation 1 draws all of it.

### 8.1 Cause and fix

- T is not the problem. The cell's vertical range is the current frame's own anchor T: occupant vt+0x14 =
  `0x100159e2` -> `0x1005ad34` (frame = vt+0x68(zoom, rot)) -> `0x100014e7` (anchor cache record +0x10..+0x16,
  scaled by the frame's scale byte), stored as s16 at cell+4 by `0x10007b4d` (placement) and `0x1000b352` (zoom and
  rotation change) [CONFIRMED]. No cap. The anchor cache is a verbatim copy of the type-1 record (`0x1001dfd1`).
- Draw order is. The frame table header (reader `0x10001c90`): `+0x0c` ZoomCount, `+0x0d` RotCount, `+0x0e`
  ZoomSetCount, `+0x0f` AnimSetCount (20), `+0x10` AnimFrames (layers: 2 on bridge tables), `+0x11` RegRects, `+0x12`
  u32 LayerFlags, `+0x16` u16 Frames. (netcat's `layer_flags` is the raw dword at +0x10; sprites.py now also reports
  `anim_frames`, `reg_rects`, `draw_flags`.) LayerFlags bit 0x80 becomes cell flag bit 0 (`0x100192aa`), and
  `FUN_1000dc17` draws those records in a pass before all other records [CONFIRMED]. Road 39 and 29 ship 0x80,
  highway 73 ships 0, curve 11203 0xC0, bridge 83 0x01020401.
- Fix, data only: netpack `"art": {"first_pass": false}` clears the bit in the variant's table copy (`true` sets
  it). netpack warns when a frame is taller than its source frame and the bit stays set. Measured: lamps complete
  in all 20 dumps (verify/artkit arm F).
- Open: a cell without the bit sorts by depth with cars and pedestrians on it; not run with traffic. The bridge
  tables' child-layer bits (+0x12 low bits, 40 frames) are the way the stock pieces split a ground layer from a
  tall layer; using that for props instead of clearing the bit was not tried.

## 9. The kit

`netart.py` subcommands. Every route ends in a netpack `png_dir` (z{z}_r{r}.png, plus anchors.json when sizes
change) or in a compose recipe that netpack runs at build time (`"art": {"from": <base>, "recipe": "recipe.json"}`),
so a package can ship JSON only and never game pixels.

| command | what |
|---|---|
| `geometry` | the table in section 2, re-measured from the install |
| `check-rot` | the slot-turn measurement in section 6 |
| `template DIR --like 73 [--ghost 73] [--scale 4]` | route a: one guide PNG per frame at the frame's size and registration point: ground diamond, raised deck diamond, edge midpoints (arm centres), quarter points (lane centres), edge names per slot, neighbour outlines, the registration point; `guide_*.png` enlarged copies |
| `compose RECIPE DIR` | route b: layers of stock frames (or a png_dir, or a Blender render) cut by tile-space regions |
| `render SCENE DIR --work W [--like P] [--palette-from P]` | route c: Blender render with the calibrated camera, alpha cut, 5/6/5 quantise, optional snap to a stock piece's palette |
| `calibrate PIECE WORK [--model ...] [--fixed]` | route c: fit or evaluate the camera against stock frames |
| `preview LAYOUT OUT.png [--zoom z]` | the piece among stock neighbours at every zoom x rotation, drawn at the engine's draw points |
| `match LAYOUT 'dumps/X_z{z}_r{r}.png'` | in-game check: finds the offline composite in game frame dumps, counts equal 5/6/5 pixels |
| `lint DIR --like P` | sizes, anchors, soft alpha, pixels that hit the colour key |

### 9.1 Compose recipes

```json
{"canvas": 39,
 "layers": [
  {"piece": 11203, "slot_offset": 0},
  {"piece": 29, "slot_offset": 1,
   "region": {"and": [{"box": [0, 0, 1, 0.55]}, {"not": {"disc": [1, 1, 0.84]}}]}}]}
```

- `canvas`: a stock piece (its frame sizes), `{"like": P, "grow_top": <altitude units>}`, or explicit
  `{"z3": [w, h, L, T], ...}`.
- layer source: `"piece"` (stock frames), `"dir"` (a png_dir), `"render"` (a netart_blender scene, rendered and
  cached under %TEMP%\netart_cache). `slot_offset` k takes the source's slot (r + k) for output slot r.
- `region` (slot-0 tile space, turned with the slot): `all`, `poly`, `half` N/S/W/E, `disc [cu, cv, r]`,
  `ring [cu, cv, r0, r1]`, `box [u0, v0, u1, v1]`, `and` / `or` / `not`; `e` = height of the plane the region lies
  on (zoom-3 px), `down` = also the pixels hanging that far below it (walls), `clamp: false` turns off the rim rule.
- `shift [du, dv]` moves a source by tiles, `erase` clears the region instead.

### 9.2 Blender (route c)

Blender 4.5 LTS (winget `BlenderFoundation.Blender.LTS.4.5`, outside the game). Scene: Blender X = v, Y = u, Z up,
1 cell = 1 unit, origin = the cell's left vertex. Orthographic camera at 30 degrees elevation, 45 azimuth: the
ground diamond comes out 2:1, and one altitude unit = 0.20412 Blender units (`ALT`). Slot r = the model turned
+90 degrees x r about the footprint centre. `parts` scenes (cylinders, boxes, balls in tile coordinates and
altitude units) need no .blend; a .blend with a `SC3_PIECE` collection under an `SC3_ROOT` empty also works.

Calibration (`netart_calib.json`), fitted on flat tile 39 by searching camera shift (-1.5..1.5 px, quarter steps)
and footprint bleed (0..1 px) per zoom:

| zoom | shift (px) | bleed (px) | mismatched px per slot (flat 39) | held-out road 29 | box vs highway 73 |
|---|---|---|---|---|---|
| 0 | 0, 0.5 | 0.75 | 4 of 28 | 4 of 28 | 4 of 60 |
| 1 | 0, 0 | 0.75 | 8 of 88 | 8 of 88 | 8-12 of 212-216 |
| 2 | 0, 0.25 | 1.0 | 8 of 304 | 8 of 304 | 29-46 of 786-801 |
| 3 | 0, 0.5 | 0.75 | **0** of 1,088 | **0** of 1,088 | 76-139 of 2,999-3,062 |
| 4 | 0, 1.0 | 0.75 | **0** of 4,224 | **0** of 4,224 | 404-641 of 11,775-12,025 |

Every mismatch on the flat tiles lies within 1 px of the silhouette edge. The highway box residue is model, not
camera: one pixel column on one face (the stock deck is 1 px narrower on its rail side), 42-59 px beyond the 1 px
band at zoom 3.

## 10. Proof piece

The demo agreed with tasks lanekit and multitile: a 2x2 mini roundabout made of ONE new id in states 3,0 / 2,1
(pinwheel). Art: `examples/roundabout/recipe.json` (package `roundabout`, which also carries the lanes and the template; it replaced `example_roundabout_art` and lanekit's `example_roundabout`) = stock curve 11203 (a road quarter-circle round
the right vertex, which is the 2x2 centre in slot 0) + the exit road from stock straight 29 within 0.55 tile of the
NW edge, outside the ring's road. Results in `verify/artkit/RESULTS.md`.
