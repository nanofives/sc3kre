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
- **Growables: not in stock.** The zone developer (SIMRCI `0x10027699`) reads only SizeInCellsX and lays out n x n blocks. Section 11 (lotgrow): all 16 rule bodies do, the rest of the zone path is already rectangular, so it is a rule-body patch.
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

### 5.4 Growables (superseded by section 11)

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

## 10. Civic looks (civlot, round 2026-11-23b)

Civic looks take [w, d] too (CIVIC_REWARD.md 8): kind civic is in RECT_KINDS, stats from the button's own exemplar.
One extra rule for them: X <= Z, because a saved look whose key is gone comes back as a square exemplar of its type with
side = the saved X (SIMGEOM `0x100038a8` -> SIMINIT `0x1000cb3d`). A w > d civic lot is installed turned a quarter.

## 11. Growables: can zone growth place a w x d lot? (lotgrow, round 2026-11-24c)

Static reading only (SIMRCI, SIMINIT, SIMGEOM exports; rule vtables read from `original/modules/SIMRCI.DLL`). Nothing
built, nothing run. Replaces section 5.4, which named one developer body: there are 16 rule bodies, and 11.2 lists which
of them assume a square. DLL addresses are Ghidra VAs.

**Verdict: feasible with code, in one layer.** The zone layer already works in rectangles: the buildable block it hands
to a rule is W x D with W and D grown independently, PlaceBuilding claims and clears X x Z, abandonment and
re-occupation re-place the same attrib at its origin, and the per-tile evaluator finds a building by its origin cell. The
square lives only in the **rule Apply bodies**, which read SizeInCellsX (attrib vt+0x40) and use it for both axes. No
rule body calls SizeInCellsZ (vt+0x44). Drawing is LOTRECT (section 8), the save field is LOTRECT's filler patch.

### 11.1 The developer path, end to end

| step | what | where |
|---|---|---|
| 1 | Zone tick: W*H/30 tiles per sim day, each to its zone's developer (res / com / ind evaluator) | SIMRCI `0x1003372a` (ZONE_REDEVELOPMENT 1) |
| 2 | Evaluator: building at the tile? `SurfaceOccupantManager vt+0x7c`, then occupant vt+0xbc (origin x, z). **A tile that is not the origin returns 0**, so a building of any shape is evaluated once per pass, at its origin | res `0x10028f12` (com `0x1000fd53`, ind `0x10017fc0`) [CONFIRMED @ 0x10028f12] |
| 3 | Empty tile or a redevelopment roll: class pickers, then develop | `0x100295dc` / `0x1002971a` / `0x100298af`, develop `0x10029666` |
| 4 | Develop: ZoneLayer vt+0x74 FindBuildableRect(rect, x, z, dist, minLV, oldClass, 0), then up to `min(4, n)` rules at random without replacement, rule vt+0x1c Apply(rect, newClass, demand - filled, max) until one returns true | `0x10029666`, `0x10029962` [CONFIRMED] |
| 5 | FindBuildableRect: rect = the seed cell, then one column on -x or +x (`0x10033525`) and one row on -z or +z (`0x10033611`) in turn, each only while every cell of the new column or row passes the tile test. **W and D grow independently: the block is a rectangle** | `0x100332e4` [CONFIRMED] |
| 6 | Tile test: zone type == the seed's, a second layer byte (`this+600` vt+0x48) == the seed's, powered (`+0x260`), land value >= minLV (`+0x264`), IsNearTransport. An occupied cell passes when its occupant is a building without flag 0x200 that is abandoned, or of type == oldClass, or has attrib flag 0x100 (filler) | `0x10033368` [CONFIRMED] |
| 7 | Rule Apply: class -> the first family record with that LandUse, crop the block to the rule's max side, then place members on a local occupancy grid (10 x 10 bytes, stride 10) | 16 bodies, table below |
| 8 | PlaceBuilding(attrib, cell, state, rotation in degrees, check): footprint = **X (vt+0x40) by Z (vt+0x44)**. Check: zone type equal over x0..x0+X, z0..z0+Z clamped to the map. Every footprint cell must pass `+0x244 vt+0x6c`; a building occupant in it is removed (vt+0x48) unless flag 0x800, any other occupant refuses. Then the occupant is created from the key, positioned (vt+0xf0), rotated (vt+0x108, degrees * 0xffff / 360), given its state (vt+0x50) and inserted | ZoneLayer `0x10032dfc` (slot +0x68), key form `0x1003306d` (+0x64) [CONFIRMED] |
| 9 | Abandon, re-occupy, construction done: the same key re-placed at the origin with the occupant's own rotation (vt+0xb0) and the new state | `0x10029a38` (ind copy `0x100191fe`) [CONFIRMED] |

Merging lots is steps 5 and 6: the rect grows over same-class, abandoned and filler neighbours, and step 8 removes every
old building a new footprint touches. Redevelopment and merging need nothing shape-specific beyond step 7.

Rule CLSID -> Apply body (factory in `sc3_rci_director_ctor` `0x10036382`, slot 0x1c of the ctor's second vtable, read
from the PE), families from `SC3ZoneLayer.ini [ZoneDeveloperRules]`, LandUse from `BUILDFAM.IXF`:

| rule | Apply (vtable +0x1c) | layout | families (LandUse) |
|---|---|---|---|
| 0xa22653c0 | `0x10026b01` (`0x1004ccb0`) | block fill | 11 (3100), 4 (3300), 31 (3500, dev 1), 10 (3500, dev 2/3) |
| 0x822c9d13 | `0x10020762` (`0x1004c8dc`) | block fill | 13 (4700), 14 (4500), 15 (4300) |
| 0x422b55f2 | `0x10014794` (`0x1004c3e8`) | block fill | 5 (8100), 20 (8700) |
| 0x822c9d24 | `0x100152a2` (`0x1004c428`) | block fill | 6 (8300), 19 (8900) |
| 0xc22c9d34 | `0x10013c66` (`0x1004c3a8`) | block fill | 18 (8500), 21 (9100) |
| 0x822c9d62 | `0x1000c3eb` (`0x1004c10c`) | block fill | 22 (6700), 24 (6300) |
| 0x222c9d00 | `0x10027699` (`0x1004ccf0`) | corners + strip + fill | 12 (3900), 16 (3700), 17 (4100) |
| 0x622c9d42 | `0x1000dd1a` (`0x1004c18c`) | corners + strip + fill | 8 (5700), 23 (6100) |
| 0x422c9d52 | `0x1000cf87` (`0x1004c14c`) | com block | 7 (5100), 9 (5500) |
| 0x61f44687 | `0x1002a1af` (`0x1004cd6c`) | fixed: row houses | 1 (3900) |
| 0xe22f4a83 | `0x10011721` (`0x1004c328`) | fixed: large lot | 10 (3500) |
| 0x630ea608 | `0x10012661` (`0x1004c368`) | fixed: L of three copies (`0x10012715`, `0x10012ab3`, `0x1001305a`) | 16 (3700), 28 (3900), 29 (4300), 30 (4500) |
| 0xa2c1eda3 | `0x100015ab` (`0x1004b17c`) | fixed: farm | 25 (9300) |
| 0x2207d9ee, 0x81ffc3ce, 0xc2d3fd7e, 0xe2d3fd92 | `0x100032d1`, `0x1002b04c`, `0x1002d27f`, `0x1002c12a` | airport, seaport (dev 14, 15) | 2, 3, 26, 27 |

The six "block fill" bodies are one algorithm. The five 785-byte ones are the same code with their own tunables (their
decompilations hash equal once DAT names are blanked). `0x10026b01` (763 bytes) is the same without the per-cell
IsNearTransport test. Block tunables (SC3Tune `[ZoneDeveloperRules]`, read for 0x222c9d00 by `0x1002713c`): min side
(both axes), max side (both axes, capped at 10), demand threshold %, pick %.

### 11.2 Every place a square is assumed

| site | what | square? |
|---|---|---|
| block fill x6 (11.1) | one vt+0x40 = n. Fits if `(n-1) + dx < W` and `(n-1) + dz < D`, grid fill n rows of n bytes, only the anchor cell is tested free (`0x10020762`, `0x10026b01`) | **yes** (n on both axes) |
| corners + strip + fill (`0x10027699`, `0x1000dd1a`) | a corner lot at each block corner whose two edges are fully road-adjacent (ZoneLayer vt+0x70 count == edge length), offset by n on both axes, a 1-row strip of filler beside it, then the block fill | **yes** |
| com block `0x1000cf87` | `n <= W && n <= D`, then `(n-1)+dx < W`, `(n-1)+dz < D` | **yes** |
| row houses `0x1002a1af` | block even and >= 6 per side, capped at 8; 2-cell steps along the edges, 1-cell steps inside; never reads a size | **yes, hard-coded** |
| large lot `0x10011721` | block 4..6 per side; one n x n centre building at a random inner cell; 1x1 corner and edge pieces sorted by attrib flags (`0x10011078`); an empty side reuses the opposite side's piece turned 180 degrees (`0x100114be` sets the flag, `0x100133ac` passes 0xb4) | **yes** |
| L layouts `0x10012715`, `0x10012ab3`, `0x1001305a` | 2n (3n, 1n) deep blocks of three copies of one n x n member plus fillers | **yes** |
| farm `0x100015ab` | n x n farmhouse, then 1x1 field pieces at rotation 0 or 90 degrees (`rand(100) > 50`, constant 0x5a) | **yes** |
| family list split `0x100274bb` | corner list = flag 0x100 clear and X >= 3 | X only (tuning) |
| evaluator divisor (`0x10028f12`) | no-service, negative-demand, construction and density rolls scaled by x = vt+0x40 (ZONE_REDEVELOPMENT 5.5) | X only (tuning) |
| PlaceBuilding `0x10032dfc`, re-place `0x10029a38` | X and Z | no |
| FindBuildableRect `0x100332e4` | W and D | no |
| occupant grid, bounds, bulldoze, Mover (section 1) | X and Z | no |
| sprite insert and draw (section 1) | X only | yes, fixed by LOTRECT (section 8) |
| save filler (9 copies) | X twice | yes, fixed by LOTRECT (8.2) |
| load, key present (SIMGEOM `0x10002cc2`) | size from the exemplar | no |
| load, key gone: stand-in | SIMINIT `0x1000c60c` indexes the attrib cache by (type, (X, Z)) for 25 parent types (3000 .. 15421) with only the keys (1,1) .. (5,5) created, so a non-square entry is never indexed. `0x1000cb3d` asks for (saved type, (saved X, saved X)) | **yes**: a missing w x d growable comes back as a random stock w x w of its type |
| BAT replacement list (SIMINIT `0x100053be`, SIMUI `0x1001bb56`) | filtered by X | yes (keep non-square ids out of `[ReplaceableBuildings]`) |
| loading placeholder (SIMSPR record `+0xa` indexes `this+0x48c`) | drawn while a sprite is not prepared at a zoom, sized by X | yes, briefly, as for LOTRECT landmarks today |
| construction (state 4) and abandoned (state 2) art | which sprite a growable shows in these states was not read | `[UNCERTAIN]`: needs the building occupant's sprite choice per state, or one look at a w x d growable under construction |

Rotation: every block, corner and com placement passes rotation 0 (`..., 4, 0, 1` at each PlaceBuilding call). The
exceptions are the large-lot 180-degree fallback and the farm fields' 0 / 90 degrees above. The footprint getters
ignore rotation (section 1), so a 2x3 and a 3x2 are two exemplars, not one building turned. A 180-degree turn keeps a
rectangle on the same cells and with LOTRECT draws as view slot r + 2 (derived, not run).

### 11.3 What a w x d growable needs

1. **Rule bodies (the one real change).** Replace the rule-interface vtable slot 0x1c (one `.rdata` pointer per rule)
   with a C copy that reads X and Z: fits if `(X-1)+dx < W` and `(Z-1)+dz < D`, fills X rows of Z bytes, and when
   X != Z refuses an anchor whose X x Z grid is not all free (stock tests the anchor only, and PlaceBuilding then
   removes any building the new one overlaps). Square members must take exactly the stock path and the same
   `cRZRandom::RandomUint32Uniform` calls on the rule's `this+0x18`, so square-only cities grow as before.
   - block fill: 1 C body, 6 slots (`0x1004ccb0`, `0x1004c8dc`, `0x1004c3e8`, `0x1004c428`, `0x1004c3a8`,
     `0x1004c10c`, each +0x1c), a flag for the IsNearTransport test (5 of the 6).
   - corners + strip + fill: 1 C body, 2 slots (`0x1004ccf0`, `0x1004c18c` +0x1c). Corner offsets: x by X, z by Z.
   - com block: 1 C body, 1 slot (`0x1004c14c` +0x1c).
   - The fixed layouts stay stock: non-square ids never go in families 1, 10, 16, 25, 28, 29, 30. Classes 3500 and
     3700 reach a generic rule only through families 10 and 16, which a fixed rule shares, so they need a copy family
     (instance 32+) and an edited `[ZoneDeveloperRules]` row pointing the generic rule at it (data, SYS.PAK).
2. **Orientation: X < Z only.** Growables are placed at rotation 0 and the footprint does not turn, so the long side
   always runs along z. A 3x2 twin (X > Z) would, on a load without the package, come back as a 3x3 stand-in one row
   over its neighbour (11.2, stand-in). X < Z comes back as an X x X stand-in on part of the lot and the rest regrows.
   Same rule as civic looks (section 10). Allowing both orientations would need the stand-in path patched, which does
   not help a player who removed the mods.
3. **|X - Z| = 1 only** (1x2, 2x3, 3x4, 4x5). Growables stand packed against neighbours on all sides, and LOTRECT's draw
   order is exact only for |X - Z| = 1 (8.3).
4. **LOTRECT on** (sc3perf `lot_rect`) for drawing and for a save field that records Z. Without it the lot draws cut
   (section 2) and the save field says X x X. The game still rebuilds X x Z from the exemplar on load.
5. **Data:** exemplar prop 0x66 = (X, height, Z) with the stats of the size-Z base, 20 frames for the X x Z diamond with
   LOTRECT anchors (8.4, bldimport writes them for landmarks today), a family line (netpack `growables`), attrib flags
   `+0xbc` without layout-role bits (0x1..0x800 sort pieces in `0x10011078`, 0x100 marks filler in `0x100274bb`), not
   in `[ReplaceableBuildings]`.
6. **Without the mods.** Save opened in stock with the package installed: the occupant is X x Z, drawn cut (section 2).
   Package removed: an X x X stand-in of the same type (11.2), or nothing when no stock X x X of that type exists.
   `[static: neither load was run for a growable]`

### 11.4 Size of the change and a smaller first step

- **Full (every generic rule, R, C and I):** 3 C bodies (about 120, 250 and 150 lines, from 785, 1862 and 1266 byte
  originals), 9 vtable-slot writes in SIMRCI `.rdata`, one switch, a byte check of each slot's old pointer. Risk:
  medium. The code runs on every develop call of every zone, so a slip stops or skews growth city-wide, and the RNG
  order must match stock for square members. Gate: same save, switch off and on, no non-square members installed,
  occupant layers identical after N game days. Home: sc3simrun, which already patches SIMRCI (CHURN, SANDBOX).
- **First step (code):** rule 0xa22653c0 only, block fill `0x10026b01`, one slot (`0x1004ccb0` +0x1c), 1x2 and 2x3
  members in families 11 (3100) and 4 (3300), which no other rule uses. Low-density residential, one C body of about
  120 lines. The data side is what the importer already writes for landmarks, plus growable kinds accepting [w, d]
  with w < d and |w - d| = 1.
- **No-code alternative (available today):** the model on the smallest square lot that holds it, the rest of the lot
  dressed (objprops stream). Works in every rule and in stock, costs density.

## 12. Growables built: sc3simrun LOTGROW (lotgrowb, round 2026-11-24d)

Code: `re/harness/src/sc3simrun_lotgrow.c` (included by `sc3simrun.c`), table `sc3simrun_lotgrow_tab.h` from
`re/tools/lotgrow_tab.py`. Results and pictures: `verify/lotgrowb/RESULTS.md`.

### 12.1 What it does

- Home: sc3simrun, the mod that already patches the zone developer (CHURN, SANDBOX, GENTLE, LVWRAP). LOTRECT stays in
  sc3perf; LOTGROW only reads whether it is in (SIMSPR `0x10019341` is a jmp into sc3perf.dll).
- The 9 rule-interface slots 0x1c of 11.3.1 (SIMRCI `0x1004cccc`, `0x1004c8f8`, `0x1004c404`, `0x1004c444`, `0x1004c3c4`,
  `0x1004c128`, `0x1004cd0c`, `0x1004c1a8`, `0x1004c168`) point at C copies of the bodies, written after a byte check:
  SIMRCI TimeDateStamp `0x38fd559f` and SizeOfImage `0x60000`, each slot's pointer, an FNV-1a hash of each body with its
  relocated dwords zeroed, and each tunable among the body's relocated operands. All or nothing.
- Each copy follows its body instruction by instruction: the same `cRZRandom::RandomUint32Uniform` (`0x10039a9a`) calls
  on `rule+0x18`, the same ZoneLayer calls with the same arguments (`vt+0x68` PlaceBuilding, `vt+0x6c` transport,
  `vt+0x70` road count along an edge), the same signed / unsigned compares. A member with X == Z takes that path.
- X != Z (X from attrib `vt+0x40`, Z from `vt+0x44`): the z extent uses Z (bounds, grid mark X rows of Z bytes, corner
  and strip offsets on z), the anchor is refused unless all X x Z grid cells are free, and the member is refused while
  LOTRECT is not in, or when X > Z or Z - X != 1. A refused member is "does not fit" (at a corner it takes the n x n path
  so the RNG calls are the same, then is not placed).
- Two facts found while copying: `0x10027699` skips the corner step when the corner list is empty (`jbe` at
  `0x1002790c`); `0x1000dd1a` has no such guard and draws from the empty list (`rand(0)` = 0). `0x1000dd1a` is 1,847
  bytes (Ghidra's 1,862 runs into the next function at `0x1000e451`).
- Switch: `simrun.ini [lotgrow] enabled=1`, env `SC3SIMRUN_LOTGROW=0` leaves every slot stock. Mods page row "Non-square
  zoned buildings" (sc3resize MODTOGGLE, '-' row, default on).

### 12.2 The identity check

The rule RNGs are seeded from `timeGetTime` (`cRZRandom::Seed` `0x10039a7f`), so two runs of one save never grow alike
and a switch-off vs switch-on comparison of occupant layers across runs cannot be equal. VERIFY mode
(`SC3SIMRUN_LOTGROW_VERIFY=1`) checks in lockstep instead: each Apply runs the copy for real while a proxy ZoneLayer
records every call and answer, then the stock body runs on the same rect / class / demand with the seed put back and
`rule+0x38` pointed at a replay layer that checks each call and returns the recorded answer; the final seed and the
result are compared. Measured with no non-square member installed: Sacramento 1,487 Apply calls and Europolis 1024
99,891, all identical (7,019 and 231,849 layer calls checked); with members installed, every difference fell on a call
where a non-square member was drawn (0 unexplained in Sacramento, Berlin, Madison). All 9 bodies ran (dense commercial
`0x1000c3eb`: 532 calls in Berlin).

### 12.3 Answers to 11.2's open rows (measured)

- Construction (state 4), standing (1) and abandoned (2): one sprite over the whole X x Z lot, record flag 0x400 on every
  cell (`lab.py cells`), drawn by the building's own frames.
- Save: the occupant records hold the true size (217 of them in one Sacramento autosave: 1x2 and 2x3).
- Package removed (mods on): each X x Z building came back as a 1x1 stock building of its class on its origin cell, the
  other cell empty zoned land (Sacramento, 1x2 at (218,66) -> id 0x13bc 8900 1x1 at (218,66)). With X < Z the stand-in
  stays inside the lot, as 11.3.2 derived.
- Bulldoze with the Demolish tool: both cells cleared, ordinary single-cell sprites without 0x400 left.
- Cost: 0.12 to 0.13 ms per Apply in Sacramento and Berlin with VERIFY on (copy + stock replay + PlaceBuilding), 1.4 s of
  sim-thread time over 25 minutes of Berlin.

### 12.4 Data side (bldimport, task lotgrowb)

Growables accept "lot": [w, d] = 1x2, 2x3, 3x4. Stats of the class's d x d base. Family lines only in families no fixed
rule uses (`FIXED_FAMILIES` 1, 10, 16, 25, 28, 29, 30). Classes 3500 and 3700 get copy families 38100 (of 10) and 38116
(of 16) holding the family's members plus ours, and the generic rule rows `2,0xa22653c0`, `3,0xa22653c0` (10 -> 38100),
`2,0x222c9d00`, `3,0x222c9d00` (16 -> 38116) are rewritten in the overlay SYS.PAK. Measured live: class 3700 members drawn
by the residential corner rule in Madison (the copy family loaded).
