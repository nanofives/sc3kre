# pausetrips: PRE-REGISTRATION (2026-10-15, written before any game run)

Owner question (2026-10-15): "what are the trips when paused?" What does the traffic simulation do while the game is
paused, compared with running? Also: does the camera hold (city `+0x144`) behave like the user pause for trips, and do
trips queued by sc3perf `traffic_mt_smooth` drain during a pause?

## Known before this file (cited, not re-derived)

- Monthly building trips: SimTransit `FUN_100097b9`, per building, gated on `day/7 == this+0x10` [CONFIRMED @ SimTransit
  0x100097b9]; it calls the trip function `FUN_10006fe3`, which calls the router `FUN_100070d0` (route_trip). Router step
  `FUN_1000755e`, congestion deposit `FUN_10006edd`.
- route_trip returns AL = 1 on arrival and 0 on failure; it adds 1 to layer `+0xb0` per attempt and 1 to layer `+0xb4`
  per failure (`piVar7[0x2d]`) [CONFIRMED @ SimTransit 0x100070d0]. Live layer = `DAT_1001fdb8`.
- Other trip entry points: `FUN_1000706a` (trip from a cell, ~17/s from zone development on Europolis 1024,
  PERFORMANCE.md Finding 24), SIMECO+0x423c and SC3U.exe `FUN_004bfe89` (Finding 23/24).
- Clock: SIMCITY vtable `0x10013988`, `+0x4c` day count, `+0x50` speed, `+0x54` pause count, `+0x60` ms per day; one
  1000 ms timer callback adds real time only while `+0x54` is 0 and fires `FUN_1000aa4d` per whole day
  (PERFORMANCE.md Finding 10). Clock = city `+0x130`.
- Three city counters pause that same clock: `+0x140` user pause (messages `0xc2a35d7e` / `0xc2a35d80`), `+0x144`
  camera / UI holds (`FUN_100058ac` / `FUN_1000590e`), `+0x148` (SIM_WHILE_SCROLLING.md).
- The sim thread is a timer-list thread, SIMCITY `FUN_1000c8db`: it runs every due entry of a list (period `piVar2[6]`,
  one-shot flag `piVar2[5]`) and sleeps until the next one is due [CONFIRMED @ SIMCITY 0x1000c8db]. The clock's
  1000 ms callback is one entry; what the other entries are is not known yet (measured here, `timers` lines).
- How the harness pauses without focus: a posted `P` key is handled by sc3resize PAUSEKEY (`rz_wndproc`), which posts
  `0xc2a35d7e` (depth 0 -> pause) or `0xc2a35d80` through the message service (sc3resize.c, PAUSEKEY comment, citing
  [CONFIRMED @ SIMCITY 0x10002fa6]). Speed keys 1-4: sc3resize SPEEDKEYS posts `0xc2684065` and does not unpause.
  KEYFOCUS lets these through when no text field has the in-game focus (the city view).
- sc3perf smoothing workers loop on `smooth_work` + `WaitForSingleObject(evt, 2)` with no clock check
  (sc3perf.c `mt_worker`); the sim thread drains only before `FUN_10009242`, a full ring or teardown.

## Setup

- Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips`: hard links of MAIN `Apps`, `Buildings`, `Cities`,
  `Scripts` (3,472 linked, release mod files skipped), `*.ini/*.cfg/*.txt` in Apps / Cities de-linked (5),
  `GZGraphicD.dll` / `SIMSPR.DLL` = `original\modules` copies. SHA-256 prefixes: SC3U.exe 49dd55e1 (anchor),
  SimTransit b478ded4, STRTSIM c02ce38f, SIMCITY 56546048, GZGraphicD 48201f47, SIMSPR eec71500.
- City: stock `Berlin, Germany.sc3` (99327775), copied into the instance folder per arm.
- Builds from branch `child/pausetrips` at its base (round/1012 eb81a1a), VC x86 /O2 /MT:
  mods_launch 059ae8df, sc3resize 43cb5059, sc3bigcity 76a83845, sc3overscroll a5b69ca3, sc3simrun 87b748d0,
  sc3perf 0f47ac9d.
- Instances in `<tree>\re\harness`:
  - `inst_pt_stock`: mods_launch + sc3resize only (needed for the P / speed keys). No sc3perf, no sc3simrun: trips
    are routed by the game itself and the stock scroll hold is intact.
  - `inst_pt_full`: all six mods, `perf.ini` = MAIN `re\harness\combo\perf.ini` (2b9708f0: traffic_mt=8,
    traffic_mt_smooth=1, clock_ms=50, fast_ceil=1, mt_locks=1), `bigcity.ini` of combo (1eda071c), simrun default
    (run_while_scrolling=1).
- Probe `re/tools/pt_probe.py` (Frida, read-only), driver `re/tools/pt_run.py`. Per second:
  calls to route_trip (by caller return address, by thread, arrivals / failures), `FUN_10006fe3` and `FUN_1000706a`
  (by caller, with up to 3 backtraces per phase), `FUN_100097b9`, `FUN_10006edd`, `FUN_1000755e`, `FUN_10009242`,
  `FUN_100093e9`, day fires `FUN_1000aa4d`, STRTSIM `FUN_1001c750` (calls, distinct `this` = vehicles moved, by thread,
  by caller, 3 backtraces per phase); state: city `+0x140/+0x144/+0x148/+0x14c/+0x150`, clock `+0x4c/+0x50/+0x54/+0x60`,
  layer `+0xb0/+0xb4`; and the sim thread's timer list at the end of each phase.
  In `inst_pt_full` (`--safe`) the entries sc3perf patches (`0x10006fe3`, `0x1000706a`, `0x10006edd`, `0x10009242`)
  are not hooked; route_trip's caller and thread split carries that information.
- One game at a time, launched with `mods_launch.exe -multi`, harness claimed by `pausetrips`, killed by PID at the end.

## Smoke run (tooling check, not an arm)

One short run on `inst_pt_stock` (schedule `s3:40,P:30,s1:30,P:20`) to check that the probe loads, that P and 1-4
change `+0x140` / `+0x150`, and that the hook load does not stop the sim (days advance at speed 3). If the tooling
changes after it, the change is listed in an addendum before the arms.

## Arms

Schedule `SCHED` (seconds): `s3:60` (warm-up, excluded), `s1:120`, `P:90`, `s2:90`, `P:90`, `s3:90`, `P:90`, `s4:90`,
`P:90`, `H:60` (camera hold at speed 4), `s4:30`, `PH:45` (user pause + camera hold), `s3:60`, `P:60`.

| arm | instance | probe |
|---|---|---|
| S1, S2 | inst_pt_stock | full hooks |
| F1 | inst_pt_full | `--safe` |

Analysis excludes the first 3 s of every phase (key latency, a day already in progress). Counts are per-phase sums and
per-second means.

Validity (decided before reading any counter): process alive at the end; in every P / PH second after the first 3,
`+0x140` >= 1; in every s* / H second after the first 3, `+0x140` = 0 and `+0x150` = the phase's speed.

## Predictions

Stock (S1, S2):
1. Pause state: in P phases `+0x54` >= 1 every second and day fires = 0.
2. Monthly trips stop: in P phases `FUN_100097b9` = 0, `FUN_10006fe3` = 0, route_trip = 0 (every caller),
   `FUN_1000755e` = 0, `FUN_10006edd` = 0. Layer `+0xb0` and `+0xb4` unchanged across each P phase.
3. Zone-development trips stop: `FUN_1000706a` = 0 in P phases; > 0 summed over the s* phases.
4. Running: route_trip > 0 summed over each s* phase at speeds 2, 3, 4 (speed 1's 120 s may hold no weekly group);
   day fires per second within 25% of nominal (1/8.571, 0.5, 1.5, and for speed 4 the 1000 ms poll gives <= 6.1).
5. Visible cars: STRTSIM `FUN_1001c750` = 0 in P phases (cars frozen); > 0 in s* phases.
6. Camera hold (H): `+0x144` >= 1 and `+0x54` >= 1 in >= 90% of the H seconds, day fires = 0, and the trip counters of
   prediction 2 and 3 = 0, i.e. the same as the user pause. In PH both counters >= 1 and the same zeros.

Full mods (F1):
7. Smoothing queue: route_trip calls on threads other than the sim and game threads (sc3perf workers) may be > 0 in
   the first seconds of a P phase when a weekly group was queued just before; in the last 30 s of every P phase
   route_trip = 0 on every thread (queue empty, nothing new enqueued while paused). sc3perf.log `TRAFFIC_SMOOTH>`
   lines in paused spans show the queue at 0.
8. H in F1: sc3simrun removes the scroll hold, so `+0x144` = 0, days keep firing and trips continue during H (not
   the same as the user pause there).

Anything not covered by a prediction (timer list contents, STRTSIM tick, what drives `FUN_1000706a`, rates per day) is
recorded and reported as found.
