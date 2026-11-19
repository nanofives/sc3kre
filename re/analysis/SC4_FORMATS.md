# SC4_FORMATS.md: SimCity 4 plugin files, as read by the SC4 -> SC3U building converter (task sc4conv, 2026-11-18h)

Round 2026-11-18h, stream sc4conv. Readers: `re/tools/sc4conv/` (`dbpf.py`, `exemplar.py`, `s3d.py`, `fsh.py`,
`catalog.py`, `views.py`). Every layout below was checked on one input, the SC4Evermore "BSC JMyers Homes Pack V3.1"
(19 DBPF files after the Java installer: 1 prop pack of 7,577 entries + 18 lot files), with the counts given. That
pack is the owner's download and is not redistributable: nothing from it is in the repository, only these layouts
and counts. Field names in quotes are the SC4 community's names where the converter does not depend on them. What
was not observed in the pack is marked [UNCERTAIN] or "not read".

Little endian unless stated. TGI = {type, group, instance}, three u32.

## 1. DBPF container (`dbpf.py`)

| offset | size | field | in the pack |
|---|---|---|---|
| 0x00 | 4 | magic `DBPF` | 19 of 19 files |
| 0x04 | 4 | major version | 1 |
| 0x08 | 4 | minor version | 0 (minor 1 files are read the same way; not in the pack) |
| 0x0C | 12 | reserved | 0 |
| 0x18 | 4 | created (Unix time) | |
| 0x1C | 4 | modified (Unix time) | |
| 0x20 | 4 | index major version | 7 |
| 0x24 | 4 | index entry count | 7,577 in the prop pack |
| 0x28 | 4 | index offset | |
| 0x2C | 4 | index size in bytes | = count x 20 on 19 of 19 files |
| 0x30 / 0x34 / 0x38 | 4 each | hole count / offset / size | 0 |
| 0x3C | 4 | index minor version (DBPF 1.1 only) | (0) |
| 0x40 | 32 | reserved | 0 |

Index entry: type, group, instance, offset, size (5 x u32, 20 bytes). With index minor version 2 a second instance
u32 follows the instance (24 bytes) [not in the pack; the reader takes offset and size from the last 8 bytes].

**Directory** (type 0xE86B1EEF, one per file, never compressed): one record per compressed entry, {type, group,
instance, uncompressed size} (16 bytes; 20 with index minor 2). An entry is QFS-packed exactly when the directory
lists it: 7,434 entries over the 19 files.

## 2. QFS / RefPack (`dbpf.qfs_decompress`)

Packed entry: u32 compressed size, then the RefPack stream: flag byte, 0xFB, u24 uncompressed size BIG endian, then
commands. The flag byte is 0x10 on 7,434 of 7,434 entries (no 0x01 "compressed size follows" bit, no 0x80 4-byte
sizes). The leading u32 equals the index entry size on 7,301 entries; it is 4 less on the 128 exemplars of the prop
pack and 4 more on 5 lot-file exemplars. The reader does not use it. Every packed entry unpacks to exactly the
directory's size.

| first byte | length | literal bytes | copy length | copy offset (back from the output end) |
|---|---|---|---|---|
| 0x00-0x7F | 2 | b0 & 3 | ((b0 & 0x1C) >> 2) + 3 | ((b0 & 0x60) << 3) + b1 + 1 |
| 0x80-0xBF | 3 | (b1 >> 6) & 3 | (b0 & 0x3F) + 4 | ((b1 & 0x3F) << 8) + b2 + 1 |
| 0xC0-0xDF | 4 | b0 & 3 | ((b0 & 0x0C) << 6) + b3 + 5 | ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1 |
| 0xE0-0xFB | 1 | ((b0 & 0x1F) << 2) + 4 | 0 | |
| 0xFC-0xFF | 1 | b0 & 3, then the stream ends | 0 | |

Literals are copied before the back-reference; a copy whose offset is shorter than its length repeats bytes. This
is the same RefPack SC3's own DAT files use (bldweb.js `qfsDecompress`).

## 3. Exemplars, cohorts, LText (`exemplar.py`, `catalog.py`)

Type 0x6534284A (exemplar), 0x05342861 (cohort). Binary form only (`EQZB1###`, cohort `CQZB1###`); the text form
`EQZT` is not in the pack and is not read.

| offset | size | field |
|---|---|---|
| 0x00 | 8 | `EQZB1###` |
| 0x08 | 12 | parent cohort TGI (0 / 0 / 0 on all 128 + 110 exemplars read) |
| 0x14 | 4 | property count |
| 0x18 | | properties |

Property: u32 id, u16 value type, u16 key type (0x00 = one value, 0x80 = a list), u8 (0), then for a list a u32
count, then the values. Value types: 0x0100 u8, 0x0200 u16, 0x0300 u32, 0x0700 s32, 0x0800 s64, 0x0900 f32,
0x0B00 bool (1 byte), 0x0C00 string (a list of count bytes, no NUL). Every exemplar of the pack parses to its exact
length.

Properties the converter reads. The meaning column is what the pack's own data shows, not a claim about the game:

| id | type | holds | evidence in the pack |
|---|---|---|---|
| 0x00000010 | u32 | exemplar type: 2 building (110 in the lot files), 0x10 lot configuration (42), 0x1E prop (110 in the prop pack, same names and models as the buildings), 0x11 the foundation models (18) | |
| 0x00000020 | string | exemplar name, e.g. `JFM_AbbyGlen_Blue_02` | |
| 0x27812810 | 3 x f32 | occupant size x, y, z in metres | equals the zoom-5 view box size (section 6) to 0.03 m |
| 0x27812821 | 3 x u32 | model TGI {0x5AD0E817, group, 0x00030000} | an S3D entry exists at base + zoom << 8 + rotation << 4 for all 20 views of all 110 buildings |
| 0x27812832 | u8 | wealth | 1 on all 110 (readme: R$ = low wealth) |
| 0x27812833 | u8 | purpose | 1 on all 110 (readme: residential) |
| 0x27812834 | u32 pairs | capacity {demand group, count} | {0x1010, 11..22}; readme: occupants 11-22 |
| 0x27812870 | u32 list | building family | 18 values, one per design: the 6 (Shotgun: 8) colour variants share it, and 39 of 42 lots name it in their building row |
| 0x8A416A99 | 3 x u32 | name key -> LText | an LText entry at that TGI in the same lot file for all 110 |
| 0x88FCD877 | u32 | (building) the foundation exemplar's instance, group 0x361CF9D5 | resolves to a type-0x11 `*_FND_*` exemplar |

Lot configuration (type 0x10): 0x88EDC790 u8 x 2 = lot size {width, depth} (the lot names say `1x2` / `1x3` /
`2x2` / `2x3`; 41 of 42 agree, `R$3_1x2_JFM_Fleetwood_BLU` holds {2, 1}); 0x27812837 u8 = growth stage (the `R$<n>_`
name prefix agrees on 42 of 42); 0x88EDC900 and up = lot objects, 13 u32 each:

| word | holds (pack) |
|---|---|
| 0 | object kind: 0 building (one per lot), 1 prop, 2 texture, ... |
| 1 | 0 |
| 2 | rotation 0-3 in the low bits (0x80000000 / 0x80000003 on two texture rows: high bit [UNCERTAIN]) |
| 3, 5 | x, z of the object centre, s32 / 65536 metres |
| 4 | 0 (y) |
| 6-9 | bounds min x, min z, max x, max z, same unit |
| 10 | 0 |
| 11 | object id 0x00FD41xx.. [UNCERTAIN: a per-lot serial] |
| 12 | the object's resource: for kind 0 the building family (39 lots) or a building exemplar instance (3 corner lots) |

The building row of the 1x3 Abby Glen lot: rotation 2, centre (6.43, 30.0) m, bounds (2.19, 25.3)-(10.67, 34.65) m
in a 16 x 48 m lot. Lot props (kind 1) reference the BSC Common Dependencies Pack, not in the download: not read.

LText (type 0x2026960B): u16 character count, u16 0x1000, then count UTF-16LE characters. Some names hold two lines
(`501 Mill Street, by JMyers\nStage 3`): the converter keeps the first.

Type 0x88777601 (128 in the prop pack): UTF-8 XML, `<SC4PLUGINDESC Name=... ResKey="0x5ad0e817-<group>-0x00030000"
BATVersion=... Quality=...><DIMENSIONS Width Height Depth>`, the BAT's description of each model. Not needed.

## 4. S3D model (type 0x5AD0E817, `3DMD`, `s3d.py`)

2,560 entries (128 models x 5 zooms x 4 rotations), all QFS-packed, all version 1.5. Instance = model base
(0x00030000 in the pack) + zoom << 8 + rotation << 4, zoom 0-4 = SC4 zooms 1-5, rotation 0-3 = the BAT names S, W, N,
E (`..._UserModel_Z5S_0` ... in the ANIM mesh names).

| offset | field | pack |
|---|---|---|
| 0x00 | `3DMD` | |
| 0x04 | u32 | not the file length on 2,560 of 2,560 (e.g. 0x1B00 for a 440-byte model) [UNCERTAIN] |

Then chunks, each a 4-byte tag and a u32 length. The length is right for HEAD, PROP and REGP (12) and wrong for the
others on 2,560 of 2,560 (first model: VERT 3,120 for a 160-byte chunk, INDX 894 for 54, PRIM 306 for 26, MATS
1,625 for 85, ANIM 923 for 71) [UNCERTAIN: what the number is]. So the reader walks the chunks by content in the fixed
order below and checks it lands on each next tag and on the file end (2,560 of 2,560).

| chunk | body |
|---|---|
| HEAD | u16 major (1), u16 minor (5) |
| VERT | u32 groups (1); group: u16 flags (0), u16 count, u32 format (0x80004001 on all), count x {3 f32 position, 2 f32 uv} |
| INDX | u32 groups (1); group: u16 flags (0), u16 stride (2), u16 count, count x u16 |
| PRIM | u32 groups (1); group: u16 count (1); prim: u32 type (0 = triangle list), u32 first index, u32 index count |
| MATS | u32 groups (1); group: u32 flags (0xAB), u8 alpha func (4), u8 depth func (3), u8 src blend (1), u8 dst blend (0), u16 alpha threshold (0x7FFF), u32 material class (0), u8 reserved (0), u8 texture count (1); texture: u32 FSH instance, u8 wrap s (3), u8 wrap t (3), u8 mag (0), u8 min (0), u16 anim rate (33), u16 anim mode (2), u8 name length, name with NUL |
| ANIM | u16 frames (1), u16 rate (0), u16 mode (3), u32 flags (0), f32 displacement (0), u16 meshes (1); mesh: u8 name length, u8 flags (0), name with NUL, frames x {u16 vert group, u16 index group, u16 prim group, u16 mat group} |
| PROP | u32 count (0) |
| REGP | u32 count (0) |

Values in brackets are the only values found in the pack (every field of every model). The meaning of the MATS
numbers (blend and compare enums) is the community's reading [UNCERTAIN: not needed, the converter alpha-tests at
0.5 as the render showed].

## 5. FSH texture (type 0x7AB50E44, `SHPI`, `fsh.py`)

4,760 entries in the prop pack (4,713 QFS-packed), each one bitmap.

| offset | field | pack |
|---|---|---|
| 0x00 | `SHPI` | |
| 0x04 | u32 file size | = length, 4,760 of 4,760 |
| 0x08 | u32 entry count | 1 |
| 0x0C | 4-char directory id | `G344` |
| 0x10 | count x {4-char name, u32 offset} | name `0000`, offset 0x20 |
| 0x18 | 8 bytes | `Buy ERTS` (padding) |

Bitmap header at the offset (16 bytes): u8 format code, u24 offset to the next block (0), u16 width, u16 height,
u16 x 4 (centre x, centre y, position x, position y). The high 4 bits of the last u16 hold the mipmap count in
SC4 files by the community's reading; 0 on all 4,760, and the data after the main image is zero padding to a
16-byte file size (16 bytes on all), so there are no mipmaps here. Formats found: 0x60 DXT1 (1,117), 0x61 DXT3
(3,643). The reader also decodes 0x62 DXT5, 0x7D A8R8G8B8, 0x7F R8G8B8, 0x78 R5G6B5, 0x7E A1R5G5B5, 0x6D A4R4G4B4
[not in the pack: written to the common DXT / packed-pixel definitions, untested].

Instances: 0x30xxx (2,280 entries) = base + zoom << 8 + rotation << 4, the texture each S3D view's MATS names;
0x38xxx (2,200, the same + 0x8000, the same sizes, not named by any MATS) [UNCERTAIN: night-light textures; not
used]; 0x31xxx (280, the textures of the foundation models whose base is 0x31000). Sizes at zoom index 4: 128 x 128
to 256 x 256.

## 6. What a view model is: geometry space and culling (`views.py`)

Measured on the 110 buildings x 4 zoom-5 views (440 meshes):

1. **Every zoom-5 view is a box.** 7 vertices, 6 triangles: the top and the two walls that face the camera of that
   view, the other three faces culled (440 of 440). Zooms 1-2 are always the box too (1,024 of 1,024 meshes of all
   128 models); at zooms 3-5 the 18 foundation models (exemplar type 0x11, 17 named `*_FND_*`, one
   `*_Foundation_01`) have finer meshes of 24-125 vertices, the 110 houses never.
2. **The texture is the BAT's render of that view**, mapped by screen projection: a least-squares fit of
   uv x texture size against position, [u v] = A [x y z 1], has a largest error of 0.50 px over the 440 meshes (one
   exact affine map = an orthographic camera). Texels outside the house are transparent (DXT3 alpha or DXT1's
   1-bit alpha).
3. **One camera for all four views; the model turns.** In each view's own coordinates the fitted camera is the
   same: elevation 44.5-45.5 degrees, azimuth 22.5 degrees off +z (towards +x), 7.0 px per metre at zoom 5. The four
   boxes are the same box turned by quarter turns: view-space (x, z) of view r = model (x, z) turned r times;
   model = view turned back by (x, z) -> (z, -x) per step (after the turn the four boxes coincide exactly, largest
   difference 0.0000 m, on all 110; the box size equals the occupant size property to 0.001 m).
4. **In the model frame** (view 0 = S), the SC4 cameras sit at azimuth +22.5 (S), +112.5 (W), -157.5 (N), -67.5 (E)
   degrees (all 440 within 0.5 degrees), the SC3 slot cameras at -45 / -135 / +135 / +45 (slots 0-3, bldrender's
   axes +X -> u, +Z -> v, front +Z on the lower right of slot 0). Each SC3 slot has one SC4 view 22.5 degrees away
   that sees the same two walls: slot 0 E, slot 1 N, slot 2 W, slot 3 S.
5. **The view S frontal wall (+z) is the front**: the door and porch face that way on the designs looked at (Abby
   Glen, Craftsman, Empire); this matches bldimport's front +Z.
6. Units: metres, Y up, right-handed: the fitted screen-right direction of view S is (6.418, 0, -2.706) px per
   metre, unit (0.921, 0, -0.388) = (cos 22.8, 0, -sin 22.8) degrees, which is screen right for a camera at
   azimuth +22.8 in a right-handed Y-up frame (a left-handed frame would give +z). SC4 tiles are 16 m, the same as
   bldimport's cell [the SC4 tile size is the community's figure; the lot exemplars agree: a 1x3 lot's objects lie
   within 0-16 x 0-48 m].

## 7. How the converter rebuilds a building for SC3 (`sc4conv.py`, decision renders in verify/sc4conv/RESULTS.md)

There is no 3D model of the house in the files, only four pictures on four boxes. Three rebuilds were rendered
through SC3's camera and compared (`reproject.py`):

| rebuild | result |
|---|---|
| `match`: SC3 slot r draws only the SC4 view 22.5 degrees from it | consistent picture; the wall the SC4 camera saw at 67.5 degrees is stretched about 1.85 x sideways; on houses that are not box-shaped (L plans, porches) the transparent texels open gaps |
| `frontal`: each wall from the view that sees it at 22.5 degrees, top from the slot's view | sharper walls, but holes and seams where one view's roof outline meets another view's wall |
| `fixed`: one face set for all slots | the same holes, plus a roof seen from the wrong side in 3 of 4 slots |

Chosen: `match`, plus the box's two back walls and floor (0.05 m up) with uv from the same projection: a ray that
passes a transparent texel of a front face reaches them and shows what the SC4 camera saw along that line. That
closes most gaps (Fleetwood, Craftsman), with some repeated roof pieces where the fill shows a front part again.
The SC4 light is painted into the texture, so the converter writes `x_bldrender.style = "baked"` (bldrender: no
light, the stock lawn and palette, and a luminance tone 0.75 / 1.33 fitted so the structure luminance matches the
stock buildings').

What the rebuild cannot do: give the SC3 camera's 30-degree view of surfaces SC4 saw at 45 degrees (the roofs look
steeper and shorter than drawn for SC3), show what the BAT render did not (the far side of a porch), or keep the SC4
light direction consistent with SC3's axis light (BUILDING_ART.md 4.1).
