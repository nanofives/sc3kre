# roadloss: road cells vanishing during play in the showcase city (2026-11-17)

Brief: orchestrator "SC3 Simtropolis feedback triage", report `verify/showcase/ISSUES.md` 4a / 5. Saves read:
`dev/roadloss/tree/Cities/showcase*.sc3` (copies of the showcase child's saves).

## Verdict

**Not a player-facing bug. Fire, the mods, and save/load are not the cause.** The showcase city was zoned offline by
`verify/showcase/zone.py`, which wrote every zone mirrored in x (`c.zone_set(z, x)` with no `N-1-x` flip). That put
zones on 1,773 road and highway cells, as the game reads the raster. The stock zone developer then builds 1x1
commercial and industrial lots on those cells and its footprint clear bulldozes the network piece. Players cannot
make this happen: the zone tool refuses an occupied cell (CanZone SIMRCI `0x1003559f`, `re/analysis/ZONEDEMO.md`).

Fixed in the tooling (no mod code changed): `re/tools/city_write.py` `zone_get` / `zone_set` now take the game cell
(x, z) and do the flip themselves (`City.zone_index`). A correctly zoned copy lost no road cell in 150 s at speed 4.

## 1. Which cells vanished (offline, `savediff.py`, `orient.py`)

| save pair | network cells lost | of them zoned (game view, see 3) |
|---|---|---|
| showcase.sc3 (built, unzoned) -> showcase_g1.sc3 (zoned offline, grown) | 48 (38 road, 10 highway) | **48** |
| showcase_zoned (auto 1 h) -> showcase_zoned | 27 | 20 |
| showcase_zoned -> showcase_shoot | 8 | 4 |

The g1 -> zoned-autosave step also holds the showcase child's own rebuilds (cloverleaf redo, ramps, 260 lost and 100
added), so it is not counted here. Nothing else was lost with the roads: the losses are single network cells on grid
roads, junction drags and highway cells, each next to a C (6) or I (10) zone.

## 2. Who removes them (live, read-only Frida hooks, `re/tools/net_remove_watch.py`)

Game: `rl_zoned0.sc3` = `zone.py` run on the clean built `showcase.sc3`, the original pipeline. Speed 4, 150 s.

| run | network removals (manager vt+0xb4, SIMNTWRK `0x1001d6ef`) | caller |
|---|---|---|
| all mods (dev/roadloss inst) | 11 | 11 of 11 SIMGEOM `0x1001408d` (+0x142cf) under SIMRCI `0x10032dfc` (+0x32f9b) |
| `-Stock` (sc3winonly.dll only) | 33 | 33 of 33, same path |

Call path (Frida FUZZY backtrace; frames mapped to `re/ghidra_export_simrci` functions):
`sc3_zone_on_simulate 0x10031499` -> `sc3_zone_tick_develop_tiles 0x1003372a` -> `sc3_comdev_evaluate_tile 0x1000fd53`
/ `sc3_inddev_evaluate_tile 0x10017fc0` -> `develop_lot 0x1001049e` / `0x10018bc1` -> `0x100107a9` / `0x10019061` ->
`sc3_comdev_place_lots_block 0x1000cf87` / `sc3_inddev_place_lots_block_v2 0x10014794` ->
`sc3_zonelayer_place_building_attrib 0x10032dfc` -> SIMGEOM `0x100134fb` -> `0x1001408d` -> SIMNTWRK `0x1001d6ef`.

`0x10032dfc` reads the occupant on each footprint cell (occupant manager vt+0x7c). When the occupant's vt+0x6c
answers true, it removes it: through manager vt+0x48 (Remove), or, for GeomFlag 0x800 (network pieces), through the
demolition layer (+0x25c vt+0x58) `[CONFIRMED @ 0x10032dfc]`. With mods, each of the 11 removed cells was the origin
of a 1x1 placement (10) or inside a 2x2 footprint (1, origin (105,114)), all with param_3 = 4. That is the constant
`place_lots_block` passes to zone layer vt+0x68 `[CONFIRMED @ 0x1000cf87]`. Stock: 30 of the 33 removals were at the
origin of a 1x1 param_3 = 4 placement, and the other 3 were not attributed. The lot rects handed to the placers (`verify/roadloss/rects.py`) held
road cells in 861 of 5,565 calls, some of them a single road cell (`[63,51,63,51]`).

`sc3_zone_tick_develop_tiles` calls a developer only for the zone slot it reads at the visited cell (zone layer
vt+0x34, then `param_1[slot*2 + 0x67]`) `[CONFIRMED @ 0x1003372a]`, so a road cell is developed only when it is zoned.

Fire is not on this path, and no fire was seen in either run. sc3simrun CHURN only repoints three roll thresholds
(`sc3simrun.c` CHURN block). The stock control removes roads at the same rate. So the mods neither cause nor stop it.

## 3. The zone raster orientation (the root cause)

Live raster read through the zone layer's own getter (vt+0x34, the zone layer taken as ecx of `0x1003372a`;
`re/tools/zone_live_dump.py`), stock game, `rl_zoned0.sc3`:

- all 33 removed cells read zoned (2, 3, 6, 10). 1,942 network cells read zoned;
- the live byte at game cell (x, z) equals the saved byte at `(N-1-x)*N + z` for **35,990 of 36,864** cells (the
  rest changed by growth). The other mappings match 10,370 to 22,904 cells.

Cross-check on cities zoned by the game itself (network cells holding a zone 1..21; the zone tool refuses them):

| city | network cells | `data[(N-1-x)*N+z]` | `data[x*N+z]` | `data[z*N+x]` | `data[(N-1-z)*N+x]` |
|---|---|---|---|---|---|
| Berlin | 19,220 | **0** | 5,861 | 6,277 | 6,420 |
| Madrid | 17,253 | **0** | 8,968 | 9,216 | 9,306 |
| Farmsville | 2,232 | **0** | 214 | 188 | 226 |
| Seoul | 12,431 | **3** | 4,098 | 4,753 | 5,217 |

This agrees with `re/tools/query_id_check.py` (12 of 12 query readings in Berlin: row N-1-x, column z) and with
CITY_SAVE.md (the zone writer emits rows in reverse). `zone.py` wrote `data[x*N + z]`, which is the game cell
(N-1-x, z): every zone landed mirrored in x.

## 4. Fix (worktree `child/roadloss`)

- `re/tools/city_write.py`: `City.zone_index(x, z, n) = (n-1-x)*n + z`. `zone_get(x, z)` / `zone_set(x, z, slot)` take
  the game cell, the same coordinates as network tiles. `--selftest` adds an orientation check: zoned network cells
  must be 0 in Berlin, Madrid and Farmsville (measured 0 / 0 / 0; round-trip 80/80 identical).
- Callers: `query_id_check.zone_at` drops its hand flip, the `city_planes` selftest compares against row N-1-x (PASS on
  Berlin), and `city_grid.py` writes through `zone_index`. It wrote `data[y*N + x]`, the same class of error.
- `verify/showcase/zone.py` (MAIN, untracked): `zone_set(x, z)` with the new API, `zone_set(z, N-1-x)` with the old one.
  Both give byte-identical output.
- Tools: `re/tools/net_remove_watch.py` (network removal watcher with stacks), `re/tools/zone_live_dump.py`.

Live re-check: `rl_zoned_fixed.sc3` (fixed `zone.py` on the clean built save, 0 of 7,232 network cells zoned), all
mods, speed 4, 150 s: **0 network removals**. The city grew to 24,173 people by 1/30/2004. In the next 40 s sample
the placers ran 6,716 lot blocks and placed 234 buildings, with 0 removals. Picture (MAIN, gitignored):
`verify/roadloss/owner_shots/fixed_zoning_after_150s.png` (zones beside the roads, buildings growing).

## 5. Not explained here

- **ISSUES 5, the cloverleaf F1 and the S-curve F6.** None of their cells were zoned in g1 (0 of 180, 0 of 84). The
  cloverleaf box goes from 180 cells (g1) to 82 (first zoned autosave), with 15149 left at (19..20,152). That window
  also holds the showcase child's edit scripts, and its netmod logs were overwritten by later runs. Replaying g1
  does not reproduce it: g1 loads with the zone sim stopped. With pause depth 0 and speed 4, `0x10031499` and
  `0x1003372a` were called 0 times in 15 s. In 360 s, the cloverleaf / S-curve boxes saw 0 network removals and the
  5-minute autosave kept 180 / 84 cells. Cause not found.
- **g1's stopped sim** is ISSUES 2 ("a fire froze game time"). Seen, not investigated.
- `re/tools/city_clone.py` and `city_tile.py` (1024 test cities) copy the raw raster while testing it against
  network coordinates (`szone[y*SRC_N + x]` beside `(ox+x, oy+y) in road`), the same class of error. Not changed and
  not measured. `Europolis 1024.sc3` (in `stage/release/Cities`) has 64 of 153,840 network cells zoned in the game
  view, so its roads can be built over the same way.

## Owner call (optional)

Stock lets a zoned network cell be developed and bulldozed. Only offline tools can create one, so no mod guard is
proposed. If one is wanted, the place is the footprint clear in `0x10032dfc`: refuse GeomFlag 0x800 occupants there.
