# boulevard_diagonal (task orthfix, 2026-11-15)

The OPENING box where a diagonal avenue leaves a straight boulevard through one side while the boulevard runs on
(xsect case 39; owner "Yes, all three" for the looks in verify/orthfix/owner_shots/mockdiag_options.png).

- Pieces 22470..22478 (the avenue going +x+z from the boulevard's +w side) and 22479..22487 (the mirror), cell
  k * 3 + j = boulevard row k, j-th avenue band cell. Base 43, so a game without the mod keeps the roads joined.
- sc3netmod's BV block places them (`bvo` lines, sc3netmod_bv.c bv_obox, off: SC3NETMOD_BVOBOX=0).
- Art and lanes from one world scene per orientation (diagave_paint.Crossing + the boulevard), lanes right-hand,
  curve shapes 29000..29085.

Build (art comes from the game's frames, not shipped):

```
cd re/tools
py -3.12 -m netmod.bvdiag_build build <pack dir>
py -3.12 netmod/netpack.py install <pack dir> --tree <game tree>
```
