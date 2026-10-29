# highway_scurve (task hwyscurve)

Highway S-curve. Two parallel straight highways drawn one cell apart (half the band) that overlap by 2 to 4 cells
become one highway that shifts sideways over the overlap and keeps going, both directions drivable. Stock leaves
"Highway Construction" (15149) tiles there forever (owner picture 2026-10-29, `verify/hwyscurve/RESULTS.md`). Along x
and z, shifted either way, either drag order. An overlap of 1 is already a stock one-column diagonal and is left alone.

- **Pieces** 28200..28253, one per footprint cell (overlap columns x 3 rows): S (shift to the left of travel) and Z
  (to the right) for overlaps 2, 3, 4. Base 15051, frame table from 15127 with ground under. Lit twins 28300..28353
  (+100), written where the S runs along z, so the walls get the stock shading.
- **Art:** `hwsc_build.py art` (hwpaint scene: the two-cell deck on a straight, two opposite arcs and a straight;
  radius 1.25 / 2.5 / 4.25 cells for overlap 2 / 3 / 4), twins included. Not shipped (game art).
- **Lanes:** `hwsc_build.py lanes` (curve shapes 28400..28495), 4 lanes in and out at each end on the stock lane
  positions. 8 corner cells the deck only grazes carry no lane (empty turn matrix).
- **Table lines** (manifest `highway_lines`): `hwyp` + `hwys` + `hwyl` per piece, `hwsc <hand> <L> <a> <c> <piece>`
  per cell (the rule, `re/harness/src/sc3netmod_hwsc.c`).
- **Saves:** every cell saves as what the stock tiler leaves there (15149 on the shared row and the two band ends, the
  plain straight elsewhere): without the mod the city loads as stock shows it; with it the S comes back.
- **Not built:** sloped ground, a ramp or interchange on or next to the footprint, overlaps of 5 or more, the
  full-width shift (two bands touching side by side). Those stay stock.
- **Off:** `SC3NETMOD_HWSC=0`.

Build and install:

```
py -3.12 re/tools/netmod/hwsc_build.py lanes re/tools/netmod/examples/highway_scurve
py -3.12 re/tools/netmod/hwsc_build.py art re/tools/netmod/examples/highway_scurve --jobs 6
py -3.12 re/tools/netmod/hwsc_build.py manifest re/tools/netmod/examples/highway_scurve
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/highway_scurve --tree <game tree>
```
