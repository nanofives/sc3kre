# STATUS avflow (2026-10-24) - M2 measured; AVFIRST + AVDEPOSIT built, on by default, uncommitted
goal: owner "make a 2-road avenue and 3-road avenue (boulevard) increase traffic flow"; owner chose AVENUE-FIRST routing
  + LIGHTER TRAFFIC PER TRIP on avenue / boulevard cells, together.
design (re/harness/src/sc3netmod_avflow.c, #included by sc3netmod_lanes.c after rampfirst):
  - CLASS grid (byte per cell: 0 other, 1 avenue, 2 boulevard), filled at the end of rb_pass (box+3) and rb_load_pass.
  - AVFIRST in ld_select after rf_close; AVDEPOSIT = retarget_call at SimTransit 0x10007463 (x2/3 avenue, x1/3
    boulevard, exact remainder per cell). Detail: verify/avflow/RESULTS.md section 1.
  - env SC3NETMOD_AVFIRST=0 / SC3NETMOD_AVDEPOSIT=0 (off), SC3NETMOD_AVDEP_AV / _BV = n/d; live exports
    sc3netmod_avf_set / avd_set / avflow_set / avf_grid.
proven in game (Seoul, one game, 24 months per arm off / F / FD): avenue share of path road cells 27.7 -> 34.9 -> 38.1%
  (window ranges disjoint), failed 2.02 -> 1.99 -> 1.97%, side-street density 48.6 -> 46.0 -> 44.3, game traffic avg
  60.5 -> 60.5 -> 56.6, paths 45.4 -> 47.9 cells. Router cost (ld_alt, batch mode): AVFIRST +7.8%, both +5.7% per trip.
  Deposit ratios exact (0.66667 avenue, 0.33333 boulevard). 0 faults over 734k smooth + 867k batch worker trips.
  Commute time: not read (no such statistic / string found).
  Boulevard arm (bvlanes' seoul_bv2_saved.sc3, one 39-cell boulevard, PID 18944): avenue result repeats (28.0 -> 39.1%),
  boulevard use NOT up: 0.59% (off) / 0.44% (F) / 0.50% (FD) of arrived trips, ranges overlap, density 38.6 -> 19.1;
  cause not isolated. Unbuilt lever: rank boulevard cells ahead of avenue cells in AVFIRST.
owner sheet: MAIN\verify\avflow\owner_shots\avflow_sheet.png (+ traffic_off.png, traffic_on.png, traffic_off2.png:
  the game's own traffic layer, same camera).
blocked on: -
needs owner: whether boulevards should rank ahead of avenues (boulevard arm showed no gain); defaults are on.
files owned (worktree Simcity_wt_avflow, uncommitted):
  re/harness/src/sc3netmod_avflow.c (NEW, gitignored by /re/*: git add -f)
  re/harness/src/sc3netmod_lanes.c (lines marked /* task avflow */)
  re/harness/src/sc3netmod_rbt.c (3 lines marked /* task avflow */)
  re/tools/netmod/avflow_probe.py, avflow_report.py, avflow_sheet.py, budget_closer.py (NEW)
  verify/avflow/RESULTS.md (NEW)
  verify/avflow/data/seoul_baseline.json, seoul_abba.json, seoul_class.npy, seoul_dens_off.npz, seoul_dens_fd.npz,
    seoul_dens_off2.npz, seoulbv_alt_avfirst.json, seoulbv_alt_both.json, seoulbv_baseline.json, seoulbv_abba.json (NEW, git add -f; ~800 KB)
  MAIN (not in git): verify/avflow/owner_shots/*.png, this status file.
instance: Simcity_stock_avflow\re\harness\inst_avflow\ (default-on DLLs) and inst_avflow_batch\ (smooth=0 copy, the
  sc3netmod there is the default-off build). All my games stopped (19672, 16432, 20532, 18944).
