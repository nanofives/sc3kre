# STATUS cartrips2 (M1 trip tap + M2 lane routes + M3 route cars), 2026-10-16: M3 DONE, hand test staged

Branch `child/cartrips2` (worktree `Simcity_wt\cartrips2`). Not merged (the orchestrator integrates). Harness claim
released at the end. No game left running.

- M1 / M2: `verify/cartrips2/` (2026-10-15).
- M3: `verify/cartrips3/PRE.md` (+ addenda 1-5) -> `RESULTS.md`, data in `verify/cartrips3/data/`;
  `re/analysis/CAR_TRIPS.md` section 7.
- Code: `re/harness/src/sc3cartrips.c` + `sc3cartrips_lanes.c` + `sc3cartrips_cars.c`; tested build 33ef673e
  (`Simcity_stock_pausetrips\re\harness\build_ct3`).
- Hand test: MAIN `re\harness\handtest_cartrips\` (sc3cartrips.dll 33ef673e, mods_launch.exe 88452c54, cartrips.ini,
  README.txt). Owner pictures: MAIN `verify\cartrips3\owner_shots\` (3 PNG, 1 GIF, captions.md).
- Tools: `ctm_m3summary.py`, `ctm_modealt.py`, `ctm_shots.py`; pt_run `Z:n` (zoom-in button clicks); queue
  `verify/cartrips3/ct3_queue.sh`.

Open: count below target at Berlin speeds 1-3 in replace mode (route supply); two startup deaths of the full mod set
on the 1024 city before sc3cartrips armed (sc3perf's known one, LANE_DENSITY 5); a game that survived the driver's
first taskkill (L2c). Arrival is still a vanish.
