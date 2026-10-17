# diagonal_avenue (task diagave)

Draw two diagonal roads JOINED side by side and they become one diagonal avenue, four lanes wide, with the tree
median of the stock two-road avenue.

- **How to draw one:** drag a diagonal road, then a second diagonal one cell over (one cell along x, or one cell up).
  The pair must run side by side for at least 3 rows. Each row of the avenue is three cells: an outer piece, a middle
  piece, an outer piece.
- **Why it works:** stock diagonal 35 draws only the road half of its cell (the other half shows terrain). Two
  diagonals one cell apart share their middle cells, and each middle cell holds the inner half of both roads. The
  stock tiler draws that as a ladder of curve / 4-way / curve; sc3netmod's DAV block
  (`re/harness/src/sc3netmod_dav.c`) checks the band after every road edit and after a city load and puts back the
  pieces two lone diagonals would have, with the shared cells as this package's middle pieces (two stock halves on
  one tile, and both halves' lanes, so cars on each carriageway keep to it).
- **Pieces:**
  - 20500 = 35 + 35 with the median (grass and 11204's trees); 20501..20504 = a diagonal plus the other road's start
    (18004) or end (1999) cap; 20505 = an outer cell, stock 35 with the median-side tip as grass.
  - 20510..20519 = junctions: a straight road crossing the avenue, meeting it from one side, or the avenue ending on
    it. Road 29 with the avenue's halves as asphalt, crosswalks across the road at the avenue's edge and across the
    avenue at the road's edges.
  - 20520..20524 (B ends) and 20530..20534 (A ends) = merges: one drag shorter than the other, so one carriageway
    ends and the other goes on as a single road. The ending carriageway's outer curb tapers into the other over three
    rows, the median stops with a concrete nose, and yellow dividers carry on through the taper (the ending lane's
    centre line, and a line in the median's place).
- **Bends:** when both drags go on as two parallel straight roads (the stock avenue 11204), the diagonal avenue turns
  into the straight one. No extra pieces: the carriageways' edges meet the straight avenue's on one cell line, so the
  diagonal cells keep their middle-of-band pieces and the straight cells stay stock.
- **Limits:** other roads may touch the band only as straight arms (junctions); anything else leaves it to the stock
  tiler (e.g. the existing double diagonals in Berlin and Moscow). Avenue x avenue is not handled. Bulldozing a cell
  breaks a carriageway: the avenue goes back to the stock ladder until the cell is rebuilt.
- **Saves:** the pieces that hold both roads save as 4-way 43, the others as their stock base, so a game without the
  mod still loads and keeps the roads joined (the stock ladder look).

Build and install (the art is made from the game's own frames, so it is not shipped):

```
cd re/tools/netmod/examples/diagonal_avenue
py -3 ../../diagave.py build .                       # art/<id>/ and the *.lanes.json specs
cd ../../../../..
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/diagonal_avenue --tree <game tree>
```

The art is painted per world scene by `diagave_paint.py` (straight avenue, junction, merge): every pixel samples the
stock pieces' own frames at the same screen position, so neighbouring pieces meet exactly.

The game needs an sc3netmod.dll built from a tree that has `sc3netmod_dav.c` (`pwsh re/scripts/build_mod.ps1 -Mod
sc3netmod -Src re/harness/src -Out <instance folder>`). Off switch: `SC3NETMOD_DAV=0`.

Offline: `diagave.py combos` (the pieces every drag footprint needs), `scan` (bands per save and why each converts or
not), `plan SAVE`, `preview`.
