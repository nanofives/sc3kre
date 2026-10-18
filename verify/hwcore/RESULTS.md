# hwcore results (highway program shared base, 2026-10-18)

## 1. hwpaint.py (offline)

`py -3.12 re/tools/netmod/hwpaint.py proof <out>`: stock pieces rebuilt from scratch by the painter, every zoom 3 and 4
frame, all four views, compared pixel by pixel with the stock frame (tolerance 24 per channel):

| stock piece | within tolerance | exact | silhouette overlap |
|---|---|---|---|
| 73.0, 73.2, 15051.0, 15051.2 (straight highway, both carriageways, both axes) | 96.4..97.0% | 96.2..96.5% | 97.2..97.5% |
| 15127.0 (On-ramp corner: one-lane slab arc, geometry fitted) | 52..55% | 0.7% | 84..87% |
| diagonal bands (highway_diag, update 2026-10-18): 11224.0 / 15106.0 middle cells | 96.1..96.5% (zoom 4) | 95.4..95.8% | |
| 11223.0 / 11223.2 / 15052.0 / 15052.2 side cells | 90.1..90.3% (zoom 4) | 89.7..90.0% | |

Update 2026-10-18 (sibling requests): 45-degree decks and outer walls read the stock diagonal bands (the head-on wall
of 11223 view 1 now matches stock, buttresses included); the hit refinement stays inside the cell's column (the straight
pieces went from 96.7% to 97.0%); `gaps=` parapet openings; the ramp profile split holds on narrow decks (RAMP_W stays 0.62, the program width).

The straight pieces miss only a one-pixel rim along the silhouette. 15127's shape is reproduced; its slab fascia is a
smooth blue-grey that no 73 / 15051 face carries, and the painter draws slab edges with the stock plain-wall concrete,
which is most of the colour gap. Demo (`hwpaint.py demo`): a highway rising over another on a slab bridge, a 270 degree
one-lane loop on pillars, a one-lane ramp rising beside a carriageway.

## 2. sc3netmod_hwy.c (in game)

Instance `Simcity_stock_hwcore\re\harness\inst_hwcore`, package `examples/highway_core` (pieces 21100 / 21101), lab
city copy `lab2.sc3`. Log lines quoted from `sc3netmod.log`.

| step | result |
|---|---|
| highway drag (58,22)-(58,32) | `hwy: edit: highway end at (57,21) -> proof piece 21100.2 in (57,20)` and three more: 4 variants written into 4 empty (tree) cells past both ends, each with the parapet on the outer side |
| second highway drag beside it | its pass box held the first highway's ramps: kept, `4 written, 0 reverted` (the second highway's own) |
| drag again over the first highway (the stock flood retiles all of it) | the end caps 11235 / 11237 became 73 running into the ramps (read as their Protected base 15099); the ramps stayed |
| save (menu 0x10009002) | `save: 8 variant tile(s) written as base, section 0x4E56 written` |
| restart on the saved city | `load: all 8 variant tiles restored`; load pass `0 written, 0 reverted`; cells identical |
| bulldoze the two cells in front of one ramp pair | `(61,37) piece 21101.0 kept by no block -> removed (land), 3x3 retile` (and 62,37); new ramps written at the new end (61,36), (62,36) |

Shots: `verify/hwcore/art/game/g01_written.png`, `g02_after_retile.png`, `g03_reloaded.png`, `g04_revert.png` (game art,
not committed). No exceptions after the fix below.

First launch: `### hwy: exception 0xC0000005 in the highway pass`. Cause: FUN_10009c65 is a method of the On-ramp
selection object (its +0x54 = the terrain object), not of the manager; the free-cell test now reads the manager's own
terrain object (+0x30, the same city vt+0x13c object, FUN_10012609) and surface layer.

Not tested: a zoned empty cell (`hwy_free` passes it; what terrain vt+0xd0 tests is not decoded), a building next to a
highway end (buildings are occupants of the surface layer, TMPL reads them the same way, so `hwy_free` refuses them; not
run), map-edge cells (refused by rule).

## 3. hwlanes.py (offline + load check)

- Stock facts read with lanekit (`hwlanes.py stock`): carriageway lanes 73.0 x 61 / 145 (+z), 73.2 x 194 / 110 (-z),
  y 1024, speed 110,000; one-lane ramps 15123..15141 speed 74,999 / 65,000; X decks at y 512 / 1536 / 1792; curve
  headings = direction of travel at each end; English-UK curves = same key, points reversed, headings + 16 (checked on
  15104, 67840, 67841, 70145, 15360).
- `hwlanes.py demo`: lane specs for every cell of the painter's three demo scenes (bridge 34 cells, loop 9, ramp 16)
  compile with lanekit in all 7 language folders; the bridge's crossing cells get both movements in their matrix
  (`x- -> x+` and `z+ -> z-`), the loop cells one turn each.
- `hwlanes.py core`: lanes of 21100 / 21101 land exactly on stock 73's lane points (61 / 145 at y 1024, 194 / 110 on
  the 73.2 side). netpack install writes 4 new curve shapes = 16 records into every language's VPathAtt.IXF (overlay):
  read back, the 908 stock records are unchanged and the 16 new ones decode with the intended points and headings
  (English-UK reversed). The game loads the extended files through the overlay (`GZResourceD.dll` opens them) and
  restores the city; animated cars on the new lanes were not watched (no population in the lab city).

Owner sheet: `MAIN\verify\hwcore\owner_shots\hwcore_sheet.png`. How-to for the shape streams: `re/analysis/HWY_BASE.md`.

## 4. Ground under painted pieces (2026-10-18, sibling reports from hwt and hwdx)

Symptom: grey or slate-blue patches where a land piece's art is transparent (under slab ramps, between decks), and on
plain empty cells next to such pieces, in some views.

| test (lab city, same narrow slab-ramp art, highway ends along z and x, zoom 3, all four views) | result |
|---|---|
| art "from" 15127 (frame table class 1650, draw flags 0x440), pieces at states 0 / 2 | grass in all shots |
| art "from" 73 (class 29440, flags 0), "ground_under": true forced, states 0..3 | slate patches under the slabs at the x-axis ends in views 2 / 3 |
| hwt's save (t8) with its package forced to 0x40 on all 54 tables | slate patches still in window 3, view 3 |
| art "from" 15127, states 0..3, both full-column and cropped frames | grass in all 16 shots (4 ends x 4 views) |
| frames 1 px wider than the tile (hwt's), from 73 + flag | no change from the from-73 result |

Also: hwt's window-1 grey right after its pass was gone after save + reload (pixels left on screen, not stored state).
Rule (HWY_BASE.md): every painted piece that can leave ground visible takes its frame table from 15127. Mechanism,
traced statically in SIMSPR: the frame table's class id (CSATTRIB header) selects the sprite class built by the factory
(FUN_10002088 / FUN_1004c611). Class 0x672 (= 1650, 15127 and 11203) stores the terrain attached by vt+0x5c at +0xc
(FUN_10015e72) and draws it before the piece with the same draw point and clip (FUN_10015dd0); class 0x7300 (= 29440,
73's table) has a no-op vt+0x5c (FUN_10054c75), so FUN_100192aa's 0x40 path attaches nothing and no terrain is drawn
under the piece.

## 5. Saved state turn for declared pieces (hwt request, 2026-10-18)

`hwyp <piece> <land> <save id> <state delta>`: SAVEBASE writes the state as (state + delta) & 3 (save word0 bits
30-31, QUERY_ID.md), so a game without the mod reads the base turned the way the stock tiler would place it; the load
side (load_rec, after the variant id is put back) turns it back by the same delta. In game with `hwyp 21100 1 0 2` /
`hwyp 21101 1 0 2`: live 21100.2 at (57,20) and 21101.0 at (57,33) were saved as 15099.0 and 15099.2 (read with
tiler.City.load); reloaded with the mod: `load: all 4 variant tiles restored`, cells 21100.2 / 21101.2 / 21101.0 /
21100.0 as before, load pass 0 written, 0 reverted. With SC3NETMOD_HWY=0 the load side does not know the delta and the
restored variants stay turned.

Superseded the same day by the general form: `hwys <piece> <id0> <st0> .. <id3> <st3>` (saved id and state per state),
and the variant section now records the original state (id bits 16-17, flag bit 18; an older DLL skips such entries and
keeps the base), so the load side no longer needs the table. In game: `hwys 21100 73 0 73 2 15051 0 15051 2` plus
`hwyp 21101 1 0 2`: live 21100.2 / 21101.2 / 21101.0 / 21100.0 saved as 15051.0 / 15099.0 / 15099.2 / 73.0 (read
without the mod), reloaded with the mod: all 4 restored at their original states, load pass 0 written, 0 reverted.

## 6. Kept cells after reverts (hwdd report, 2026-10-18)

hwdd measured a block's freshly written flyover being replaced by the stock stub: hwy_end's 3x3 rect retiles around
removed land pieces re-tiled neighbouring kept on-highway cells (nested passes are blocked, so no block re-applied).
Fix: hwy_keep / hwy_put record (x, z, piece, state) per pass; after the reverts hwy_end re-reads each kept cell and
writes it again (FUN_10008919) when it changed, logged "re-placed after a revert retile". Builds; first in-game run
will be hwdd's re-test.

## 7. Known limitation: land pieces without the mod

Measured by hwdx and hwdd (no-mod loads, 2026-10-18): on-highway pieces come back as the right stock straight and band
pieces (with `hwys` where needed); land pieces come back as their base 15099 (slope blocks / ramp-down staircases) unless
`hwys` saves them as stock one-lane ramp pieces (15123..15141, which stock places only at states 0 / 2, counted over the
16 shipped cities). Saving them as empty ground is not done (orchestrator decision): FUN_10012fc3 counts each tile
before FUN_1000d688 writes it, so skipping a record means correcting that count and recreating the cells on load.
