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
