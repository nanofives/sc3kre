# cartrips: RESULTS (2026-10-15)

Pre-registration: `PRE.md` (f7aeec3; addendum 1 7b7f884, addendum 2 d3a1dad, each committed before the runs it covers).
Findings and design: `re/analysis/CAR_TRIPS.md`. Raw per-second data stays in the stock tree
`C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_ct_stock\` (`S1.jsonl`, `S2.jsonl`, smoke
runs `smoke*.jsonl`) and `...\inst_ct_full\` (`E2.jsonl`, the stopped `E.jsonl`); per-arm summaries and the lane
checks are in `data/`. Tools: `re/tools/ct_probe.py`, `ct_run.py`, `ct_summary.py`, `ct_lanefeas.py`; benchmark
`capbench.c`.

## Answer for the owner

**Why cars disappear.** Almost every car you see vanish (90-95% in Berlin) is deleted on purpose by the street sim: when
a car drives on a street quieter than the average of the area on screen, every step it takes has a growing chance of
deleting it (1 in 40, then 2 in 40, and so on). That happens 41-59 times a minute in Berlin while the game runs and ~35
times a minute while paused. The cars are not trips: the game keeps a number of cars proportional to the traffic in
view (up to 200), puts them on random busy streets, and at each junction they pick a turn at random, leaning toward
busier streets. They have no origin and no destination.

**What a "real trip" car needs.** The trips' routes are easy to take from the game at almost no cost (about 10
nanoseconds per route cell), and Berlin sends 0.7 / 1.6 / 6.6 / 24 trips per second through the view at speeds 1 / 2 /
3 / 4. But a car cannot follow the router's cells literally: the router treats a two-cell avenue as two roads it hops
between, and only 42-48% of the on-screen parts of routes can be driven cell for cell. Outside avenues 96-97% of
steps are drivable, so the plan includes a route solver that keeps the car on the route's lanes (milestone M2).

## Table: Berlin, stock DLLs, arms S1 / S2 (per phase, first 3 s dropped)

| phase | cars alive | removals/s | visible removals/min | visible density removals | viewport trips/s | routed trips/s |
|---|---|---|---|---|---|---|
| speed 1 | 77.5 / 77.5 | 3.07 / 2.93 | 16.0 / 20.2 | 22 / 29 | 0.74 / 0.65 | 16.5 / 16.7 |
| speed 2 | 135 / 144 | 4.09 / 4.41 | 59.3 / 52.3 | 77 / 68 | 1.53 / 1.74 | 46.5 / 45.5 |
| speed 3 | 128 / 140 | 3.87 / 3.74 | 53.0 / 53.7 | 72 / 74 | 7.15 / 6.14 | 182 / 175 |
| speed 4 | 119 / 133 | 3.62 / 3.53 | 41.2 / 50.2 | 52 / 68 | 23.3 / 24.1 | 637 / 634 |
| user pause | 153 / 132 | 3.21 / 3.18 | 34.7 / 35.8 | 26 / 33 | 0 | 0 |
| camera move | 180 / 154 | 0 / 0 | 0 | 0 | 0 | 0 |
| speed 3 after the move | 126 / 120 | 2.98 / 3.96 | 36.8 / 54.6 | 32 / 48 | 7.40 / 8.07 | 179 / 181 |

Removals by cause, whole arm (S1 / S2): next cell outside the sim rect 751 / 798, density 494 / 513, placement failed
310 / 304, unattributed 54 / 43, no lane node at the arrival position 4 / 2. Visible: density 281 / 320, outside-rect
21 / 13, no arrival node 4 / 2, unattributed 5 / 3. Passes since the last Draw at removal (S1): never drawn 768, 0-3 311,
4-50 7, 51-250 8, more 519.

Arm E2 (Europolis 1024, full mods, virtual 33 x 28 view): CAR_TRIPS.md 3.2.

## Predictions (PRE.md)

| # | prediction | result |
|---|---|---|
| 1 | count <= target + 1 and <= 200 every second | **not met** as written: count above target + 1 in 0-20 seconds per phase (max in S1 speed 4: 20 of 86 s; camera move 16 / 13 of 17 s). The cap `count > target` is applied only when placing; when the target falls the cars already out stay. Never above 200. |
| 2 | every removal reaches `FUN_1001f610` with one of the listed causes | met: all 3,273 removals have a cause from the list (`no-mark` 97, see 1.4 of CAR_TRIPS) |
| 3 | density removals have counter >= 1 | met: 494 / 494, 513 / 513 |
| 4 | outside-rect removals on the rect's edge | met: 751 / 751, 798 / 798 |
| 5 | paused: spawns and removals within 25% of s3, route_trip 0 | met: spawns 3.21 vs 3.87 (-17%) / 3.18 vs 3.59 (-11%), removals 3.21 vs 3.87 / 3.18 vs 3.74; route_trip 0 |
| 6 | camera hold: spawns and Tick removals 0 | removals 0 met; Tick spawns 0 met; **2 / 1 spawns** came from the view update (`FUN_1001f040`, caller `0x1001f0ed`) re-placing cars over the moved rect, which the prediction did not allow |
| 7 | last popped node type 0x80, first not | met on every complete sample: 478 / 478, 465 / 465, E2 128 / 128 (truncated samples, over 128 nodes, excluded: 26, 26, 792) |
| 8 | >= 80% of car-entered cells on sampled path road nodes | met: 241 / 272 (89%), 246 / 281 (88%); transposed 20 and 17 |

Validity: 0 native faults in S1, S2, E2; every arm alive to the end of its schedule and killed by its PID.

## Deviations

- Smoke runs found two probe faults that killed the game before any counted second (CModule globals read-only; a
  Frida native listener on the call instruction `0x100072f8` faults even when empty). Fixed and registered in
  addendum 1 before S1, with the Draw accessor change and the `placement-failed` tag.
- Arm E loaded zoomed out (zoom 0, no cars, no sim rect) and was stopped by its PID after the settle period, before any
  counted phase; addendum 2 (virtual view rect) registered before E2. E and E2 used a 90 s settle (pt_run default 60;
  the settle is not in PRE).
- The probe hooks the sprite accessor `0x1001a950`, which runs for every agent every tick (~88k calls/s); the agent-loop
  time in S1 / S2 (81-131 ms per second) includes that hook. The unhooked figure is smoke B's 60 ms per second.
- Routing times include the probe's per-node hooks (CModule); on E2 they slow sc3perf's workers (sim thread waited
  64.8 s in drains over the run).

## Addendum 3: P1, freeze cars on pause (arm FZ)

sc3simrun with FREEZECARS (commit cfd618e, build `re/harness/build_ct/sc3simrun.dll` SHA-256 a6cac208), Berlin, schedule
`s3:60,P:60,s3:60,P:30,s3:30`. Data: `data/FZ_summary.json`, `data/FZ_sc3simrun.log`; raw `inst_ct_freeze\FZ.jsonl`.

| phase | cars alive | car cell moves/s | despawn tests/s | removals/s | spawns/s | visible removals/min |
|---|---|---|---|---|---|---|
| speed 3 | 129.8 | 54.7 | 58.4 | 5.55 | 7.88 | 66.4 |
| **pause 60 s** | **130 (flat)** | **0** | **0** | **0** | **0** | **0** |
| speed 3 | 134.6 | 51.0 | 54.4 | 3.96 | 4.05 | 64.2 |
| **pause 30 s** | **135 (flat)** | **0** | **0** | **0** | **0** | **0** |
| speed 3 | 133.9 | 45.5 | 48.1 | 3.00 | 2.78 | 44.4 |

Stock control, paused (S1 / S2): 44.1 / 41.2 moves/s, 3.21 / 3.18 removals/s, 34.7 / 35.8 visible removals per minute.

| # | prediction | result |
|---|---|---|
| F1 | paused: moves, despawn tests, removals, spawns 0; count constant | met, both pauses |
| F2 | running: moves within 30% of S1 / S2 speed 3 (46.0 / 44.6) | met: 54.7, 51.0, 45.5 (max +19%) |
| F3 | log armed=1; frozen ticks grow only while paused | met: armed=1; frozen 1,430 -> 2,771,080 over the 60 s pause, unchanged over the next run phase (2,773,915), -> 4,186,555 over the 30 s pause |
| F4 | 0 faults, game alive to the end | met |

The first run phase's higher spawns and placement failures are the probe attaching to a city whose cars were not yet
placed (count 0 -> 145 in its first seconds). One second of the agent-loop timer in the 60 s pause reads 429,557 ms
(an unmatched enter/leave in the probe's CModule timer); the other 59 read 51-70 ms. Not measured: trains, boats,
planes, people (not patched).

## Addendum 4: freeze all street animation on pause (arms FS street, FC cars)

sc3simrun FREEZE (commit 6c49a04, build SHA-256 408194e5): the agent loop's tick call at SC3U `0x00425a99` skips agents
of the frozen set while user-paused. Berlin, `s3:60,P:60,s3:60,P:30,s3:30`, first 3 s of each phase dropped. Agent
Tick calls per second by class (`ticks` probe group); census in `data/HB_enum_running.json`; logs
`data/FS_sc3simrun.log`, `data/FC_sc3simrun.log`; raw `inst_ct_freezes\FS.jsonl`, `inst_ct_freezec\FC.jsonl`.

**FS, `freeze_on_pause=street` (the new default):**

| phase | cars | trains | subway | people | boats | aircraft | other road | class 0x1002c19c | SIMSPR sprites | car moves/s | removals/s | spawns/s | agent-loop passes/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| speed 3 | 35,621 | 15,889 | 33,963 | 21,226 | 3,327 | 5,273 | 1,515 | 115 | 6,327 | 52.1 | 4.54 | 7.02 | 261 |
| **pause 60 s** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | 8,910 | **0** | **0** | **0** | 377 |
| speed 3 | 36,716 | 36,348 | 42,312 | 24,948 | 5,006 | 5,348 | 2,338 | 403 | 6,507 | 41.9 | 3.26 | 3.18 | 275 |
| **pause 30 s** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | 9,349 | **0** | **0** | **0** | 391 |
| speed 3 | 40,558 | 50,180 | 39,826 | 26,659 | 6,833 | 5,345 | 2,656 | 483 | 6,671 | 52.6 | 3.27 | 3.15 | 281 |

**FC, `freeze_on_pause=cars`:** paused, cars 0 Ticks, 0 moves, 0 removals, 0 spawns (count flat at 115 and 113); trains
37,711 / 47,845, subway 27,845 / 24,929, people 26,520 / 25,081, boats 9,251 / 9,564, aircraft 6,761 / 5,729 per
second, all still ticking.

| # | prediction | result |
|---|---|---|
| S1 | FS paused: every STRTSIM class 0; SIMSPR within 25% of s3; car moves, removals, spawns 0 | STRTSIM classes 0 (all nine, including `0x1002c19c`, which the census had not seen), car moves / removals / spawns 0: **met**. SIMSPR **not met as written**: +41% / +43% per second, because the agent loop ran 377-391 passes/s while paused against 261-281 running (frozen agents make a pass cheaper: 8-9 ms against 156-183 ms of loop time per second, probe included); per pass SIMSPR is unchanged (23.6-23.9 against 23.7-24.2 ticks). |
| S2 | FC paused: cars 0; trains, subway, people within 25% of the s3 phases | cars 0: met. Against the mean of FC's three s3 phases: subway +13% / +1%, people +13% / +7%, trains +4% / +32%. **Trains miss in the 30 s pause**: train ticks rise through the run in both arms (FS running 15.9k -> 36.3k -> 50.2k; FC 20.5k -> 39.6k -> 48.4k), not tied to the pause. |
| S3 | running: per-class rates and car moves within 30% of the first s3 phase | **not met for trains and boats** (the same rise through the run, both arms); car moves met in FS (41.9, 52.6 against 52.1), missed by 2 points in FC's last phase (33.9 against 49.9, -32%, with 98-107 cars against 115-145). 0 faults, both games alive to the end, `armed=1` in both logs: met. |

The frozen-tick counts also grew during the pause the game loads with (FS: 5.85 M of 6.39 M agent ticks before the
first unpause), so street animation now stays still from load until the first unpause, as it does in any later pause.
