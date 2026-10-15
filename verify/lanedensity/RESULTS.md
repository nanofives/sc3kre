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
2026-10-15 (session lanedensity2): v3a `dedc412e` (v3 + the ALT export, perf ALT_v3_*), m1 `ab20b39f` (merged with
round/1012 + ALT: ALT_m_*, MN*, MA1, MR*).

## Deviations

- Arm B_on first run (v0 build) hung: wrong-way retry loop (PRE addendum 2), fixed, re-run.
- Lot-entered self-step read as wrong-way (addendum 3), fixed before the re-runs.
- The pre-registered roundabout site carries no density in stock Berlin (addendum 1): B2 arms on a busier site.
- An orphaned probe from the hung run overwrote B_on's first re-run output with an empty file; A1's v2 re-run died at
  startup (game exited at 0.25 s). Both re-run again (A1, B_on as listed). A1's first-run file kept as probe_firstrun.npz.
- Perf: P_cnt and the v3 arms P_off3 / P_on4 never ran the sim (another session's game slowed the 1024 load past the
  wait; keys landed before the city). Void. Replaced by the alternating series Q*.
- Router-step and density predictions were judged on v2 arms; v3 arms repeat the honoured ones.
- 2026-10-15: the Q* series started on 2026-10-14 was never registered and is not used; addendum 6 registered a new
  one (Q_off1..Q_on3). Its QB arms were dropped before running (addendum 7). Perf result (c) is judged on the paired
  ALT runs (addendum 7), the Q series is reported as measured.
- 2026-10-15: first ALT_v3_euro game died at startup (sc3perf fault, below), re-run as ALT_v3_euro_r. The first MR_ctl
  launch was stopped by me before its probe began (its driver would have killed the game under the path probe: no
  `pgrep` in Git Bash); driver fixed, re-run. The MR ring check as registered used the old package's ring order and an
  unfiltered witness (addendum 8); MR_ctl2 / MR_on2 repeat it with both fixed.

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

Session lanedensity2, 2026-10-15 (PRE addenda 6-8). The 2026-10-13 tree was gone; rebuilt as
`Simcity_stock_lanedensity2` (addendum 6). Every PID mine, census of SC3U processes every 10 s in every run (only the
run's own game in all samples; the one 0 in ALT_v3_b2 is the tick after its kill), passive log of other processes'
CPU from Q_on2 on. Numbers: `perf/` (ld_perf.py / ld_alt.py output).

**Between games (Q series, v3 48bd8545, Europolis 1024, 300 s, speed 3, batch mode).** `ld_perf.py`:

| arm | trips | routing ms | ms per trip |
|---|---|---|---|
| Q_off1 | 1,335,720 | 65,700 | 0.04919 |
| Q_on1 | 1,082,753 | 121,704 | 0.11240 |
| Q_off2 | 1,015,228 | 135,811 | 0.13377 |
| Q_on2 | 1,273,581 | 75,460 | 0.05925 |
| Q_off3 | 1,321,853 | 73,766 | 0.05580 |
| Q_on3 | 1,063,596 | 122,737 | 0.11540 |

All six valid (addendum 6 rule), 0 faults, lanedensity counters in the on arms: 0 evaluations (Europolis has no
variant piece), 1 trusted vtable. Bound as worded: **met** (every on arm <= the largest off arm, 0.13377). Not
informative: the games fall in two states, ~0.05 and ~0.11-0.13 ms per trip, in both conditions (off-off spread 172%),
and the slow state holds for the whole game (per-minute rates of Q_off2: 0.180, 0.141, 0.099, 0.098; Q_off1: 0.051,
0.039, 0.037, 0.039). What sets the state was not found: the other processes' CPU stayed below 0.6 cores during Q_on2,
the power plan is Balanced, the game was not under explicit power throttling `[UNCERTAIN]`. The 2026-10-13 P arms
(P_off 0.04592, P_off2 0.04577, P_on 0.05599) are three single games and share this exposure.

**In game, paired (ALT, addendum 7).** One game alternates SimTransit's shipped bytes and the detours at both patch
sites (export `sc3netmod_ld_set`, other threads suspended; 21 switches + the final one per run, 0 retries, 0 `NOT
switched`), ABBA, 40 windows of 30 s after 60 s warm-up; ms per trip pooled over the windows of each state.

| run | build | city | off | on | on / off | block ratios (median) |
|---|---|---|---|---|---|---|
| ALT_v3_euro_r | v3a (v3 code) | Europolis 1024 | 0.04559 | 0.04391 | **0.963 (-3.7%)** | 0.748-1.045 (0.995) |
| ALT_v3_b2 (record) | v3a | berlin_lanes2 (one-way + roundabout honoured) | 0.01418 | 0.01444 | 1.018 (+1.8%) | 0.922-1.086 (1.016) |
| ALT_m_euro | m1 (merged) | Europolis 1024 | 0.09409 | 0.09216 | **0.980 (-2.1%)** | 0.853-1.034 (1.018) |

Bound (addendum 7, pooled on / off <= 1.05): **met** for v3 and for the merged build. ALT_m_euro's game was in the
slow state in both conditions alike (0.094 off, 0.092 on), so the state belongs to the game instance, not to the
patch. ALT_v3_euro_r's first block holds the warm-up's tail (first off window 0.0739); without it (post hoc) on / off
= 1.005. ALT_v3_b2 honoured the run and the roundabout in its on windows (16,612 honoured steps, 834 wrong-way fails,
902 refused-transition closes) on small windows (about 4,000 trips, 50-90 ms of routing each). 0 sc3perf faults in
all runs. Europolis has no block RBT converts (`0 qualify`), so ALT_m_euro honoured nothing either.

Incident: the first ALT_v3_euro game exited 0.2 s after start, VEH fault at sc3perf.dll+0x7963 (a function that reads
a module's PE header, `mov eax, [ebp+0x3c]`), before SimTransit had loaded (no lanedensity line in its log). Same
symptom as A1's 2026-10-13 re-run that "died at startup". Re-run as ALT_v3_euro_r. Cause not traced `[UNCERTAIN]`.

Verdict (c): v3 and the merged build cost no measurable routing time per trip on the 1024 city (paired: -3.7% and
-2.1%, bound +5%). v2's +22% came from one game per condition, the kind of comparison the Q series shows can differ
by 2x between identical arms; v2 (C wrapper on every step) was not re-measured, so its own cost stays unknown.

## Merge with round/1012 (RBT roundabouts 20400 / 20401)

`round/1012` merged into this branch (f3a129f): one conflict, the `#include` lines in `sc3netmod.c` (both kept,
`sc3netmod_rbt.c` then `sc3netmod_lanes.c`); no symbol shared between the two files. Build m1 (f3a129f + 3254071):
sc3netmod ab20b39f, sc3resize dbdaf0bc; sc3perf / sc3bigcity / mods_launch sources unchanged by the merge (the
2026-10-13 builds used). Tree `Simcity_stock_lanedensity2m` (addendum 7), packages roundabout 4.0.0 + example_oneway,
stock Berlin (9932777587b602f1).

Stock preserved (merged build, RBT off so no variant piece in the city; `merge_stock_compare.json`):

| pair (12-month means, 17,226 road tiles) | mean abs diff per tile | p99 | total |
|---|---|---|---|
| MN1 vs MN2 (noise, block off) | 12.51 | 74.8 | +3.7% |
| MN1 vs MA1 (hook on, nothing honoured) | 11.51 | 68.7 | -1.8% |

Bound <= 1.25 x noise = 15.6 / 93.5: **met**. MA1 counters: evaluations 0, honoured steps 0, wrong-way 0, arrivals
refused 0. **Met.**

RBT pieces honoured by the router (Berlin, RBT on: `3 qualify, 3 converted, 0 reverted` in every arm; blocks (29,86)
closed quarter (30,86), (57,167) closed (57,168), (145,102) closed (145,102); final paths, `ld_paths.py`, 120 s):

| arm | (29,86) with / against | (57,167) | (145,102) | 20401 quarter <-> outside |
|---|---|---|---|---|
| MR_ctl (count, unfiltered, registered order) | 502 / 511 | 377 / 79 | 52 / 65 | 0 |
| MR_on (unfiltered, registered order) | 0 / 1,163 | 163 / 312 | 0 / 213 | 0 |
| MR_ctl2 (count, `--mask 0x35`, 4.0.0 order) | 577 / **482** | 86 / **102** | 55 / **52** | 0 |
| MR_on2 (`--mask 0x35`, 4.0.0 order) | 1,196 / **0** | 537 / **0** | 152 / **0** | 0 |

MR_ctl / MR_on as registered in addendum 7: **not met as worded**. The registered order was the 2026-10-13 package's;
4.0.0 runs the ring the other way (addendum 8, from `quarter.lanes.json`), and the witness counted subway deposits:
Berlin's subway runs under block (57,167) along x = 58 (MR_on's 163 "with" steps there are (58,168) -> (58,167), with
(58,169) -> (58,168) 163 beside them, and (58,169) has no surface road). The router-step counters of MR_on agree with
the 4.0.0 order and show no step from (58,168) to (58,167) (sc3netmod.log cell lines). MR_ctl2 / MR_on2 (addendum 8,
registered before they ran): **met**, 0 steps against the ring at all three blocks with the patch, 636 without.
The closed quarter: 0 steps to or from outside its block in every arm, patch or not (its lanes have no exit, and
roundabout4 found the same for the street sim). Router counters MR_on2: 17,106 honoured steps, 0 wrong-way fails,
0 `step through a closed side` lines.

Perf on the merged build: ALT_m_euro in (c). ALT_m_berlin (record, stock Berlin, RBT blocks honoured in the on
windows: 29,295 honoured steps, 0 wrong-way fails): off 0.01086, on 0.01116 ms per trip, on / off **1.028 (+2.8%)**,
block ratios 0.958-1.073 (median 1.032, 8 of 10 above 1), windows of about 4,500 trips / 55 ms of routing. Together
with ALT_v3_b2 (+1.8%) this is the cost where pieces are honoured (the C path runs); no bound was registered for it.

## Cleanup

All instances stopped by PID. Packages left installed in `Simcity_stock_lanedensity` (overlay) for re-runs; instance
folders, cities and logs left in place.
2026-10-15: every game of session lanedensity2 stopped by its own PID (or exited by itself: the first ALT_v3_euro).
Trees `Simcity_stock_lanedensity2` and `Simcity_stock_lanedensity2m` kept with their instance folders and logs; the
2026-10-13 tree `Simcity_stock_lanedensity` no longer exists. Per-run data in `perf/`.
