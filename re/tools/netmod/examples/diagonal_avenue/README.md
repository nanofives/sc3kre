# diagonal_avenue (task diagave)

Draw two diagonal roads JOINED side by side and they become one diagonal avenue, four lanes wide.

- **How to draw one:** drag a diagonal road, then a second diagonal one cell over (one cell along x, or one cell up).
  Each drag needs 3+ steps and the pair must run side by side for at least 3 rows. Each row of the avenue is three
  cells: stock 35, a middle piece, stock 35.
- **Why it works:** stock diagonal 35 draws only the road half of its cell (the other half shows terrain). Two
  diagonals one cell apart share their middle cells, and each middle cell holds the inner half of both roads. The
  stock tiler draws that as a ladder of curve / 4-way / curve; sc3netmod's DAV block
  (`re/harness/src/sc3netmod_dav.c`) checks the band after every road edit and after a city load and puts back the
  pieces two lone diagonals would have, with the shared cells as this package's middle pieces 20500..20504 (two stock
  halves on one tile, and both halves' lanes, so cars on each carriageway keep to it).
- **Middle pieces:** 20500 = 35 + 35 (the avenue itself); 20501..20504 = a diagonal plus the other road's start (18004)
  or end (1999) cap, where one carriageway ends inside a shared cell.
- **Limits:** no other road may touch the band (it is left to the stock tiler otherwise, e.g. the existing double
  diagonals in Berlin and Moscow, which end in junctions). Bulldozing a cell breaks a carriageway: the avenue goes back
  to the stock ladder until the cell is rebuilt. The two carriageways end half a step apart (the second drag is one
  cell over).
- **Saves:** the middle pieces save as their stock base (35 / 18004 / 1999), so a game without the mod still loads.

Build and install (the art is made from the game's own frames, so it is not shipped):

```
cd re/tools/netmod/examples/diagonal_avenue
py -3 ../../diagave.py build .                       # art/<id>/ and mid_<id>.lanes.json
cd ../../../../..
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/diagonal_avenue --tree <game tree>
```

The game needs an sc3netmod.dll built from a tree that has `sc3netmod_dav.c` (`pwsh re/scripts/build_mod.ps1 -Mod
sc3netmod -Src re/harness/src -Out <instance folder>`). Off switch: `SC3NETMOD_DAV=0`.

Offline: `diagave.py combos` (the middle pieces every drag footprint needs), `scan` (bands per save and why each
converts or not), `plan SAVE`, `preview`.
