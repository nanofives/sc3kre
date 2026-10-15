# STATUS cartrips2 (M1 trip tap + M2 lane routes), 2026-10-15

Branch `child/cartrips2` (worktree `Simcity_wt\cartrips2`), from child/cartrips + round/1012. Harness claimed by
`cartrips2`. Games run in `Simcity_stock_pausetrips` (inst_ct2_stock, inst_ct2_full) and `Simcity_stock_roundabout4`
(inst_ct2_rbt). Arm queue: `verify/cartrips2/tools/ct2_queue.sh`, log `Simcity_stock_pausetrips\re\harness\ct2_queue.log`.

| step | state |
|---|---|
| PRE + addenda 1, 2 | committed (119c695, 08464a5, 52cce78) |
| sc3cartrips.dll M1 (c392ccbc) | K smoke, A1, V2 done: 0 faults, deposits exact, A1 410/410 samples matched |
| M2 solver in DLL (a3038ce4 -> 7adfb2e2) | M2B on a3038ce4 running; queue M2B2 M2M M2L M2E M2R F2 next, then F1 C1 C2 |
| offline twin `re/tools/ctm_lanes.py` | analyse / match / sources |
| RESULTS.md, CAR_TRIPS.md update | after the queue |

If resuming after a usage limit: check `harness_claim.ps1`, `tasklist SC3U.exe`, `ct2_queue.log`; only kill PIDs in
`pid_<arm>.txt` of this task's instances.
