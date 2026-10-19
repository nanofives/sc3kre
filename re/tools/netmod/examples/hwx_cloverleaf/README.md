# hwx_cloverleaf (task hwx)

A cloverleaf at a straight highway X. When two straight highways cross on flat ground (the stock 12-cell X, the
highway along z over, the one along x under, whatever the drag order) and the four quadrants around it are free,
sc3netmod's HWX block (`re/harness/src/sc3netmod_hwx.c`, on hwcore's HWY base) adds, per quadrant:

- a 270-degree loop for the left turn (radius 1.25: leave after the X on the right, loop, join before the X);
- an outer ramp for the right turn, around the outside of the loop;
- every ramp one lane, a slab on pillars at the highway deck height; nothing new bridges (the X is the only bridge).

The X itself becomes a clean flyover: the stock lane heights on one smooth hump per highway, straight full-width decks
(stock squeezes the lower highway into an arched tunnel). Footprint 12 x 12 cells around the X. When a quadrant is
built up, only the clean flyover (the 12 core cells). An X whose arm stops right after the 4x4 (a stub X) is left to
the T package (`hwt_trumpet`). A city load never adds a cloverleaf; it keeps the ones the save holds.

- **Pieces:** 35 variants. 17 ramp pieces 21120..21136 (land cells, base 15099, Protected), used in the four quadrants
  at state = quadrant; 8 junction pieces 21150..21157 (a carriageway cell where a ramp leaves or joins, base 15051 /
  73, states 0 / 2); 6 clean core pieces 21160..21165 (base = the stock X piece, same states); 4 capped junctions
  21166..21169 (task hwcap2, below). 96 cells per cloverleaf.
- **Arm ending at the cloverleaf (task hwcap2, owner 2026-10-18: "never extend"):** a highway dragged so that it ends
  ON its arm's last junction row (dx / dz 5 or -6 from the X centre) holds the stock end caps on both cells there;
  the block writes the capped junctions 21166..21169 (the outer junctions 21151 / 21153 / 21155 / 21157 with the
  stock end face) and the cloverleaf builds. Base = the stock cap, at the cap's own state (table class 3), so saves
  and the stock tiler see the stock end. Turn matrix = the junction's turns with the outward side replaced by the
  side toward the row's other lane (the stock cap's U-turn plus the ramp's turn), no lanes. An arm that ends earlier
  leaves a junction cell empty: the clean flyover. Nothing is ever added past the player's drag. Every piece's art is painted at its ref cell with hwcore's `hwpaint.py` (stock highway frames as the
  material), frame table from stock 15127 with `ground_under` (HWY_BASE.md ground rule).
- **Lanes and turn matrices:** hwcore's `hwlanes.py`: `hwx_<id>.lanes.json` (29 specs, new curves 22500..22555,
  turn matrix auto from the lanes; plus the 4 capped junctions' specs: turn matrix only). The 2 deck-edge cells without a lane get an empty turn matrix.
- **Table lines** (`highway_lines`): `hwyp <id> <land>` for every piece, `hwys <id> <id0> <st0> .. <id3> <st3>` for
  the 14 on-highway pieces, `hwx <id> <state> <dx> <dz> <cls>` the 96 cells from the X centre (15113.0), plus 8
  class-3 lines (the capped junction of each outer junction cell, at the cap's state).
- **Saves:** junction and core cells save as the stock piece and state at their cell (`hwys`), so a game without the
  mod loads the stock X; ramp cells save as 15099 (they show as slope blocks without the mod). With the mod every
  piece comes back from section 0x4E56.
- **Off:** `SC3NETMOD_HWX=0` (this block), `SC3NETMOD_HWY=0` (the whole highway program).

Build and install (art is not shipped; a few minutes with 8 jobs). From `re/tools/netmod`:

```
py -3.12 hwx_build.py art examples/hwx_cloverleaf --jobs 8      # capped junctions: + the stock end face
py -3.12 hwx_build.py pad examples/hwx_cloverleaf
py -3.12 hwx_build.py lanes examples/hwx_cloverleaf
py -3.12 hwx_build.py manifest examples/hwx_cloverleaf
py -3.12 netpack.py install examples/hwx_cloverleaf --tree <game tree>
```

Checks: `py -3.12 hwx_twin.py selftest examples/hwx_cloverleaf <lab city .sc3>` (offline rule + routing),
`py -3.12 hwx_build.py preview examples/hwx_cloverleaf <out dir> [--fallback]` (the package art as the game draws it).
Geometry, plan and mockup: `hwx.py` (`cells`, `plan`, `mockup`, `sheet`; `--loop-r` for another loop size, then
rebuild all four steps). Needs an sc3netmod.dll built with `sc3netmod_hwy.c` + `sc3netmod_hwx.c`. Design:
`verify/hwx/README.md`; results: `verify/hwx/RESULTS.md`.
