# diagonal_boulevard (task diagbv)

Draw three diagonal roads joined side by side and they become one 3-wide diagonal boulevard: the straight
boulevard's cross-section (package `boulevard`) turned 45 degrees.

- **How to draw one:** three diagonal drags, each one cell over from the last (one cell along x on the down-right
  diagonal, one cell up on the other, the gesture of `diagonal_avenue`). Each row of the band is four cells. At least
  three rows must have nothing beside them.
- **Look:** the outer drags are the carriageways (stock road edge), the middle one gives each an extra lane and holds a
  grass median with avenue 11204's trees. Lane lines are white dashes (`lanelines.py`).
- **Junctions:** a straight single road crossing it along x or z, meeting it from one side (T), or the band ending on
  a road (along x on the down-right diagonal). The median ends in a nose parallel to the road; crosswalks are stock
  43's two white lines.
- **Ends:** narrowing into the diagonal avenue (one outer drag shorter: the diagonal avenue's own pieces start where
  the narrowing ends), taper into any one of the three roads (the single road's yellow line jogs to the median nose),
  a round curb where all three stop (square, or past the drags' last cells), bend into the straight boulevard where
  the three drags go on straight.
- **Limits:** ends of other shapes (drags ending raggedly in some ways, two diagonals two cells apart) leave the band to
  the stock tiler (log: `dbv: ... left to the stock tiler: <why>`). Avenue or boulevard crossings are not handled.
- **Saves:** every piece saves as its base (outer cells 35, the others 43), so a game without the mod keeps the roads
  joined (the stock ladder look).

Build and install (the art is made from the game's own frames, so it is not shipped):

```
cd re/tools/netmod/examples/diagonal_boulevard
py -3 ../../diagbv.py build .
cd ../../../../..
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/diagonal_boulevard --tree <game tree>
```

Needs an sc3netmod.dll built with `sc3netmod_dbv.c` (off switch `SC3NETMOD_DBV=0`); install `diagonal_avenue` and
`boulevard` too for the narrowing and the bend (DBV claims its cells first, DAV and BV start where it stops).
Offline: `diagbv.py fit`, `check`, `pieces`, `plan SAVE`.
