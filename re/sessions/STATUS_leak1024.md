# STATUS leak1024 (child, 2026-11-17)

## goal
Measure the view rotation / zoom leak on Europolis 1024 with 2026-11-17c: arm A shipped (SPR_IMGREF on), arm B SC3PERF_SPR_IMGREF=0.
100 paused rotations at zoom 4 and widest zoom per arm, then 15 min soak per arm.

## verdict + deciding RVA
DONE, no code change. On Europolis 1024 (800x600) arm B (IMGREF=0) does NOT leak: 0.16 MB/rotation (A 0.14), no crash in 100 rotations at two zooms or in the 15 min soak (A +64.6 MB, B +88.9 MB, largest free 768 / 735 MB, 0 VEH faults). Follow-up done: Berlin control B 16.06 / A 0.93 MB per rotation (harness valid), 1024 view turns (shots), tally: 1024 re-makes ~226 images (~0.57 KB each) per rotation vs Berlin ~1245 (~9.4 KB), 0 freed on both in B. Larger client not run. See verify/leak1024/RESULTS.md.

## built
nothing (measurement only). Tools copied from verify/rotleak with the tree changed to dev\leak1024.

## proven game-side vs static only
Game-side: 4x100 paused rotations, 2x15 min soak. Not done: widest zoom picture check, larger client, Frida decode count.

## blocked on
nothing

## files owned
verify/leak1024/{RESULTS.md, rotmem.py, soak.py, ab100.sh, soak2.sh, runs/*, rot_trace.py, ctrl.sh, trace_arm.sh, trace2.sh, shots/Eur_B_*.jpg}, re/sessions/STATUS_leak1024.md

## game-harness need
dev\leak1024 tree only

## asks of other sessions
none

## update 2 (closest zoom)
The earlier 1024 runs were at a FAR zoom. At the closest zoom, 40 paused rotations: B (IMGREF=0) 6.98 MB per rotation (293.9 -> 573.0 MB, largest free 787 -> 549), A 1.07 (294.1 -> 336.9, free 786 -> 770). Trace B closest: ~340 images / ~6.1 MB per rotation, 0 freed. See RESULTS.md.
