# highway_diagonal_cloverleaf (task hwdx)

A diagonal highway that crosses a straight highway at 45 degrees becomes a skewed cloverleaf. Stock leaves two
"Highway Construction" 15149 blocks there forever.
- **Bridge:** the straight bridges over the diagonal (the stock X's split: up to the upper deck, down to the lower).
- **Ramps:** four loops for the left turns and four outer ramps for the right turns, all 8 turns connected. No ramp
  crosses a road.
- **Footprint:** 20 x 14 cells.
- **Orientations:** both diagonal families, with the straight along x or along z.
- **Fallback:** each quadrant joins only its own two carriageways, so a built-up quadrant drops its two ramps and the
  rest still builds.

Rule and pieces are placed by the HWDX block of sc3netmod.dll (`re/harness/src/sc3netmod_hwdx.c`, on hwcore's
`sc3netmod_hwy.c`). Design, rule and offline checks: `verify/hwdx/README.md`; in-game results:
`verify/hwdx/RESULTS.md`.

- **Pieces:** 172 ids in 21260..21359 and 21460..21531. That is 120 classes; every class that sits on highway comes
  in two versions, one for a straight along x and one along z.
  - **On-highway pieces** (core and ramp joins) have a plain base: 15051 / 73, or 11223 / 11224 / 15052 / 15106.
    Their state is the stock state of that cell.
  - **Land pieces** (ramp-only cells, written into empty cells) have the Protected base 15099.
  - Every piece's art uses stock 15127's frame table with `ground_under` and frames padded to the cell diamond (the
    program's ground rule, `re/analysis/HWY_BASE.md`).
- **Lanes:** `lanes/<id>.json`, one-lane ramp and carriageway lanes cut by `hwlanes.py` from the painter's decks,
  states 0..3, new curves with shapes 22000..22361.
  - The turn matrix (prop 310) is hwdx's own table, not "auto". In the core, the diagonal takes its sideways steps
    only where they run against the straight's traffic, so the router cannot turn between the two highways without
    a ramp.
  - The installer's "lane vs matrix" warnings for the core (and a few corner cells) come from this and are expected.
- **Table lines** (manifest `highway_lines`): `hwyp <id> 0|1` for every piece (1 = land). There is also a
  `hwys <id> ...` line per land piece: what it saves as.
- **Saves:** with the mod, the variant ids and states come back. Without the mod:
  - on-highway pieces read as their stock base at the right state (the highways load as plain straight and diagonal
    highway);
  - land pieces read as the stock one-lane ramp piece their `hwys` line names (arcs 15127 / 15128, corners
    15123..15126, strips 15134..15137, states 0 / 2).
- **Off:** `SC3NETMOD_HWDX=0` (this block only), `SC3NETMOD_HWY=0` (every highway block).

Build the art and lanes, then install (run from `re/tools`; the art is game art and stays out of the repo):

```
py -3.12 -m netmod.hwdx package netmod/examples/highway_diagonal_cloverleaf        # manifest (ids, bases, lines)
py -3.12 netmod/hwdx_paint.py lanes netmod/examples/highway_diagonal_cloverleaf 22000
py -3.12 netmod/hwdx_paint.py art netmod/examples/highway_diagonal_cloverleaf     # all pieces, all zooms (slow:
                                                                                     # split ids over processes)
py -3.12 netmod/hwdx_paint.py pad netmod/examples/highway_diagonal_cloverleaf
py -3.12 netmod/netpack.py install netmod/examples/highway_diagonal_cloverleaf --tree <game tree>
```

After a geometry change, regenerate the block's tables
(`py -3.12 -m netmod.hwdx ctab ../harness/src/sc3netmod_hwdx_tab.h`), rebuild sc3netmod.dll, and run the offline
check (`py -3.12 -m netmod.hwdx check`).
