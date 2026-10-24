# STATUS refaudit (child of "SC3: owner bugs 10-23", protocol CHILD_PROTOCOL_2026-10-23_ownerbugs.md)

Task: audit the ~80 plain-refcount vtables left by reload1024 for cross-thread reachability, then make the
race-prone ones atomic in sc3perf. Worktree `Simcity_wt_refaudit` (branch child/refaudit from main 09ed238), test tree
`Simcity_stock_refaudit`. Write-up: `verify/refaudit/RESULTS.md` (both tables: the 70 and the 86).

## State (2026-10-24): FIXED, both passes audited, final soak clean

- Pass 1: 70 vtables (static read + Frida CModule census v1/v2). 4 RACE-PRONE:
  - SIMSPR resource object
  - GZResourceD resource object
  - STRTSIM occupant Release 0x1001607D
  - SCENARIO layer
- Pass 2: the 86 `<= 1` vtables (census v2-v4, about 39 min of 1024 at speed 4, 2 reloads of 1024, 1024 -> 256).
  10 had live objects. 1 new RACE-PRONE: SIMUI wrapper 0x100A8164 (game -> sim -> game on every object, rare).
- Fix: sc3perf RES_REFCOUNT, 5 switches, all default 1: `res_refcount_simspr`, `res_refcount_gzres`,
  `strtsim_refcount_ecx`, `scenario_refcount`, `le1_refcount_simui`. Each is byte-checked against the shipped DLLs.
- Final soak f1 with all 5 on, no probe: Europolis 1024 10 min at speed 4, 3 reloads, 1024 -> Berlin -> 1024.
  All PASS: loads 3 to 6 s, 0 faults outside the KERNEL32 first-chance reads, 6.57 M trips with 0 faulted.
- Probe note: census v3/v4 died inside frida-agent after a load. The cause was the in-process FUZZY backtrace thread
  labeler. census.py now reads stack tops out of process (checked 60 s, no fault).

## Files to commit (orchestrator, by path)
- worktree `re/harness/src/sc3perf.c` (RES_REFCOUNT block + 5 cfg switches + rr_watcher start; nothing else changed)
- worktree `re/tools/refaudit/` (census.py, census_report.py, census_merge.py, gen_table.py, gen_table_le1.py,
  le1_live.py, scan_le1.py, soak.sh, soak2.sh, ab_measure.sh, nav.sh, launch.ps1, dbl2.py; re/ is gitignored:
  force-add. nav.sh / launch.ps1 / dbl2.py / soak*.sh carry this PC's paths and maximized click coordinates)
- MAIN `verify/refaudit/` (RESULTS.md, census_merged.tsv, census_le1_merged.tsv, census_c1_report.txt,
  census_c2_report.txt, le1_refcount_vtables.txt, owner_shots/*.png)
- MAIN `re/sessions/STATUS_refaudit.md`
