# diagonal_avenue (task diagave, phase 1)

Draw two diagonal roads side by side and they become one avenue with a tree median.

- **How to draw one:** drag a diagonal road, then a second diagonal next to it, touching it. Either two cells further
  along x (the avenue ends cut at 45 degrees) or one cell along the other diagonal (square ends). Each drag needs 3+
  steps, and the pair must overlap for at least 3 rows.
- **What happens:** sc3netmod's DAV block (`re/harness/src/sc3netmod_dav.c`) checks the band after every road edit and
  after a city load. Every cell gets the piece a lone diagonal would get (35, start cap 18004, end cap 1999); the cells
  beside the median get this package's variants 20500 / 20501 / 20502 (same piece, plus the median half with a tree).
  Without this, the stock tiler draws a ladder of 4-way crossings (verify/diagave/RESULTS.md section 2).
- **Phase 1 limits:** no other road may touch the band (it is left to the stock tiler otherwise, e.g. the existing
  double diagonals in Berlin and Moscow, which end in junctions). Bulldozing one cell breaks that carriageway: the
  avenue goes back to the stock ladder until the cell is rebuilt.
- **Saves:** the variants save as 35 / 18004 / 1999, so a game without the mod shows two plain diagonals.

Build and install (the art is made from the game's own frames, so it is not shipped):

```
cd re/tools/netmod/examples/diagonal_avenue
py -3 ../../diagave.py art art                       # art/20500, art/20501, art/20502 (z*_r*.png + anchors.json)
cd ../../../../..
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/diagonal_avenue --tree <game tree>
```

The game needs an sc3netmod.dll built from a tree that has `sc3netmod_dav.c` (`pwsh re/scripts/build_mod.ps1 -Mod
sc3netmod -Src re/harness/src -Out <instance folder>`). Off switch: `SC3NETMOD_DAV=0`.

Offline: `diagave.py scan` (bands per save and why each converts or not), `diagave.py plan SAVE`, `diagave.py preview`.
