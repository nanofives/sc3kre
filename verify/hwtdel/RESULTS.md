# hwtdel results: deleting highway beside an interchange left 15149 in it (owner bug, 2026-10-22)

Owner report (LAN build 4f780c5, `img15_t_broken_after_delete.png`): "deleting adjacent highway pieces breaks the T
intersection nearby". A block of cells of a built hwt T showed the stock 15149 "Highway Construction" marks.
Orchestrator scope after the cause: the fix as shared helpers in `sc3netmod_hwy.c`, the same repro against hwt, hwx,
hwdx, hwdd and hwave, every block that shows the class fixed.

## Cause

1. A highway pass reads the retile rect plus 8 cells (`hwy_begin`), and `hwy_end` reverts every declared piece one
   cell inside that box that no block kept. A block that recognises or keeps a built interchange from the cells
   inside the box only misses one the box just grazes. Owner log: the pass over (16,39)-(42,62) after an 80-occupant
   bulldoze of the cloverleaf beside the T held only (41,47) of the T, and logged
   `(41,47) piece 21227.2 kept by no block -> stock retile`.
2. That stock revert retile (mask 3) re-tiles the whole highway run around the cell, and the road beside it. Next to
   an interchange's land pieces (Protected HWAY bases) the stock tiler writes the side-hit 15149. Measured: one revert
   at (61,31) left 15149 in 13 T cells up to 6 cells away. The re-place after reverts covers only cells a block kept.
3. Cells an interchange leaves stock (plain arm and through cells) were never kept, so a revert retile, or the game's
   own retile of a nearby bulldoze, left 15149 there for good.

## The repro per block (lab city with all five, a short separate highway dragged beside each)

Each drag puts the pass box over the edge of one structure. Old = main 4f780c5's sc3netmod, new = this branch.

| block | grazing drag | old build | new build |
|---|---|---|---|
| hwt | (45,34)-(45,42), box takes the T's west column | **broken**: 2 T cells reverted, then 15149 in 15 T cells, stem cell 21200 lost (`owner_shots/hwtdel_blocks_sheet.png` row 1) | no revert, no change |
| hwt | (69,35)-(69,43), box takes the T's east column (first repro) | **broken**: 13 cells 15149 | kept, no change |
| hwx | (58,18)-(63,18) north, (58,44)-(65,44) south, slope stub at x 81..82 east | no change | no change |
| hwdx | (116,78)-(116,84), box takes its north-east corner | no change, but 24 `### hwdx: cell refused` lines (cells past the box) | no change, no ### lines |
| hwdd | (142,26)-(142,32), box takes its south-east corner | no change, but `### hwdd: 79 cells refused` | no change, no ### line |
| hwave | (128,40)-(128,46), box takes the transition's west column | **broken**: its 2 column-135 cells `kept by no block -> stock retile`, and that retile turned 3 rows of the avenue's one-way lanes (21700) back to stock 11204 | no revert, no change |

So the 15149 class shows in hwt (any grazing pass) and hwave (a pass whose box edge falls on the transition: hwave
looked for its pieces only from 3 cells inside the box). hwx, hwdx and hwdd already read their footprint past the box.
Their holes showed in the bulldoze checks instead (next table).

## Bulldoze next to each, undo / redo, save + reload, no-mod load (new build, final)

Bulldoze = sc3undo's paused test drag with the Demolish tool (a strip across one arm, right past the footprint),
saves before / after / undone / redone compared byte for byte (`re/tools/undo/cmp_saves.py`).

| block | bulldoze | result | undo / redo | reload with the mod | no-mod load |
|---|---|---|---|---|---|
| hwt | through highway at x 49..50, 2 cells past the T | T kept, 15 cells re-put (the game's retile had changed them) | byte-identical both | 0 written, 0 reverted, 0 cells 15149 | loads, highways whole |
| hwx | east arm at x 76..77, 2 cells past the cloverleaf | old: ramps removed ("an arm is not plain straight highway"), a reload rebuilt them. New: cloverleaf kept, 4 arm cells the game's retile made 15149 put back, the 2 cells next to the cut capped (15054.2 / 15053.2) | byte-identical both | 0 / 0, 0 cells 15149 | loads |
| hwdx | diagonal arm at (113..114, 97..98) | 2 quadrants drop (its rule: a quadrant whose join no longer holds). New: 8 cells the reverts left as 15149 put back, the dropped quadrant's join cells back to plain highway, its border-row cells taken back | byte-identical (S0 vs S2: 1 B of the flammability grid, the known benign section) | 0 / 0, 0 cells 15149 (before the border-row fix: 2 leftovers cleaned on load) | loads |
| hwdd | both diagonal arms at x 139..140 | cloverleaf becomes the flyover (its rule: arms must run on 2 rows), every kept cell re-placed, no 15149 | byte-identical both | 0 / 0, 0 cells 15149 | loads |
| hwave | the highway behind, the transition and the avenue (strip z 32..43) | transition goes back to the stock ends (its rule) | byte-identical both | 0 / 0, 0 cells 15149 | loads |

T only, earlier build of this branch (before the hwx / hwdx / hwave work): the owner-like case (T + cloverleaf, a
cloverleaf arm bulldozed) clean, a through lane cut inside the T breaks cleanly with stock caps on both sides of the
gap, and a city saved by the unfixed build with 13 cells of 15149 is repaired by the load pass.
Frames: `MAIN\verify\hwtdel\owner_shots\hwtdel_blocks_sheet.png` (per block), `hwtdel_sheet.png` (T), single frames
`hwtdel_blk_*.png` / `hwtdel_*.png`. The no-mod frames show each save's default view, not every structure.

## Fix

Shared (`sc3netmod_hwy.c`, task hwtdel):
- `hwy_rd`: any map cell (the buffer inside the box, a fresh read past it). hwcap_rd, hwdx_rd, hwdd_rd now call it.
- `hwy_put` past the buffer never writes. A cell already holding the piece is kept for the re-place (`hwy_keep_far`),
  else -1. So every block's "put all my cells" loop keeps its cells past the box, and hwdx / hwdd stop logging
  refusals.
- The 15149 net: when a pass reverts anything, `hwy_end` snapshots the box plus 8 cells first. Afterwards a cell that
  turned into 15149 gets its snapshot piece back. For our own on-highway piece reverted in place, it gets the stock
  piece that piece saves as (`hwy_stock_of`: hwys table / save id / base), unless that is 15149 itself (stub pieces).
  A 15149 the game made before the pass stays.
- `hwy_unput`: takes back a cell of an interchange part that no longer holds when it is on the box's border row or
  past it (land: `hwy_drop`, on highway: its stock piece, border row only).
- `hwy_gap_cap`: the stock end cap facing a bulldozed neighbour, for a cut interchange's straight cells.

Per block (each uses the shared helpers, marked task hwtdel):
- hwt: votes over the whole footprint (a grazed T is recognised), keeps its cells past the box, `hwt_band` keeps its
  plain cells and repairs 15149 there (2 past the T: only next to a cut, as the cap), a failed full T is never re-read
  as a right-in / right-out T (that turned a full T into a RIO one with its far ramps removed), broken-T ends capped.
- hwx: ramps counted over the whole footprint, a built cloverleaf accepts re-tiled arm cells, every cell put (kept
  past the box), `hwx_band` (same as hwt_band), unput takes back border / past-box cells and caps junction cells next
  to a cut (the X-broken case left open ends: kept straight pieces forced over the stock caps).
- hwdx: a dropped quadrant's border-row / past-box cells taken back.
- hwdd: no logic change (the shared put / read / net cover it), its unbuild no longer tries to write past the box.
- hwave: built transitions looked up from 1 cell inside the box instead of 3, checked and kept with hwy_rd /
  hwy_keep_far.

Needs block-specific code beyond the helpers: hwt (vote threshold, RIO re-read), hwx (re-tiled arm acceptance) and
hwave (scan bounds), all done. Behaviour the owner did not report that changed: the hwx ramps no longer go when a
nearby bulldoze re-tiles an arm, broken T / X ends get stock caps, and a broken full T is not re-read as RIO.

## Lab notes

- Old vs new: the old DLL was built from `git archive 4f780c5 re/harness/src`.
- `rb_lab cam`'s zoom job sometimes fails ("system error"), and the game then froze at the next Frida call several times
  (old and new DLL alike, no netmod pass running). One session per group with one camera call avoids most of it.
  The window was also found maximized once (3840x1992 client), which breaks every pixel: restore it first.
- Drags outside the lab's flat windows hit slopes (x 81..82: a 2-cell slope stub). The GZ retile message
  (`nr_drive.py retile`) is not a substitute: its work box came out (0,0)-(0,0).
- sc3undo records only while paused: use its test commands (`SC3UNDO_TEST=1`, WM_APP+0x5d0: 10 tool, 12 GZ drag,
  13 save, 1 undo, 2 redo) and `SC3RESIZE_FRAMEDUMP`, no Frida while paused. Its temp folder of a previous PID is
  deleted at the next launch: copy the test saves first.
- Lab scripts (instance folder, not committed): `group.sh` (grazing), `undo_group.sh` + `undo_group.py`,
  `reload.sh`, `sweep.py` (grids), `drag.py` (refuses off-view pixels), `up.sh`.
