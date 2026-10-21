# highway_dd_cloverleaf (task hwdd, highway program 2026-10-18)

Two diagonal highways of the two families (A = x - z band 11223 / 11224, B = x + z band 15052 / 15106) that cross
become a cloverleaf turned 45 degrees: A on a deck over B, four loops for the left turns, four outer ramps for the
right turns (stream hwx's ramp geometry), every movement connected. When the quadrants are not free the crossing
becomes a flyover (A over B, no ramps). Stock leaves a straight stub around 15149 "Highway Construction" forever.

Placed by sc3netmod's HWDD block (`re/harness/src/sc3netmod_hwdd.c`, on hwcore's `sc3netmod_hwy.c`), which needs
this package installed (its `hwyp` lines). Off: `SC3NETMOD_HWDD=0`.

| what | ids |
|---|---|
| cloverleaf, O on a cell centre (11x11) | 21360..21394 |
| cloverleaf, O on a cell corner (12x12) | 21395..21432 |
| flyover, centre / corner | 21433..21441 / 21442..21449 |
| lane curve shapes | 23000.. (one per distinct lane cut) |

Pieces on the player's highway cells have the stock piece the cell held as base, at that state (they save as the
stock stub and bands); pieces written into free cells (ramps) have base 15099 (Protected, hwcore's land base).
Turn matrices come from hwdd's router flows (`hwdd.py flows`), not from the drawn lanes: in the corner parity B's two
directions take other staircases through the crossing so A and B never share an entry side.

Build (art and lanes are derived, never committed; the lane specs `hwdd_*.lanes.json` are text):

```
py -3.12 re/tools/netmod/hwdd.py ctab re/harness/src/sc3netmod_hwdd_tab.h
py -3.12 re/tools/netmod/hwdd_paint.py build            # art/<id>/ (all zooms, views), lane specs, manifest.json
py -3.12 re/tools/netmod/hwdd.py check                  # offline twin of the block
```

Notes: `verify/hwdd/RESULTS_plan.md` (stock, design), `verify/hwdd/RESULTS.md` (build and in-game check).

## Lit twins (task hwlight, 2026-10-21)

Stock wall shading follows the wall's world axis (73's walls light, 15051's dark in every view) and a piece's frame is
shared by (state + view), so art painted at state 0 is lit wrong where the block writes it at state 1 or 3 (owner
img11). The 30 pieces the block writes at odd states have twins 26180..26209 (`lit_twins.json`): same base, lanes and
saves, art painted from the scene turned one state. sc3netmod writes the twin at odd states (`hwyl` lines) and every
reader sees the piece. After the art: `py -3.12 re/tools/netmod/hwlight.py twart <this package>`, the pad step if the
package has one, `hwlight.py manifest`, `hwlight.py check`. Notes: `verify/hwlight/RESULTS.md`.
