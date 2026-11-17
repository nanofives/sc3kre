# STATUS roadloss (2026-11-17)

## goal
Orchestrator brief: road cells disappear during play in the showcase city (ISSUES.md 4a / 5). Find what removes them
(fire candidate), stock or ours, fix with an off switch if ours.

## verdict + deciding RVA
Our offline zoning tool, not the game or a mod. `verify/showcase/zone.py` wrote zones mirrored in x (city_write
`zone_set(z, x)` = raster `data[x*N+z]`, the game cell is `data[(N-1-x)*N+z]`), zoning 1,773 road / highway cells.
The stock zone developer builds 1x1 C/I lots there: SIMRCI `0x10032dfc` place_building_attrib clears the footprint
through SIMGEOM `0x1001408d` -> SIMNTWRK `0x1001d6ef`. Same rate in the `-Stock` control (33 in 150 s). No fire.
Detail: `verify/roadloss/RESULTS.md`.

## built
Tooling only, no mod code: `city_write.zone_get/zone_set` take the game cell (`City.zone_index`), selftest orientation
check, callers updated (`query_id_check`, `city_planes`, `city_grid`), `zone.py` fixed in MAIN (untracked).
New read-only tools `re/tools/net_remove_watch.py`, `re/tools/zone_live_dump.py`.

## proven game-side vs static only
Game-side: removal stacks (mods + stock), live zone raster read (35,990 / 36,864 cells match the N-1-x mapping), fixed
copy 0 removals in 150 s with growth to 24,173 pop. Offline: 0 zoned network cells in Berlin / Madrid / Farmsville under
the mapping. Not found: the cloverleaf F1 / S-curve F6 loss (ISSUES 5, cells never zoned; g1 loads with the zone sim
stopped, 0 ticks in 15 s).

## blocked on
-

## files owned
child/roadloss: re/tools/city_write.py, city_grid.py, city_planes.py, query_id_check.py, net_remove_watch.py,
zone_live_dump.py, verify/roadloss/RESULTS.md, this file.
MAIN (untracked, gitignored): verify/showcase/zone.py (one call fixed), verify/roadloss/* (scripts, jsonl runs,
owner_shots/fixed_zoning_after_150s.png).

## game-harness need
none (dev/roadloss game only, stopped).

## asks of other sessions
- showcase: re-zone from showcase.sc3 with the fixed zone.py before any new gallery run.
- city_clone.py / city_tile.py (1024 test cities) mix raw raster indexes with network coords. Europolis 1024 has 64
  zoned network cells (game view). Not changed here.
