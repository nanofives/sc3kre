# lanedensity: RESULTS (2026-10-13)

Pre-registration: `PRE.md` (committed 4efaa23 before the first arm, addenda 1-5 committed before the runs they cover).
Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_lanedensity` (hard links of `Simcity_stock`, 3,488 linked),
packages `example_oneway` (20430) and lanekit's `example_roundabout` (20400) installed as overlay. Instances
`re\harness\inst_ld_<arm>`, each with mods_launch / sc3resize / sc3bigcity / sc3perf / sc3netmod built from this branch
and perf.ini of `MAIN\re\harness\combo` (traffic_mt=8, smooth=1). Every PID mine, stopped with taskkill /PID.
Probe `ld_probe.py` (monthly published density `+0x60`, 14 months, months 3-14 analysed), `ld_paths.py` (direction of
final paths), sc3netmod.log counters. Numbers: `density_compare.json`, logs in the instance folders.

sc3netmod builds: v1 `5a374629` (A1 first run, dbg), v2 `61d12a69` (B, B2, P2, S_cnt, perf P_*), v3 `48bd8545` (asm fast
path; A1v3, B2_onv3, perf Q*). v2 and v3 run the same C code for honoured nodes; v3 only adds the filter in front.

## Deviations

- Arm B_on first run (v0 build) hung: wrong-way retry loop (PRE addendum 2), fixed, re-run.
- Lot-entered self-step read as wrong-way (addendum 3), fixed before the re-runs.
- The pre-registered roundabout site carries no density in stock Berlin (addendum 1): B2 arms on a busier site.
- An orphaned probe from the hung run overwrote B_on's first re-run output with an empty file; A1's v2 re-run died at
  startup (game exited at 0.25 s). Both re-run again (A1, B_on as listed). A1's first-run file kept as probe_firstrun.npz.
- Perf: P_cnt and the v3 arms P_off3 / P_on4 never ran the sim (another session's game slowed the 1024 load past the
  wait; keys landed before the city). Void. Replaced by the alternating series Q*.
- Router-step and density predictions were judged on v2 arms; v3 arms repeat the honoured ones.

## (a) Stock behaviour preserved

| pair (12-month means, 17,226 road tiles) | mean abs diff per tile | p99 | total |
|---|---|---|---|
| N1 vs N2 (noise, block off) | 11.54 | 67.0 | +1.3% |
| N1 vs A1 (hook on, nothing honoured, v2) | 11.37 | 65.7 | -0.4% |
| N1 vs A1v3 (v3) | 11.25 | 61.8 | +1.3% |
| B_off vs B_ctl (count mode filters nothing) | 11.08 | 68.1 | +1.6% |

Bound (PRE): <= 1.25 x noise = 14.4 mean, 83.8 p99. **Met** for A1, A1v3 and count mode. A1 / A1v3 counters: honoured
steps 0, neighbours closed 0, wrong-way 0, arrivals refused 0. **Met.**

Stock matrices vs today's router (arm S_cnt, count mode, v2, Berlin, about 80 s of play): 2,216,925 road steps on
pieces with lane data. The piece's own matrix forbids 99,361 of them (4.5%) and 134,605 (6.1%) entered the piece
through a side whose row is empty. Largest: Avenue 11204 (61,682 forbidden + 105,096 against of 404,335: the router
steps sideways between the avenue's two cells, its matrix is a straight's), T 39 (14,489 + 14,716 of 322,791), road 29
(7,082 + 743 of 927,951), curve 11203 (2,677 + 2,844 of 77,362). So honouring stock pieces would change stock routing:
the default honours only variant ids. (The pre-PRE smoke run's 4.7% / 6.0% counted self-steps; S_cnt does not.)

## (b) One-way piece and roundabout

Router steps through the variant cells (sc3netmod.log, every DFS step including backtracked ones):

| arm | one-way run: steps with the lane (x+) / any other exit | entries refused (wrong way) | B2 roundabout: steps the lanes allow / do not |
|---|---|---|---|
| B_ctl (count, v2) | 1,409 / **2,360** | (2,513 counted, not refused) | |
| B_on (v2) | 1,368 / **0** | 204, all at (157,46) | |
| B2_ctl (count, v2) | 1,748 / **1,748** | (1,977 counted) | 1,221 / **614** |
| B2_on (v2) | 2,436 / **0** | 348 | 1,290 / **0** |
| P2_ctl (count, v2) | 1,933 / **1,547** | (1,680 counted) | 1,163 / **504** |
| P2_on (v2) | 2,640 / **0** | 292 | 1,769 / **0** |
| B2_onv3 (v3) | 2,538 / **0** | 274 | 2,345 / **0** |

Allowed roundabout turns per cell, world sides (0 x-, 1 z-, 2 x+, 3 z+, 4 = from a lot), from the quarter's lanes rotated
by its state: (61,95)/3: 2>3, 0>3, 2>0. (62,95)/0: 3>0, 1>0, 3>1. (61,96)/2: 1>2, 3>2, 1>3. (62,96)/1: 0>1, 2>1, 0>2.

Final paths (what density is made of; `ld_paths.py`, 50 s):

| arm | inside the run +x / -x | (158,46) -> (157,46) | ring with / against |
|---|---|---|---|
| P2_ctl (count, v2) | 716 / **394** (35%) | 22 | 42 / **9** |
| P2_on (v2) | 615 / **0** | 0 | 71 / **0** |
| B2_onv3 (v3) | 537 / **0** | 0 | 106 / **0** |

Predictions (b) on steps and final paths: **met** (0 against with the patch, > 0 and >= 20% without).

Density over the eleven one-way cells (sum of 12-month means):

| arms without honouring the run | arms honouring it |
|---|---|
| N1 1,332, N2 1,319, A1 1,341, A1v3 1,366, B_off 1,489, B_ctl 1,385, B2_off 1,399, B2_ctl 1,300, P2_ctl 1,371 | B_on 1,374, B2_on 1,294, P2_on 1,050, B2_onv3 1,481 |

PRE prediction "B_on lower than B_ctl by more than the N1-N2 spread (12.8)": B_on 1,373.8 vs B_ctl 1,384.6 (-10.8),
B2_on 1,294.0 vs B2_ctl 1,299.8 (-5.8): **not met**. The direction of the traffic on the piece follows the lanes,
the amount of density on it does not measurably change. Measured facts that bear on it: the ring scan takes a road
cell only while its congestion byte is below `DAT_1001f0c0` = 0x96 = 150 [CONFIRMED @ SimTransit 0x1000755e, byte at
0x1001f0c0], and the one-way cells sit at 120-150 per month in every arm. That this cap is what keeps the total level
is `[UNCERTAIN]` (not tested, e.g. with a quiet one-way street).

Post hoc (not registered): on the diagonal street that feeds the B2 roundabout (15 cells (54,87)..(60,95)) the three
arms that honour the roundabout read 918, 1,005, 1,155; the ten that do not read 1,068-1,709.

## (c) Performance

PERF_PLACEHOLDER

## Cleanup

All instances stopped by PID. Packages left installed in `Simcity_stock_lanedensity` (overlay) for re-runs; instance
folders, cities and logs left in place.
