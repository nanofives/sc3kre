# avenue_junctions (task avx)

Where straight avenues meet, the junction becomes one paved box instead of the stock patch of small crossings.

- **What converts:** two avenues crossing (avenue x avenue), an avenue ending on another (avenue T), a single road
  crossing an avenue (road x avenue), a single road ending on an avenue (road T). Along x and along z, all rotations.
  An avenue here is the stock two-road avenue (11204): draw two parallel roads side by side.
- **Look:** a paved box made from stock 43's asphalt, 43's own crosswalk lines across every arm at the box edge, 43's
  corner sidewalk at the outer corners, road 29's curb along a side with no arm (the far side of a T), and each avenue
  arm's median ending in a concrete nose on the cell next to the box, its lane line white and dashed (owner,
  2026-10-17: `lanelines.py`; road arms keep their yellow line). Plain avenue and road cells stay stock.
- **Pieces:** box cells 20800..20804, one per edge pattern (N E S W, each I another box cell, A an arm, C closed):
  20800 AIIA, 20801 AAIA, 20802 IACA, 20803 IACI, 20804 IICA; base 43, lanes of 43 (or of T 39 for the three with a
  closed side). Nose cells 20810 / 20811 = 11204 with the median nose at its E / W end (base 11204, its lanes and trees).
- **Rule** (sc3netmod's AVX block, `re/harness/src/sc3netmod_avx.c`; offline twin `re/tools/netmod/avx.py`): a 2x2,
  1x2 or 2x1 box of road whose corner cells are empty, each side either all road or empty, every arm straight and
  clean (no road beside it) for 2 cells. It leaves alone the 2x2 roundabout (one road per side), 3x3 blocks, three
  parallel roads, diagonal shapes, junctions closer than 2 cells apart along an avenue, and cells holding another
  block's pieces.
- **Saves:** box cells save as 43, the far half of a T as 11204, nose cells as 11204, so a game without the mod loads
  the stock avenue and crossings with the roads joined.

Build and install (the art is made from the game's own frames, so it is not shipped):

```
py -3.12 re/tools/netmod/avx.py build re/tools/netmod/examples/avenue_junctions
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/avenue_junctions --tree <game tree>
```

The game needs an sc3netmod.dll built from a tree that has `sc3netmod_avx.c`. Off switch: `SC3NETMOD_AVX=0`.

Offline: `avx.py check --tiler` (every kind x rotation on the stock tiler, the shapes it must refuse, RBT's rule on
its boxes), `avx.py mockup OUT.png PACK` (stock vs avx sheet), `avx.py scan [SAVE ...]` (junctions per city).
