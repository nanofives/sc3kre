# hwt_trumpet (task hwt)

A highway T that connects every movement: a TRUMPET. When a highway stem ends beside a straight highway (its stock end
caps against the side), or the player draws the stock stub X (a drag started on the near carriageway), sc3netmod's HWT
block (`re/harness/src/sc3netmod_hwt.c`, on hwcore's HWY base) replaces it with ramps:

- the stem's two lanes climb on walls and cross both carriageways side by side on slab bridges, 31.5 above the through
  deck (the stock X's separation);
- far side: the inbound lane loops clockwise (radius 1.25, as hwx's cloverleaf) on pillars down into the far
  carriageway; an outer ramp, concentric with the loop, leaves the far carriageway and carries it back over the bridge;
- stem side: two right-turn ramps (stem -> near direction, near direction -> stem);
- every exit and entry is on the right, exits before entries; the through highway stays level and straight.

When the far side is built up the block builds the right-in / right-out set (the two stem-side ramps only, the stem
keeps its caps). The T goes away when its stem or through highway is cut: plain stock highway goes back, the stem stub
left against the through highway is removed.

- **Pieces:** 54 variants 21200..21253 (50 for the full T, 4 more for the fallback; 14 cells shared). 30 + 8 land
  cells (base 15099, Protected), the rest rewritten highway cells (base 15051 through, 73 stem). Each cell has its own
  art, painted by `hwt_paint.py` with hwcore's `hwpaint.py` (stock highway frames as the material).
- **Lanes and turn matrices:** hwcore's `hwlanes.py`: `hwt_<id>.lanes.json` (51 specs, new curves 22800..22883,
  turn matrix auto from the lanes). They equal the routes walked from the scene (`hwt_paint.py routes`). The 3 cells
  without a lane (deck slivers) get an empty turn matrix.
- **Table lines** (`highway_lines`): `hwyp <id> <land>` for every piece, `hwt <id> <dx> <dz> <land> <sets>` the T's
  cells in the stem frame.
- **Saves:** every piece saves as its base; with the mod the ids come back from section 0x4E56.
- **Off:** `SC3NETMOD_HWT=0` (this block), `SC3NETMOD_HWY=0` (the whole highway program).

Build and install (art is not shipped; ~10 min with 10 jobs):

```
py -3.12 re/tools/netmod/hwt_build.py table
py -3.12 re/tools/netmod/hwt_build.py art re/tools/netmod/examples/hwt_trumpet --jobs 10
py -3.12 re/tools/netmod/hwt_build.py lanes re/tools/netmod/examples/hwt_trumpet
py -3.12 re/tools/netmod/hwt_build.py manifest re/tools/netmod/examples/hwt_trumpet
py -3.12 re/tools/netmod/netpack.py install re/tools/netmod/examples/hwt_trumpet --tree <game tree>
```

Needs an sc3netmod.dll built with `sc3netmod_hwy.c` + `sc3netmod_hwt.c`. Results: `verify/hwt/RESULTS.md`.
