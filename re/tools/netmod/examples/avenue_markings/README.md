# avenue_markings (task avenues)

The stock straight avenue with white dashed lane lines. Owner, 2026-10-17: "on avenues instead of yellow lines they
should be white striped lines for every lane". Single roads keep their yellow centre line.

- Reskins 11204 (the avenue, one carriageway per cell) only: every yellow centre-line
  pixel on the ground becomes a white dash or lane asphalt. 11204's tree layer is not touched. 11203 (the stock plain-road curve, also the stock avenue end) is NOT reskinned: it would put dashes on every road corner (owner, 2026-10-22). Avenue ends and corners are 21701 / 21726 of `avenue_lanes`, which ships the dashed 11203 art itself.
- Dashes: `re/tools/netmod/lanelines.py`, measured on stock highway 73 (period 0.25 cell, dash 0.375 of it, centred,
  phase from the world coordinate along the road), so the avenue program's own pieces (diagonal avenue, boulevard,
  junctions, roundabouts) meet these dashes exactly. On the end cap's arc the phase follows the arc length.
- Builder: `re/tools/netmod/avenue_markings.py` (fits the line per frame: straight along a lane axis, or a circle).

Build and install (the art is made from the game's own frames, so it is not shipped):

```
cd re/tools/netmod/examples/avenue_markings
py -3 ../../avenue_markings.py build .
cd ../../../../..
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/avenue_markings --tree <game tree>
```

A reskin needs no DLL: it applies to every avenue in every city, saved ones included.
