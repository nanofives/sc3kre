# big_roundabout: automatic 3x3 roundabouts (task bigrbt, 2026-10-17)

Draw a 3x3 square of road cells and let roads or avenues leave it. sc3netmod's RBT9 block turns the square into one
big roundabout by itself, after every road edit and after a city load, and back into stock road when it stops
qualifying. Rule, pieces and tools: `re/tools/netmod/bigrbt.py`; evidence `verify/bigrbt/RESULTS.md`.

Build the art (made from the installed game's frames, not shipped), then install:

```
cd re/tools
py -3.12 -m netmod.bigrbt build netmod/examples/big_roundabout --manifest
py -3.12 netmod/netpack.py install netmod/examples/big_roundabout --tree <TREE> --allow-tree
```

| piece | cell | arms (state 0 frame) | base (what a game without the mod loads) |
|---|---|---|---|
| 20600 | centre | none (the island) | 43 |
| 20601..20604 | side middle, state 0 = E cell | x+: none / road / avenue half, median toward z- / z+ | 39 / 43 / 43 / 43 |
| 20610..20618 | corner, state 0 = NE cell | 20610 + 3 * kN + kE; k on z- (N) and x+ (E): 0 none, 1 road, 2 avenue half | 11203 for 20610, else 43 |

Lanes (`<id>.lanes.json`, stock curves only): one ring lane counter-clockwise (ENGLISH, right-hand traffic) on the
stock slots, entries and exits as stock right turns or straights where the arm is tangent to the ring; pedestrians on
the block's outer sidewalk, a crosswalk over each arm. Table lines `rbt9 <c|s|k> <k> <piece>`. Off:
`SC3NETMOD_RBT9=0`.

## One-way avenue arms (task avmisc, avenue lane rework)

Where an avenue arm's band is converted to one-way halves by avcore's block (`re/analysis/AVENUE_LANES.md`), the block
takes a second set of pieces: sides 20605 (avenue, median z-) / 20606 (avenue, median z+) / 20607 (no arm) / 20608
(road arm), corners 20620 + 3 * kN + kE. Each half's two lanes sit at the stock slots 80 / 175 of the arm edge and run
one way: side 20605 and a corner's z- arm take the half INTO the ring, side 20606 and a corner's x+ arm take it OUT.
Lane specs have `"mirror_uk": false` and no path keys (avcore rule): new shapes 23900..23903 plus reverse shapes
23904..23913 give English-UK the same right-hand lanes. Manifest keys `side_oneway`,
`corner_oneway`; table lines `rbt9 o <kind> <piece>` / `rbt9 w <k> <piece>`. Art = the two-way pieces' (copy the
`art/<id>` dirs: 20605 <- 20603, 20606 <- 20604, 20607 <- 20601, 20608 <- 20602, 20620+k <- 20610+k). Offline
check of the direction rule on all 16 arm placements: `py -3.12 re/tools/netmod/avmisc_plan.py check`.
Declarations for avcore's band end (`avlj`, netpack key `avenue_lines` once avcore's netpack change is merged):
`avlj 20605 .I..`, `avlj 20606 .O..`, `avlj 20622 .O..`, `avlj 20625 .O..`, `avlj 20626 I...`, `avlj 20627 I...`,
`avlj 20628 IO..` (N E S W at state 0; I = traffic enters the piece across that side, O = leaves).
