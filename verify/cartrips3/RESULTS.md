# cartrips3 (M3 route cars): RESULTS (2026-10-16)

Pre-registration `PRE.md` (606400b; addenda 1 2f17198, 2 05a4829, 3 67dc629, each before the runs it covers). Build
under test `sc3cartrips.dll` 33ef673e. Raw data in `Simcity_stock_pausetrips\re\harness\inst_ct3_stock` and
`inst_ct3_full` (`<arm>.jsonl`, `<arm>_sc3cartrips.log`); per-arm summaries (`re/tools/ctm_m3summary.py`) in `data/`.
CARS> counters: `followed` = lane decisions answered from the car's path; ends `arrived` (path end), `lost` (car off its
path), `other` (anything else; `edge` when on the rect border).

## Answer for the owner

Every car on screen is now a real trip (replace mode, the default): it appears on the trip's road in view, drives the
route the trip took, and leaves where the trip ends or where the route leaves the view. In 30 minutes in Berlin
(L1) 5,372 route cars were placed and 5,232 reached the end of their route; none went off its route; 38 ended another
way. The density deletion that made 41-59 cars a minute vanish mid-street in stock never touches a route car; the cars
that still disappear on screen (13-18 a minute in R1) are cars arriving at their destination or leaving the view.
Pause freezes them with the rest of the street (FREEZE) and they continue on resume. At game speeds 1-2 there are not
enough trips crossing Berlin's view to fill the stock car count (speed 2: 28 cars against a target of 133); filler
mode (`mode=filler`) tops the street up with stock random cars.

## Per arm and phase

| arm, phase | s | cars (mean) / target | route cars | decisions from the path | ends: arrived / lost / other (on edge) | path steps covered | placed / tries (on a retry) |
|---|---|---|---|---|---|---|---|
| R1 Berlin speed 1 | 57 | 5.6 / 42.2 | 100% | 97.7% | 7 / 0 / 0 | 100% | 22 / 58 (9) |
| R1 speed 2 | 57 | 27.9 / 133.3 | 100% | 97.3% | 43 / 0 / 0 | 100% | 93 / 225 (43) |
| R1 speed 3 | 117 | 100.0 / 128.6 | 100% | 97.5% | 168 / 0 / 1 (0) | 98.2% | 232 / 593 (86) |
| R1 speed 4 | 118 | 141.4 / 142.6 | 100% | 96.5% | 265 / 0 / 6 (1) | 97.3% | 272 / 712 (89) |
| R1 paused | 38 | 122 / 125 (flat) | 100% | 0 decisions | 0 / 0 / 0 | | 0 / 0 |
| PZ speed 3 | 88 | 73.4 / 125.5 | 100% | 97.4% | 158 / 0 / 0 | 100% | 283 / 829 (138) |
| PZ paused | 27 | 125 / 141 (flat) | 100% | 0 decisions | 0 / 0 / 0 | | 0 / 0 |
| PZ speed 3 after | 57 | 127.0 / 141.6 | 100% | 97.6% | 163 / 0 / 0 | 100% | 135 / 313 (52) |
| R2b Europolis 1024 speed 3 | 118 | 6.3 / 6.3 | 100% | 97.6% | 17 / 0 / 0 | 100% | 30 / 50 (8) |
| R2b speed 4 | 116 | 12.9 / 12.6 | 100% | 96.8% | 50 / 0 / 0 | 100% | 47 / 59 (10) |
| R2b paused | 27 | 11 / 11 (flat) | 100% | 0 decisions | 0 / 0 / 0 | | 0 / 0 |
| R2b speed 3 after | 56 | 10.6 / 10.4 | 100% | 97.6% | 15 / 0 / 0 | 100% | 11 / 11 |
| FL Berlin filler speed 3 | 117 | 139.0 / 140.0 | 53.9% | 96.8% | 207 / 0 / 3 (0) | 99.0% | 304 / 708 (116) |
| FL speed 4 | 57 | 132.7 / 130.3 | 71.2% | 97.2% | 92 / 0 / 5 (0) | 95.5% | 83 / 156 (22) |
| L1 Berlin speed 3 (10 min) | 597 | 109.9 / 132.5 | 100% | 96.9% | 1,636 / 0 / 7 (0) | 99.5% | 1,729 / 4,712 (671) |
| L1 speed 4 (20 min) | 1,199 | 130.4 / 129.3 | 100% | 96.9% | 3,596 / 0 / 31 (0) | 99.3% | 3,643 / 8,906 (1,238) |

Visible car removals (R1, ct_probe Draw recency, PRE addendum 1 of cartrips): speed 3 25 in 117 s = **12.8 per minute**,
speed 4 35 in 118 s = 17.8 per minute (stock S1 / S2: 53 / 54 at speed 3, 41 / 50 at speed 4). 1,135 of R1's 1,407
removals were cars never drawn, 969 of them placements that failed inside PlaceOnTransitTile (start lane taken; tries
minus placed), as stock's failed placements are never drawn.

## Predictions

| # | prediction | result |
|---|---|---|
| 1 | alive within 10% of target in >= 80% of the queued seconds, speed 2-4 (R1, R2) | **not met at R1 speed 2 (0 of 1 queued second; 28 cars against 133) and speed 3 (65%)**; met at speed 4 (92%) and in R2b (88-95%). Also PZ 82% / 88%, L1 100% / 96%. Speed 2-3 in Berlin is supply-limited: 1.8 / 5.9 viewport trips per second (cartrips2 A1) and 2.5-3 placement tries per placed car. Never above 200 (max 141 mean). |
| 2 | route cars >= 99% of alive after 60 s (replace) | **met: 100% in every replace arm and second**. Filler (FL): count within 10% of target in 99% / 91% of seconds, route share 54% / 71%. |
| 3 | followed >= 95%, lost <= 5% of ends, steps covered >= 90% | **met**: followed 96.5-97.7% (the rest are the decisions at a path's last node, which take the stock edge before the car is removed), lost 0 in every arm, covered 95.5-100%. |
| 4 | NeedVehicleDisappear true only after ended / lost; other non-edge ends <= 2 per minute at speed 3 (R1) | **met**: need_true <= arrived in every phase; R1 speed 3 0.51 per minute (1 end). Speed 4: 2.55 per minute (R1), 1.55 (L1). |
| 5 | paused: 0 decisions, 0 spawns, 0 ends, count flat; resume continues the same cars | **met** in R1, PZ, R2b; PZ at the resume: 125 cars before, decisions restart within the second, the first new spawn ~3 s later. |
| 6 | 0 faults, alive to the end | met in R1, R2b, FL, PZ, L1 (L2, CA below). R2 (void) and the ZT zoom test: see addenda. |
| 7 | cost | below (CA) |

## Cost (CA: Berlin, speed 3, one game, sc3cartrips_mode switched route (2) / stock (1), ABBA, 45 s windows after 30 s)

19 of 24 windows ran (addendum 5); the 4 complete blocks:

| | route-car windows | stock-car windows | route / stock | per block |
|---|---|---|---|---|
| agent loop (SC3U `FUN_00425a10`) ms per second | 92.6 | 91.7 | **1.010** | 1.028 1.010 1.025 0.977 |
| ... per car | 0.781 | 0.808 | 0.967 | 0.977 0.936 1.007 0.954 |
| cars (mean) | 120.4 | 116.6 | 1.033 | |
| route cars (mean) | 94.9 | 25.1 | | |
| sc3cartrips game-thread time (spawn, solve, hooks), ms per second | 0.13 | 0.006 | | |

Prediction 7 (pooled <= 1.10 at car counts within 10%): **met** (1.010; counts 3.3% apart). The windows are mixed: a
route-car window still holds some stock cars and a stock window some route cars (30 s settle is shorter than a car's
life), so the figure bounds the difference rather than isolating it. Routing is not touched by M3 (cartrips2 C1 / C2).
0 faults in CA.

## Faults and incidents

0 faults reported by the probe's handler in K3b, K3c, R1, R2, R2b, FL, PZ, L1, CA, SH. K3 (182db562): 153 caught
first-chance faults, the stdcall mistake fixed in addendum 1. Startup deaths of the full mod set on the 1024 city:
ZT's first launch (~0.15 s) and L2b (~2.75 s), both before SimTransit / STRTSIM loaded, so before sc3cartrips arms
anything; L2 never started its schedule. L2c: below.

### L2c: Europolis 1024, sc3perf 8 workers + smoothing, replace, 30 minutes

| phase | s | cars / target | route cars | from the path | ends arrived / lost / other (edge) | covered | placed / tries |
|---|---|---|---|---|---|---|---|
| speed 3 | 892 | 11.1 / 10.7 | 100% | 97.1% | 304 / 0 / 0 | 100% | 311 / 475 |
| speed 4 | 897 | 13.4 / 13.5 | 100% | 96.2% | 469 / 0 / 10 (10) | 97.1% | 506 / 880 |

11,188,385 paths captured on 9 routing threads; **0 faults, game alive to the end**. Its end: the driver's kill
(`taskkill /F`) left PID 22740 alive for minutes; a second taskkill ended it (noted, not investigated).

Prediction 6 (0 faults in every counted arm, alive to the end): **met** in R1 (until its driver stopped, addendum 2),
R2b, FL, PZ, L1, L2c, CA. R2 / L2 / L2b: see addenda 3-5 (no counted phase ran; L2b a startup death before
sc3cartrips armed anything).
