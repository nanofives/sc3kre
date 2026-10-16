# cartrips2: RESULTS (2026-10-15)

Pre-registration `PRE.md` (119c695; addendum 1 08464a5, addendum 2 52cce78, each committed before the runs it covers).
Raw data stays in the instance folders (`Simcity_stock_pausetrips\re\harness\inst_ct2_stock`, `inst_ct2_full`,
`Simcity_stock_roundabout4\re\harness\inst_ct2_rbt`): `<arm>.jsonl`, `<arm>_sc3cartrips.log`, dumps
`<arm>_cartrips_{trips,graphs,routes}.bin`; summaries copied to `data/`. Tools: `re/tools/ctm_read.py`,
`ctm_summary.py`, `ctm_lanes.py`, `ctm_alt.py`; queue `tools/ct2_queue.sh`.

## M1: trip tap

### A1 (Berlin, stock threading, c392ccbc + ct_probe trip counters in the same game)

| phase | paths/s | nodes/s | viewport paths/s | ... flagged | ... road-only | flagged paths/s | road-only / mixed / transit-only paths/s | drops |
|---|---|---|---|---|---|---|---|---|
| speed 1 | 27.4 | 1,022 | 0.96 | 0.51 | 0.92 | 11.6 | 25.8 / 0.69 / 0.90 | 0 |
| speed 2 | 56.9 | 2,289 | 1.80 | 0.88 | 1.70 | 24.5 | 52.8 / 1.98 / 2.11 | 0 |
| speed 3 | 171.4 | 6,885 | 5.89 | 3.12 | 5.78 | 69.3 | 158.4 / 5.76 / 7.24 | 0 |
| speed 4 | 623.6 | 26,283 | 22.98 | 10.58 | 21.65 | 249.3 | 578.2 / 20.1 / 25.4 | 0 |
| paused | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Routing threads seen: 2 (the sim thread routes; the second id routed 2 trip-from-cell calls during load).

| # | prediction | result |
|---|---|---|
| 1 | DLL viewport trips/s within 5% of ct_probe's, same seconds | **not met as written** in two phases: DLL / ct_probe = 1.077 (speed 1), 1.096 (speed 2), 1.047 (speed 3), 1.031 (speed 4). The DLL's total paths are higher by the same factors (27.38 / 25.42 = 1.077 at speed 1): ct_probe's per-second records carry no wall time (`t` is overwritten by the payload's `"tick"`), so its rates assume 1.000 s per record. Per routed trip the viewport share agrees: DLL / ct_probe = 1.00, 1.02, 1.01, 1.02. Paused: 0 paths: met. |
| 2 | >= 99% of ct_probe's complete samples found in the dump, same cells and types | **met: 410 of 410** (19 ct samples over 128 nodes excluded) |
| 3 | deposits exact | **met**: 75,539 trips, 30,353 flagged; 1,353,550 deposit calls, 0 outside the popped node, 1,341,695 nodes deposited cell for cell, 0 bad nodes, 0 unflagged trips with a deposit, 0 gated nodes |
| 4 | 0 faults, alive, armed | met (capture=1, verify=5/5, drain=1) |
| 5 | one routing thread (two if trip-from-cell runs elsewhere) | met (2) |
| 6 | drops 0 | met |

### V2 (Europolis 1024, sc3perf traffic_mt=8 + smoothing, c392ccbc, verify + dump, no Frida hooks)

| phase | paths/s | nodes/s | viewport paths/s (virtual 33 x 28 rect) | ... road-only | flagged paths/s | road-only / mixed / transit-only | threads | drops |
|---|---|---|---|---|---|---|---|---|
| speed 3 | 6,377 | 789,631 | 46.6 | 5.4 | 1,159 | 2,437 / 147 / 3,794 | 9 | 0 |
| speed 4 | 8,734 | 748,689 | 14.6 | 5.6 | 3,842 | 3,423 / 237 / 5,074 | 9 | 0 |

Deposits: 1,778,795 trips, 588,929 flagged, 56,680,789 deposit calls, 0 outside, 55,917,045 nodes cell for cell, 0 bad,
0 unflagged with a deposit: **exact on all 9 routing threads**. 0 faults, game alive to the end. Phase 1's E2 (probe
hooks slowing the workers) read 35.1 / 11.3 viewport trips/s.

Log artifact: the drain-latency maximum reads 4,294,967 ms in the first phase of A1 and V2: a trip committed after
the tick read its clock gives a negative difference stored unsigned. Other phases: 14-73 ms. Clamped in the source
after the runs (no effect on any counted figure).

### Open question: least or most congested (CHOICE, unflagged trips)

| arm | scored steps (2+ candidates, distinct bytes) | b = the most congested | b = the least congested | between |
|---|---|---|---|---|
| A1 Berlin | 337,572 | 322,895 (95.7%) | 12,093 (3.6%) | 2,584 |
| V2 Europolis 1024 | 1,249,155 | 1,215,609 (97.3%) | 21,134 (1.7%) | 12,412 |

(Other steps: only one candidate 862,411 / 33,123,382; all equal 5,096 / 177,543; b not a candidate under the cap
240,770 / 7,694,655.) **The ring scan keeps the most congested road neighbour below the cap (150)**, as the static read of
`FUN_1000755e` says; PERFORMANCE.md Finding 22's "least congested" is wrong. The minority are consistent with visited
cells, which the tap cannot see.

### Open question: the trips without the deposit flag

CALLER (A1, stock threading; K agrees): of 75,539 routed trips,

| caller of route_trip -> its caller | dest kind | trips | flagged | viewport |
|---|---|---|---|---|
| `FUN_10006fe3` <- building issuer `FUN_100097b9` (returns `0x100099E0`, `0x100098CB`) | 0, 1, 2 | 59,481 | 30,353 (51%) | 2,691 |
| `FUN_1000706a` (trip from a cell) <- SIMRCI `+0x1AA6C` (zone development) | 3 | 15,968 (21%) | **0** | **0** |
| `FUN_10006fe3` <- SIMMISC `+0xA5BC` / `+0xAE43` | 3 | 90 | 0 | 0 |

(A1's first return address reads Frida's trampoline, ct_probe hooked route_trip's entry; K, without it, reads
SimTransit `0x10007064` / `0x100070B3`.) So the unflagged ~60% are two things: **zone development's trip-from-cell
probes** (21% of routed trips, never deposit, never in the view in A1 / K) and **building trips that lose a random
draw** (49% of building trips). The draw, in the issuer [CONFIRMED @ SimTransit 0x100097b9]: `r = random(100)`; when
`r > *(u8 *)(layer + 0x31)` the trip is issued with flag 0 (both branches pass 0); otherwise the flag is 1 only when
the building occupant answers `vt+0x54() == 1`, QIs `0xe0faadc7`, has bit 1 in `vt+0x4c()`, and a second
`random(100)` is at or below `ftol(f(x, z) * DAT_1001f12d)`, `f` from `DAT_1001fdb8[0x27]->vt+0x24(x, z)` at the
building's cell. What `layer+0x31`, `f` and `DAT_1001f12d` hold is `[UNCERTAIN]`. Every viewport trip in A1 is a
building trip.

## M2: lane routes (build 7adfb2e2 unless named; PRE addenda 1-2)

A route = the in-view road run of a viewport trip (types 1-3, inside the trip's rect, travel order, repeats merged).
**Exact** = a lane path through the route cells and only them, in order (w = 0): "fully drivable as routed".
**Corridor** = the in-game solver (w = 1): within one cell of the route, progress by proximity, route cells may be
skipped at a cost, start on r0 or a cell beside it. **No skip** = solved with 0 skipped route cells; **cov90** = <= 10%
skipped. In-game columns from the DLL's last `M2>` line; literal (phase-1 rule) and w = 2 offline (`ctm_lanes.py`,
graphs from the save + TrBlkAtt, equal to the in-memory graphs on all 256 cells compared in M2B).

| arm, city | routes | exact (w0) | literal (phase 1 rule) | corridor (w1) | ... no skip | ... cov90 | w2 (offline) | budget-skipped | solve time per route, median / p99 / max |
|---|---|---|---|---|---|---|---|---|---|
| M2B2 Berlin | 3,053 | 21.7% | 22.5% | **88.7%** | 72.1% | 83.6% | 94.6% | 0 | 26 / 112 / 1,242 us |
| M2M Moscow | 3,607 | 67.1% | 66.7% | **96.7%** | 94.3% | 95.8% | 99.6% | 60 (1.6%) | 22 / 138 / 4,742 us |
| M2L London (most avenues) | 4,916 | 49.7% | 50.5% | **92.7%** | 86.4% | 88.7% | 93.5% | 0 | 24 / 122 / 1,232 us |
| M2E Europolis 1024 (sc3perf 8 workers) | 1,030 | 99.3% | 99.3% | **100%** | 100% | 100% | 100% | 21 (2.0%) | 68 / 248 / 1,257 us |
| M2R Berlin + RBT, box 45-70 / 155-180 | 1,405 | 38.6% | 40.5% (dump graphs) | **100%** | 93.2% | 96.8% | 100% | 45 (3.1%) | 35 / 133 / 3,954 us |
| M2B Berlin, a3038ce4 (start on r0 only) | 3,196 | 25.4% | | 87.0% | 76.1% | 80.5% | | 0 | mean 29 us |

**Roundabouts (M2R).** RBT converted Berlin's 3 qualifying blocks at load (`3 qualify, 3 converted`); the four cells
of block (57,167) read different graphs in memory than the save's stock pieces (39, 39, 11203, 39 -> 4, 4, 2, 4 car
nodes: 20400 x 3 and the closed quarter 20401 at (57,168)). 379 routes enter the block: corridor 379 (342 no skip),
exact 14; 369 of the solved lane paths pass through block cells.

**Match (prediction 1)**: the DLL's result equals `ctm_lanes.py match` on the dumped graphs for **every route of every
arm**: M2B 3,196 / 3,196, M2B2 3,195, M2M 3,720, M2L 4,916, M2E 1,043, M2R 1,408 (w1: ok, cost, skipped, off-route
cells and the full lane path; w0: ok and cost). Met.

**Faults / budget (prediction 2)**: 0 faults, `fault=0` graph lookups in every arm: met. Budget-skipped <= 1% in the
Berlin-size arms: **not met in Moscow (1.6%)**; Berlin and London 0. (Europolis 1024 2.0%, M2R 3.1%: the 4 ms
per-tick cap is shared by every trip drained in that tick; M3 can carry unsolved trips to the next tick instead.)

**Failure reasons (corridor, offline, 8-step look-back)**:

| city | failed | router step with no lane link either way (`unconnected`) | against the lanes | other |
|---|---|---|---|---|
| Berlin | 368 | 362: avenue half to avenue half 259, avenue <-> T 39, curve 11203, road 29 and others 103 | 0 | turn 6 |
| Moscow | 121 | 25 (avenue halves at (134-141, 90-91)) | **95 at (85,127) -> (85,128), piece 11211/0 -> 11213/0** | u-turn 1 |
| London | 357 | 341: avenue 11204 <-> T 39 247, 11203 -> 11204 45, avenue halves 40, others 9 | 0 | turn 16 |
| Europolis 1024 | 0 | | | |

Top places: Berlin (70,105)-(70,106) 84 both ways, (72,105)->(72,106) 35, (90,98)->(90,99) 24, (92,99)->(92,98) 21;
London (149,210)->(148,210) 73, (100,204)->(100,205) 64, (134,197)<->(135,197) 85. Share of routes with at least one
unconnected step: Berlin 75.8%, Moscow 28.2%, London 49.7%, Europolis 0 (the router's road ring scan ignores lanes,
LANE_DENSITY 1). Most such routes still solve in the corridor; they fail where the hop is to the half or road that the
rest of the route needs and no lane joins them inside the corridor.
