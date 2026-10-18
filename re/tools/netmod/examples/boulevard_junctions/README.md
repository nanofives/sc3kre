# boulevard_junctions (task bvx)

Where an avenue or another boulevard meets a boulevard, the junction becomes one paved box instead of the stock patch
of small crossings. Needs the `boulevard` package (its outer and median-nose pieces stand next to the box).

- **What converts:** an avenue (two parallel roads) crossing a boulevard, an avenue ending on a boulevard, a boulevard
  ending on an avenue, a boulevard crossing another, a boulevard ending on another. Along x and along z, all rotations.
- **Look:** a paved box of stock 43's asphalt, 43's own crosswalk lines across every arm at the box edge, 43's corner
  sidewalk at the outer corners, road 29's curb along the far side of a T. Every median ends in a concrete nose with
  its trees: the boulevard's on its own nose piece, an avenue's on 20910 / 20911 (11204 with the nose and white dashed
  lane lines, as avenue_junctions' arm pieces).
- **Pieces:** box cells 20900..20905, one per edge pattern N E S W at state 0 (I another box cell, A an arm, C closed):
  20900 AIIA, 20901 IACI, 20902 IICA, 20903 IIAI, 20904 IICI, 20905 IIII; base 43, lanes of 43 (copied) or of T 39
  state 1 where a side is closed. Avenue nose cells 20910 (nose E) / 20911 (nose W), base 11204, its lanes and trees.
- **Rule** (inside sc3netmod's BV block: `re/harness/src/sc3netmod_bvx.c`, called from `sc3netmod_bv.c`; offline twin
  `re/tools/netmod/bvx.py` with `boulevard.py runs()`): along a boulevard run, 2 or 3 consecutive columns with road
  beside the run, each side road over all of them or empty, every arm straight and clean for 2 cells. At the very end
  of a run with arms on both sides it is a T (the boulevard ends there). One side only at an end, or road 4+ wide
  beside the run, is refused. Single roads stay the boulevard's own junction pieces.
- **Saves:** box cells as 43, nose cells as 11204, so a game without the mod loads joined stock crossings.
- **TrBlkAtt:** 23 slots per language (3 copied 43 records, 3 specs x 4 states, 2 copied 11204 x 4 states).

Build and install (the art is made from the game's own frames, so it is not shipped):

```
py -3.12 re/tools/netmod/bvx.py build re/tools/netmod/examples/boulevard_junctions
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/boulevard_junctions --tree <game tree>
```

The game needs an sc3netmod.dll built from a tree that has `sc3netmod_bvx.c`. Off switch: `SC3NETMOD_BVX=0` (the
wide junctions are then left to the stock tiler, as before). Offline: `bvx.py check --tiler`, `bvx.py mockup OUT.png
PACK`, `bvx.py plan SAVE`. Evidence: `verify/bvx/RESULTS.md`.
