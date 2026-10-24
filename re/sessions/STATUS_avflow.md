# STATUS avflow (2026-10-24) - follow-up BVFIRST measured: built, OFF by default; class-grid sweep fix; uncommitted
goal: owner "make a 2-road avenue and 3-road avenue (boulevard) increase traffic flow". First round merged (main ef8b8c8):
  AVFIRST + AVDEPOSIT on by default. Follow-up (owner): rank boulevard cells above avenue cells (BVFIRST).
built (this round, worktree Simcity_wt_avflow on child/avflow = ef8b8c8):
  - BVFIRST in avf_close: an open class-2 candidate below the level also closes open class-1 candidates. Env
    SC3NETMOD_AVF_BVFIRST=1, live sc3netmod_avf_bv_set; AVF_DEFAULT_BVFIRST 0. Stats "bvfirst offers / avenue cells closed".
  - Class-grid SWEEP: after each edit pass the whole grid is re-read on the game thread, 16 rows per RB_WM+1 message
    (blocks write outside the edit box: BV whole-map re-run, AVL far band ends). Found when the extended boulevard was
    classified 27 of 189 cells. Checked: an edit left 132 stale boulevard cells, the sweep corrected to 24.
  - probes: bvtrace_probe.py (NEW), avflow_probe.py (arms FDB / FB, two-arm blocks a b b a, export sc3netmod_avf_bv_set),
    avflow_report.py (FB / FDB arms, boulevard columns).
proven in game:
  - trace: no router step ever had an open boulevard AND an open avenue candidate (0 of 1,193 steps on seoulbv1, 0 of
    5,247 / 5,154 on seoulbv2). Boulevards are entered only from plain roads (ends taper into a plain row, crossing arms);
    BV refused a run reaching the avenues ("an avenue arm that would stay two-way").
  - seoulbv2 (inst_avflow\seoulbv2.sc3: boulevard extended to x 126..188, 189 cells; not in git).
  - ABBA FD vs FD+BVFIRST, one game, 24 months per arm: failed 2.23 / 2.20%, avenue share 39.4 / 39.9%, boulevard use
    0.43 / 0.38%, all window ranges overlap; counter bvfirst offers=282,047, avenue cells closed=0 -> identical routing,
    the run is an A/A noise floor.
  - side finding: boulevard carries ~0.4% of trips, density 1.3..1.6 vs avenues 48; at its 7 entry cells 52% of steps
    offering it end with no step, 26% take a plain road (likely one-way outer-row entries refused, [UNCERTAIN]).
recommendation: BVFIRST default OFF (it has nothing to act on in any BV layout seen; only a boulevard narrowing straight
  into a one-way avenue could trigger it, none exists).
incident: PID 14180 crashed in SIMSPR+0xDF01 during rb_lab.py cam (Frida camera queue); logs inst_avflow\crash_14180\.
blocked on: -
needs owner: nothing; if boulevard use matters, the next lever is the entries (one-way outer rows / junction arms), not ranking.
files owned (worktree Simcity_wt_avflow, uncommitted):
  re/harness/src/sc3netmod_avflow.c (BVFIRST + SWEEP), re/harness/src/sc3netmod_rbt.c (+2 lines /* task avflow */)
  re/tools/netmod/avflow_probe.py, avflow_report.py (modified), re/tools/netmod/bvtrace_probe.py (NEW)
  verify/avflow/RESULTS.md (section 2.7 + open list)
  verify/avflow/data/seoulbv_trace_fd.json, seoulbv2_trace_fd.json, seoulbv2_trace_fdb.json, seoulbv2_abba_bvfirst.json
    (NEW, git add -f)
instance: Simcity_stock_avflow\re\harness\inst_avflow\ (DLLs with BVFIRST + sweep). All my games stopped
  (14180 crashed, 21840, 25388 killed by PID). Closers stopped.
