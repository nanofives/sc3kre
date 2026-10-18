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
