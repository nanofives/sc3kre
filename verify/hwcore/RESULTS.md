# hwcore results (highway program shared base, 2026-10-18)

## 1. hwpaint.py (offline)

`py -3.12 re/tools/netmod/hwpaint.py proof <out>`: stock pieces rebuilt from scratch by the painter, every zoom 3 and 4
frame, all four views, compared pixel by pixel with the stock frame (tolerance 24 per channel):

| stock piece | within tolerance | exact | silhouette overlap |
|---|---|---|---|
| 73.0, 73.2, 15051.0, 15051.2 (straight highway, both carriageways, both axes) | 96.4..97.0% | 96.2..96.5% | 97.2..97.5% |
| 15127.0 (On-ramp corner: one-lane slab arc, geometry fitted) | 52..55% | 0.7% | 84..87% |

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
