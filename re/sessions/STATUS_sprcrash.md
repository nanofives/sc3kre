stream: sprcrash (child of "SC3: owner bugs 10-23"), worktree Simcity_wt_sprcrash (child/sprcrash from abfd044)
state: DONE (milestone 2: fixed, tool only). Moved claude2 -> claude3 mid-run on 2026-10-24 (license limit).
cause: the Frida camera tool, not ordinary play. nramp_cam.JS called iso SetZoom / SetRotate through NativeFunction with
  the default exceptions:'steal'. A mod's OutputDebugStringA (0x40010006) inside the call was stolen and Frida unwound
  out of SetZoom halfway, leaving an unfinished camera rebuild: crash on a freed occupant (14180) or a main-thread
  deadlock (2 of 2 control games, first job). No mod calls the camera bare in ordinary play.
results: verify/sprcrash/RESULTS.md. Game path 159 steps 0 crash. Fixed tool 145 jobs 0 fail. Bare + propagate 60 jobs
  0 fail. Old tool (SC3_CAM_RAW=1) hang 2 of 2.
games: none running (14180 was avflow's; my 18656, 8236, 23568, 29676 all ended, last two stopped by PID).
files to commit (worktree Simcity_wt_sprcrash, uncommitted, no mod sources changed):
  re/tools/netmod/nramp_cam.py (modified)
  re/tools/netmod/np_drive.py (modified: post() uses propagate)
  re/tools/sprcrash/cam_soak.py, excprobe.py, stacks.py (NEW)
  verify/sprcrash/RESULTS.md (NEW)
  verify/sprcrash/data/*.txt (NEW, 10 files, git add -f if ignored)
  MAIN verify/sprcrash/crash_14180/ (already in MAIN, the original logs) and MAIN verify/sprcrash/data/*.log (run logs,
  optional)
open: 26 other re/tools files create NativeFunctions with 'steal' (55 sites), not sorted or changed.
