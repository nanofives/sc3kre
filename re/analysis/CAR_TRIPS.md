# CAR_TRIPS.md - the visible cars, the simulated trips, and a plan for cars that drive real trips (task cartrips, 2026-10-15)

Owner goal: "Plan C: cars drive real trip paths." Every car on screen should be a simulated trip that appears at the
trip's origin and follows the router's route to its destination, without slowing the game. This phase decodes and
measures; nothing is implemented. Branch `child/cartrips`. Evidence: `verify/cartrips/PRE.md` -> `RESULTS.md`.

Addresses are Ghidra VAs; every DLL is based at 0x10000000, so each cites its module (STRTSIM unless named).
`[LINUX-HINT]` names come from the Loki demo's `libStrtSim.so` (`re/ghidra_export_linux_libstrtsim`, exported for this
task), whose code shape matches the Windows functions cited next to them.

**Verdict.**
1. **Why cars vanish**: in Berlin 90-95% of the cars that disappear on screen are deleted by the producer's density
   rule `FUN_1001eec4`: on a street quieter than the view's average, each step a car takes has a growing chance (1/40,
   2/40, ...) of deleting it, mid-street. Measured 41-59 visible deletions per minute at speeds 2-4 and ~35 per minute
   while paused (1.4). The other ways a car leaves (at the edge of a rect 2 cells beyond the view, at a failed
   placement, on camera moves) are almost never on screen.
2. **Cars have no destination**: the visible car count is `0.008 x` the view's summed congestion (max 200), cars are
   placed at random road cells weighted by congestion, and at every lane node pick the next edge at random weighted by
   the congestion of the cell it leads to (`FUN_1001c290`). Their only link to the trips is that congestion.
3. **The trips' paths are cheap to take**: route_trip pops its final path cell by cell, destination first, at one
   call site (`0x100072f8`) on whichever thread routes it. Berlin routes 0.7 / 1.6 / 6.6 / 24 trips per second through
   the view at speeds 1-4; a capture costs ~10 ns per node (+0.6% routing time).
4. **Router paths are not lane paths**: the router walks avenues as two cells and hops between parallel roads, so only
   42-48% of in-view segments can be driven cell for cell; 96-97% of the non-avenue in-view steps are drivable. A
   corridor lane-route solver is required (M2).
5. **Design**: a new `sc3cartrips.dll`: capture at `0x100072f8` into a per-thread buffer and a lock-free ring; on the
   game thread, keep the newest viewport trips, spawn one car per trip up to the stock count, drive it by answering
   SelectAnEdge from the solved lane route, never density-despawn it, end it at its destination or the view edge;
   freeze cars while paused. Milestones M1-M4 (4.5), owner decisions D1-D5 (4.6).

## 1. Car lifecycle

### 1.1 Who decides how many cars, and where

The street sim's layer (`SC3StrtSimLayer`, `DAT_10033208` = city `vt+0x164`) owns one car **producer**
(cSSVehicleProducer `[LINUX-HINT]`) at layer `+0x100`, interface vtable `0x1002d1d0`:

| producer field | meaning | evidence |
|---|---|---|
| `+0xc` | cars alive (this producer's) | `+= 1` in `FUN_1001f112`, `-= 1` in `FUN_1001f610` |
| `+0x10` | target count = `ftol(sum * 0.008)`, capped 200, `* 0.2` in emergency mode | `FUN_1001f556`: `sum`, `cells` from density layer `vt+0x64` over the rect; constants `0x1002d1c8` = 0.008, `0x1002d1cc` = 0.2 |
| `+0x20` | emergency mode (disaster) | `FUN_1001f3ab` |
| `+0x24..+0x30` | the **sim rect** x0, z0, x1, z1 (cells) | `FUN_1001f3ba` (SetSimRect) |
| `+0x34` | mean density byte of the rect, `sum / cells` | `FUN_1001f556` |
| `+0x35` | producing on/off | `FUN_1001f3d1` |

`[CONFIRMED @ 0x1001f556, 0x1001f3ba, 0x1001f3ab, 0x1001f610]`. The density is the SimTransit traffic layer
(`DAT_10033220` / `DAT_10033288`, `vt+0x60` per cell, `vt+0x64` over a rect, `kind` 3), the same congestion bytes the
trips deposit (NET_LANES 8). What triggers `FUN_1001f556` while the view does not move is not identified: its only
reference is a table entry (`FUN_100155a0`); measured, the target follows the traffic (S1: 77.6 at speed 1, 134.7 at
speed 2, same view) `[UNCERTAIN trigger]`.

**The sim rect is the view.** `FUN_10013e66` (ProcessViewChange) stores the view's cell bounding box at layer
`+0x27b0..+0x27bc` and that box grown by 2 cells (clamped to the map) at `+0x90..+0x9c` (`FUN_100120b7`);
`FUN_10015415` (UpdateVehicleView) copies `+0x90` into the vehicle sim rect `+0xb0..+0xbc` and the producer's rect
`[CONFIRMED @ 0x10013e66, 0x10015415]`. Cars exist only there; a city's other streets have none.

**Spawning, every animation tick.** The layer's animation tick `FUN_10012e46` calls the producer tick `FUN_1001f44a`:
when `alive < target`, it calls `FUN_1001ef25` `max(1, ftol((target - alive) * 0.1))` times (`0x1002d1e8` = 0.1)
`[CONFIRMED @ 0x10012e46, 0x1001f44a]`. `FUN_1001ef25` (PutAVehicleInRect) starts at a random cell of the rect and scans
it; at a road or avenue cell (`FUN_1001f018`: occupant `vt+0x48` & 0x8000 or 0x10000) with density byte `d` it places
one car when `random(max(mean, 1)) <= d` `[CONFIRMED @ 0x1001ef25]`. So cars appear in proportion to the cell's
traffic, at a random place, with no origin and no destination.

**The car object.** `FUN_1001f112` (PutVehiclesOnRoadTile): stops when `alive > target` or `alive >= 200`; `new(0x15c)`,
ctor `FUN_10019750`, `vt+0x13c` Init (`FUN_1001ace0`, vehicle attrib by resource key), `alive += 1`, `vt+0x140`
SetProducer, then PlaceOnTransitTile on the tile `[CONFIRMED @ 0x1001f112]`. When the placement fails the car is
released inside this same call. On a view change `FUN_1001f040` (PutVehiclesInRect) puts `ftol(d * 0.008)` cars
(plus one with the fraction's probability) on every road cell of the rect, up to the same caps
`[CONFIRMED @ 0x1001f040]`.

Car fields used here (vtable `0x1002cd20`; second and third vtables at `+0x18`, `+0x1c`):

| offset | meaning | evidence |
|---|---|---|
| `+0x0c`, `+0x14` | x, z position, 1/256 cell (cell = `>> 8`) | Tick `FUN_1001d2c0` toxic-cloud test |
| `+0x20` | initialised | `FUN_1001ace0` |
| `+0x22` | visible (Draw skips when 0) | `FUN_100199b0`, `FUN_10019a30` |
| `+0x2c` | the sim-rect test applies (1 for cars) | ctor, `FUN_1001c750` |
| `+0x2d` | class 0 car, 1 train, 2 subway (lane node class) | `FUN_1001c750`, `FUN_10020108` |
| `+0x44` | producer | `FUN_1001c9e0`, `FUN_1001b340` |
| `+0xc0 + 4i`, `+0xf4` | action stack (ids), top index | `FUN_1001d2c0`, `FUN_10019ab0` |
| `+0xf0`, `+0x48..` | action data stack (offset, records) | `FUN_1001b340`, `FUN_1001b280` |
| `+0xf8` | vehicle attrib (script key `+0x20`, sprite `+0x1c`) | `FUN_1001ace0` |
| `+0x118` | current lane path | `FUN_1001b340` |

There is **no destination field and no route**: the behaviour is a script. Placement pushes ExecuteScript (action 10,
`FUN_10019c70`) with the attrib's script; every car's script op `0x1001b320` calls MoveNStages(N, range, action)
`FUN_1001b280` (action 0 = `FUN_1001b340`, MoveNStagesUpdateFn) `[CONFIRMED @ 0x1001d060, 0x1001b320]`. Measured:
**N = 10000, range 0 for every car** (all MoveNStages calls in S1/S2), so a car's life never ends by its script in
practice.

### 1.2 One step of a car (`FUN_1001b340`, MoveNStagesUpdateFn)

Per stage (one lane path: an internal edge of a piece or the crossing into the next cell):
1. `counter += 1`; `counter >= N` -> pop, return 0 (script continues; at the end the car is removed).
2. Producer `vt+0x14` = `FUN_1001eec4` (**NeedVehicleDisappear**) with a per-car u16 at the stage record `+0x18`: reads
   the density byte `d` at the car's cell; `d < mean` (producer `+0x34`) -> `c += 1`, returns `random(40) < c`;
   otherwise `c = 0`, false `[CONFIRMED @ 0x1001eec4]`. True -> pop, return 1.
3. `FUN_1001c440` (SelectNextPath): `vt+0x158` = `FUN_1001c290` (**SelectAnEdge**) on the current edge's target node;
   none -> no path (`0x1001c48f`); an internal edge -> `FUN_10018630` builds the path; an exit edge ->
   `FUN_1001c750` (SelectPathFromConnectingNodeOnNextCell). No path -> pop, return 1.
4. Path entered (`vt+0x48`); blocked -> push WaitForPathClearance (action 9, `LAB_1001d4f0`) `[CONFIRMED @ 0x1001b340]`.

Status 1 aborts the script `[LINUX-HINT ExecuteScriptUpdateFn]` (Windows `FUN_10019c70` same shape), the stack empties,
and Tick `FUN_1001d2c0` calls AnimOccMan `vt+0x54(this)` = the car leaves the city; Shutdown `FUN_1001c9e0` calls the
producer's `vt+0x10` = `FUN_1001f610` (`alive -= 1`) `[CONFIRMED @ 0x1001d2c0, 0x1001c9e0]`.

`FUN_1001c750` returns 0 (no path) when the next cell `cell + EXIT_STEP[code >> 2]` is off the map
(`0x1001c794/0x1001c7a0`), is **outside the sim rect** (`FUN_10011e4e`, `0x1001c7bc`), has no occupant of the class
(`vt+0x7c`, `0x1001c7dc`), is not road/avenue (`LAB_1001ac90`, `0x1001c7fc`), has no QI or no lane graph
(`0x1001c812`, `0x1001c82d`), or `FUN_10020108` finds no node of the class in the position bucket (`0x1001c852`)
`[CONFIRMED @ 0x1001c750]`.

### 1.3 Every way a car is removed

| cause | where | visible to the player |
|---|---|---|
| **density despawn** | `FUN_1001eec4` true in `FUN_1001b340` | yes: anywhere in view, mid-road |
| next cell outside the sim rect | `FUN_1001c750` `0x1001c7bc` | rarely: 21 / 13 of 751 / 798 were still drawn (S1 / S2) |
| no lane node at the arrival position / not a road / no lane graph / off map | `FUN_1001c750` | yes when in view |
| no outgoing edge (dead end) | `FUN_1001c440` `0x1001c48f` | not seen in S1 / S2 |
| script end (N stages) | `FUN_1001b340` | N = 10000: not seen |
| strips leaving the rect on a camera move | `FUN_10015415` filter `+0x70`, AnimOccMan `vt+0x58` | no (outside the new view) |
| zoom below the birth zoom / produce off | `FUN_100146b2` (filter `+0x58`) | all cars at once |
| placement failed | inside `FUN_1001f112` | no (never drawn) |

### 1.4 Measured: why cars vanish (Berlin, stock DLLs, arms S1 and S2)

Stock Berlin, default camera (zoom 3, view cells x 66-94 / z 99-122, sim rect 64-96 / 97-124 = 33 x 28 cells), every
car removal recorded with its cause, cell, age and whether the car had been drawn by its Draw (`FUN_100199b0` /
`FUN_10019a30`) within the last 3 agent-loop passes (~14 ms at ~220 passes/s) before it was removed (PRE addendum 1). Two arms, same
schedule; S1 / S2 per phase (first 3 s of each phase dropped):

| phase | days/s | cars alive | removals/s | **visible removals/min** | of which density | not visible: sim-rect edge S1 / S2, placement failed S1 / S2 |
|---|---|---|---|---|---|---|
| speed 1 | 0.118 | 77.5 / 77.5 | 3.07 / 2.93 | **16.0 / 20.2** | 22 / 29 of 23 / 29 | 105 / 97, 106 / 93 |
| speed 2 | 0.494 | 135 / 144 | 4.09 / 4.41 | **59.3 / 52.3** | 77 / 68 of 85 / 75 | 168 / 197, 52 / 68 |
| speed 3 | 1.48 / 1.49 | 128 / 140 | 3.87 / 3.74 | **53.0 / 53.7** | 72 / 74 of 76 / 77 | 157 / 162, 50 / 49 |
| speed 4 | 5.44 / 5.45 | 119 / 133 | 3.62 / 3.53 | **41.2 / 50.2** | 52 / 68 of 59 / 72 | 156 / 147, 54 / 40 |
| user pause | 0 | 153 / 132 | 3.21 / 3.18 | **34.7 / 35.8** | 26 / 33 of 33 / 34 | 80 / 95, 34 / 22 |
| camera move (stock hold) | 0 | 180 / 154 | 0 / 0 | 0 / 0 | - | - |

Whole arms: 1,613 / 1,660 removals; **visible 311 / 338, of which the density despawn 281 / 320 (90% / 95%)**,
next cell outside the sim rect 21 / 13, no lane node at the arrival position 4 / 2, unattributed 5 / 3. Every density
removal had counter `c >= 1` (494 / 513, PRE prediction 3); every outside-rect removal was on the rect's edge (751 /
798, prediction 4). Failed placements (310 / 304) were never drawn.

**Answer to "cars disappear randomly":** almost every car the player sees vanish is the **density despawn**
(`FUN_1001eec4`): on a cell whose congestion byte is below the view's mean, each stage adds 1 to a per-car counter and
the car is deleted with probability counter / 40 (1/40, then 2/40, ... on consecutive quiet stages: after 8 quiet stages in a row 62% of
cars are gone, computed from the rule). It happens mid-street, in plain view, 41-59 times a minute in
Berlin at speeds 2-4 and ~35 a minute while paused (cars keep driving and despawning while paused, pausetrips). The
visible density removals sit on 80-83 distinct cells, concentrated on a few quieter streets of the view (top cells x
87-92, z 109-118, 8-14 removals each per arm). The car had driven a median 31 s and 12-13 cells. The other visible
causes are rare: a car reaching the sim rect's edge while still drawn (21 / 13 per arm; the rect is the view's cell
box grown by 2 cells), and no lane node where the car arrives in the next cell (4 / 2, the lane
mismatch NET_LANES 2.3 describes).

Unattributed removals (54 / 43 per arm, 3% of all, 5 / 3 visible) are old cars (median age 94 / 74 s). The one removal
path the probe did not mark is WaitForPathClearance (action 9) giving up: blocked behind another car for more than
40,000,000 heartbeat units it returns 1 and the car is removed `[CONFIRMED @ 0x1001d553]`; that these are such cars is
`[UNCERTAIN]` (not hooked).

**Count and churn.** The count tracks the producer target (`0.008 * sum` of the rect's density bytes): 78 at speed 1,
119-153 at speeds 2-4 and paused, never above 200. The count exceeded target + 1 in 3-20 seconds per running phase
(PRE prediction 1 not met as written): the target is re-derived downward while the cars already placed stay; the
`count > target` stop is only applied when placing. Cars live a median 25-27 s and 11 cells; ~3.5 are removed and
~3.5 placed per second at every speed (the animation runs in real time, pausetrips). During a camera move the cars
freeze (0 moves, 0 removals) and the view update re-places cars over the new rect; the count rose above target (180 /
154 against 140 / 109) and settled after.

## 2. How a car picks its way, and where a route could be injected

**Today.** `FUN_1001c290` (SelectAnEdge `[LINUX-HINT]`, car `vt+0x158`) takes a lane node and the car's cell, lists the
node's outgoing edges (`FUN_1001fdfd`, at most 6); 0 -> null, 1 -> that edge; for trains / subways (`+0x2d != 0`)
uniform random; for cars, each edge weighted by the density byte of the cell it leads to (the next cell for an exit
edge, the current cell for an internal edge; off-map -> 0), uniform when all are 0 `[CONFIRMED @ 0x1001c290]`. **A car
has no destination**; it follows traffic intensity one edge at a time.

**Injection points** (narrowest first):

| point | what it controls | covers | cost |
|---|---|---|---|
| **SelectAnEdge `FUN_1001c290`** (car `vt+0x158`) | which edge at every lane node; called from SelectNextPath (current node) and from `FUN_1001c750` (arrival node in the next cell) | every turn decision | one hook; route lookup per decision |
| NeedVehicleDisappear `FUN_1001eec4` (producer `vt+0x14`) | the density despawn | per stage | one hook (return false for route cars; true at the route's end) |
| `FUN_1001c750` | moving into the next cell (sim-rect test, arrival node) | per cell crossing | not needed for routing |
| a new action id (behaviour) in the update table `DAT_10033158` | the whole step | full control | the table is static data (17 ids); a new id needs the table extended in place |
| the car's position (`+0x0c/+0x14`) driven directly | everything | full control | re-implements path following, curves, speed, collision queue (`WaitForPathClearance`): large |

Recommendation: **SelectAnEdge + NeedVehicleDisappear**, plus a spawn routine. The stock step machine keeps moving the
car along the lane curves, with its speed, queues and animation; the mod only answers "which edge" and "not yet".

**Placing a car on a chosen lane.** PlaceOnTransitTile uses SelectPath(occupant) = a random node and internal edge
(`SelectANodeAndInternalEdge` `[LINUX-HINT]`); the second overload SelectPath(x, y, z) takes the node at a position
(`GetNode`) and builds the path from there `[LINUX-HINT cSSVehicle::SelectPath(int,int,int)]`. A route car can be
started on the lane that leaves its first cell toward the second one.

**From a router cell path to a lane path.** The router gives cells (one node per cell for roads, rect for stations),
types and entry sides (LANE_DENSITY 1). A car crosses a cell along one of the piece's TrBlkAtt lanes (NET_LANES 2), so a
step `a -> b -> c` is drivable when piece `b` has a lane from the side facing `a` to the side facing `c`.

Measured offline on the sampled final paths of S1 / S2 (`re/tools/ct_lanefeas.py`: piece and state under each router
cell from the Berlin save's network layer, turns from the piece's TrBlkAtt car lanes, `lanekit.lane_turns`):

| | S1 | S2 |
|---|---|---|
| complete sampled paths (<= 128 nodes) | 478 | 465 |
| road nodes with a network tile at (x, z) / at the transposed (z, x) | 27,068 of 27,068 / 10,497 | 24,561 of 24,561 / 10,320 |
| road steps drivable on the piece's lanes, whole path | 85.2% (22,080 of 25,925) | 85.6% |
| ... steps inside the view's sim rect | 79.1% | 78.2% |
| ... inside the rect, every undrivable step on avenue 11204 set aside as a corridor step (1,723 / 1,748; not checked) | **96.1%** of the rest | **96.8%** |
| in-view segments drivable end to end, literal / with the avenue corridor | 162 / 287 of 388 (42% / 74%) | 167 / 326 of 348 (48% / 94%) |

- Router cells and street-sim cells are the same coordinates (every road node sits on a network tile; the transposed
  pairing finds 39-42%). Cars enter cells that are on sampled trip paths too: 241 of 272 / 246 of 281 car-entered
  cells (89% / 88%), transposed 20 / 17 (PRE prediction 8).
- **Avenue 11204 is two parallel straight roads in the lane graph** (its records equal road 29's: one lane each way along
  the cell, no turn). The router walks an avenue as two cells and hops between them and turns off them where the lanes
  run straight: 81% of all undrivable steps (3,100 of 3,843 in S1). The rest: straight road 29 entered and left through
  adjacent sides (a hop to a parallel road, LANE_DENSITY 1), curve 11203 and T 39 used against their lanes, junction
  11214, 14030.
- So a car **cannot follow the router's cells literally** (42-48% of in-view segments). Outside avenues, 96-97% of the
  in-view steps are drivable as routed. Whether every avenue step can be driven through the paired avenue cell was not
  checked step by step: that is milestone M2's lane-route solver (section 4), which searches the lane graph inside the
  route's corridor (route cells plus their side neighbours) instead of matching cells one by one.

## 3. The trip side

### 3.1 Where the final path is

route_trip `FUN_100070d0` (SimTransit, thiscall on the traffic layer, `ret 0x1c`; args: start node, destination kind
0..3, budget base, deposit flag byte `[ebp+0x14]`, three mode flag bytes) keeps its DFS stack in a local deque at
`[ebp-0x80]`. Nodes are pushed going forward and popped on backtrack, so on arrival the deque holds exactly the final
path. The arrival node is pushed at `0x100072b6`, then the loop `0x100072d8..0x10007554` pops every node: back()
`FUN_10009e8e`, `rep movsd` of the 32-byte node into `*ebx` (`0x100072f3`), pop `FUN_10009eed` at **`0x100072f8`**,
the deposit switch on the node type (gated by the flag), the occupant Released (`0x10007551`)
`[CONFIRMED @ SimTransit 0x100072b6..0x10007554]`. Node: `+0` occupant, `+4/+8/+0xc/+0x10` cell rect x0 z0 x1 z1,
`+0x14` type, `+0x15` previous type, `+0x18` cost, `+0x1c` entry side (LANE_DENSITY 1).

- **Order: destination first, origin (type 0x80) last.** Every complete sample of S1 / S2 (478 / 465) ends at a 0x80
  node and starts at another type (PRE prediction 7; the 26 / 26 exceptions are paths over 128 nodes the probe
  truncated).
- **Mode is per node**: types 1 road, 2 highway, 3 ramp-road, 4 rail, 8 subway, 0x14 / 0x18 / 0x30 / 0x50 stations,
  0x41..0x43 bus, 0x80 the origin lot. Road-only trips (0x80, 1, 2, 3 only): 92-93% of arrived trips in Berlin.
- **Threads**: the stock game routes on the sim thread (S1 / S2: one thread). sc3perf `traffic_mt` routes the monthly
  building trips on its workers (shadow layers) and the trip-from-cell / other callers on the sim thread
  (PERFORMANCE Finding 24); the pop loop is unpatched by both sc3perf and sc3netmod.
- **Deposit flag**: 38-41% of arrived trips carry it (deposit congestion); the rest are routed without depositing. Which
  callers pass 0 is not decoded (the issuer packs the arguments through layer `vt+0x50` / `vt+0x4c`) `[UNCERTAIN]`.
- **Destination**: the arrival test `FUN_10008a94` stops on a road node with flag 0x400, a highway node with 0x800,
  rail 0x1000, subway 0x2000, else on a cell set in one of the kind grids `layer+0x84/+0x88/+0x8c` (kind 0..2, 3 = any)
  `[CONFIRMED @ SimTransit 0x10008a94]`; what each kind grid holds is `[UNCERTAIN]`.

### 3.2 Rates (Berlin stock, S1 / S2; viewport = the sim rect, 33 x 28 cells)

| speed | routed trips/s | arrived | with deposit flag | nodes / trip | nodes/s | **viewport trips/s** | ... with flag | ... road-only | in-view nodes / viewport trip | route ms / trip (probe incl.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 16.5 / 16.7 | 16.4 / 16.7 | 6.3 / 6.3 | 37.8 / 39.5 | 618 / 661 | **0.74 / 0.65** | 0.28 / 0.20 | 0.73 / 0.65 | 20.7 / 25.5 | 0.055 / 0.053 |
| 2 | 46.5 / 45.5 | 46.3 / 45.3 | 16.9 / 17.2 | 38.5 / 38.0 | 1,781 / 1,724 | **1.53 / 1.74** | 0.64 / 0.81 | 1.47 / 1.72 | 23.2 / 24.4 | 0.065 / 0.056 |
| 3 | 182 / 175 | 181 / 174 | 71.5 / 71.9 | 41.0 / 39.9 | 7,419 / 6,925 | **7.15 / 6.14** | 3.08 / 2.90 | 6.67 / 5.86 | 21.2 / 22.6 | 0.064 / 0.060 |
| 4 | 637 / 634 | 632 / 629 | 252 / 250 | 40.7 / 40.6 | 25,768 / 25,549 | **23.3 / 24.1** | 10.2 / 10.6 | 20.7 / 23.1 | 22.3 / 20.9 | 0.066 / 0.068 |
| paused | 0 | 0 | 0 | | 0 | **0** | 0 | 0 | | |

Path length (nodes) at speed 4, S1: < 4: 30%; 4-7: 3%; 8-15: 10%; 16-31: 12%; 32-63: 22%; 64-127: 17%; 128-255: 5%;
>= 256: 0.7%. Viewport trips are 3.7-4.5% of routed trips although the rect is 1.4% of the 256 x 256 map (the view is
the city centre).

**Europolis 1024 test city, full mod set (sc3perf 8 workers + smoothing), arm E2.** The city loads zoomed out (no
cars), so viewport trips were counted in a virtual 33 x 28 rect at the view's centre (cells 521-553 / 554-581, PRE
addendum 2). Routing ran on 9 threads (8 workers + the sim thread); the probe's per-node hooks slow the workers
(pausetrips saw the same with JS hooks), so the rates are a lower bound for an unhooked game.

| speed | routed trips/s | arrived | with flag | nodes / trip | nodes/s (all threads) | viewport trips/s | ... with flag | ... road-only | in-view nodes / viewport trip | routing ms per s (sum of threads) |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 5,175 | 4,849 | 638 | 134 | 651,880 | 35.1 | 4.0 | 5.2 | 38.9 | 6,110 |
| 4 | 7,644 | 6,744 | 2,853 | 85 | 572,294 | 11.3 | 7.2 | 4.2 | 24.7 | 5,792 |
| paused | 0 | 0 | 0 | | 0 | 0 | 0 | 0 | | 0 |

Road-only trips are 38-39% of arrived trips on this city (Berlin 92-93%), and the 128 complete in-view samples are
mostly subway nodes (4,898 of 6,047 nodes; road 933): at that view the viewport trips are subway trips under it. 792 of
920 samples were longer than the probe's 128 nodes. 0 faults; sc3perf's log: 1,527,410 trips routed in the background,
0 faults, the sim thread waited 64.8 s in 14 drains over the run (the probe slows the workers).

### 3.3 Handing a path to the game thread

Nothing in the current mods hands data to the game thread (sc3perf's rings go worker -> sim thread). The pattern to
copy is sc3perf's finished-trip ring (`g_sdone`, sc3perf.c `smooth_settle`), with the reader on the game thread
instead: the STRTSIM producer tick `FUN_1001f44a` runs on the game thread once per animation tick (from the layer tick
`FUN_10012e46`) and is where the stock game spawns cars, so it is where the mod drains the ring and spawns.

### 3.4 What to sample

Only trips with a node in the sim rect (the view's cell box + 2), road part only. Rates per Berlin view are above;
with ~60 s per car (risk 4) and the stock count (78-153 cars), every viewport trip can be shown at speed 1-2
(0.7-1.7 trips/s -> ~45-105 cars), about 1 in 3 at speed 3 and 1 in 10 at speed 4 (the newest trips win).

## 4. Design

### 4.1 Shape

```
 sim thread / sc3perf workers (SimTransit)              game thread (STRTSIM, each animation tick)
 route_trip pop loop 0x100072f8                          producer tick FUN_1001f44a (no random cars in "replace")
   our call -> per-thread trip buffer (x, z, type)          drain the ring -> trip queue (newest first, bounded)
   origin node (type 0x80) popped = trip done               while alive < target: take a trip, solve its lane route
   in view (any node in the sim rect)? 1 in K -> commit ->  in the corridor, spawn a car on the route's first lane
   lock-free ring (MPSC) ------------------------------->   SelectAnEdge FUN_1001c290 hook: route cars take the edge
                                                             toward the next route cell (stock choice for others)
                                                           NeedVehicleDisappear FUN_1001eec4 hook: false for route
                                                             cars until the route's last cell, true there
```

- **Capture** (any routing thread). Replace the 5-byte `call 0x10009eed` at SimTransit `0x100072f8` with a call to our
  stub, which reads the node copy in `ebx` (+4 x0, +8 z0, +0xc x1, +0x10 z1, +0x14 type), appends it to a
  thread-local buffer and jumps to `0x10009eed`. The trip is complete when the origin (type 0x80, always the last pop,
  PRE prediction 7) comes out. A trip with any node in the view's sim rect is committed (1 in K, K from the queue's
  fill) to a lock-free ring: one 32-bit write index, interlocked; entries are copies, nothing points into game memory
  (the occupant at `+0` is Released at the end of the same iteration). No other mod patches that site (sc3perf patches
  the route_trip prologue `0x7158` and the entries `0x6fe3/0x706a/0x6edd/0x6a72/0x9242`, sc3netmod `0x755e` and the
  call at `0x71eb`). sc3perf's workers run route_trip, so the stub runs on them too: the trip buffer is TLS, and the
  sim rect is four ints the game thread writes and the workers read (a stale rect for one trip is harmless).
  A Frida native listener on that call instruction faulted the game (PRE addendum 1); a plain `call` patch has no
  Frida relocation and is how the other mods patch SimTransit, but proving it is M1's first check.
- **Queue and sampling** (game thread). Drain the ring each animation tick into a queue of the newest viewport trips
  (bounded, e.g. 256; older ones dropped). The car count stays the stock formula (`min(200, 0.008 * sum)` of the rect's
  density, producer `+0x10`), so the street looks as busy as today, but every car is a trip.
- **Route** = the in-view part of the path in travel order, road / highway / ramp nodes only (types 1, 2, 3; a trip
  that changes to transit shows its road part). A **lane-route solver** turns it into lane nodes: a search over the
  TrBlkAtt graphs of the pieces in the route's corridor (route cells plus the side neighbour where the router hopped,
  section 2) from a lane entering the first cell to an exit toward the last one. The game keeps each piece's graph in
  memory (occupant QI `0x41658d28` -> `vt+0x54` -> `[+4]+0x28`, as `FUN_1001c750` reads it), so the solver needs no
  file access. Infeasible: skip the trip and take the next one (no car for a route it cannot drive).
- **Spawn**: the car is made the way `FUN_1001f112` makes one (`new(0x15c)`, `FUN_10019750`, Init `vt+0x13c` with a
  roster vehicle, `alive += 1`, SetProducer) and placed on the route's first lane with SelectPath(x, y, z) (the
  position overload) instead of a random node. Where: if the origin lot is in the view, at its first road cell (the car
  leaves home); otherwise at the route's first in-rect cell, the sim rect's edge.
- **Driving**: SelectAnEdge for a route car returns the outgoing edge the solved lane path takes (an exit edge whose
  `EXIT_STEP` cell is the next corridor cell, or the internal edge toward it). Curves, speed per edge, queues,
  WaitForPathClearance, animation and Draw stay the game's.
- **End**: at the route's last cell NeedVehicleDisappear returns true: the car arrives (inside the view it vanishes at
  the destination's road cell, where the trip ended). A route that leaves the view ends at the sim rect edge (the
  existing `FUN_1001c750` test; 21 / 13 of 751 / 798 such removals were still drawn in S1 / S2). The density despawn
  never fires for route cars.
- **Stock cars**: in "replace" mode the producer tick `FUN_1001f44a` and PutVehiclesInRect `FUN_1001f040` place no
  random cars; in "filler" mode they still place cars up to `target - route cars`, with their density despawn.
- **Pause and camera**: no trips are routed while paused (pausetrips), so the queue does not refill. Recommended:
  freeze the cars while the user pause (city `+0x140`) is set by skipping their Tick `FUN_1001d2c0` (the stock camera
  hold already freezes them). The alternative (route cars finish and are not replaced) empties the street in about a
  minute (cars take ~60 s to cross the view, risk 4).
- **Where**: a new DLL `sc3cartrips.dll` loaded by mods_launch, with an ini switch (off / replace / filler). It patches
  one SimTransit call site and hooks four STRTSIM functions, needs nothing from sc3netmod, and works with or without
  sc3perf. (A block inside sc3netmod is possible: its LANEDENSITY code already hooks the router and its ALT export is
  the in-game A/B tool; but cars are a separate feature the owner may want to switch alone.)

### 4.2 Runtime cost (from measurements)

| item | measured | cost |
|---|---|---|
| capture per router node | `verify/cartrips/capbench.c` (rect test + TLS append + 1-in-5 commit, cl /O2 x86): **10.0-10.5 ns per node** | Berlin speed 4: 25.5-25.8k nodes/s (S1 / S2) -> **0.26 ms per second**; per trip +0.4 us against 53-79 us of routing (`route_ms_per_trip`, probe included) = +0.6%. Europolis 1024 (E2): 572-652k nodes/s over 9 threads -> 6-7 ms per second of CPU summed over the threads, against 5,800-6,100 ms per second of routing (0.1%). |
| ring traffic | viewport trips/s (3.2) | Berlin speed 4: 24/s, 1 in K committed, one ~1.3 KB copy each |
| lane-route solver | not measured (M2) | one search per spawned car: 3.5-4.6 spawns/s in Berlin (S1 / S2) over ~21 corridor cells |
| driving | SelectAnEdge runs per lane node; all cars together make ~45 cell moves/s (S1 / S2) | a table lookup per call |
| animation | agent loop (all street agents) 60 ms per second at ~300 passes/s with no per-agent hooks (smoke B) | unchanged: same car count |

The capture is the only part that runs per trip; the rest runs per car on the game thread at rates stock already has.
Acceptance A2 bounds both in game.

### 4.3 Risks

1. **Lane routes**: outside avenues 3-4% of in-view steps have no lane as routed, and avenue steps are unverified
   (section 2). Such trips are skipped, so the shown sample leans toward drivable routes. Measured per city in M2.
2. **The native patch at `0x100072f8`**: Frida's listener there faulted the game; a plain `call` patch must be proven
   (M1, first check).
3. **Worker threads**: the stub runs on sc3perf workers (8 on the 1024 city): TLS and one interlocked index, no game
   call from the stub.
4. **Car count against trips**: at speed 1 Berlin routes 0.65-0.74 viewport trips/s; a car needs ~60 s to cross the
   view (21-25 in-view cells at 0.32-0.36 cells/s, S1 / S2), so the queue can keep ~45 cars against stock's 78.
   Replace mode shows fewer cars at speed 1 and on quiet views; filler mode keeps the count with random cars.
5. **Trips are instant, cars are slow**: a trip happens in one sim step; its car takes a minute of real time. The car
   shows a real route, not the trip's timing.
6. **Arrival is still a vanish**: a route ending in view ends with the car disappearing at its destination cell, for a
   reason the player can see (it arrived). Driving into the lot is a later option.
7. **Long paths**: 5.5% of Berlin trips at speed 4 have 128 nodes or more (3.2); the mod keeps only the in-view part, so it needs
   no path limit.

### 4.4 Acceptance tests (measurable with a probe like `ct_probe.py`)

- **A1 capture**: viewport trips captured per second within 5% of `ct_probe`'s count for the same city and speed
  (Berlin speed 3: 6.1-8.1/s); 0 faults in 30 minutes at speed 4 on the 1024 city with sc3perf workers.
- **A2 cost**: paired in-game A/B (the `ld_alt.py` pattern, patch switched on and off inside one game): route ms per
  trip within +2%; agent-loop ms per second within 10% at the same car count.
- **A3 fidelity**: for route cars, >= 95% of cell crossings go to the next route cell or its corridor neighbour, and
  each car covers >= 90% of its in-view route.
- **A4 no random vanishing**: visible removals of route cars that are neither at the route's end nor at the sim rect
  edge <= 2 per minute in Berlin's default view at speed 3 (stock today: 53 per minute, table 1.4).
- **A5 pause**: while user-paused, 0 car cell moves and 0 spawns; on resume the same cars continue.
- **A6 count**: alive cars <= 200 and within 10% of the stock target while the queue holds trips (replace mode).

### 4.5 Milestones

| milestone | delivers | needs from the owner |
|---|---|---|
| M1 trip tap | `sc3cartrips.dll`: capture stub, ring, game-thread queue, counters in its log (optional overlay of queued routes); no visible change. A1, and A2's routing half | nothing |
| M2 lane routes | the corridor lane-route solver in game, a per-city drivable-route report (Berlin, Europolis, the 1024 city), a debug overlay of solved lane paths; classifies the unflagged trips by caller (D5) | nothing |
| M3 route cars | spawn on the route, SelectAnEdge and NeedVehicleDisappear hooks, end at destination / rect edge, replace / filler switch. A3, A4, A6 | D1, D3, D4, D5; a hand test |
| M4 pause, polish, release | pause freeze (or the alternative), camera checks, A2 in full, A5, packaging into the release set | D2; hand test and release approval |

### 4.6 Decisions for the owner

- **D1 stock random cars**: replace all (every car is a trip; fewer cars at speed 1 and on quiet views) or keep them as
  filler (today's count; filler cars still drive at random and still despawn). Recommended: replace, filler as a
  switch.
- **D2 pause**: freeze the cars while paused (recommended; no trips happen) or let route cars finish and not replace
  them.
- **D3 how many cars**: the stock count formula (recommended; today's visual density) or one car per sampled viewport
  trip up to 200 (busier at speeds 3-4).
- **D4 mixed trips**: show the road part of trips that change to rail / subway / bus (recommended), or pure road trips
  only (92-93% of arrived trips in Berlin, 38-39% on the 1024 test city, 3.2).
- **D5 which trips**: all routed trips, or only those that deposit congestion (the flag, ~40% of routed trips). What the
  unflagged routed trips are is not decoded yet (3.2); recommended: decide after M2 classifies them by caller.

## 5. Open

- What triggers the target recompute `FUN_1001f556` while the view is still (its caller `FUN_100155a0` is only in a
  table); measured, the target follows traffic.
- The unattributed removals (3%): WaitForPathClearance's give-up `0x1001d553` is the one removal path not hooked.
- Which routed trips run without the deposit flag (60% in Berlin) and what the arrival kind grids `+0x84/+0x88/+0x8c`
  hold.
- Avenue steps: whether every sideways or turning step on 11204 can be driven through the paired cell (M2's solver).
- `FUN_004758e3` (the heartbeat's time source, STRTSIM 8) is still not decoded.
