# slopeend RESULTS (2026-10-26): rounded road ends on slopes

Owner ask: "is it possible to add an end of road on a slope?" (`MAIN\verify\slopeend\owner_shots\img1_road_end_on_slope.png`:
a road that ends on a sloped cell stops with a square cut; on flat ground the game draws the rounded cap 11225).

Verdict: yes, built and checked in game. 24 new piece ids 27000..27023 (the 4 stock slope pieces, each with the uphill
end, the downhill end or both ends rounded, one set per state) and sc3netmod block SLE, which swaps them in after every road edit and
after a city load. Saves keep the stock slope piece, so a game without the mod shows today's square cut.

## 1. What stock does (code + 16 shipped cities)

- A road cell on a legal slope never sees the tiling rules. The retile pass FUN_1001547b moves non-flat legal-slope
  cells to a slope list, and FUN_1001a2c0 picks the piece from the ROAD slope table (SIMNTWRK 0x1003195C) by the
  corner pattern alone: 11202 state 0 / 2 (slope along x, downhill +x / -x), 11201 0 / 2 (along z, downhill +z / -z),
  steep 32 / 31 the same. Neighbours are never read, so road ends going up or down, on either axis, 1-cell stubs
  included, all get the square-cut straight piece. No stock art has a sloped cap (the dead `ROAD_GRND_SlopeRULES.txt`
  names the same 4 pieces).
- Flat end = 11225 (Simple / final rules, arm (3 + s) % 4), cropped frames, frame-table ground bit 0x40. Flat isolated
  cell = 43.
- 16 shipped cities (`slopeend.py survey`): 1,766 sloped road cells; 19 are road ends (10 with a road beside the
  cell), 1 is isolated. No plain road sits on a cell that is not flat or a legal slope (only bridge and tunnel pieces).
- An end at a raised corner (one corner up, not a legal slope): the drag puts a FLAT 11225 there (in game, cell
  (49,24) of the lab). Nothing for SLE to do.

## 2. Design

| base | state 0: up / down / both | state 2: up / down / both |
|---|---|---|
| 11202 (along x) | 27000 / 27001 / 27002 | 27003 / 27004 / 27005 |
| 11201 (along z) | 27006 / 27007 / 27008 | 27009 / 27010 / 27011 |
| 32 (along x, steep) | 27012 / 27013 / 27014 | 27015 / 27016 / 27017 |
| 31 (along z, steep) | 27018 / 27019 / 27020 | 27021 / 27022 / 27023 |

(One set per state: section 4. The plan sheet showed the first design, 12 ids.)

Rule (`re/harness/src/sc3netmod_sle.c`), on a road cell holding a slope piece or one of its variants, downhill side
from (base axis, state): road beside the cell (across the slope) -> base; road on both axis sides -> base; road
downhill only -> uphill cap; road uphill only -> downhill cap; neither -> both ends. Written with the game's piece
writer FUN_10008919, same state, height from the terrain (as the stock commit). Runs after every ROAD retile (work
box + 1) and once after a city load. Off: `SC3NETMOD_SLE=0`. Package `examples/road_slope_ends` (netpack key
`road_end_lines`: `sle <base> <up> <down> <both> <up> <down> <both>`, state 0 then 2).

Art (`slopeend_paint.py`): each frame's slope plane is fitted from its own pixels at zoom 4 (high edge, magnitude,
anchor reference; IoU 0.91..0.96; zooms 0-1 are too small to fit and reuse the zoom-4 plane). The end half is the
piece's own cross profile bent round a half circle centred on the cell, radius 0.5. The same bend applied to road 29
reproduces the flat cap 11225 at shape IoU 0.97..0.99 per slot. The straight half and the open edge are the stock
pixels; outside the circle the art is transparent, and the ground bit draws the terrain there (with 11225's frame table:
section 4).

## 3. In game

Lab: `slopeend.py lab` = Roadless Paradise with two plateaus (P1 one unit up, P2 two units up) on the flat window
x 42..74 / z 12..44. Drags with posted input (`slopeend_lab.py`), the camera by rb_lab's game-thread calls. All mods
except sc3overscroll: its edge scroll while placing moved the view under the posted drags in run 1 (drags landed 2
cells off). The owner's game runs sc3overscroll. That only matters for the driver, not for SLE.

(results table in section 5)

## 4. Terrain under a sloped piece: the sprite class (found in game, read in SIMSPR)

The first in-game build (art on 11202's frame table) drew the caps right but left the transparent corners as a flat
colour (64,72,96) = the view background: nothing drawn there (all 649 such pixels round the stub lie inside the
cell's sloped outline). What was ruled out, each by one in-game run on the same saved lab:

| run | change | holes |
|---|---|---|
| 2 | frames cropped to the opaque box (as 11225 ships) | yes |
| 3 | full base frame size and anchor | yes (fewer) |
| 4 | first-pass bit cleared (0xC0 -> 0x40, as the stock slope power / pipe pieces) | yes |
| 5 | only sc3resize + sc3netmod loaded | yes |
| 7 | occupant height 82 vs 83 (planted) | yes, both |
| 6, 8 | CONTROLS planted on the same slopes: stock power slope 11262 (bit 0x40) and stock flat cap 11225 | no |
| 9 | frame table header +0x08 = 0x0672 (11225's) instead of 0x059D (11202's) | **no** |

Read in SIMSPR (subagent trace of FUN_100192aa / FUN_1001a303 / FUN_10015dd0, `[CONFIRMED]` per address there):
every occupant's cell loses its own terrain entry; with bit 0x40 the cell's terrain (a 4-corner Gouraud quad, SIMDIRT
FUN_10012e44 / FUN_10013241) is attached to the occupant and drawn at the occupant's draw point before it. The header
dword +0x08 is the sprite class (netcat `clsid`): 0x059D (the straight slope pieces) draws no attached terrain, 0x0672
(11225, 11203, the roundabout's 20401) does. So the variants take their frame table from 11225 (`art.from: 11225`,
all 20 frames from the png_dir with anchors.json).

Class 0x0672 anchors the art at the occupant's altitude, the cell's (x, z) corner (the save's tile z; the piece writer
with height -1 asks the terrain for it): the high corner at state 0, the low corner at state 2. The slope art's anchor
sits at a fixed corner per piece (plane fit: 11202 / 32 at the low corner, 11201 / 31 at the high one; class 0x059D
corrects for it). With one art set, one state of each base came out one altitude unit off in run 9 (the north cap).
Hence one id set per state (24 ids) with T moved by (fit ref - wanted ref) x (1 << zoom).

## 5. Results, final build (package 1.1.0, ids 27000..27023, sc3netmod with SLE)

Lab run 11 (`lab11.sc3`, all mods except sc3overscroll), every write from `sc3netmod.log`:

| case | cell | stock piece | written |
|---|---|---|---|
| west slope, road climbs and stops | (49,20) | 11202 / 2 | 27003 (uphill cap, state 2 set) |
| west slope, road comes down and stops | (49,22) | 11202 / 2 | 27004 |
| east slope, up / down | (56,21) / (56,19) | 11202 / 0 | 27000 / 27001 |
| north slope, up / down | (53,17) / (51,17) | 11201 / 2 | 27009 / 27010 |
| south slope, up / down | (52,24) / (54,24) | 11201 / 0 | 27006 / 27007 |
| 1-cell stub | (49,18) | 11202 / 2 | 27005 (both ends) |
| steep, west up / east up | (61,19) / (68,21) | 32 / 2, 32 / 0 | 27015 / 27012 |
| steep, south down / north up | (66,24) / (63,17) | 31 / 0, 31 / 2 | 27019 / 27021 |
| road extended past the cap onto the plateau | (49,20) | | stock 11202 again (the stock retile re-placed it, SLE agreed) |
| flat cell below a cap bulldozed | (49,20) | | 27004 (downhill cap) |
| raised-corner cell | (49,24) | | stock flat 11225 (SLE not involved) |

- Save: 13 variant tiles written as their base, section 0x4E56. Reload with the mod: 13 restored, SLE load pass wrote
  0. `slopeend.py classify` on the save: 13 slope cells, 0 differ from the rule.
- Mod off (no sc3netmod) on the same save: the stock slope pieces, square cuts as today, no cell lost.
- Pictures (zoom 4 at the owner's angle, zoom 3 in all 4 views, both plateaus, before = mod off, after = mod on, same
  save and cameras): `MAIN\verify\slopeend\owner_shots\slopeend_sheet.png`, frames in `owner_shots\frames\`. No
  terrain holes, caps aligned with their road in every view.
- Not checked: traffic on a cap cell (a dead end, base lanes copied); zooms 0 to 2 only seen in the zoom-3 overview
  scale; slope ends in the shipped cities loaded with the mod (the load pass handles them by the same rule).

## 6. Design calls (confirmed by the owner 2026-10-26)

- A slope end with a road beside it (across the slope) stays stock: 10 of the 19 ends in the shipped cities.
- A 1-cell slope road with no neighbour gets both ends rounded (a pill). Stock flat equivalent is piece 43 (square).
