# boulevard (task boulevard)

Draw three parallel straight roads side by side and they become one boulevard: the outer roads are the carriageways
(stock road look, yellow centre line), the middle road gives each one an extra lane along its inner side and holds a
grass median with the stock avenue's trees, about twice as wide as the stock avenue's median.

- **How to draw one:** three straight drags next to each other, at least three columns long (plus the end columns).
- **Junctions:** a single straight road crossing it, or meeting it from one side, gets stock 4-way crosswalks across
  the whole boulevard; the median ends in a concrete nose on each side.
- **Ends:** where all three roads stop, the end column closes the boulevard with a round curb. Where only one of them
  goes on, the boulevard tapers into it over its last three columns (the single road's centre line runs straight to
  the median nose). Where two neighbouring roads go on, it narrows back into the stock avenue over its last three
  columns.
- **Lane lines:** white dashes on every lane line of the boulevard (each carriageway's centre and its extra lane's
  edge); single roads keep their yellow line.
- **Pieces:** 20700 outer row, 20701..20703 middle row (plain, nose at one end, noses at both), 20704..20706 end cap,
  20710..20712 junction (entry row, middle row, far row of a T), 20720..20748 tapers (to the middle, north, south
  row; nine cells each), 20750..20768 narrowing to an avenue (rows 0, 1 or 1, 2 go on).
- **Lanes:** the outer and middle pieces carry their own lane records (19 TrBlkAtt slots per language); the others
  use road 29's straight lanes (the game's fallback), junctions 43's.
- **Saves:** every piece saves as its base (11204 / 29 / 43), so a game without the mod still loads with the roads
  joined.

Build and install (the art is made from the game's own frames, so it is not shipped):

```
cd re/tools/netmod/examples/boulevard
py -3.12 ../../boulevard.py build .                  # art/<id>/, bv_<id>.lanes.json, manifest.json
cd ../../../../..
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/boulevard --tree <game tree>
```

The game needs an sc3netmod.dll built from a tree that has `sc3netmod_bv.c`. Off switch: `SC3NETMOD_BV=0`.
Offline: `boulevard.py plan SAVE` (runs and wanted pieces), `boulevard.py mockup OUT.png .`, `boulevard.py preview`.
Evidence: `verify/boulevard/RESULTS.md`.
