# cartrips3 (M3 route cars): PRE-REGISTRATION (2026-10-16, written before any game run of this milestone)

Owner decisions 2026-10-16 (orchestrator message): D1 route cars **replace** the stock random cars by default, stock
cars as filler behind the ini mode; D2 pause follows FREEZE; D3 car count = the stock formula; D4 road part of mixed
trips; D5 all building trips, zone probes excluded; D6 corridor 1 cell. Branch `child/cartrips2` (not merged).
Addresses are Ghidra VAs; STRTSIM unless named.

## Known before this file (static, cited)

- **Spawning a car** (`FUN_1001f112`): roster pick `FUN_1001ed36(producer, (z >> 5) * DAT_10033280 + (x >> 5), &inst)`
  (thiscall, ret 8; x, z from `occ->vt+0xbc(&x, &z)`), `new(0x15c)` (MSVCRT `??2@YAPAXI@Z`), ctor `FUN_10019750`,
  `vt+4` AddRef, `vt+0x13c` Init(`{0xc25c2bf7, 0x025c2c45, inst}`), producer `+0xc += 1`, `vt+0x140` SetProducer,
  PlaceOnTransitTile = `(car + 0x18)->vt+0x10(occ)`, `vt+8` Release `[CONFIRMED @ 0x1001f112]`.
- **PlaceOnTransitTile** is `FUN_1001bc70` (car's second vtable `0x1002ccb4` slot `+0x10`); it takes the first path from
  car `vt+0x154` = `FUN_1001c510` SelectPath(occupant), sets the position from the path, pushes it (`vt+0x160` =
  `FUN_1001b030`), registers the car and starts its script (action 10) `[CONFIRMED @ 0x1001bc70]` (Linux
  `cSSVehicle::PlaceOnTransitTile` / `SelectPath(cISC3Occupant *)` same shape `[LINUX-HINT]`).
- **`FUN_1001c510`** (the Windows place-at-position building block): QI `0x41658d28` -> piece, `holder = piece->vt+0x54()`,
  `occ->vt+0xbc(&x, &z)`, `rot = occ->vt+0xc0() - [[holder + 4] + r * 4 + 0x14]` with `r` from
  `occ->vt+0xa0()->vt+0x1c(&r)`, a random node and internal edge `FUN_1002034d(graph; &node, &edge, class)`, path =
  `FUN_10018630(holder, x, rot, z, edge)` (stdcall, `ret 0x14`; the same call the crossing makes at `0x1001c8f8`), piece Released
  `[CONFIRMED @ 0x1001c510]`. The Linux overload `SelectPath(int, int, int)` (node by position) has no separate slot
  here: a route car is placed by answering `vt+0x154` with the same steps and the solved path's internal edge.
- SelectAnEdge `FUN_1001c290` = car `vt+0x158`, thiscall `(node, x, z)`, `ret 0xc`; the crossing (`0x1001c878`) reads
  `[edge + 4]` of its result, so it must never get NULL. Producer vtable `0x1002d1d0`: `+0x10` VehicleDisappears
  `FUN_1001f610` (arg car + 0x18, `ret 4`), `+0x14` NeedVehicleDisappear `FUN_1001eec4` (car + 0x18, &counter; `ret 8`).
- Random cars come from the producer tick `FUN_1001f44a` (called at `0x10012e8a`, `ret 4`) and PutVehiclesInRect
  `FUN_1001f040` (called at `0x100154a0`, `0x10015573`, thiscall, `ret 4`).

## Build under test: `sc3cartrips.dll` **182db562** (`build_ct3`, source `sc3cartrips.c` + `_lanes.c` + `_cars.c`)

- `[cartrips] mode=off|capture|replace|filler`, **default replace**. replace / filler force the solver on.
- **Routes**: each drained trip (zone probes, return `0x100070B3` into `FUN_1000706a`, excluded) is solved (w = 1, as M2);
  a solved lane path joins a queue of the newest 64 routes. Trips not solved within the 4 ms tick budget wait for the
  next tick (`carried`); more than 256 waiting -> the oldest dropped (`dropped`).
- **Spawn** (producer tick, game thread): unless user-paused (city `+0x140`) or producing off, while `alive < target`
  (producer `+0xc`, `+0x10`: the stock formula, unchanged) up to `max(1, (target - alive) / 10)` per tick (the stock
  rate), take the newest route, start at its first internal lane edge (inside the producer's rect), make the car as
  `FUN_1001f112` does, and answer its `vt+0x154` with `FUN_10018630(...)` on that edge.
- **Driving**: car `vt+0x158` swapped: for a route car, the edge toward the next lane step (internal: the edge whose target
  is the next node; crossing: the exit edge whose arrival node, by `FUN_10020108`, is the next node); a car found off its
  path (`lost`) or at its last step (`ended`) gets the stock choice. Other cars: stock.
- **Despawn**: producer `vt+0x14` swapped: route cars get false (no density despawn) until `ended` or `lost`, then true.
  Producer `vt+0x10` swapped to count each route car's end: `arrived` (ended), `lost`, `other` (anything else; `edge` when
  its cell is on or outside the rect border).
- **Replace mode**: the producer tick call returns at once (no `FUN_1001f44a`) and both PutVehiclesInRect calls return at
  once. **Filler**: both run, after route cars took their share of the tick.
- Measurement only: `time_agents=1` wraps SC3U `FUN_00425a10` (the agent loop) to time it; `sc3cartrips_mode(1|2|3)`
  switches the mode at run time; `sc3cartrips_cars()` returns counters. Log `CARS>` every log_s.
- Tools: `ctm_modealt.py` (A/B), `pt_run.py` new token `Z:n` (n wheel notches at the view centre).

## Setup

Tree `Simcity_stock_pausetrips` (SC3U 49dd55e1, SimTransit b478ded4, STRTSIM c02ce38f).
- `inst_ct3_stock`: mods_launch 88452c54, sc3resize 43cb5059, **sc3simrun 7ba79a07** (FREEZE, owner-tested), sc3cartrips
  182db562.
- `inst_ct3_full`: inst_ct2_full's set (sc3bigcity 76a83845, sc3overscroll a5b69ca3, sc3perf 0f47ac9d with perf.ini
  2b9708f0 traffic_mt=8 + smoothing, sc3simrun 7ba79a07, sc3resize, bigcity.ini) + sc3cartrips 182db562.
- Cities: Berlin 99327775; Europolis 1024 `verify/perf1024/europolis1024_v2_test.sc3` 9ce07478 (loads at zoom 0, below
  the cars' birth zoom 2: the arms zoom in with `Z:2` before counting).
- Driver `ct_run.py` (CT_GROUPS as listed), harness claimed by `cartrips2`, one game at a time, own PIDs only. First 3 s
  of each phase dropped. Fault = a non-system exception from the probe's handler, or the game gone early.

## Arms

| arm | instance | city | cartrips.ini | probe | schedule |
|---|---|---|---|---|---|
| K3 (smoke, not counted) | stock | Berlin | replace, log_s=5 | none | `s3:60,s4:40,P:20` |
| R1 | stock | Berlin | replace | CT_GROUPS=rem,acc (removals with their Draw recency) | `s1:60,s2:60,s3:120,s4:120,P:40,s3:60` |
| R2 | full (`--safe`, settle 90) | Europolis 1024 | replace | none | `Z:2,s3:120,s4:120,P:30,s3:60` |
| FL | stock | Berlin | filler | none | `s3:120,s4:60` |
| L1 | stock | Berlin | replace | none | `s3:600,s4:1200` (30 min) |
| L2 | full (`--safe`, settle 90) | Europolis 1024 | replace | none | `Z:2,s3:900,s4:900` (30 min) |
| CA | stock | Berlin | replace, time_agents=1 | none; `ctm_modealt.py --window 45 --settle 30 --blocks 6` | `s3:1500` |

## Predictions

1. **Count (D3)**: in R1's speed 2-4 phases and R2's running phases, alive cars are within 10% of the producer target in
   >= 80% of the seconds with routes queued, and never above 200. Speed 1 measured only (0.7-1 viewport trips/s).
2. **Route share (D1)**: in replace mode, route cars / alive cars >= 99% in every second after the first 60 s of
   running (R1, R2, L1, L2). Filler (FL): alive within 10% of target in >= 80% of running seconds; route share reported.
3. **Corridor (A3)**: route-car lane decisions answered from the path (`followed` / `decisions`) >= 95%; cars ending
   `lost` <= 5% of route-car ends; steps covered / path steps over ended cars >= 90%.
4. **No density deletion (A4)**: NeedVehicleDisappear returns true for route cars only after `ended` / `lost` (by
   construction; checked: `need_true` <= ended + lost cars); route-car ends `other` that are not on the rect border
   <= 2 per minute at speed 3 in R1 (stock S1 / S2: 53 visible removals per minute, CAR_TRIPS 1.4).
5. **FREEZE pause (D2)**: in every P phase: 0 route-car decisions, 0 spawns, 0 ends, route-car count constant; in the
   phase after it, decisions resume and the route-car count at its start equals the count during the pause.
6. **Faults**: 0 in every arm, every game alive to the end; graph lookups `fault=0`.
7. **Cost (CA, inside one game, route vs stock cars)**: agent-loop ms per second, route / stock, pooled <= 1.10 (A2's
   10%) at car counts within 10% of each other; sc3cartrips' own game-thread time reported (no bound). Routing cost is
   unchanged by M3 (capture identical in both modes; M1's C1 / C2 stand).

Owner pictures: `MAIN\verify\cartrips3\owner_shots\` (screenshots / short GIF clips of route cars, captions.md), not
counted. Hand-test build staged in `MAIN\re\harness\handtest_cartrips\` when the arms pass.

## Addendum 1 (2026-10-16, after smokes K3, K3b, K3c; before every counted arm)

- K3 (182db562) faulted on every spawn (first-chance AV caught by the spawn's own handler, 153 events, cars never
  moved): `FUN_10018630` is **stdcall** (`ret 0x14`), not cdecl. Fixed. A fault during a spawn now unregisters the car.
- K3b: 0 faults, 158 route cars arrived, 0 lost, 0 other ends; but 441 of 741 placements failed (PlaceOnTransitTile's
  path test, the start lane taken). Change: up to 3 starts along the path, each in a later cell (`retry_ok`).
- `decisions` now counts only route-steered decisions (after `ended` / `lost`: `decisions_after_end`).
- K3c (build **33ef673e**): 0 faults, 272 placed (109 on a retry), 171 arrived, 0 lost, 0 other, 100% of path steps.
- **Build under test: 33ef673e** for every arm. Counted short arms use `log_s=1`; L1 / L2 `log_s=5`.
- R1's probe groups: `rem,acc,ag` (the removal records need the agent-loop count for "visible", as phase 1).
- Owner pictures: an extra arm **SH** (not counted): inst_ct3_stock, Berlin, replace, `s2:240`, screenshots and a short
  GIF taken with `sc3io.grab_to`.

## Addendum 2 (2026-10-16, after R1; before FL, L1, L2, CA and the new arm PZ)

R1 ran s1, s2, s3, s4 and P as registered; the driver then stopped (`could not set speed 3`: pt_run's
ensure_speed tried 3 times without waiting after the last key, the third key had worked). R1's last phase (s3 after the
pause) is missing, so prediction 5's resume half is measured in a new arm **PZ** (inst_ct3_stock, Berlin, replace,
`log_s=1`, CT_GROUPS=none, `s3:90,P:30,s3:60`). pt_run's ensure_speed now tries 8 times, 0.6 s apart. Nothing else
changes; R2 runs on the old driver (already started).
