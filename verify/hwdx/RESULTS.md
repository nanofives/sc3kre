# hwdx results: the diagonal x straight highway cloverleaf (2026-10-18)

Design and rule: `README.md`. Owner pictures in MAIN `verify\hwdx\owner_shots\` (not committed):
- `hwdx_plan.png`, `hwdx_plan_direct.png`: the plans; the cloverleaf is the default;
- `hwdx_mockup.png`: painted offline, zoom 3 and 4, views 0 and 1;
- `hwdx_ingame.png`: in game.

## Built

| file | what |
|---|---|
| `re/tools/netmod/hwdx_plan.py` | geometry, plans, piece count (program ramp values: deck 0.62, W 0.31, turn arcs 0.75, taper 0.62, loop R 1.25, gap 0.19; D edge = hwpaint W_DIAG 0.63) |
| `re/tools/netmod/hwdx.py` | cell tables, classes and ids, detection and placement, offline twin and checks, `ctab` (C tables), `package` (manifest) |
| `re/tools/netmod/hwdx_paint.py` | hwpaint scene (S over D on a slab, D via highway_diag, parapet gaps at every join), turns and the case B mirror, `mockup`, `art`, `lanes` (hwlanes) |
| `re/harness/src/sc3netmod_hwdx.c` + `sc3netmod_hwdx_tab.h` | the HWDX block on hwcore's helpers (`hwdx_run` in `rb_hwy`), SC3NETMOD_HWDX=0 turns it off |
| `re/tools/netmod/examples/highway_diagonal_cloverleaf/` | `manifest.json` + `lanes/*.json` (172 pieces); `art/` is gitignored |

Numbers:
- footprint 20 x 14 cells, 154 cells per crossing;
- 120 piece classes = 172 ids, in 21260..21359 and 21460..21531;
- 362 lanes on new curves, shapes 22000..22361 (range 22000..22499 granted).

## Offline (py -3.12 -m netmod.hwdx check)

- The stock tiler reproduces the in-game stock aftermath cell for cell, in both drag orders.
- Four orientations x two drag orders: each crossing is detected and placed (154 cells), and 12/12 movements are
  reachable over the turn matrices.
- The core alone (no ramps) carries the 4 through movements only: no merge between the two highways.
- 0 of 308 cells disagree with their piece's turn sides at their state.
- Every joining piece saves as exactly the stock piece its cell held.
- A claimed cell inside one quadrant drops only that quadrant.
- All 172 lane specs compile in every language with no warning. The package validates and installs (37 overlay files).

## In game (inst_hwdx, Roadless Paradise lab copy lab3.sc3, 2026-10-18)

| drag | log | result |
|---|---|---|
| straight along x, then x-z diagonal | `hwdx: edit: new crossing O (58,28) case A r 0, quadrants A1 A2 O1 O2`, 154 written | built |
| x+z diagonal, then straight along x | `new crossing O (131,24) case B r 0`, 154 written | built |
| straight along z, then x-z diagonal | `new crossing O (105,89) case B r 1`, 154 written | built (flavour-1 pieces) |
| save, then reload (two reloads) | `load: kept crossing ...` for all three, 0 written, 0 reverted | cell dump identical before and after (case A) |

Not run in game: case A turned (straight along z with an x+z diagonal); it uses the same classes as the three runs,
and the offline check covers it.

Art:
- **Ramps on slabs:** free-standing ramp runs are slab decks (thickness 10.25, the stock 15127 fit) on pillars
  every 1.25 cells, as hwt / hwdd. Embankment walls remain only within 0.45 of a highway edge, where a ramp runs
  alongside or merges (hwdx_paint.slab_spans).
- **Ground rule (program, HWY_BASE.md):** every piece has art "from": 15127 (its frame table), "ground_under":
  true, and frames padded to the full cell diamond (hwdx_paint.py pad, as hwt_build.py pad).
- **Result in game (2026-10-18, zoom 3 view 0, all three crossings, zoom 4 at case B's loop):** grass everywhere.
  The earlier holes and the view-0 dark strip inside case B's top loop are gone.
- **History:** the base 15099 frame table drew no terrain; ground_under alone fixed most of it; the 15127 frame table
  plus padding fixed the rest.

Saves without the mod:
- On-highway pieces save at the stock state of their base (offset 0, as designed).
- Land pieces save through hwcore's `hwys` table: each land piece at each state saves as the stock one-lane ramp
  piece whose turn matches its own (arcs 15127 / 15128, corners 15123..15126, strips 15134..15137, states 0 / 2
  only, as the shipped cities use them; hwdx.save_as).
- No-mod load of the saved city (sc3netmod.dll set aside): the highways come back stock (15051 rows, 11223 / 11224
  band at the right states), and the ramps come back as stock ramp fragments tracing the loops (art/nomod2_A_z3r0.png).
- The earlier save without the table showed grey slope blocks (art/nomod_A_z3r0.png).

Lanes:
- Animated cars on the ramps were not watched; the lab city has no population.
- The turn matrices are hwdx's own (proven offline). Lanes are cut by hwlanes at true geometry, so the installer warns
  where a cell's lane sides differ from its matrix: the core by design, plus a few corner cells.
