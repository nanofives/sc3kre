# highway_core (task hwcore)

Proof package of the highway program base (`re/harness/src/sc3netmod_hwy.c`): the free cell past every highway end
gets a ramp-down piece, a carriageway that descends from deck height to the ground across the cell. It is written into
an EMPTY cell (no highway was drawn there), stays through retiles and saves, and goes away when the highway end moves.

- **Pieces:** 21100 (outer parapet on +x at state 0, as 73.0) and 21101 (outer -x, as 73.2), both variants of the
  Protected highway slope piece 15099, so the stock tiler never removes them and reads them as highway: after the next
  highway retile the end caps beside them become straight 73 and the highway runs into the ramps.
- **Art:** painted by `hwpaint.py core` from the stock 73 frames (deck, walls, dashes), not shipped.
- **Table lines** (manifest `highway_lines`): `hwyp 21100 1`, `hwyp 21101 1` (land pieces), `hwyt 21100 21101`
  (the proof rule).
- **Saves:** both save as their base 15099; with the mod the variant ids come back from section 0x4E56.
- **Off:** `SC3NETMOD_HWYT=0` (this rule only), `SC3NETMOD_HWY=0` (the whole highway block).

Build and install:

```
py -3.12 re/tools/netmod/hwpaint.py core re/tools/netmod/examples/highway_core
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/highway_core --tree <game tree>
```

Needs an sc3netmod.dll built with `sc3netmod_hwy.c`. In-game check 2026-10-18: `verify/hwcore/RESULTS.md`.
