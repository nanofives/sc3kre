# STATUS cartrips2 (M1 trip tap + M2 lane routes), 2026-10-15: DONE, reported to the orchestrator

Branch `child/cartrips2` (worktree `Simcity_wt\cartrips2`), from child/cartrips + round/1012. Not merged (the
orchestrator integrates). Harness claim released. No game left running.

- Evidence: `verify/cartrips2/PRE.md` (+ addenda 1, 2) -> `RESULTS.md`, data in `verify/cartrips2/data/`.
- Analysis: `re/analysis/CAR_TRIPS.md` section 6 (M1 / M2 results, open questions answered, revised M3 plan, decisions).
- Code: `re/harness/src/sc3cartrips.c`, `sc3cartrips_lanes.c`; build_mod.ps1 `-Mod sc3cartrips`; mods_launch lists
  `sc3cartrips.dll`. Tested build 7adfb2e2 (`Simcity_stock_pausetrips\re\harness\build_ct2m2b`).
- Tools: `re/tools/ctm_read.py`, `ctm_summary.py`, `ctm_lanes.py`, `ctm_m2report.py`, `ctm_alt.py`; queue
  `verify/cartrips2/tools/ct2_queue.sh`.
- Raw runs: `Simcity_stock_pausetrips\re\harness\inst_ct2_stock`, `inst_ct2_full`;
  `Simcity_stock_roundabout4\re\harness\inst_ct2_rbt`.

Known, not fixed: the drain-latency maximum in the log wraps when a trip is committed after the tick read its clock
(log only). M2's debug overlay of solved lane paths (CAR_TRIPS 4.5) was not built.
