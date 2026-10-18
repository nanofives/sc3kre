# pausetrips: RESULTS (2026-10-15)

Pre-registration: `PRE.md` (1b51925, addenda 1 2619d9b, 2 a22585c, 3 7e9d3e6, each committed before the runs it covers).
Raw data (per-second jsonl, per-phase summaries, backtraces) in the stock tree
`C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_pt_*\` (`S1`, `S2`, `X`, `F1`, `F2`
`.jsonl` / `_summary.json` / `_detail.txt`). The per-phase summaries and detail files (backtraces, caller and thread
buckets, timer lists) are copied to `data/` here; the per-second jsonl stay in the tree.

## Answer for the owner

**While the game is paused, no trips happen at all.** No building trips, no zone-development trips, no route
searches, no congestion added to the roads. Every trip in the game is started by the simulation calendar (a day,
a week or a month going by), and pausing stops the calendar. When you unpause, the calendar carries on from where it
was: the paused time is dropped, not caught up, so no burst of trips comes after a pause.

**What you still see moving while paused are the little cars and other street animation.** Those are not trips. They
are animations driven by real time, run by the screen (game) thread, and the pause button does not stop them: they
moved at the same rate paused as running (about 75 car moves per second in Berlin, the same at every speed).

**Scrolling the map is different.** In the stock game, moving the camera pauses the calendar too, so trips stop the
same way. It also freezes the cars while the camera moves. With our mods (sc3simrun) the calendar and the trips keep
running while you scroll (642 route searches per second at speed 4, the same as without scrolling), but the cars still
freeze until the camera stops, because the screen only animates them when the camera is still.

**With the full mod set, the pause behaves the same, with one difference:** trips that sc3perf had already queued when
you pressed pause are still routed by its worker threads during the pause, and then they stop. Nothing new is queued
while paused, because the calendar is stopped. In Berlin the queue is empty within a second, so you never see it. On the
1024 test city a pause that landed while a weekly batch was being queued saw the workers finish it in 2 to 4 seconds
of the pause (under the measuring tool, which slows them down), then nothing for the rest of the pause.

## Table: stock DLLs, Berlin, arms S1 + S2 (per second, first 3 s of each phase dropped)

| per second | speed 1 | speed 2 | speed 3 | speed 4 | **user pause** | camera hold | pause + hold |
|---|---|---|---|---|---|---|---|
| seconds measured | 232 | 172 | 286 | 226 | **803** | 112 | 83 |
| game days | 0.121 | 0.500 | 1.46 | 4.86 | **0** | 0 | 0 |
| monthly issuer `FUN_100097b9` (per-building calls) | 196 | 923 | 2,384 | 7,861 | **0** | 0 | 0 |
| building trips `FUN_10006fe3` | 16.2 | 43.0 | 135 | 456 | **0** | 0 | 0 |
| zone-development trips `FUN_1000706a` | 3.58 | 11.1 | 35.9 | 115 | **0** | 0 | 0 |
| route searches `FUN_100070d0` (all callers) | 19.8 | 54.0 | 171 | 571 | **0** | 0 | 0 |
| ... arrived | 19.8 | 53.5 | 170 | 566 | **0** | 0 | 0 |
| ... failed | 0.065 | 0.50 | 1.26 | 4.64 | **0** | 0 | 0 |
| router steps `FUN_1000755e` | 1,897 | 4,784 | 16,730 | 53,560 | **0** | 0 | 0 |
| congestion deposits `FUN_10006edd` | 381 | 972 | 3,100 | 9,998 | **0** | 0 | 0 |
| visible car moves STRTSIM `FUN_1001c750` | 75.5 | 71.5 | 76.6 | 82.7 | **75.1** | **0** | 0 |

Per game day the trip rates do not depend on the speed (speeds 2-4: 108-117 route searches, 22-25 zone-development
trips per day; speed 1's 14 days hold too few weekly groups to compare). The other trip callers named in the task
showed up as: SIMADV/SIMMISC trips (62 per arm, monthly), and none from SIMECO+0x423c or SC3U.exe `FUN_004bfe89` in
Berlin in these runs. Layer counters `+0xb0` / `+0xb4` were unchanged across every pause phase.

S1 and S2 agree phase by phase (e.g. speed 4, 90 s: 48,679 vs 49,126 route searches; every pause and hold phase 0 in
both).

## Predictions (PRE.md)

| # | prediction | result |
|---|---|---|
| 1 | P: clock `+0x54` >= 1, day fires 0 | met: `+0x54` >= 1 in 803 / 803 seconds, 0 days |
| 2 | P: issuer, trip function, route_trip, steps, deposits 0; `+0xb0/+0xb4` unchanged | met, both arms |
| 3 | P: `FUN_1000706a` 0; > 0 running | met (0 vs 3.6-115 per s) |
| 4 | running: route_trip > 0 at speeds 2-4; days within 25% of nominal | met: route_trip > 0 at all four speeds; days/s 0.121, 0.500, 1.46, 4.86 vs 0.117, 0.5, 1.5, <= 6.1 (speed 4: 80% of the 6.1 ceiling) |
| 5 | P: STRTSIM `FUN_1001c750` = 0 (cars frozen) | **not met**: 75.1 / s paused, same as running |
| 6 | H: `+0x144` and `+0x54` >= 1 in >= 90% of seconds, days 0, trip counters 0; PH same | met: 112 / 112 and 83 / 83 seconds held, all trip counters 0 |
| 9 | X: vehicle update `FUN_1001d2c0` in P within 25% of s3, its time argument likewise | met: 69,272 vs 65,775 calls / s (+5%), argument sum +13% |
| 10 | X: H / PH vehicle update 0; one `vt+0x1c(1)` / `(0)` per hold; take caller SIMSPR 0x1004402e | met (1 take, 1 `(1)`, 1 `(0)` per hold, caller SIMSPR 0x1004402e) |
| 7 | F2: workers route queued trips in paused seconds (days 0), issuing thread 0, then 0 before the phase ends | met (F1 undecidable, see F1). F2 PW#8: workers 1,856 searches in paused seconds 1-4, 0 in seconds 5-60; PW#12: 2 s then 0; issuing thread 0 after the first second |
| 8 | F1 H: `+0x144` = 0, days and trips continue | met |

Validity: every arm alive at the end, every counted second passed the PRE rule (0 bad seconds in S1, S2, X, F1, F2).

## What drives what (newly decoded)

All `[CONFIRMED @ ...]` are SIMCITY.DLL unless named.

**The sim thread is a command queue run by the clock.** SIMCITY `FUN_1000d036` starts it (`_beginthreadex`); every
trip in the backtraces sits under its command switch `FUN_10001675`:

| command | runs phase lists (`FUN_10001914(this, n)` runs lists n..0) | posted by | trips seen there |
|---|---|---|---|
| 3, 4 | 0 / 1..0 | clock kinds 1 / 2, registered by `FUN_10001bec` when the first simulator joins list 0 / 1 | |
| 5 | 2..0 | clock kind 3 = **every day** (`FUN_100017e2`) | zone development: `FUN_1000706a` from SIMRCI `0x1001aa6c` (ret `0x100016a9`) |
| 6 | 3..0 | clock kind 4 = **first day of a week** | building trips: SimTransit `FUN_100097b9` -> `FUN_10006fe3` (ret `0x100016bb`) |
| 7 | 4..0, inside city `vt+0x22c` / `vt+0x230` | clock kind 5 = **first day of a month** | SIMADV `0x100062d2` -> SIMMISC -> `FUN_10006fe3` (ret `0x100016d8`) |
| 8 | 5..0 | clock kind 6 = **first day of a year** | |

`[CONFIRMED @ 0x10001675 (call sites 0x10001696/a4/b6/d3/f6), 0x100017e2, 0x10001bec, 0x10001914]`. Clock kinds:
the clock's register `vt+0x3c` = `FUN_1000a641` puts kind 1..6 on lists `+4/+8/+0xc/+0x10/+0x14/+0x18`; the day fire
`FUN_1000aa4d` runs `+0xc` every day, `+0x10` when `FUN_100096f0` (day of week) = 1, `+0x14` when `FUN_100095ce`
(day of month) = 1, `+0x18` when `FUN_100095af` (day of year) = 1 `[CONFIRMED @ 0x1000a641, 0x1000aa4d]`. City
`vt+0x200` = `FUN_10005a70` returns city `+0x130`, the clock `[CONFIRMED @ 0x10005a70]`.

So the building trips are issued once a week (each building's own week of the month, `day/7 == this+0x10` in
`FUN_100097b9`), zone development (and its trips from a cell) once a day, and SIMADV's trips once a month.

**`+0x148` is the month-pass bracket.** City `vt+0x22c` = `FUN_100059cf` (clock Pause, `+0x148 += 1`) and `vt+0x230`
wrap command 7 `[CONFIRMED @ 0x100016c9, 0x100016ea, 0x100059cf]`. This answers the `[UNCERTAIN]` "who drives +0x148"
in SIM_WHILE_SCROLLING.md.

**The clock does nothing while paused, and drops the paused time.** Its 1000 ms callback `LAB_1000a854` tests
`+0x54` first and skips the minute, hour and day fires when it is non-zero (`cmp [esi+0x54],0; jne` at `0x1000a885`).
Pause `FUN_1000a0ec` banks the time since the last poll into `+0x5c` when the count goes 0 -> 1; Resume `FUN_1000a145`
sets `+0x58 = timeGetTime()` when it goes back to 0 `[CONFIRMED @ 0x1000a885, 0x1000a0ec, 0x1000a145]`. So after a
pause the partial day already accumulated is kept and the paused span is not replayed. The clock thread's timer list
holds one entry (the 1000 ms callback `FUN_1000c0a5`, read live in every arm).

**The cars are a real-time animation, not trips.** Chain from the backtraces (game thread):
SIMSPR view tick `FUN_10042a95` (ret `0x10042b07`) -> SIMSPR `0x1001cb09` -> SC3U.exe `FUN_00426140` -> SC3U.exe
`FUN_00425a10` -> each agent's `vt+0x100` -> STRTSIM `FUN_1001d2c0` (per-vehicle update) -> `vt+0x14c` =
`FUN_10019ab0` -> `FUN_1001b340` -> `FUN_1001c440` -> `FUN_1001c750` (next cell).
- SC3U.exe `FUN_00426140` is the heartbeat: on every call it stores `FUN_004758e3(this+0xbc)` into `+0x9c`, and only
  when its suspend count `+0xb0` is 0 calls every listener on list `+0x88` with the difference from the previous
  value (capped at 250000), plus listeners on further lists selected by a per-call mask
  `[CONFIRMED @ SC3U 0x00426140]`. What `FUN_004758e3` reads is not decoded (`[UNCERTAIN]`); measured, the summed
  argument the vehicles receive per second is the same paused and running (X: +13% paused vs speed 3), so it follows
  real time, not game time.
- STRTSIM `FUN_1001d2c0` adds that time to the vehicle's `+0x30`, steps its animation frame against `+0x34`, and runs
  its behaviour `vt+0x14c` until it reports done `[CONFIRMED @ STRTSIM 0x1001d2c0]`. It reads no city pause counter
  or clock field directly. This is the STRTSIM tick STRTSIM.md section 7 left open.
- The user pause (`FUN_100056bb`: clock Pause, `+0x140 += 1`, posts `0xc2a35d7f`) does not touch the heartbeat.
- The camera hold (`FUN_100058ac`: clock Pause, `+0x144 += 1`) also calls `FUN_1000ee96()->vt+0x1c(1)`, and that
  object is the heartbeat's: live it resolved to SC3U.exe vtable `0x4d1030`, slot `0x1c` = `FUN_004263d0`, which is
  `+0xb0 += 1` (arg 1) / `-= 1` (arg 0) `[CONFIRMED @ SIMCITY 0x100058ac, 0x1000590e; SC3U 0x004263d0]`. So in stock a
  camera move suspends every listener of the heartbeat; `+0x9c` keeps updating while held, so nothing jumps afterwards.
- That suspension is not the only reason the cars stop while the camera moves. The heartbeat is reached from the
  SIMSPR view tick `FUN_10042a95` through `[view+0xb4]->vt+0x20` at `0x10042b04` (the `0x10042b07` frame), which runs
  only when the camera-busy bytes `+0x1dd..+0x1e2` are all 0; otherwise the tick calls the scroll step `FUN_10043daf`
  at `0x10042ad7` and nothing else `[CONFIRMED @ SIMSPR 0x10042ad5..0x10042b04]`. Measured in F1 (sc3simrun removes
  the hold: no take, no `vt+0x1c(1)`, `+0x144` = 0 all phase): vehicle updates 0 during the camera move, while days
  (5.7 per s) and trips kept running.

**How the harness pauses without focus:** a posted `P` key, handled by sc3resize PAUSEKEY in its window procedure,
which posts `0xc2a35d7e` (pause) or `0xc2a35d80` (resume one level); speed keys 1-4 post `0xc2684065`. KEYFOCUS lets
them through because the city view (not a text field) has the in-game focus. Measured: `+0x140` 0 -> 1 -> 0 and
`+0x150` = the key's speed in every phase.

## F1: full mod set (Berlin; sc3perf traffic_mt=8 + traffic_mt_smooth=1, sc3simrun, sc3resize, sc3bigcity, sc3overscroll)

Probe in `--safe` mode (sc3perf's patched entries `0x10006fe3`, `0x1000706a`, `0x10006edd`, `0x10009242` not hooked, so
those columns are absent; route_trip carries the trips).

| per second | speed 1 | speed 2 | speed 3 | speed 4 | **user pause** | camera move (H) | pause + camera |
|---|---|---|---|---|---|---|---|
| seconds measured | 117 | 87 | 144 | 114 | **405** | 57 | 42 |
| city `+0x144` held / clock paused (seconds) | 0 / 0 | 0 / 1 | 0 / 3 | 0 / 13 | **0 / 405** | **0 / 4** | 0 / 42 |
| game days | 0.111 | 0.494 | 1.47 | 5.52 | **0** | **5.67** | 0 |
| monthly issuer `FUN_100097b9` | 193 | 777 | 2,354 | 8,936 | **0** | 9,296 | 0 |
| route searches (all threads) | 19.4 | 47.3 | 172 | 637 | **0** | 643 | 0 |
| ... failed | 0.085 | 0.47 | 1.63 | 6.47 | **0** | 7.05 | 0 |
| router steps | 2,051 | 4,761 | 18,780 | 77,500 | **0** | 85,050 | 0 |
| visible car moves STRTSIM `FUN_1001c750` | 70.1 | 72.8 | 78.2 | 70.0 | **75.2** | **0** | 0 |

Speed 4 runs 5.5 days per second here (stock 4.9) because sc3perf `clock_ms=50` polls the clock 20 times a second.

Prediction 8 (H in F1: `+0x144` = 0, days and trips continue): met (0 of 57 seconds held, 323 days, 36,625 route
searches). Prediction 7 (smoothing queue drains during a pause): not decidable on F1. Each pause landed in the same
second as the tail of a small weekly group (at most 569 searches in that second, on the 8 workers and the sim thread),
and from the next second on every thread read 0. sc3perf.log `TRAFFIC_SMOOTH>` lines read queue 0 at every 60 s sample,
0 faults, 5 drains in 18 minutes. Moved to F2 (addendum 3).

The second in which a pause lands can still carry trips in every arm, stock included (S2: 845 route searches in the
first second of a PH phase, then 0): a day or week pass that has already started on the sim thread runs to its end; the
pause stops the next one from starting.

## F2: full mod set, Europolis 1024 test city, pause on a weekly group

City `MAINerify\perf1024\europolis1024_v2_test.sc3` (9ce07478), `inst_pt_full`, `--safe` probe, schedule
`s3:60,PW:60,s3:60,PW:60,s3:60,PW:60` (PW = run until a second with `FUN_100097b9` calls, then P). Issuing thread
(the one calling `FUN_100097b9`) = tid 11168; the other 8 threads routing trips are the sc3perf workers.

| PW phase (60 s, all paused: `+0x140` = 1, 0 day fires every second) | worker route searches | seconds with worker searches | issuing-thread searches |
|---|---|---|---|
| #4 | 37,253 | 60 of 60 (queue still not empty at the end) | 0 |
| #8 | 1,856 | 4 (then 0 for 56 s) | 25, all in second 1 |
| #12 | 1,859 | 2 (then 0 for 58 s) | 10, all in second 1 |

In #8 and #12 the pause landed while the weekly group was still being issued (2,967 / 2,603 issuer calls in the pause's
first second): the week pass already running on the sim thread finished, its last trips went into the queue, and the
workers emptied it while the game stayed paused. This matches the code: the workers loop on `smooth_work` +
`WaitForSingleObject(evt, 2)` and never look at the clock (sc3perf.c `mt_worker`).

Measurement artifact, reported not corrected (addendum 3): Frida's JS hook on route_trip serialises the 8 workers to
~500-1,500 searches per second (Finding 21 measured ~27k/s unhooked). So the queue grew to 302,221 (sc3perf.log), and
the sim thread waited 472 s and then 181 s more in sc3perf's month-end drain (`TRAFFIC_SMOOTH> ... sim thread waited
652585 ms`) with the clock held by the month bracket `+0x148` (bracket 2, clock pause 2 in the readouts). That is why
phase #4 never emptied and the s3 phase after it ran 0 days. Without the probe a 1024 weekly group takes a few seconds
on 8 workers (Finding 21/24); the drain-during-pause behaviour is the same, only shorter. 0 faults.

## Deviations

- Smoke run before the arms (PRE addendum 1), tooling only.
- Prediction 5 was wrong; addendum 2 added the vehicle-update / heartbeat hooks and arm X to explain it, before F1.
- `pt_summary.py` first merged repeated phase labels; fixed to group phases in run order before any table here.
- F1 could not decide prediction 7; addendum 3 registered F2 before it ran. The probe also records the issuing thread
  of `FUN_100097b9` from F2 on (commit after addendum 3, before the F2 launch).
- F2's `sw>` seconds (keys being posted, waiting for the issuer) ran up to 180 s because the probe-slowed queue stalled
  the sim; those seconds are not counted, as registered.
- Thread labels: the probe's `sim_tid` is the thread that fires days (the clock timer thread), not the sim command
  thread that runs the trips; tables use thread ids from the backtraces instead.
