# avenue_junctions (task avx, reworked by task avjunc 2026-10-19)

Where a road or another avenue meets a straight avenue, the junction becomes one paved box across both halves, and
since the avenue lane rework (2 lanes each way, right-hand traffic, avcore's package `avenue_lanes`) the box carries
one-way lanes: every turn and U-turn works inside it, so the box is the median opening.

- **What converts:** road x avenue, a road T on one side, two T's offset by a cell, roads at adjacent cells (runs up to
  4 cells), avenue x avenue (the four box cells form a one-way ring), avenue T, an avenue ending on a road. Along x and
  z, every rotation. Rule: `re/tools/netmod/avjunc_rule.py` (offline twin of sc3netmod's AVX block,
  `re/harness/src/sc3netmod_avx.c`); plan `verify/avjunc/PLAN.md`, results `verify/avjunc/RESULTS.md`.
- **Lanes:** each box cell has, per edge, 2 lanes in, 2 out, two-way or closed (`avjunc.py`): straight lane by lane,
  right turns from the right lane, left turns from the left lane. The halves next to a box get the median nose
  (one-way: avcore's 21700 lanes). An arm whose avenue avcore leaves two-way gets two-way edges and a two-way nose.
- **Look:** AVX's paved box (43's asphalt, crosswalks on the arms, curbs on closed sides), noses with the white dashes.
- **Pieces:** box cells 20805..20809, 20812..20849, 21750..21767 (`avjunc_pieces.json`), one-way noses 20800..20803,
  two-way noses 20804, 20810, 20811. Each saves as its base (box cells 43 / 39 / 11203 / 29, noses 11204), so a game
  without the mod loads stock junctions.

Build and install (art is made from the game's frames, not shipped; run from re/tools):

```
py -3.12 -m netmod.avjunc_build pieces netmod/examples/avenue_junctions   # only to regenerate the piece table
py -3.12 -m netmod.avjunc_build build netmod/examples/avenue_junctions    # specs, curves, art, manifest
py -3.12 -m netmod.avjunc_build check netmod/examples/avenue_junctions    # lanes in ENGLISH + English-UK
py -3.12 netmod/netpack.py install netmod/examples/avenue_junctions --tree <game tree>
```

Needs an sc3netmod.dll with the AVX and AVL blocks; install `avenue_lanes` too (without it every box is two-way).
Off switch: `SC3NETMOD_AVX=0`.
