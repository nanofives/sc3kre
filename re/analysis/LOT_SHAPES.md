# LOT_SHAPES: non-square building lots (2x3) in SC3U (lot2x3, round 2026-11-20d)

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
| save | SIMGEOM `sc3_record_fill_descriptor` `0x1001cd38` | `0x1001cd9a` and `0x1001cda8` both vt+0xd4, `0x1001cdb4` SetSizeInCells(X, X) (`0x1001dd82`: bits 0-5 / 6-11 of record `+8`) | **yes** |
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
- SIMGEOM `0x1001cda8`: `call [eax+0xd4]` -> `call [eax+0xd8]` (one byte) so saves record X x Z.

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
