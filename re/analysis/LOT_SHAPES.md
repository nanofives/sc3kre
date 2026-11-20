# LOT_SHAPES: non-square building lots (2x3) in SC3U (lot2x3, round 2026-11-20d; patch: lotdraw, round 2026-11-20e)

> **2026-11-20e (lotdraw): the drawing patch exists.** sc3perf block LOTRECT (`re/harness/src/sc3perf_lotrect.c`,
> switch `lot_rect` / `SC3PERF_LOT_RECT=0`, mods page row "Edificios no cuadrados") draws X x Z buildings whole in both
> orientations and saves the true footprint. Sections 1-7 describe the shipped game; section 8 is the patch, with three
> corrections to the text below: the save of a landmark goes through SIMMISC's copy of the descriptor filler, not
> SIMGEOM `0x1001cd38`; the Z call to change is the one at `0x1001cd9a` (bits 6-11), not `0x1001cda8`; and the cell
> record has no free byte in the shipped mod set (sc3bigcity ANCHOR16 uses `+0x12/+0x13`).

Owner request (2026-11-20): "Test a 2x3 lot, and then Allow 5x5". SimCity 4's Small Police Station sits on a 2x3 lot, and
the converter puts SC4 buildings on the smallest SC3 square. Question: can SC3U place, draw, rotate, save, load,
bulldoze and move a non-square building, for hand-placed landmarks and rewards, and could growables ever get one?
Static reading of SC3U.exe (CodeView names), SIMGEOM, SIMSPR and SIMRCI, plus one in-game probe in `dev\lot2x3\tree`
(`verify/lot2x3/RESULTS.md`). Every claim carries an address, a measurement or `[UNCERTAIN]`. DLL addresses are Ghidra
VAs (image base 0x10000000). "X" and "Z" are the exemplar's prop 0x66 values 1 and 3 (prop 0x66 = {X, height, Z}).

**Verdict.**

- **Simulation side: rectangles work.** Placement check, placement highlight, the occupant grid, bounds, bulldozer, the
  Mover and the query dialog all use SizeInCellsX and SizeInCellsZ separately. A 2x3 landmark is placed, holds 6 cells,
  refuses buildings on all 6, accepts neighbours on every side, bulldozes from any of its cells and moves.
- **Drawing side: squares only.** The sprite manager registers every building in an n x n block of the sprite cell map with
  n = SizeInCellsX (SIMSPR `0x100192aa`), and the cell map, the draw list and the clip carry one size byte. A 2x3 (X 2,
  Z 3) draws as a 2x2 sprite plus a third row of bare plopped ground: in every view rotation a strip (Z - X) x W / 2 px
  wide at the far (+z) end of the lot is not drawn. A 3x2 (X 3, Z 2) is worse: its sprite claims a 3x3 block, hides a
  neighbour's building drawn in the extra row, draws fragments twice, and leaves a ghost of itself there after a
  bulldoze (until the city is loaded again).
- **The save writes X x X.** SIMGEOM `0x1001cd38` passes SizeInCellsX twice to SetSizeInCells, so a 2x3 is saved with a
  2x2 footprint field. The game rebuilds the 2x3 from the exemplar on load (measured), so only offline readers see 2x2.
- **Growables: no.** The zone developer (SIMRCI `0x10027699`) reads only SizeInCellsX and lays out n x n blocks.
- **So:** a data-only 2x3 landmark or reward works but always shows a cut end. Correct drawing needs a SIMSPR code patch
  (section 5). X must be the short side (X < Z); X > Z must never be written.

## 1. Where the footprint is read

prop 0x66 is loaded by SIMGEOM `sc3_building_occupant_load_props` `0x1002286f`: value 0 -> `+0x20`, value 1 -> `+0x28`,
value 2 -> `+0x24` (lines 47-55 of the export, property table `DAT_1002b4f0`). The occupant's getters forward to its
attrib: `cISC3Occupant` vt+0xd4 SizeInCellsX = SIMGEOM `0x1001d15d` -> attrib vt+0x40, vt+0xd8 SizeInCellsZ = `0x1001d16c` ->
attrib vt+0x44, vt+0xdc SizeInCellsY = `0x1001d17b` -> attrib vt+0x48 (building occupant vtable `0x1002bbe8`, CV slot
names from `cv_vtables.tsv`). Neither getter looks at the occupant's rotation bits (`+0x10` bits 30-31): the footprint
never turns. A placed landmark has rotation 0 (measured, section 6), and the placement tool has no rotate input.

| path | code | X and Z | square assumption? |
|---|---|---|---|
| attrib cache entry | SIMINIT `0x1000c428` | stores type (vt+0x50), X (vt+0x40), Z (vt+0x44) | no |
| place tool, Execute | SIMGEOM `cIGZGameCommand::Execute` `0x1000956b` | tool `+0x116` = X - 1, `+0x117` = Z - 1 (attrib vt+0x40 / +0x44) | no |
| place tool, highlight | SIMGEOM `0x1000968b` (tool vtable `0x10029504` +0x54) | bounds = cursor cell + (`+0x116`, `+0x117`), highlighter vt+0x4c(bounds, 0x23 / 0x24) | no |
| check + place | SIMGEOM `sc3_geom_place_footprint_region` `0x10006ba6` | attrib vt+0x40 / +0x44 -> bounds max x += (X - 1) * 0x100, max z += (Z - 1) * 0x100, then site check `0x100072f6`, commit `0x10007760` | no |
| occupant grid | SIMGEOM `sc3_occmgr_insert_occupant_at_cell` `0x1000df90` | `0x1000dfda` vt+0xd4, `0x1000dff3` vt+0xd8; loops x..x + X - 1, z..z + Z - 1 | no |
| bounds | SIMGEOM `0x1001d305` (vt+0xcc GetBounds), `0x1001d3af` (vt+0xd0 GetBoundingRectInCellCoords) | vt+0xd4 for x, vt+0xd8 for z | no |
| sprite insert | SIMSPR `sc3_spr_insert_cell_aligned_sprite` `0x100192aa` | `0x10019341` vt+0xd4 only; removes n x n cells (cell map vt+0x68), Insert (vt+0x64) with size n = X | **yes** |
| cell map insert | SIMSPR `sc3_spritecellmap_insert` `0x10007b4d` | one size byte (param 5): writes n x n records, record `+10` = n, `+8/+9` = (x + n - 1, z), corner flags 0x20/0x40/8/0x10 | **yes** |
| registration point | SIMSPR `0x1000c678` | view coords of (x + n - 1, z) (`0x1000a62c`), then per rotation `vz += 1 - n` (r1), `vx += n - 1, vz += 1 - n` (r2), `vx += n - 1` (r3), n = record `+10` (`0x1000c6bc`, `0x1000c6ce`, `0x1000c6df`) | **yes** |
| draw list + clip | SIMSPR `sc3_iso_build_displaylist_lowzoom` `0x1000be25` | clip width `n << (zoom + 3)` from the registration point (line 120), depth bounds from n (lines 163-170) | **yes** |
| sprite change | SIMSPR `ChangeCellAlignedSprite` `0x10019899` (`0x100199b6` vt+0xd4), `RemoveAndInsertCellAlignedSprites` `0x10019830` (`0x10019848`, `0x10019856` vt+0xd4) | X only | **yes** |
| sprite remove | SIMSPR `RemoveCellAlignedSprite` `0x100196b7` | GetBounds (vt+0xcc, X x Z), then `0x1001a25d` rebuilds each cell of that rect (`sc3_occbridge_rebuild_tile` `0x1001a291`) | no, but it does not match the insert when X != Z |
| save | the occupant descriptor filler, one copy per module (SIMGEOM `sc3_record_fill_descriptor` `0x1001cd38`; a landmark is a SIMMISC class and saves through SIMMISC's copy at `0x100359f6`, section 8) | `0x1001cd9a` and `0x1001cda8` both vt+0xd4, `0x1001cdb4` SetSizeInCells(a, b) (`0x1001dd82`: bits 0-5 = a = the `0x1001cda8` value, bits 6-11 = b = the `0x1001cd9a` value, of record `+8`) | **yes** |
| load | SIMGEOM `sc3_geom_load_dispatch_by_shape` `0x10002cc2` | `0x1000320c` GetSizeInCells (`0x1001dcde`) -> [ebp-0x40] X, [ebp-0x44] Z; only X is passed on (`0x1000324a`, create call vt+0x18 at `0x10003252`); Z is never read. The occupant's size then comes from its attrib | no effect in game |
| zone developer | SIMRCI `sc3_resdev_place_lots` `0x10027699` | attrib vt+0x40 at `0x10027964`, `0x10027c2d`, `0x10027d43`; no vt+0x44 call in the function; n x n checks and an n x n fill (`0x1010101` stores at `0x10027bac`, `0x10027c73`) | **yes** |
| BAT list | SIMINIT `0x100053be`, SIMUI `0x1001bb56` | filtered by SizeInCellsX (BUILDING_PICK.md) | yes, growables only |

`[LINUX-HINT]` The Loki build's `cSC3CitySpriteManager::InsertCellAlignedSprite` (`libsimspr.so` `0x000a8a14`) also calls
one size getter only.

## 2. The view geometry (why the cut lands where it does)

World cell (x, z) -> view (vx, vz) for view rotation r (SIMSPR `0x1000a62c`, N = city size): r0 (x, z), r1 (N-1-z, x),
r2 (N-1-x, N-1-z), r3 (z, N-1-x). Screen x grows with vz - vx, so a lot's left vertex is its max-vx, min-vz corner.

The sprite's registration point (SIMSPR `0x1000c678`) is the left vertex of the n x n block at (x0, z0) with n = X. The
real X x Z lot has the same left vertex in r0 and r1. In r2 the real min vz is N - z0 - Z instead of N - z0 - X, in r3
the real max vx is z0 + Z - 1 instead of z0 + X - 1: for X < Z the real left vertex is (Z - X) x W / 2 px further left.
The clip is `[reg, reg + X x W]` while the lot is (X + Z) x W / 2 wide. For X < Z the strip outside the clip is
(Z - X) x W / 2 px: the right end in r0 and r1, the left end in r2 and r3, in all four the corner at the +z end of the
lot (the cells z0 + X .. z0 + Z - 1, which the sprite map does not hold). All of this matched the probe, section 6.

## 3. Rotation of the art

Frame = zoom x 4 + ((state + viewRot) & 3) (BUILDING_ART.md 1). A placed landmark has state 0, so frame slot = view
rotation. Slot r must show the X x Z lot through view transform r. The probe art does this with
`view(r, x, z)` = (x, z), (-z, x), (-x, -z), (z, -x) and draws each world side in its own colour: in all four rotations
the long sides, the short ends and the origin cell are where the occupant is (`owner_shots/04`). No mirror or axis swap is
needed in the art for a non-square lot beyond that transform.

## 4. Lot ground

The commit writes zone 22 (plopped building) over the footprint (RELOCATE.md 1). Cells of zone 22 with no building sprite
draw orange-brown plopped ground (plop2: a removed landmark's lot). The third row of a 2x3 is such a cell pair: the art
covers most of it, but the clipped strip shows that ground (`owner_shots/09`). Right after placement the strip showed the
placement highlight colour instead (sampled (0, 112..116, 152), the tool's highlight (0, 116..120, 152), `owner_shots/03`, `04`),
which stayed through camera changes until the lot was moved or the city reloaded: the highlight is cleared on the cells
the building sprite replaced, not on the two cells it does not cover `[mechanism UNCERTAIN: the highlighter's clear path
was not read]`.

## 5. What correct support would need

### 5.1 Data only (no code), X < Z

What bldimport, the page and the converter would write for a w x d lot with w < d (as `verify/lot2x3/work/make_lot2x3.py`):

- prop 0x66 = (w, base height, d). Base exemplar: the stock base of size w (the stats a w-square would get), prop 0x66
  overwritten. A 3x2 model is turned 90 degrees so its long side runs along z; X > Z is never written.
- 20 frames rendered for the real w x d diamond: width (w + d) x W / 2, slot r through view transform r.
- Anchor = the registration point the engine uses: the left vertex of the w x w block in each slot. L = 0 in slots 0 and
  1, L = (d - w) x W / 2 in slots 2 and 3 (T from the same point), as the probe's anchors
  (`0:20x16@0,8 ... 2:20x16@4,10`, RESULTS 2).
- The importer's lot checks (`lot_of`, `[n, n]` only) and the page's lot picker would accept [w, d] for kinds landmark
  and reward only; growables, ports and civic looks stay square (civic looks keep their base's lot already).
- Risks: in every view a (d - w) x W / 2 px strip at the +z end is not drawn (plopped ground shows, any building part
  there is lost; a building kept on the w x w square with open ground in the extra rows hides most of it, not all). The
  saved footprint field is w x w (offline tools that read it: `occupant_layer.py`, city tools, zone raster checks would
  need the exemplar instead). The page's preview would have to show the cut, or players will report it as a bug.

### 5.2 Code: rectangular sprite registration (SIMSPR + one SIMGEOM byte)

Every site in the "yes" rows of section 1:

- SIMSPR `0x100192aa` (`0x10019341`): read X and Z; remove and insert an X x Z block.
- `0x10007b4d`: the insert loops (x .. x + X - 1, z .. z + Z - 1), the corner flags, the registration cell `+8/+9`. The
  0x14-byte cell record has one size byte (`+10`); Z needs a second one. Which record bytes are free was not read
  `[UNCERTAIN]`.
- `0x1000c678`: per-rotation offsets from X and Z (r1 vz uses X, r2 vx uses X and vz uses Z, r3 vx uses Z; derived in
  section 2, not run).
- `0x1000be25`: clip width (X + Z) x W / 2 and the depth bounds (lines 163-170), and GetCellSizeOfSprite (cell map
  vt+0xa8) for its callers.
- `0x10019899`, `0x10019830`: the same X / Z pair.
- SIMGEOM `0x1001cda8`: `call [eax+0xd4]` -> `call [eax+0xd8]` (one byte) so saves record X x Z. **Corrected in section
  8:** the Z argument is the `0x1001cd9a` call, and every module has its own copy of the filler.

Risk: this is the draw loop and every building insert / change / remove, shared with sc3resize's repaint and zoom work
(REPAINT8, cityzoom); a mistake shows on every building in the city, not only on 2x3 ones. Each site needs its own off
switch and an A/B over a full city in all four rotations.

### 5.3 Code: square pieces

A w x d lot as square pieces (2x3 = one 2x2 + two 1x1), each its own occupant and art slice, placed together. Stock does
this for three rewards (Theme Park, Military Base, Generic University: four 2x2 pieces through the 4-key tool
`FUN_1000a2a9`, CIVIC_REWARD.md 1). Needs a multi-piece placement in a mod; each piece then bulldozes, moves and counts
on its own, and the one-per-city landmark rule applies per piece key.

### 5.4 Growables

Not without rewriting the developer: `0x10027699` sizes and fills lots from SizeInCellsX only, so a 2x3 growable would
be laid out as 2x2 while its occupant claims 2x3. Static only, not run.

## 6. Measured (verify/lot2x3/RESULTS.md)

2x3 (X 2, Z 3), Madison: tool highlight 2x3; placed (177, 213), occupant rect [177, 213, 178, 215], 6 cells; sprite map
2x2 (size byte 2, reg (178, 213)), cells (177..178, 215) terrain; clip at exactly 2 x 64 px at zoom 3; four rotations
oriented correctly, cut end as section 2; query dialog and Mover work, the move removed the full 2x3 rect; 2 cells inside
the third row refused, 7 outside neighbours accepted on flat ground; save footprint field 2x2; reload rebuilds the 2x3
occupant and the 2x2 sprite; Demolish over a third-row cell removed the whole building and both sprite rows.
3x2 (X 3, Z 2): occupant 3x2 (6 cells), sprite 3x3 (9 cells) over the neighbour park at (181, 206); garbage in all four
rotations; after a bulldoze the three extra cells still pointed at the removed sprite and drew it; a reload cleared it.

## 7. Open

- Whether the 3x2 ghost pointer is freed memory (a use-after-free) or a live sprite kept by another reference: it drew
  the right pixels for several minutes and the game did not fault `[UNCERTAIN]`.
- The highlighter path that leaves the third-row highlight (section 4).
- The free bytes of the 0x14-byte cell record (5.2).
- Load without the plugin of a city holding a 2x3 (landmarks: empty lot, plop) was not run for the 2x3.

## 8. The LOTRECT patch (lotdraw, round 2026-11-20e)

Code: `re/harness/src/sc3perf_lotrect.c` (included by `sc3perf.c`), installed by sc3perf's SIMSPR watcher the moment
SIMSPR maps, all-or-nothing after a byte check of every site. Results and pictures: `verify/lotdraw/RESULTS.md`.

### 8.1 Where X and Z live

- **No free byte in the cell record.** `+0x12/+0x13` are padding in stock SIMSPR (no instruction below `0x10011000`
  touches a record's `+0x12/+0x13`; Init `0x10005e7c` clears up to the `+0x10` word), but sc3bigcity's ANCHOR16 stores
  the registration cell's high bytes there (`re/harness/src/anchor16_sites.h`, 43 sites). A first build that wrote Z to
  `+0x12` was refused at load: bigcity had already detoured `0x10007be6`.
- **Flag bit 0x400 of `+0x10`** marks every cell of a non-square sprite. Flag word use over all of SIMSPR (static):
  bits 0-3 Insert's last argument, `0x10..0x100` per-zoom prepared masks (`DAT_100624f0..0x10062500`), `0x800..0x4000`
  corners (byte `+0x11` & 8 / 0x10 / 0x20 / 0x40), `0x8000` visited; no instruction sets or tests `0x200` or `0x400`.
- **Z in a side grid**, one byte per cell, indexed by the 16-bit registration cell (`rec[8] | rec[0x12] << 8`,
  `rec[9] | rec[0x13] << 8`). Without sc3bigcity those high bytes stay 0 because the patch turns Remove's
  (`0x10007fea`) and Init's (`0x10005ed9`) `mov word [rec+0x10], 0` into dword stores, the same bytes bigcity clears.
- X stays the record's size byte `+0xa`, so every stock reader that uses n as the x extent, the placeholder index or
  GetCellSizeOfSprite keeps working.

### 8.2 Sites

| what | where | change |
|---|---|---|
| sprite insert | `0x10019341` | X = vt+0xd4, Z = vt+0xd8; pre-insert removal X x Z; size passed to Insert = X, or X, Z << 8 and the tag 0x5A3C0000 when Z != X |
| cell map Insert | `0x10007b58`, `0x10007c52`, `0x10007c9d`, `0x10007d02`, `0x10007d27` | decode; z loop and +z corners use Z; flag 2 (multi-cell) from the longest side; 0x400 on the X x Z cells + side grid before the bucket registration (`0x10007da5`) and the dirty rect (`0x10007dbe`) |
| registration view cell | `0x1000c678`, `0x1000f6f4` | C copies, 16-bit anchors: r1 vz += 1 - X, r2 vx += X - 1 and vz += 1 - Z, r3 vx += Z - 1 (the lot's left vertex) |
| sort key | `0x1000c14b` (low zooms), `0x1000d63f` (high zooms) | key - (B - A) * 0x2000 (A, B = view extents; section 8.3) |
| depth boxes | `0x1000c15d`, `0x1000d64c`, do_pick `0x10009afd` | z end = z0 + Z |
| pixel widths | `0x1000bffb`, `0x1000d506`, `0x1000cadc`, `0x100092e5`, `0x10009433`, `0x100099a6`, `0x10009bd9`, `0x1000ae86`, `0x1000f7ec` | longest side instead of n (the lot is (X + Z) / 2 cells wide; max(X, Z) is never smaller) |
| single-cell tests | `0x1000bf8d`, `0x1000d4aa`, `0x1000ca88` | a 0x400 record takes the multi-cell path (1 x Z lots) |
| other Z uses | GetHeightOfSprite `0x1000b303`, pixel-bounds fill `0x10008116` | (X + Z) / 2 diamond height; z loop with Z |
| save | the `0x1001cd9a` call in all 9 copies of the filler (pattern addresses): SIMGEOM `0x1001cd94`, SIMMISC `0x100359f6`, SIMRCI `0x1003d498`, SIMNTWRK `0x10023b96`, SIMDSTR `0x1002dfa9`, SIMECO `0x10014b7c`, SIMSERV `0x10014f14`, SIMUTIL `0x100199b4`, SimTransit `0x10015e04` | vt+0xd4 -> vt+0xd8 (pattern byte +8): bits 6-11 = Z |

Not changed: ChangeSprite `0x1000f2c2` (its block loop rewrites the registration record only, stock), the placeholder
sprite `this+0x48c + n * 4` (uses X), GetCellSizeOfSprite `0x10008f8a` (returns X), and the effect anchors that centre
on an occupant with SizeInCellsX only (SIMSPR `0x10032e3e`, `0x10039850`, `0x1003ccbd`, `0x1002249b`) `[not run]`.

### 8.3 Draw order

The display list sorter (`0x1000c6f0`, comparator `0x1000c7a6`) orders two cell sprites by the key `+0x14 =
-(vx + vz) * 0x4000 - (alt >> 2) * 0x100 + 0x3fffc000` of their registration view cell alone (world boxes only decide
between a cell sprite and a dynamic sprite). For a square that cell is the block's centre depth. For an A x B view block
the centre is (B - A) / 2 cells further. Measured on the first build: a park on the 2x3's +x side drew over the
building's front face in rotation 2 (and on the 3x2 in rotation 3), the keys tied. B - A = Z - X in rotations 0 and 2,
X - Z in 1 and 3. With the correction the order against square neighbours is exact for |X - Z| = 1 (2x3, 3x2, 3x4,
4x5, 1x2). For |X - Z| >= 2 one neighbour cell behind the far end and one in front of the near end share the centre
depth and no single key orders both (derivation in `sc3perf_lotrect.c`, K). The 1x3 test showed no wrong overlap at
zoom 4 in any rotation.

### 8.4 Art anchors (for the importer)

LOTRECT registers the sprite at the **true X x Z lot's left vertex** in every view rotation. So the anchor of every frame
of a w x d building is that vertex: L = 0 in all four slots, T from the same point (the probe's L = (d - w) x W / 2 in
slots 2 and 3 was for the stock X x X registration). `verify/lotdraw/work/make_lotrect.py` writes these anchors
(`LOTRECT_STOCK_ANCHOR=1` writes the probe's). Without LOTRECT such art is placed (d - w) x W / 2 px off in two of the
four rotations and cut, so a non-square exemplar needs the switch on (`SC3PERF_LOT_RECT`, sc3perf loaded).

### 8.5 Answers to section 7

- The 3x2 ghost: the stock Insert wrote a 3x3 block, and the bulldoze rebuilt only the occupant's 3x2 rect, so the third
  row kept the sprite pointer. With LOTRECT the block is 3x2 and nothing is left (measured).
- The third-row highlight colour: with the whole lot under the sprite no highlight colour stays after placement
  (measured); the highlighter path itself was not read.

## 9. The importer side (lotshape, round 2026-11-20e)

Code: `re/tools/bldimport/bldimport.py`, `bldrender.py`, `bldweb.js` (the page's copy of both, byte identical),
`classifier.html`, `re/tools/sc4conv/sc4conv.py`, `props.py`, `lottex.py`, `re/tools/bldimport/sc4web.js`. Results:
`verify/lotshape/RESULTS.md`.

- **models.json** `"lot": [w, d]`, w and d from 1 to 5 each, for kinds `landmark` and `reward` only (`RECT_KINDS`).
  w = prop 0x66 value 0 = SizeInCellsX, along the model's X axis; d = prop 0x66 value 2 = SizeInCellsZ, along Z.
  Growables, ports and civic looks stay square (section 5.4; a civic look keeps its base's lot). 3x2 (X > Z) is
  written as given: with LOTRECT both orientations draw whole (section 8), so nothing is turned.
- **Frames** (`bldrender.render_frame`): slot 0 has u = 0..w, v = 0..d; each slot step (u, v) -> (v, e_u - u) with the
  u extent before the step, so slots 1 and 3 are d x w. Width (e_u + e_v) x W / 2, B = e_v x W / 4 + 1, anchor (0, T) =
  the lot's left vertex in every slot, which is where LOTRECT registers the sprite (8.4). Measured against the lotdraw
  probe's generator at zoom 0: 2x3 frames 20 px wide, T 8 / 10 / 8 / 10 in slots 0-3 (`make_lotrect.py` gives the
  same). A square lot n and (n, n) give the same bytes.
- **Stats**: the stock base of the longer side, prop 0x66 rewritten to (w, the base's height, d). 5x5 bases: landmark
  9500 (San Francisco City Hall), reward 8046 (Country Club). Rewards skip a base whose type's [AgentTypeHierarchy]
  parent is 11000 Military: the first 5x5 reward by id is 8023 Defense Contractor (type 11001 under 11000), and a new
  reward's type takes its base's parent (`agent_type_rows`). No base of 1x1 to 4x4 has that parent.
- **SC4 converter**: a landmark or reward takes its SC4 lot (`real_lot`: `props.choose_lot`, turned into the model
  frame by kb - 2 quarter turns) when both sides are 1..5 and the footprint fits it, else the smallest square (now up to
  5x5). The props window and the lot-texture canvas are w x d (`props.plan`, `lottex.composite`). Growables keep the
  smallest square.
