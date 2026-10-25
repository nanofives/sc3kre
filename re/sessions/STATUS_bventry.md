# STATUS bventry (2026-10-25) - DONE: cause found, AVSTART recommended on (code default off), BVCOST / AVCOST off; uncommitted
goal: explain why the seoulbv2 boulevard carries ~0.4% of trips, and why 52% of the steps that offered a boulevard
  cell at its 7 entry cells ended with no step; fix the cause. Follow-up (orchestrator 10-25): seoulbv3 with zoned
  blocks, BVCOST on seoulbv2 + seoulbv3, avenue option on its own switch, budget failures citywide.
worktree: Simcity_wt_bventry (child/bventry from main a4e45fb). Tree: Simcity_stock_bventry. No game or tool of mine
  running.

cause (verify/bventry/RESULTS.md sections 1-2):
  - No entry is refused: BV matrices allow every right-hand entry and exit, 0 wrong-way refusals.
  - The 52% "no step" are DFS retries after the boulevard branch failed (86%), and a plain road six rows north fails
    86% too: through-trip failure belongs to the district, not the boulevard.
  - Boulevard-specific: the trip START (FUN_1000755e start branch) takes the busiest road within the lot radius, and
    AVFIRST never acted there. Only 38% of the starts with an open boulevard cell in range took it.
  - seoulbv3 not made: seoulbv2's blocks beside the boulevard are still zoned residential and built, as in the
    original. Only the 117 cells under the outer rows (plus 8 taper-end cells) lost their zone.
levers (RESULTS section 3, one game, 24 months per arm, 0 sc3perf faults):
  AVSTART (avenue-first at the trip start)  boulevard use 0.32 -> 0.69%, avenue use 42.0 -> 47.4%, failed 2.32 -> 2.29%: default OFF in code (orchestrator 10-25), recommended ON
  BVCOST  (boulevard step cost x 1/2)       0.32 -> 0.40%, failed 2.38%: off
  AVCOST  (avenue step cost x 1/2, own switch)  failed 1.97%, budget hits 9.7 -> 8.1%, paths +8%: off, owner call
  citywide budget: 9.7% of trips hit it, 54.6% of failed trips did (FD).
blocked: launch check of the final build (and the AVSTART+BVCOST arm). Windows Defender flagged Apps\version.dll (Program:Win32/Contebrew.A!ml) at 02:15,
  hard-linked into Simcity_stock_bventry, Simcity_stock_avflow and Simcity_release. mods_launch refuses. Not touched.
owner shots: MAIN\verify\bventry\owner_shots\ traffic_avstart_off/on.png, traffic_bvcost_off/on.png, boulevard_view.png

files to commit (worktree Simcity_wt_bventry):
  re/harness/src/sc3netmod_avflow.c   (AVSTART, BVCOST, AVCOST blocks, /* task bventry */)
  re/harness/src/sc3netmod_lanes.c    (avc_adjust after both trampoline calls, AVSTART in the start branch,
                                       ld_stub checks g_avc_on / g_avc_av_on / g_avs_on, mode-4 test)
  re/tools/netmod/avflow_probe.py, avflow_report.py (arms FDC C FDA FDCA FDS FDS2, budget counters)
  re/tools/netmod/bventry_probe.py, bvbranch_probe.py, bvstart_probe.py (NEW)
  re/tools/place_direct.py (Frida API fix + exceptions 'propagate')
  verify/bventry/RESULTS.md (NEW)
  verify/bventry/data/* (NEW, git add -f)
