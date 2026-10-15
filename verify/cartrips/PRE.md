# cartrips: PRE-REGISTRATION (2026-10-15, written before any game run)

Owner goal (2026-10-15): "Plan C: cars drive real trip paths." This phase only decodes and measures (no feature):
(1) how a visible car is created and removed, and why cars "disappear randomly"; (2) how a car picks its way; (3) where a
trip's final path is and at what rate trips cross the view; (4) a design and plan from those numbers.

## Known before this file (static, cited)

Addresses are STRTSIM.DLL unless named. Linux names are `[LINUX-HINT]` from the Loki demo `libStrtSim.so`
(`re/ghidra_export_linux_libstrtsim`, exported for this task) and match the Windows code shape cited.

- **Producer** (cSSVehicleProducer `[LINUX-HINT]`, layer `+0x100`, interface vtable `0x1002d1d0`):
  - `FUN_1001f556` (UpdateSimRect): target `+0x10` = `ftol(sum * 0.008)` (`0x1002d1c8`) where `sum`, `cells` come from
    density-layer `vt+0x64` over the sim rect `+0x24..+0x30`; capped at 200; times 0.2 (`0x1002d1cc`) when `+0x20`
    (emergency mode) is set; `+0x34` = `sum / cells` (the rect's mean density byte) `[CONFIRMED @ 0x1001f556]`.
  - `FUN_1001f44a` (Tick), called from the layer's animation tick `FUN_10012e46`: when `+0xc < +0x10`, calls
    `FUN_1001ef25` `max(1, ftol((target - count) * 0.1))` times (`0x1002d1e8` = 0.1) `[CONFIRMED @ 0x1001f44a]`.
  - `FUN_1001ef25` (PutAVehicleInRect): random start cell in the rect, scans cells; at a road/avenue cell
    (`FUN_1001f018`: occupant `vt+0x48` & 0x8000 or 0x10000) with density byte `d`, places one car when
    `random(max(avg,1)) <= d` `[CONFIRMED @ 0x1001ef25]`.
  - `FUN_1001f112` (PutVehiclesOnRoadTile): stops when `count > target` or `count >= 200`; `new(0x15c)` + ctor
    `FUN_10019750`, `vt+0x13c` Init, `+0xc += 1`, `vt+0x140` SetProducer, `PlaceOnTransitTile` `[CONFIRMED @ 0x1001f112]`.
  - `FUN_1001f040` (PutVehiclesInRect), from the view update `FUN_10015415`: every road cell of the rect gets
    `ftol(d * 0.008)` cars plus one with probability of the fraction `[CONFIRMED @ 0x1001f040]`.
  - `FUN_1001eec4` (NeedVehicleDisappear): density byte `d` at the car's cell; if `d < +0x34`: per-car counter `c += 1`,
    returns `random(40) < c`; else `c = 0`, false `[CONFIRMED @ 0x1001eec4]`.
  - `FUN_1001f610` (VehicleDisappears): `+0xc -= 1`, called from vehicle Shutdown `FUN_1001c9e0` `[CONFIRMED]`.
- **Car** (cSSVehicle, `0x15c` bytes, vtable `0x1002cd20`): `+0xc`/`+0x14` x/z position (cell = `>> 8`), `+0x2c` sim-rect
  check flag (1), `+0x2d` class (0 car), `+0x44` producer, `+0xf0` action-data stack offset, `+0xf4` action stack top,
  `+0xc0 + 4*i` action ids, `+0x118` current path, `+0xf8` vehicle attrib. Update-fn table `DAT_10033158`
  (`FUN_1001d060`): id 0 = `FUN_1001b340` MoveNStagesUpdateFn, 9 = `LAB_1001d4f0` WaitForPathClearance, 10 =
  `FUN_10019c70` ExecuteScript `[CONFIRMED @ 0x1001d060]`.
  - Placement pushes ExecuteScript (the vehicle attrib's script); the script's op `0x1001b320` calls `FUN_1001b280`
    MoveNStages(N, range, action) `[CONFIRMED @ 0x1001b320]`.
  - `FUN_1001b340`: per stage, `counter += 1`; `counter >= N` -> pop, return 0 (stages done); producer
    NeedVehicleDisappear true -> pop, return 1; `FUN_1001c440` (SelectNextPath) gives no path -> pop, return 1.
    Status 1 aborts the script `[LINUX-HINT ExecuteScriptUpdateFn]`, and an empty stack makes Tick `FUN_1001d2c0` call
    AnimOccMan `vt+0x54(this)` `[CONFIRMED @ 0x1001d2c0]`.
  - `FUN_1001c440`: `vt+0x158` = `FUN_1001c290` SelectAnEdge on the current edge's target node; null -> no path
    (`0x1001c48f`); internal edge -> `FUN_10018630`; exit edge -> `FUN_1001c750`.
  - `FUN_1001c750` fails (returns 0) when the next cell is off the map (`0x1001c794/0x1001c7a0`), outside the vehicle
    sim rect (`FUN_10011e4e`, layer `+0xb0..+0xbc`, only when car `+0x2c`), has no occupant of the class
    (`vt+0x7c`), is not a road/avenue (`LAB_1001ac90`), has no QI / no lane graph, or `FUN_10020108` finds no node
    of the class in the position bucket (NET_LANES 2.3) `[CONFIRMED @ 0x1001c750]`.
- **View**: `FUN_10013e66` (ProcessViewChange) sets the view cell rect `+0x27b0..+0x27bc` and `+0x90..+0x9c` = that rect
  grown by 2 cells; `FUN_10015415` (UpdateVehicleView): below the birth zoom (`+0x27c8 < DAT_10032710`) or `+0x27cc != 0`
  -> produce off and every car removed (`FUN_100146b2`); otherwise copies `+0x90` into the sim rect `+0xb0`, removes cars
  in the strips that left the rect (filter `+0x70`, AnimOccMan `vt+0x58`), and calls PutVehiclesInRect once per new
  strip `[CONFIRMED @ 0x10015415]`.
- **Trip side**: route_trip `FUN_100070d0`; final path popped destination first at the call `0x100072f8` with `ebx` =
  the node's 32-byte copy (+4 x0, +8 z0, +0xc x1, +0x10 z1, +0x14 type); deposit flag `[ebp+0x14]` `[CONFIRMED @
  SimTransit 0x100072b6..0x10007554]`. sc3perf workers run route_trip (traffic_mt), the pop loop is not patched.

## Setup

- Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips` (pausetrips' stock-DLL hard-link tree, reused as the
  task says). SHA-256 prefixes as in `verify/pausetrips/PRE.md`: SC3U.exe 49dd55e1, SimTransit b478ded4, STRTSIM c02ce38f.
- Instances in `<tree>\re\harness`, files copied from pausetrips' instances (same hashes):
  - `inst_ct_stock`: mods_launch 059ae8df + sc3resize 43cb5059 (P and speed keys). Stock routing, stock camera hold.
  - `inst_ct_full`: + sc3bigcity 76a83845, sc3overscroll a5b69ca3, sc3perf 0f47ac9d, sc3simrun 87b748d0, perf.ini
    2b9708f0 (traffic_mt=8, smooth=1), bigcity.ini 1eda071c.
- Cities: stock `Berlin, Germany.sc3` (99327775); `verify/perf1024/europolis1024_v2_test.sc3` (9ce07478).
- Probe `re/tools/ct_probe.py` (Frida, read-only), driver `re/tools/ct_run.py` (pt_run.py with this probe). Per second:
  - trip side (CModule, all threads): route_trip calls, arrived trips (pop loop ran), nodes, deposit-flag trips,
    road-only trips (node types 0x80/1/2/3 only), **viewport trips** (>= 1 node whose rect meets the vehicle sim rect),
    their in-rect node counts, node-type counts, path-length histograms, time inside route_trip; 1 viewport trip in 5
    per thread kept as a full path sample.
  - car side (JS): spawns (by caller), MoveNStages N / range, NeedVehicleDisappear calls / true (with counter),
    no-path events by reason, cell moves; every removal with cause, cell, age, cells moved, stages, N, and the last
    agent-loop number at which each of the 4 vehicle sprite accessors (`0x1001ab60/aa80/a950/aa10`, vtable at car
    `+0x1c`) ran for that car; agent loop SC3U `FUN_00425a10` calls and time; producer `+0xc/+0x10/+0x34/+0x35/+0x20`;
    view rect, sim rect, zoom.
- One game at a time, `mods_launch.exe -multi`, harness claimed by `cartrips`, the started PID killed at the end.

## Arms

| arm | instance | city | schedule (seconds) |
|---|---|---|---|
| smoke | stock | Berlin | `s3:40,P:20` (tooling only, not counted) |
| S1, S2 | stock | Berlin | `s1:90,s2:90,s3:90,s4:90,P:60,H:20,s3:60` |
| E | full (`--safe`) | Europolis 1024 | `s3:120,s4:120,P:60` |

First 3 s of each phase dropped. A second counts if the probe sent it and the game is alive.

**Visible removal** (definition, fixed now): a removal for which any of the 4 sprite accessors ran for that car within
the last 3 agent-loop passes. Which accessor(s) run per frame for on-screen cars is measured in the smoke run (accessor
calls per second against alive cars) and the rule is applied to whichever accessor(s) show that; if none of them is
per-frame, visibility is reported as UNKNOWN and only the cause and position of removals are reported.

## Predictions

1. Count: every second, producer `+0xc` <= `+0x10` + 1 and <= 200; `+0x10` = `min(200, ftol(0.008 * sum))` cannot be
   checked without `sum`, so only the bound is checked.
2. Every car removal reaches `FUN_1001f610`; each one's cause is one of: `density`, `nopath:<reason>`, `no-mark`
   (script end, including stages done), `view-update`, `produce-off`.
3. `density` removals have counter >= 1 (code: `random(40) < c`).
4. `nopath:next-cell-outside-sim-rect` removals are at cells on the sim rect's edge (x or z equal to a rect bound).
5. While user-paused (P), spawns and removals continue at a rate within 25% of the s3 phase (cars are real-time);
   route_trip calls are 0.
6. During H (stock camera hold), spawns and Tick removals are 0 (heartbeat suspended).
7. Trip paths: in every sampled trip the last popped node has type 0x80 (the origin) and the first does not.
8. Coordinates agree between the router and the street sim: at least 80% of the cells cars enter (cell moves inside the
   sim rect, per phase) are cells of a road or highway node (type 1 / 2) of some sampled or counted trip path of the same
   arm. Checked on the samples (1 in 5 viewport trips), so this is a lower bound.

Not predicted (measured only): the share of each removal cause, the share visible, rates of viewport trips per speed.

## Addendum 1 (2026-10-15, after the smoke runs, before arms S1 / S2 / E)

Smoke runs (Berlin, `inst_ct_stock`, files `smoke*.jsonl` in the instance folder) were tooling checks only. What they
showed and what changed:

- **Two of my probe versions killed the game** (both before any counted second): (1) CModule globals are read-only
  once linked, so the first write from a hook faulted; every mutable object is now allocated by JS and passed in as an
  `extern`. (2) A native (CModule) listener on the call instruction `0x100072f8` itself faults the game even with an
  empty callback (sim thread, SIMRCI `0x100312f8` after a trip-from-cell call, its saved `edi` garbage), while a JS
  listener at the same address runs. The final-path nodes are now taken at the **entry of the deque pop
  `FUN_10009eed`**, counted only when the return address is `0x100072fd` (the call from the final-path loop); `ebx`
  still holds the node copy there. Checked: 7,045 trips in 12 s at speed 4, the last popped node of every sample has
  type 0x80 and the trips' type mix matches the code (road 1 dominant).
- **Visibility accessor.** Of the four accessors registered, `0x1001a950` runs ~320 times per agent-loop pass (every
  agent, every tick) and the other three never ran, so none is a visibility signal. The Windows Draw pair was then found:
  `FUN_100199b0` (Draw at x, y; sprite attrib `vt+0x40`) and `FUN_10019a30` (Draw in a rect; `vt+0x3c`), both
  skipping when car `+0x22` (the visible byte) is 0, as Linux `cSSVehicle::Draw` does with `this[0x22]`. The probe
  now records accessors k = 0 `0x100199b0`, 1 `0x10019a30`, 2 `0x1001a950`, 3 `0x1001ae30`. Measured: k0 runs
  ~15-23k times per second with ~120 cars alive (~70 per agent pass). **Visible removal is applied to k0 or k1
  (Draw)**: drawn within the last 3 agent-loop passes, as registered; the distribution of passes since the last draw is
  reported too, and a 250-pass (~1 s) window as a secondary figure.
- **Every car's script is MoveNStages(10000, 0)** (all 1,000+ MoveNStages calls seen), so "stages done" is not a
  practical end of life; removals without a mark are mostly not lifetime.
- **Placement failures**: cars removed inside `FUN_1001f112` itself (backtrace through `0x1001609d` / `0x1001d618`),
  age 0, never drawn. The probe tags removals inside `FUN_1001f112` as cause `placement-failed` (added to prediction 2's
  list).
- **Cars spawned before the probe attached** get a record on first sight (`tracked = false`, no age); their marks are
  recorded. Removals with no mark and no context stay `no-mark`.
- The exception handler that logs a native fault ignores `system` exceptions (driver OutputDebugString noise).
