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

Type 0x6534284A (exemplar), 0x05342861 (cohort). Binary form `EQZB1###` (cohort `CQZB1###`) in this pack; the text
form `EQZT1###` is read since round 2026-11-19f (section 8.1).

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

## 8. More packs (round 2026-11-19f, stream sc4pass2)

Three more of the owner's downloads, local only: Global Office Center (a 251 m office tower, 6 DBPF files),
DiegoDL Growable Pack 2019 (46 files, lots + descriptions only), I-M manufacturers lots (8 files, lots + a blank
model). Counts below are from those files. Readers: the same modules, plus `views.compose_tiles` / `model_state`,
`catalog.others`, `sc4conv.pack_notes` / `readme_deps`; the page runs the same steps (`sc4web.js`).

### 8.1 Text exemplars (`exemplar.parse_text_exemplar`)

Every exemplar of the DiegoDL pack (46 of 46) and the tower's two descriptor files (2 of 7 exemplars; its lot files
are binary) are the text form. Latin-1 text, CR LF lines:

```
EQZT1###
ParentCohort=Key:{0x00000000,0x00000000,0x00000000}
PropCount=0x00000017
0x27812810:{"Occupant Size"}=Float32:3:{55.068001,251.145996,38.369999}
0x00000020:{"Exemplar Name"}=String:1:{"DiegoDL_555CaliforniaStreet"}
0x27812832:{"Wealth"}=Uint8:0:{0x03}
```

`<id>:{"<name>"}=<Type>:<count>:{<values>}`. Types seen: Uint8, Uint32, Sint32, Sint64, Float32, Bool, String.
Count 0 = one value, otherwise a list; a String is one quoted value with count 0 (tower) or 1 (DiegoDL). Integers
are hex, floats decimal (read as float32, which is what the binary form stores), Bool `True` / `False`. The name in
braces is the authoring tool's label and is not used (it differs between packs: "Pollution at center" / "at
centre"). The reader gives the same dict as the binary reader; 60 of 60 exemplars of the three packs read the same in
Python and in the page (`webtest/sc4_packs.mjs`).

**One-value lists.** The I-M descriptor is binary but stores exemplar type, wealth, purpose (and most other single
values) with key type 0x80 and count 1: `0x00000010 = [2]`. `catalog.sc` takes the value out of a one-element list for
the exemplar type, wealth and purpose.

### 8.2 A tall building's view is cut into tiles (`views.compose_tiles`)

The tower's S3D views have 1 mesh at zooms 1-2, 2 at zoom 3, 3-4 at zoom 4 and **12 (S, N) or 14 (W, E) at zoom 5**,
each mesh with its own 256 x 256 DXT3 texture (82 day textures over the 20 views). Each mesh is one or a few faces of
the box (planar: a per-mesh camera fit is singular on 7 of 14). A joint fit, one linear projection for all meshes of
a view plus a pixel offset per mesh, fits every vertex to 0.59 px or better, and the offsets of one view differ by
multiples of 256 to within 0.15 px (view S: x 237.26 / -18.84, y 1384.03, 1128.18, 872.18, 616.08, 360.14, 104.12).
So the BAT rendered one screen picture and cut it on a 256-pixel grid; the texels outside each mesh's triangles are
transparent (at most 145 opaque texels outside, of 44,000 inside). The converter pastes the tiles into one canvas per
view (512 x 1536 for S / N, 512 x 1792 for W / E) and re-maps the uv; from there the view is a one-mesh view. The
fitted camera is the JMyers one: elevation 44.99-45.00 degrees, azimuth 22.5 off the axis, 6.97-6.99 px per metre.

**Night textures:** 82 more FSH at instance + 0x8000 (`00038000` for `00030000`), the same sizes; no S3D mesh names
them (the game swaps them at night). SC3 has no night, so they are not read.

### 8.3 Ploppable and landmark versions (`catalog.others`, `sc4conv.pack_notes`)

The tower comes as three lots of the same size (4 x 3 tiles):

| lot | its building (type 0 row) | the tower |
|---|---|---|
| Global Office Center (growable, stage 8, zone types [6], purpose [3]) | text exemplar `Global Office Center`, model key `5AD0E817-3352A0BB-00030000`, wealth 3, purpose 3, capacity CO$$ 3500 + CO$$$ 3000 | the building's own model |
| Global Office Center Jobs (stage 7, zone types empty) | binary exemplar `Global Office Center - Jobs`, occupant size 1 x 0 x 1, no model key, parent cohort `05342861-CA386E22-0A64ED55`, capacity {0x3130, 3150} | a lot prop (type 1 row) naming prop exemplar `9355BAB7` (type 0x1E, the same model key) |
| Global Office Center Landmark (stage 7) | `JP Stevens Company Tower - Landmark` (its LText: "Global Office Center - Landmark"), no model, property 0x2781284F = [85, 75] | the same prop |

So a building without a model key whose lot holds a prop with a converted building's model is reported as that
building's "ploppable" (or "landmark", when the building has 0x2781284F) version, in `x_sc4.versions`. SC3 grows
buildings only, so they are named, not converted.

### 8.4 Lot-only packs (`views.model_state`)

- **DiegoDL**: 23 building exemplars with model keys in 21 groups (`897D9EFB` ...; the two Bacata pairs share) that no file of the download holds
  (no S3D, no FSH: the 46 files are 23 `.SC4Lot` + 23 `.SC4Desc`). `model_state` = `missing`. The readme
  (`readme_2019_vanilla.html`) has a "Dependency Listing" `<ul>` of 20 links to the models on Simtropolis (BD Bacata's
  one link covers its two buildings, ...): `readme_deps` quotes it.
- **I-M**: one building exemplar `!I§§--1542 jobs` (purpose 7, manufacturing), model `713D210C`, which
  `blank.SC4Model` holds as 20 one-mesh views whose 4 x 4 DXT1 textures are all transparent (alpha 0 on every texel):
  `model_state` = `blank`. The 6 lots (9 x 8 tiles) use that building and show 1,105 lot props (97 distinct ids):
  the visible factory is props.

Neither converts; `sc4conv.py` prints the report and writes nothing (exit 3); the page shows the same lines.

### 8.5 The BSC Common Dependencies Pack (V9e, report only)

`SC4D LEX Legacy - BSC Common Dependencies Pack V9e.zip` (1.7 GB): one LEX installer jar (1,636,901,067 bytes,
deflated in the zip) holding 168 `.dat` files under `installation/@1BSC`, `@2CSX`, `@3!Maxis Original`, 32 Java
classes, readmes. Over the 168 files: 297,896 S3D, 492,103 FSH, 18,850 exemplars + 1,492 cohorts, 11,673 type
0x88777601 (BAT XML descriptions), 4,295 LText. Prop exemplars (type 0x1E): 18,850 instance keys, 1,837 prop
family ids (property 0x27812870).

S3D shapes (every model, every zoom and rotation): 256,284 one mesh of 7 vertices (the box-and-picture of section 6),
27,680 one mesh of another shape, 5,879 two meshes, 7,982 three or more. 66 entries are not `3DMD`, 3 have REGP
entries, 2 fail the reader. FSH codes: 0x61 (DXT3) 271,839, 0x60 (DXT1) 219,785, 0x7D 47.

Lot props resolved against it: the I-M lots' 97 distinct prop ids, 61 are BSC prop instances, 36 are in neither the
download nor the BSC pack; the tower lots' 9 prop ids (`2AC20000` .. `2CB00000` and the tower's own prop), 0 are in
the BSC pack. [UNCERTAIN: where the unresolved ids live; the SC4 game files were not read, no SC4 install here.]
Feasibility: verify/sc4pass2/RESULTS.md section 4.

## 9. Lot props (round 2026-11-19g, stream sc4props: `deps.py`, `props.py`, `sc4conv.write_props`)

### 9.1 Reading a dependency pack by streaming (`deps.DepsIndex`, `sc4web.js depsIndex`)

The BSC Common Dependencies Pack V9e zip (8.5) holds its 168 `.dat` files inside one deflated 1.64 GB jar. A zip reader
cannot seek inside a deflated member, so the jar is read front to back by its LOCAL headers: none of its 384 members
uses a data descriptor (flag bit 3 clear), so every local header carries the compressed and uncompressed sizes.
Measured walk: 4.4 s to pass the jar without inflating any member; 20 s to inflate and index all of them (Python and
the page alike). Index kept: every prop exemplar (exemplar type 0x1E: 17,410 instance keys, a later file winning) and
cohort (1,481), and where each S3D / FSH entry is (789,999 rows: type, group, instance, file number). Python caches it
on disk (`%LOCALAPPDATA%\sc4conv\<zip>-<size>-<mtime>.idx.json` + `.map.npy`, 1 s to load); a conversion then walks
the jar once more and inflates only the files holding the props it places (JMyers: 4 files, 224 entries, 4-5 s), and
Python keeps those entries in `entries\` for the next run. The page keeps both in memory for the session.

### 9.2 What a lot's prop row names

Lot object kind 1 (section 3), word 12 = an exemplar instance of type 0x1E, or a prop family (0x27812870). Over the 42
JMyers lots: 2,266 prop rows, 231 distinct ids; against the BSC pack 646 rows are prop instances, 134 families, 1,486
in neither (85 ids, the most used `1EDF0000` 602 rows and `28330000` 342: instance ids ending in `0000`, the pattern of
SC4's own exemplars: confirmed in round 2026-11-19l, section 10.5). Prop exemplar properties the converter reads:

| id | holds (BSC pack) |
|---|---|
| 0x27812821 | Resource Key Type 1 {S3D type, group, instance}: views at instance + zoom << 8 + rotation << 4, as buildings (14,130 props) |
| 0x27812824 | Resource Key Type 4: records of 8 u32 {state, 0, 0, 0, 0x27812821, type, group, instance} (3,107 props; fences carry a state-1 and a state-0 record, seasonal trees one state-0 record). The converter takes the first record of state 0 |
| 0x27812820 | Resource Key Type 0 (98 props): not read |
| 0x27812870 | family ids (a lot row naming a family gets one member) |
| 0x0A751675 / 0xCA7515CC / 0x4A764564 | interval in days / start {month, day} / duration in days. The four seasonal variants of a tree share one lot position, each with interval 365 and its own start and duration (Dogwood: Summer {5, 19} 123 days, Winter {11, 19} 92 days). Fences carry interval 14,600 / duration 3,650 [UNCERTAIN: meaning], treated as always shown |

Lot textures (kind 2) name FSH instances of group 0x0986135E, 19 of the 25 most used ones are in the BSC pack. Drawn
since round sc4lottex (section 12).

### 9.3 Lot frame and rotations

- The street side of a JMyers lot is its +z edge: the front setback of the house is 13.3-13.7 m on every 1x2 and 1x3
  lot with house rotation 2, the back yard 9.0-25.3 m. The house model's front is +Z (section 7), so house rotation 2
  maps the model frame to the lot frame unturned, and rotation k turns it k - 2 quarter turns.
- The sense of a quarter turn: diagonal fence pieces show the parity only (a diagonal line turned 90 degrees either way
  is the same line). Lot textures decide it: on `R$2_1x2_JFM_FourSeasons Corner Lot` (house rotation 1) the driveway
  tiles (D400F165 rotation 1, D400F155 rotation 2, DD7A7900 rotation 3) join into one drive that ends at the car only
  when rotation k turns the image (x, z) -> (-z, x) per step; the other sense puts a driveway band under the house.
  That is also the sense in which the BAT views turn the model (section 6), so an object of rotation k drawn under
  camera rotation c uses view c + k. [UNCERTAIN: no SC4 render of a lot was compared; a lot with a rotation-1 or -3 house
  or an odd-rotation car shows its props turned the wrong way round if this is wrong.] `props.QUARTER` holds it.
- The converter takes props from the building's smallest SC4 lot. On the JMyers pack that lot has the house at
  rotation 2 for 104 of the 110 buildings; the 6 Four Seasons colours take `R$2_1x2_JFM_FourSeasons Corner Lot`
  (rotation 1), the one place where the sense moves prop positions. Elsewhere it only turns props of odd relative
  rotation (fences along x, cars parked across) end for end.

### 9.4 Results on the JMyers pack with the BSC pack (110 buildings)

5,190 prop rows over the 110 buildings' chosen lots: 486 placed (72 buildings), 866 outside the SC3 lot (the SC3 lot
is 16 m square, the SC4 lots 16 x 32-48 m), 378 seasonal variants of another season (DATE = 1 July), 3,454 in no pack
given (54 ids), 6 whose model is in no pack given. Lot textures (driveways, paths): section 12.

## 10. SimCity 4's own civic buildings, parks, rewards and landmarks (round 2026-11-19l, stream sc4civ)

Read in place from the Steam SimCity 4 Deluxe install (EA's files, never copied: nothing of them is in the repository
or docs). Readers: `catalog.install_files` / `Index.full`, `views.tex_key` / `compose_atlas`, `rewards.py`,
`sc4conv.service_for`; the page the same (`sc4web.js`). Results: `verify/sc4civ/RESULTS.md`.

### 10.1 The install's files

| file | entries | held |
|---|---|---|
| SimCity_1.dat | 60,440 | 41,075 S3D, 8,957 exemplars, 388 cohorts, 158 Lua scripts (type 0xCA63E2A3), others |
| SimCity_2..5.dat | 15,238 / 7,495 / 9,797 / 5,619 | FSH only |
| EP1.dat (Rush Hour) | 4,099 | 2,278 FSH, 1,820 S3D, no exemplar |
| SimCityLocale.DAT | 5,963 | 5,962 LText (the building names) |

No TGI is in two of the 7 files (0 shared), so their order does not change what is read. `catalog.install_files`
takes exactly these (a folder holding `SimCity_1.dat` at its top), never `Plugins`, `Regions`, `Intro.dat`, `Sound.dat`
or the shop plugin in `Sku_Data`. Files from 16 MB are memory-mapped in Python and read by slices in the page: the
whole install (720 MB) converts with 79.0 MB read.

**Cohort parents matter here.** 3,160 of the 8,957 exemplars name a parent cohort, and 63 of the 113 civic / park /
reward / landmark buildings with a model hold their exemplar type (0x10 = 2) only in the parent. `Index.full` reads an
exemplar with its parents' properties under its own (8 deep, as `props.OwnSource.prop_value`); a parent the index does
not hold adds nothing, so the downloads of sections 3-9 read as before.

### 10.2 How SC4 files a building: OccupantGroups (0xAA1DD396)

A list of u32 on every building exemplar. Counts over the install's 743 buildings (713 with an S3D model key, 30
without), each value checked against the exemplar names (prefix) and the LText names:

| group | buildings (with a model) | exemplar names | what the converter makes |
|---|---|---|---|
| 0x1005 | 42 (23) | 17 `CV*` (police, fire, schools, and so on) and 25 of the 32 parks | civic look (the service group decides the button) |
| 0x1006 | 32 (11) | `PZ*` / `Pz*`: Gazebo, Tennis Court, Softball Field, plazas, gardens | civic look of a park button |
| 0x150B | 53 (51) | `RW*`: Mayor's House, statues, City Hall, Courthouse, stadiums, Cemetery, Casino | reward |
| 0x150A | 39 (39) | `Lm*` / `LM*`: Big Ben, Chrysler Building, Taj Mahal | landmark |

The service is a second group: 0x1500 police (4: Small, Large, Deluxe Police Station, Police Kiosk), 0x1501 jail (2:
City Jail, Federal Prison), 0x1502 fire (3), 0x1503 school (8, the private schools included), 0x1504 college (2),
0x1505 library (2), 0x1506 museum (2), 0x1507 health (3: Medical Clinic, Large Medical Center, Disease Research
Center), 0x1702 zoo (1, City Zoo). Other values seen (0x150D..0x151C, 0x1900..0x1942, 0x1A00..0x1A04) are not read
[UNCERTAIN: meaning not needed]. A park carries no service group (its groups are 0x1005 / 0x1006 only), so its SC3
button comes from its name ("Softball" gives the Baseball Field, "Playground" the Playground) or else its footprint (the
Small Park when it fits 1x1, the Big Park when it fits 3x3): a choice of the converter, stated on the card.

Precedence when a building has several: landmark, reward, park, civic. So Coit Tower (0x150A + 0x150C) is a landmark,
the Private Schools (0x150B + 0x1503) are rewards, with a note on the card that they can be a School look instead.

21 of these buildings have no model of their own (the plazas, gardens, greens, Playground, Basketball Court,
Skateboard Park, both stadiums): their look is lot props. Not converted, named in the report.

### 10.3 Rewards: the Lua conditions

The exemplars hold no unlock rule. SimCity_1.dat's 158 Lua scripts (plain Latin-1 text, group 0x4A5E8EF6) hold 60
records `a = create_reward_<advisor>('<building exemplar instance>')` (54 `cityplanning`, 6 `finances`), each with a
`function a.condition()` that returns the "not yet" answer while the city falls short, for example
`game.g_population < tuning_constants.MAYOR_HOUSE_POP`. One script sets the thresholds,
`tuning_constants.<NAME> = <number>` (MAYOR_HOUSE_POP 500, CITYHALL1_POP 12500, COURTHOUSE_POP 40000). Records by
building: 51 on the 53 reward buildings (City Hall phases 2 and 3 have none), 4 on civic buildings (Deluxe Police
Station, Deluxe Fire Station, Large Elementary School, Large High School), 5 on utilities (Grand Rail Station, Solar,
Nuclear and Hydrogen power, Large Water Pump).

`rewards.lua_rewards` takes every `<population> < <threshold>` (a game variable ending in `population`, or a sum of
them; a constant, a number times a constant, or a number). SC3's reward row has one population (the city) and one year
(CIVIC_REWARD.md 2.1), so a comparison maps to it only when it counts the whole city: `g_population` (25 records),
`g_city_r_population` (10), the sum of `g_city_r1/r2/r3_population` (1). 36 of 60 records map. The other 24 compare
high-wealth residents, jobs (`g_city_rci_population`, `g_city_iht_population`, `g_city_co2/co3_population`), the
region, or no population (Lighthouse: seaport volume; Toxic Waste Dump: funds) and get bldimport's default 20,000, with
the SC4 condition on the card. Mayor rating, funds, missions and building counts have no SC3 column (card only). No
condition reads the year (0 of 60): year 0. The Casino's `1.6 * tuning_constants.POPULATION_STEP_6` gives 24,000.

### 10.4 SC4's own models: textures and atlases

- **Texture group.** All 42,895 S3D entries (SimCity_1.dat + EP1.dat) are in group 0xBADB57F1, and the textures their
  MATS name are FSH entries of group 0x1ABE787D (the S3D group holds no FSH). `views.tex_key` tries the S3D's own group
  first (the downloads' BATs), then 0x1ABE787D for group 0xBADB57F1.
- **Real meshes.** The zoom-5 views are not the 7-corner box of the BATs: up to 104 vertices in one mesh (the Library's
  view 0 has 25, the Mayor's House 62). The 136 one-mesh views (of the 452 views of the 113 buildings) fit one orthographic camera to
  0.67 px or better, elevation 44.1-45.9 degrees, 6.6-7.1 px per metre: the camera of the BATs (section 6). No back-wall
  fill (`hidden_faces` is for the 7-corner box only).
- **Atlases.** The other 316 views are 2 to 14 meshes (2,343 pieces) whose textures are pieces of one screen render
  packed together: each piece fits its own camera to 0.6 px, and against the projection of the piece with the most
  vertices it is moved (1,605 pieces) or moved and transposed, x and y swapped (738), not scaled (singular values of the
  fitted 2 x 2 part 1.00 / 1.00, down to 0.90 on the smallest pieces). The offsets are not on a 256-pixel grid (unlike
  the tower, 8.2), so `compose_tiles` declines them (joint fit error 9-108 px, the limit is 2 px) and `compose_atlas`
  rebuilds one canvas per view: per piece a 2D fit decides transposed (determinant < 0), the mean offset rounded to whole
  pixels says where its texels go (largest error after rounding 1.58 px), and the texels its triangles cover (a
  separating-axis test on each texel square) are copied. The rebuilt views fit one camera to 1.30 px at most. 112 of
  113 convert; one piece of the Large High School's view 3 is 59.66 px off [UNCERTAIN: another transform], skipped.
- Night textures and seasons are not read, as for the downloads.

### 10.5 Lot props of SC4's own lots

The install is its own prop source (`props.OwnSource`): 7,337 prop rows over the 112 buildings' lots, 1,302 placed (77
buildings), 4,247 outside the SC3 lot (SC4's civic lots are 1x1 to 20x9 tiles), 54 of another season, 0 missing, 1,734
without a readable model: animated people (`Aper*`, resource key type 4 with no type-1 record: 567 of the rows of the
first 60 buildings), effects (no model key) and resource key type 0 (98). The two most used prop ids the JMyers lots
left unplaced (9.2) are SC4's own: `1EDF0000` is the prop exemplar `Flora2x2x2_QuarterShrub_1EDF` and `28330000`
`Flora2x2x2_Quarterbush_2833` in SimCity_1.dat [CONFIRMED: instance keys of type-0x1E exemplars of the install]. Reading the
install as a dependency source for downloads: section 11.

## 11. SimCity 4's own props for a download's lots (round 2026-11-19l, stream sc4baseprops)

`sc4conv.py <download> --sc4 <install>` (Python) and the page (`sc4web.js installSource`: the install's `.dat` files picked
with the download, or the game opened before with Open SC4 game) add the player's install as one more prop source.
Results: `verify/sc4baseprops/RESULTS.md`. EA's files are read in place, nothing of them is in the repository or docs.

### 11.1 The install as a prop source

- `props.OwnSource(catalog.Index(<install>))`: 1,544 prop exemplars (exemplar type 0x1E) and 388 cohorts of SimCity_1.dat.
  Every one of the 1,544 holds its type 0x1E itself: of the install's 8,957 exemplars, 980 hold their type only in a
  parent cohort, and none of them is a prop (exemplar type 2: 653, 0x16: 154, 0x17: 115, 0x26: 21, 0x18: 19,
  0x19: 15, 1: 2, 0x25: 1) [CONFIRMED: `Index.exemplar` vs `Index.full` over SimCity_1.dat].
- Order: the download, then each `--deps` pack, then the install. SC4 loads its own data files before the plugins, so a
  plugin's exemplar of an id the install also holds replaces the install's: `props.owner` returns the first source
  holding an instance.
- The page reads the install's exemplars and cohorts once per page session (by slices, as section 10.1), then only
  the S3D views and FSH textures of the props it places: 13.3 MB in slices and 1.0 MB of whole small files
  (SimCityLocale.DAT) for the JMyers pack, no large file read whole.

### 11.2 One exemplar space: families and models across sources

SC4 keeps one exemplar space for its own files and the plugins. Two rules of section 9 read each source on its own and
were changed to read across them (`props.resolve`, `props.plan`; `sc4web.js resolveProp`, `propPlan`):

- **Families are pooled.** A family id's members are the union of every source's members, each read from its
  `owner`, a member counted only when its owner's exemplar still names the family; then active on DATE, sorted, row
  index mod count as before. Measured on the JMyers lots: family A0000038 has 502 members in the BSC pack (car props,
  e.g. `family single high wealth mercedes suv grey`) and 23 in the install (`R4x8x3_$JunkerTruck_1C93`,
  `R4x8x2_$bentley_1CDF`), 48 rows; A0000068 has 2 in the BSC pack and 46 in the install (`Aper2x2x4_*` people), 12 rows.
  With one source (a download alone, an install converting itself) the pool is that source's list: nothing changes.
- **The model comes from the first source holding its 4 zoom-5 views**, the prop's own source first (`row.msrc`). The
  BSC prop `CP_MaxisFluffyMed` (D0A8237D) has Resource Key Type 1 {0x5AD0E817, 0xBADB57F1, 0x1EDA0000}: SimCity 4's own
  S3D, which only the install holds (`1EDA0400`..`1EDA0430` present in the install, absent from the BSC index). With the
  install given, its 6 rows resolve (they fall outside the SC3 lot window on the JMyers lots).

### 11.3 Results on the JMyers pack (110 buildings, 5,190 prop rows)

| sources | placed (buildings) | outside the SC3 lot | other season | in no source (ids) | no readable model |
|---|---|---|---|---|---|
| download + BSC pack (section 9.4) | 486 (72) | 866 | 378 | 3,454 (54) | 6 |
| download + install | 1,786 (110) | 1,634 | 0 | 1,676 (81) | 94 |
| download + BSC pack + install | 2,236 (110) | 2,494 | 366 | 0 | 94 |

- All 54 ids the BSC run left unresolved are in the install: `1EDF0000` = `Flora2x2x2_QuarterShrub_1EDF` (1,380 rows),
  `28330000` = `Flora2x2x2_Quarterbush_2833` (804) and the 52 others.
- The 81 ids the install run leaves unresolved are BSC props (`109F9BD6` 240 rows, `109F9DCC` 210, `D09F9C1E` 204, ...):
  with both sources, 0.
- 94 rows without a readable model: 88 whose Resource Key Type 4 holds only records `{state, 0, 0, 0, 0x27812820,
  0x29A5D1EC, group 0x2A2458F9 or 0x49A593E7, instance}` (no record of 0x27812821, so `model_of` finds no S3D):
  `ACV6x4x4_jump-ropeanimate_1DE7` 18 rows, `Aper2x2x4_female-S-drk01-wait` 14, `ACV6x2x4_keep-awayanimate_1D46` 12,
  `Amill4x2x4_exploritorium_29C2` 12, `Aper2x2x4_male-drk01-negative-tantrum_2875` 8, `AR8x8x2_$DogOnAChain_1ef3` 6 and
  others of the pooled people family; 6 rows of `Randomwalk_MowerBldg`, Resource Key Type 0 {0x5AD0E817, 0xBADB57F1, 0}.
  [UNCERTAIN: what resource type 0x29A5D1EC holds; the names say animated. Not read.]
- What the two rule changes moved, with both sources (before -> after): other season 378 -> 366 and no readable model
  88 -> 94 (the 12 rows of family A0000068: its 2 BSC members 287D0000 / 28870000 have interval 365, start {10, 1}, 120 days, not active on DATE, the pooled list adds the install's
  46 people, which have no S3D record), outside 2,488 -> 2,494 and no readable model -6 (the 6 `CP_MaxisFluffyMed`
  rows, now with a model, outside the window). Placed: 2,236 both times.

### 11.4 SC4's own lots

The install converting itself (section 10.5) has one prop source, so pooling and the model lookup give the same rows as
before: 0 props missing there (the BSC pack was not added to an install run: nothing is missing for it to supply).

## 12. Lot textures (round 2026-11-19l, stream sc4lottex: `lottex.py`, `sc4conv.write_lottex`, bldrender `sc3ground`)

`sc4conv.py` (and the page, `sc4web.js lotPlan` / `lotComposite`) draw the texture rows of the props' lot (section 9) on
the ground under the building, from the same sources as the props: the download, the `--deps` packs, the install.
Results: `verify/sc4lottex/RESULTS.md`. Every count below is from the 42 JMyers lots and the install's 1,908 lots.

### 12.1 What a texture row holds

Lot object kind 2 (section 3), 13 words:

| word | JMyers (326 rows) | install (25,452 rows) | used as |
|---|---|---|---|
| 1 | 0 on all | 0 (20,021), 0x20 (5,431) [UNCERTAIN: meaning, not read] | not read |
| 2 | rotation 0-3: 150 / 23 / 77 / 43, with bit 0x80000000: 6 / 4 / 12 / 11 | 19,077 / 2,732 / 1,582 / 1,437, with the bit 247 / 148 / 93 / 136 | quarter turns, mirror (12.2) |
| 6-9 | the square, 16 x 16 m on all, on the 16 m grid | 16 m up to 2^-16 (12,913 exactly 16), not on the grid: offsets of 0.04-0.05 m are common, some anywhere (`CS$$1_6x6`: x 15.241) | where the picture lies |
| 12 | the texture id | the texture id | FSH key |

The texture is an FSH of group 0x0986135E, instance = id + zoom index (0-4 = SC4 zooms 1-5): of the install's 1,453 FSH
in that group, 290 ids have all five (8 x 8 to 128 x 128 px), two only the first, one only 5. The converter reads id + 4:
128 x 128 px over 16 m = 8 px per metre. Formats of the 76 ids the JMyers lots name and a source holds: 0x60 DXT1 (9,
every texel opaque) and 0x61 DXT3 (67, with transparent texels).

**No lot property names a base texture.** The lot exemplars carry 0x88EDC789 .. 0x88EDC798, 0x27812837, 0x4A4A88F0,
0x699B08A4, 0x88FCD877, 0xCBE243F7, 0xE99B068C (and 0x88EDC791, 0x89136440, 0xE99B068D in the install). The two that
name an instance point at exemplars of group 0xC977C536: 0x88EDC798 at exemplar type 21 (`LotRetainingWall-$$$ivy`,
`LotRetainingWall-$$rock`) and 0x88FCD877 at type 17 (`Slate Brick`), with FSH lists of their own. The lot's base is the
textures without a transparent texel among its rows: on the JMyers lots every tile that has texture rows holds exactly one
such (124 tiles), 8 of the 9 plain grass, one a vegetable garden (`25DC0000`).

### 12.2 Orientation: the cars test

Which of the 16 ways to lay the image on its square (8 turns and mirrors of the image x 2 senses of the rotation word) is
SC4's was tested on what the lots themselves say: a parked car stands on paving. For every car prop of a lot with texture
rows (name matching car / truck / van / suv / sedan ..., or the car family A0000038), the composite texel under its centre
is read (opaque layers first, 12.3) and called paved when it fails the grass test (12.4):

| mapping | install, 239 cars on 178 lots | JMyers, 29 cars on 23 lots |
|---|---|---|
| **image turned 180 degrees, then rotation x 90 degrees clockwise (columns along +x, rows along +z)** | **197 paved** (35 grass, 7 bare) | **20** |
| the same, rotation counter-clockwise | 195 | 17 |
| mirrored columns, turned 0, counter-clockwise | 193 | 15 |
| mirrored columns, turned 0, clockwise | 191 | 14 |
| the 8 mappings with rows along +x | 176-179 | 6-12 |
| the other 4 | 166-167 | 4-5 |

On cars over an odd rotation only (where the sense matters): install 30 against 28, JMyers 7 against 4, for the sense
above, which is the sense `props.QUARTER` already uses for props (9.3). The mirror bit: on cars over a mirrored texture,
mirroring the image's columns before the turn gives install 43 paved of 48 against 34 for its rows, JMyers 6 of 9
against 2. A seam test (adjacent tiles' edge colours over 1,645 install lots) only separated columns-along-x from
rows-along-x (mean edge difference 0.131-0.148 against 0.166-0.179) and not the rest. [UNCERTAIN: no SC4 render of a lot
was compared, and the sense margins are small.] The civic renders agree: the police station's cars stand in the painted
parking bays (`verify/sc4lottex/owner_shots/04`), as did the school's in a review render.

### 12.3 Layering

Lot order is not the draw order. On tiles holding an opaque texture and a transparent one, the opaque one comes later in
the lot in 190 of 296 such pairs of the install and 55 of 198 on JMyers: drawn in lot order, those overlays would be
hidden. The cars test over orders (install / JMyers paved cars): opaque textures first, then the others in lot order 197 /
20; plain lot order 182 / 11; texture id ascending 190 / 16; reverse lot order 163 / 9. The converter draws the opaque
textures first, then the others, each group in lot order. The order among the transparent ones changes no car (lot order,
reverse and by id: 197 / 20 each) and is kept as lot order [UNCERTAIN].

### 12.4 Lawn: SC4's grass is left to SC3's lawn

The 8 plain grass bases the JMyers lots use average luminance 0.32-0.40 at hue 71-85 degrees (`D400F050`, on 92 rows: RGB
93 / 115 / 44, luminance 0.39, hue 78). SC3's lit lawn (bldrender `grass`, fitted to the stock lots) is 100 / 145 / 78 at
zoom 3, luminance 0.49, hue 100. With the `baked` tone of the building art the SC4 grass would be 157 / 193 / 73,
luminance 0.66. So a converted lot drawn with SC4's grass is a darker, yellower square among the stock lawns (picture
`06`). After compositing, a texel is cleared when it is grass: green the strictly strongest channel, hue at most 108
degrees (`5 (r - b) >= g - min(r, b)`), saturation above 0.15 (`20 (g - min) > 3 g`): integers only. It clears 0.88-1.00 of
the 8 grass bases' texels and 0.65 of the garden plot. Bldrender then draws its own lawn there. On the JMyers lots the
drawn textures cover 9-58% of the SC3 lot (median 34%), on SC4's own civic lots 0-99.8% (median 63%).

### 12.5 On the SC3 lot and in the picture

- **Canvas.** The props' SC3 lot window (9.3, `props.plan`) at 8 px per metre in the house's model frame: pixel (i, j) =
  window corner + (i + 0.5, j + 0.5) / 8 m, back through the lot turn (`turn(.., kb - 2)`) into the lot frame, then into
  each texture's square. A texture square inside the window is `placed`, partly inside `cut` (drawn up to the edge), else
  `outside`. Compositing is straight alpha over in float64, then floor(x + 0.5) to 8 bits, in the same order in Python and
  the page.
- **Files.** `<stem>_lot.png` (the canvas, transparent where nothing or grass is), `<stem>_lot.obj` (the house + one quad
  over the window, OBJ group `sc3ground`, 1 cm above the house's lowest point) and `<stem>_props_lot.obj` (house, props,
  quad). `models.json` `file` = `<stem>[_props][_lot].obj` by `x_sc4.props.on` and `x_sc4.textures.on`, both kept on a
  rerun. `x_sc4.textures` = `on, lot, rows, placed, cut, outside_sc3_lot, missing, unreadable, ground {sc4_ground, lawn,
  drawn} (shares of the SC3 lot), used, missing_ids`.
- **bldrender `sc3ground`.** Faces of that group are drawn in every slot and shaded as the lawn (kind 2): the stock rim,
  no tone, saturation, grain or contrast, never a shadow caster. A sample on a transparent texel is the lawn itself (not a
  peeled layer: with props, peeling ran out and showed the canvas's empty black texels). bldweb.js does the same.
