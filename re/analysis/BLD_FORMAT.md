# BLD_FORMAT.md: the Building Architect `.bld` file (task bldfile, 2026-11-18c)

Evidence: the 17 `.bld` files the game ships in `Buildings\` (all parse to the byte with `re/tools/bldimport/bldfile.py
info`), SIMBABLD.DLL (base `0x12000000`, export `re/ghidra_export_simbabld/`), and the 15 matching buildings in
`Apps\BARender\BAT.DAT`. Reader: `re/tools/bldimport/bldfile.py` (Python), the BLD-BEGIN block of
`re/tools/bldimport/classifier.html` (JS, checked against Python by `bld_js_check.mjs`, 17 of 17).

## Verdict

A `.bld` holds the Building Architect's **block model**, an **info** record and **one 200x200 preview picture**. It
holds **no game frames**. The game's 20 frames (5 zooms x 4 view slots) exist only after the BA renders the model
into `Apps\BARender\BAT.DAT` (section 4). The preview is the BA's render of view **slot 0** in the game's projection
and lighting: mask IoU 0.98 to 0.99 against the BAT.DAT slot-0 zoom-3 frame for 13 of 13 buildings whose BAT.DAT id
matches (`bldfile.py check`, section 3).

## 1. Container

An IXF segment like every `.IXF` (`formats/IXF_segment.md`): magic `0x80C381D7`, then 20-byte index entries
`{u32 group, u32 instance, u32 type, u32 offset, u32 size}` up to an all-zero key. Group `0xC3F8D4A9` on every record.
Saved by SIMBABLD `0x12003bf6` (`sc3_ixf_segment_ctor` on a new file, then the writers below). The info record alone
is read by `0x12004302` (catalog listing). Readers of the whole file: `0x12003ed3`, `0x120043b6`, `0x12004216`.

| type | instance | content | written by |
|---|---|---|---|
| `0xE3F87B0C` | `0xA3F8D615` | block model (section 2) | `0x1200a849`, key built at `0x12003bf6` |
| `0xE3F87B0F` | `0x63FBE1CC` | info: lot, name, architect, id | `0x1200b7ef` |
| `0x644D7178` | `0xA44D71AA` | u8 length + string | `0x1200b7ef` |
| `0x644D7179` | `0xA44D71AB` | u32 category | `0x1200b7ef` |
| `0xB9EC8F72` | `0x99EC9601` | u32 (1 in all 17) | `0x1200b7ef` |
| `0x99F88B9E` | `0xB9F88BD2` | 4 bytes (`01 00 00 00` in 16, `02 00 1c 00` in Longview Park) | `0x1200b7ef` |
| `0xE3F87B0E` | `0xE3F8D655` | preview picture (section 3) | `0x12003bf6` -> `0x1200adaa` (segment vt+0x40) |
| `0xE3F87B0D` | 0 .. n-1 | 93-byte record per custom texture [UNCERTAIN layout] | `0x1200a849` |
| `0xE3F87B10` | 0 .. n-1 | custom texture image (section 3 header, 4 bytes per pixel) | `0x1200adba`, `0x1200b15e` |

`0x1200b7ef` writes the four small records with the info key's instance replaced when it is `0x63FBE1CC`:
`-0x5bb28e56` = `0xA44D71AA`, `-0x5bb28e55` = `0xA44D71AB`, `-0x661369ff` = `0x99EC9601`, `-0x4607742e` =
`0xB9F88BD2` [CONFIRMED @ 0x1200b7ef]. 84 custom textures over the 17 files (0 to 17 per file), 32x32 or 128x128.

### Info record `0xE3F87B0F`

| offset | field | evidence |
|---|---|---|
| +0 | u8 lot size n (1 to 4; the lot is n x n) | `0x1200b7ef` first vt+0x68 (u8) write; equals BAT.DAT's lot byte for 15 of 15 |
| +1 | u8 length, then the name (cp1252) | vt+0x68 + vt+0xac |
| next | u8 length, then the architect | vt+0x68 + vt+0xac |
| next | u32 length, then a string, length 0 in all 17 | written by the `0xDA6DC9A9` block of `0x1200b7ef` (vt+0xa4); its source in `0x12003bf6` is a registry string under `HKEY_LOCAL_MACHINE\Software\Electronic Arts...` passed through `ObscureString` |
| last 4 | u32 id | vt+0x88 in the same block. Equals the BAT.DAT override instance for 13 of the 15 shipped buildings (not The Joneses, not Maxis Towers: batconvert design 1) |

Why the `0xDA6DC9A9` block's bytes land at the end of `0xE3F87B0F` and no `0xDA6DC9A9` record exists in any of
the 17 files: [UNCERTAIN], not traced (segment vt+0x4c open-for-write).

### Category `0x644D7179`

Values: `0x208` Dupont House, GuestHouse Building, The Joneses; `0x209` Garvey Plaza, Headquarters, Hotel Splash,
Maxis Towers, Proton Building, Zweikky Unpainted; `0x20A` HiTech Lab, North Shore Cannery, Northeast Nonwovens, Trash
& Burn; `0x20F` Kankakee Jr. High School; `0x212` Den Burg Bruges; `0x217` Longview Park, Tutorial House. Reading
`0x208` / `0x209` / `0x20A` as house / shop or office / factory comes from the names only [UNCERTAIN]: Tutorial
House is a house with `0x217`. The tools use it only as a default class, and anything else gets no class.

## 2. Block model `0xE3F87B0C` (writer `0x1200a849`)

| offset | size | field |
|---|---|---|
| 0x00 | u8 | 8 (version, constant written) |
| 0x01 | u8 | object `+0x84` (0 to 3 in the 17 files) [UNCERTAIN meaning] |
| 0x02 | u8 | grid size N = object `+0x5c` (= 8 x lot in all 17: 8, 16, 24, 32) |
| 0x03 | u8 | object `+0xc` = lot size |
| 0x04 | u8 | `0xEA` |
| 0x05 | u16 | object `+0x60`, clamped per N by `DAT_12076805..08` (28, 65, 109, 144 in plain files; 257, 288, 385 in towers) [UNCERTAIN: height limit in grid steps] |
| 0x07 | u16 | `0xEAEA` |
| 0x09 | u32 | object `+0x68` (cell count bound: the packer is given `+0x68 << 5` bytes) |
| 0x0D | u32 | `0xEAEAEAEA` |
| 0x11 | u32, u32 | 4, 0x20 |
| 0x19 | u32 | `0xEAEAEAEA` |
| 0x1D | u32 | N x N x 4 |
| 0x21 | N x N u32 | one u32 per grid column (rising; a start index into the cell list) |
| | u32 | `0xEAEAEAEA` |
| | u32 L, then L bytes | packed cells: the L bytes start with u32 L again, then a QFS stream (cell bytes, not a multiple of 32 in 15 files [UNCERTAIN cell layout]) |
| | u32 | `0xEAEAEAEA` |
| | u32 count, then count x {u32 length, name, u32 hash} | every paint, detail and prop file the model uses (`"brick 04.tga"`, `"sm decid1 0.bmp"`: one entry per prop view), from `Apps\Res\BA\{PAINTS,DETAILS,PROPS}` and `Apps\BACustom` |
| | u32 | `0xEAEAEAEA`, last 4 bytes of the record in all 17 |

So a model is a voxel grid of BA blocks with textures by file name. Props are billboards: each prop is four BMPs
(`<name> 0.bmp` .. `<name> 3.bmp`, one per view) plus a `.met` size line (`1,3,3:"1x3x3.bmp",...`,
`Apps\BACustom\Props`).

## 3. Preview `0xE3F87B0E`

Image record header (data, all 17 previews and 84 textures): u16 format (`0x07F0` preview, `0x0EF1` texture), u16
width, u16 height, u32 packed length, then a QFS stream (`10 FB` + 3-byte size). Preview: 200 x 200 x 2 bytes,
RGB565, colour key `0xF81F`. Writer of the header bytes not traced [UNCERTAIN by code, CONFIRMED by data].

It is the slot-0 view (the comparison above). Its scale fits the art's box in the picture: the box spans the lot's
width, measured as the lot's bottom vertex lying at the box centre within 1 px on all 17 (left and right halves of
the box equal). `bldfile.preview_frames` resamples the box to `n x (8 << zoom)` px wide per zoom, bottom row on the
lot's bottom vertex, anchor `T = h - n x W / 4` as in BAT.DAT frames (`L = 0`, `B = n x W / 4`, 15 of 15).

Measured against the real BAT.DAT frames (`bldfile.py check --game <tree> <folder>`, 15 buildings):

| slot 0 | zoom 0 | zoom 1 | zoom 2 | zoom 3 |
|---|---|---|---|---|
| mask IoU, mean (min) | 0.879 (0.824) | 0.932 (0.854) | 0.968 (0.813) | 0.971 (0.793) |
| colour RMS (0-255) | 19.3 | 20.4 | 18.4 | 19.0 |
| anchor T difference, max | 1 px | 2 px | 2 px | 5 px |

The minimum and the 5 px are The Joneses, whose BAT.DAT entry has a different id than its `.bld` (a different
render, batconvert design 1). Without it the zoom-3 minimum is 0.968.

Slots 1 to 3 have no source in the file. Stock lighting (BAT.DAT, 15 buildings) puts the bright wall on the left in
slots 0 and 2 and on the right in slots 1 and 3 (mean brightness of the left and right halves), so the tool uses the
picture as it is for slots 0 / 2 and mirrored for 1 / 3. Against the real views at zoom 3: slot 1 RMS 54.9 mirrored
against 64.0 as is, slot 3 57.1 against 64.9, slot 2 58.3 as is against 65.8 mirrored. The building turns as its
mirror twin, not as its real other sides: asymmetric buildings show the wrong facade from slots 1 to 3.

## 4. Where the real frames come from: the BA's batch renderer

`sc3_bat_export_rendered_buildings_ixf` (`0x12001faf`) writes BAT.DAT: it renames the old file to
`Res\BA\RenderedBuildingsBackup.IXF` (`0x1207617c`), opens a new IXF segment, loads every `.bld` path of its list
(`this vt+0x40` per path, after `cRZFile::FileExists`), creates a render object (`+0x50`, `0x12006be1`,
`cIGZFrameWorkHooks::PreFrameWorkInit`), renders each building into the segment (`0x12002879` per building, progress
through `0x12006885` when `+0x4d`), copies the kept entries of the old file (`0x1200282c`, `0x12002840`,
`0x1200461b`), and writes the override records (`0x1200be1d`: type `0x856CD19A`, u8 lot, the `0x6300` table key,
name, architect, two more strings, u32). [CONFIRMED @ 0x12001faf, 0x1200be1d]

- It is slot +0x10 of vtable `0x12069a84` (`0x12001f71`; slot +0x18 `0x12001f8e` is the same call with `+0x70 = 1`
  and argument 1, which ends with framework vt+0x48 instead of returning to the view). The object is the BA
  application, constructor `0x12002c8f`, created only as a singleton (`DAT_12079434`) by `0x12001140`, the factory
  of class `0x79F4AAD1` that SIMBABLD's GZCOM director registers (`0x120010f4`) and starts in its OnStart
  (`0x1200106f`). [CONFIRMED]
- No game module references `0x79F4AAD1` or SIMBABLD's other classes `0x455969DF`, `0xC3023BE2`, `0xC3023BE3`,
  `0xA2FFB5D4` (searched every exe and DLL export, 2026-11-18; `0xA2FFB5D3` is also a game bitmap class, not the
  BA). The game shows `.bld` files in a catalog (SIMUI `0x1002933f`, `"*.BLD"` at `0x100be4e4`), but the render
  runs inside `Baapp.exe`: the render path needs the BA's own view object (`this vt+0x24`, then its vt+0xfc /
  +0x24 / +0x28).

So the real frames are one call away **inside a running Baapp.exe**: `(*(DAT_12079434))->vt+0x10(outPath, n,
&paths, 0, NULL)` with cRZString objects (vt+0x14 = the C string), which writes an IXF in BAT.DAT format to
`outPath` that `bldfile.bat_frames` already reads. Not done this round (verify/bldfile/RESULTS.md, "Real frames").

## 5. The batch renderer run for real (task bldbat, 2026-11-18)

**Baapp.exe carries its own copy of the BA code**: it never loads SIMBABLD.DLL (Frida LoadLibrary trace through start-up,
menu and a render), it has its own `Res\BA\RenderedBuildingsBackup.IXF` string and no `0x79F4AAD1` class id. Mapping into
Baapp.exe (base 0x400000, no relocations):

| SIMBABLD | Baapp.exe | what |
|---|---|---|
| `0x12001faf` sc3_bat_export_rendered_buildings_ixf | `FUN_004044a9` | same 2,044-byte body |
| `0x12001f71` / `0x12001f8e` | `FUN_0040446b` / `FUN_00404488` | slot +0x10 / +0x18 wrappers |
| vtable `0x12069a84` | vtable `0x480c78` | BA application |
| `DAT_12079434`, factory `0x12001140`, ctor `0x12002c8f` | `DAT_004954e0`, getter `FUN_004010c9`, ctor `FUN_00405189` | singleton |

Call (made on Baapp's main thread from a PeekMessageA hook, `re/tools/bldbat/ba_render.py`):
`(*DAT_004954e0)->vt[+0x10](out, n, &paths, 0, NULL)`. `out` and `paths[i]` are cRZString objects (vtable `0x480344`:
+4 AddRef `0x44f17d`, +8 Release `0x44f184` deletes at count <= 1, +0x14 c_str `0x45f4fd`; ctor `FUN_00402c4c`). `paths` is a
pointer to an array of object pointers, as in Baapp's own caller `FUN_00401c73` ("export to SimCity", slot +0x18).
`app+0x4d` = 0 skips the progress window. The view object (`vt+0x24` = `0x4053e2`) is created on demand, so the call works
from the main menu without opening the editor. [CONFIRMED by run: 17 of 17 shipped .bld rendered, 63 to 83 s]

Per building (`FUN_00404d73` line 303, `segment->vt+0x3c(group, instance, frames)`):
- group = `FUN_004534bb(app+0x58)`: LCG `x * 0x41C64E6D + 0x3039`, seeded by `timeGetTime()` at app construction
  (`FUN_004534a0`, seed -1). A new group per building per run. [CONFIRMED @ 0x4534bb, 0x4534a0]
- instance = the loaded building's `+0x1a8`, or a new id from `FUN_00404d52` when that is 0. In every run it was a new
  id, not the .bld info id (Dupont: 0x3809C6FE, .bld 0x45FEEAC6). [CONFIRMED by run; why +0x1a8 stays 0: UNCERTAIN]
- records: one 0x856CD19A override, one 0x6300 table (instance = override instance, the override's last u32 = the same),
  16 pixel records `{0, 1}` on consecutive instances. Same shape as BAT.DAT.

`bldfile.py render` re-keys the result to the importers' keys (group 0xBA1DBF1E, instance = .bld id, a free pixel block).

### Custom parts (records 0xE3F87B0D / 0xE3F87B10)

Record 0xE3F87B0D: u8 10, 8 x u32 (two rects), u32 hash (= the hash beside the name in the model's texture list), u32,
4 x f32 (w, h, 1/w, 1/h), u32 n + name, then the key of its image record (type 0xE3F87B10, group, instance) and u32 kind
(6 paint, 7 detail, 16 prop). The image is the section-3 header (format 0x0EF1) + 4 bytes per pixel. `bldfile.custom_textures`.

How the renderer resolves a texture name (Trash & Burn, runs X / Y / W, verify/bldbat/RESULTS.md):
1. the .bld's embedded copy: used, even when no file of that name exists anywhere (13 of its 17 parts);
2. a file in `Apps\BACustom\<Paints|Details|Props>`: Baapp lists and opens every file there at start-up only (no file is
   opened during a render), and uses it only when its content is the one the .bld was made with. A same-named magenta
   file was ignored (with and without the embedded copy); the genuine pixels written back as a TGA made a stripped
   .bld render pixel-identical to the original (16 of 16 frames);
3. otherwise the face is drawn flat and untextured. The render does not fail.
The hash follows content, not the name: Kankakee's `bourbo~3.tga` (an 8.3 name) carries 0x55CDCCEE like
`bourbon 03.tga`. Hash function: [UNCERTAIN], not a CRC32 of the name, the file or its pixels.
