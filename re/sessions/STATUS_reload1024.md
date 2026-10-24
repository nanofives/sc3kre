# STATUS reload1024 (child of "SC3: owner bugs 10-23", protocol CHILD_PROTOCOL_2026-10-23_ownerbugs.md)

Owner report: "I retried to load Europolis 1024 for a second time after I loaded it once and the game crashed".
Worktree `Simcity_wt_reload1024` (branch child/reload1024), test tree `Simcity_stock_reload1024`.
Full write-up: `verify/reload1024/RESULTS.md`.

## State (2026-10-24): FIXED, both crashes

1. Owner's load crash: non-atomic refcount on STRTSIM's strike-crowd producer (two threads via GZServiceD dispatch)
   -> destroyed twice at teardown -> STRTSIM pool double free. sc3perf STRTSIM_REFCOUNT (+ `strtsim_refcount_all`,
   14 classes): 24 + 8 owner-sequence loads, 0 crashes; before 5 of 18. `strtsim_refcount=0` arm crashed (f10).
2. Crash while playing a 1024 reloaded over a 1024 (pre-existing, HEAD 1 of 6): SIMCITY sim group freed while still
   registered, same race on its plain refcount (0x10010d0d / 0x10010d14). sc3perf SIMGROUP_REFCOUNT: 0 of 8 died;
   without it 8 of 13.
3. sc3perf RELOAD (worker shadows rebuilt on a city change): Berlin <-> 1024 in one game, 0 faulted trips, 60 fps.
4. Report: ~80 more plain-refcount vtables listed (`plain_refcount_vtables*.txt`), not fixed.
Note: the 256 <-> 1024 neighbour runs were done before the SIMGROUP/extended-STRTSIM build (both only make refcounts atomic).

## Files to commit (orchestrator, by path)
- worktree `re/harness/src/sc3perf.c` (STRTSIM_REFCOUNT(+_ALL), SIMGROUP_REFCOUNT, RELOAD; switches strtsim_refcount,
  strtsim_refcount_all, simgroup_refcount, reload_shadow)
- worktree `re/tools/reload1024/` (probes, drivers, scans; re/ is gitignored: force-add)
- MAIN `verify/reload1024/RESULTS.md`, `plain_refcount_vtables.txt`, `plain_refcount_vtables_ecx.txt`, `owner_shots/*.png`
- MAIN `re/sessions/STATUS_reload1024.md`
