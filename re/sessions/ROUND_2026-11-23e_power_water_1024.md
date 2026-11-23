# Round 2026-11-23e: power and water stop spreading about mid-map on 1024 cities

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Player report (owner 2026-11-23, picture verify/forumshots/player_power_water_1024.png): "I have started a city in the
edge of the map, on a giant 1024 tiles map. Electricity and water doesn't propagate properly anywhere in the map with
pipeline and electric cable. Electricity and water are 'stuck' approximately mid map ... You must build a powerplant and
a pump in uncovered zone to fix this. Edit: it didn't fix. it create a new powered zone and a new watered zone with new
stations. But no connexion despite the pipes and the cables." The picture shows a power line (and a pipe) running on,
with the powered / watered area ending partway along it.

Background: re/analysis/POWER_GRID.md (flood fill by dilation over the 1-bit mask raster +0x5c), POWER_SUBSYSTEM.md,
SIM_LAYERS_XREF.md, memory project-1024-scaling-round (8-bit packed coordinate / 256 limit pattern, sc3bigcity),
project-bigcity-mod, verify/bigcity_option. sc3bigcity sizes the city 512..1024.

## Stream pw1024 (opus / high)

1. Reproduce first: a 1024 city (Europolis 1024 test city or a New City "Enorme" 1024), a power plant near one edge and
   a power line across the map, the same with a pump and pipes. Measure where coverage stops (cells from the plant,
   absolute cell coordinates), on the powered / watered data views and in the layer rasters (Frida read of the layer
   objects). Also 512 and 768 cities, and the plant in the middle vs at the edge, to tell "distance from the plant"
   from "absolute coordinate" from "a fixed raster size".
2. Root cause with evidence [CONFIRMED @ addr]: iteration cap of the dilation, a raster / mask sized for 256 or 512,
   a packed coordinate, a work list size, a per-update time slice, the water layer's own path. Check power and water
   separately (they may share or not). Use the CodeView names (re/analysis/CV_SYMBOLS.md, cv_functions.tsv).
3. Fix in the right mod (sc3bigcity owns size scaling), behind the usual switch rules, stock unchanged at stock sizes.
   Check a 1024 city: one plant at the edge powers the whole connected line, the same for water; save / reload; the
   monthly sim time at 1024 before / after (sc3perf).
4. Results verify/pw1024/RESULTS.md, STATUS re/sessions/STATUS_pw1024.md, pictures (powered view before / after).
   A short paragraph for the player reply.

## Rules

Windowed game, never the real mouse or keyboard, test slot, harness claim before game runs, kill only PIDs you
started, delete BMP dumps, no git add / commit.
