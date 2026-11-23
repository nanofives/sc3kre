# Round 2026-11-23c: distortion on the parking side of the converted Large Fire Station

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Owner 2026-11-23: "the geometry of the fire station has a weird distortion on the parking side"
(verify/sc4cmp/forum/18_large_fire_station.jpg, SC3 side and in-city strip). Seen: the wall under the roof's
parking-side eave (the engine-bay doors) is a smeared, stretched band and the roof seems to overhang the apron.
The Large Fire Station (SC4 lot 3x2) is one of the 5 civic looks installed turned a quarter by civlot today
(merged e434a6c: bldimport `civic_turn` / `turned_model`, render slot remap s -> s - 1, bldweb `civicTurn`,
compare_sheet `turn_of`; verify/civlot/RESULTS.md).

## Stream firedist (opus / medium)

1. Measure, do not guess: render the Large Fire Station four ways: turned (as installed now) and on its unturned 3x2
   lot, both with `baked_sharp`, all four rotations, zoom 3 and 4. Put each SC3 frame next to the SC4 view it was
   built from. Say which wall comes from which SC4 picture in each frame.
2. Find the cause with evidence: wrong SC4 view for a slot after the turn (remap off by one or mirrored), wrong
   rotation sign, the house-view projection stretching a wall SC4 barely sees (the known 45 vs 30 degree limit),
   ground clamp, or something else. Check the other 4 turned looks and 2 non-turned civic buildings (Elementary School,
   Small Police Station) for the same artefact.
3. If it is a converter / remap fault: fix it (Python and page byte for byte), re-make the affected sheets in
   verify/sc4cmp/forum/ (18 and any other turned look, with in-city strips from new game frames if the frame changes),
   suite (CHILD_PROTOCOL suite modes). If it is the inherent camera limit: say so with the numbers, and propose what
   could reduce it (another SC4 view for that wall, blending two views), without building it.
4. Results verify/firedist/RESULTS.md, STATUS re/sessions/STATUS_firedist.md, before/after crops in owner_shots.

## Rules

SC4 install read in place, EA content never in git or docs. Windowed game, never the real mouse or keyboard, test
slot, harness claim before game runs, kill only PIDs you started, delete BMP dumps, no git add / commit.
