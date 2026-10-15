# lanedensity: PRE-REGISTRATION (2026-10-13, written before the measured runs)

Task: road traffic DENSITY respects lanes (turn matrices). Code: `re/harness/src/sc3netmod_lanes.c` (sc3netmod
LANEDENSITY block), probe `re/tools/netmod/ld_probe.py`, test package `re/tools/netmod/examples/example_oneway`.

Already measured before this file (smoke run, not a registered arm, log `smoke_count_berlin_sc3netmod.log`):
`SC3NETMOD_LANEDENSITY=count` on stock Berlin, about 5 minutes at speed 4: 775,965 router steps from road nodes on
pieces with lane data; the stock matrix of the piece would forbid 36,372 of them (4.7%) and 46,802 (6.0%) entered
the piece through a side whose matrix row is empty. So honouring the stock matrices would change stock routing: the
default honours only variant ids of the netmod tables. That run also showed the QI fast path never hit (fixed
before the arms below: per-vtable offset cache).

## Setup

- Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_lanedensity` (hard links of `Simcity_stock`, link_tree.py,
  3,488 linked). Packages installed (overlay): `example_oneway` (20430, base 29, one lane x- -> x+) and lanekit's
  `example_roundabout` (20400, base 39).
- Instance folders `re\harness\inst_ld_<arm>` in that tree, each with mods_launch.exe, sc3resize, sc3bigcity,
  sc3perf (perf.ini of `MAIN\re\harness\combo`: traffic_mt=8, traffic_mt_smooth=1, fast_ceil=1, mt_locks=1),
  sc3netmod, all built from branch `child/lanedensity`. Windowed.
- Cities: `berlin.sc3` = stock `Berlin, Germany.sc3`. `berlin_lanes.sc3` = Berlin + lanekit's roundabout cells
  (25,181) 20400/3, (26,181) 20400/0, (25,182) 20400/2, (26,182) 20400/1 + one-way run (147..157, 46) = 20430
  state 0 (was 29 state 0), written by `network_layer.py --set-piece`, diff = exactly those 15 tiles.
- Each arm: load, dismiss tips, `ld_probe.py --start 4 --months 14`: the monthly published density grid `+0x60`
  (SimTransit `FUN_100093e9` copies the decayed `+0x6c` there) for 14 months. Analysis uses months 3..14 (months 1-2
  still carry the density loaded from the save). sc3netmod.log gives the router-step counters.

## Arms

| arm | city | SC3NETMOD_LANEDENSITY |
|---|---|---|
| N1, N2 | berlin.sc3 | 0 (block off) |
| A1 | berlin.sc3 | unset (variants: hook active, nothing in this city is honoured) |
| B_off | berlin_lanes.sc3 | 0 |
| B_ctl | berlin_lanes.sc3 | count (hook active, records steps through variant cells, filters nothing) |
| B_on | berlin_lanes.sc3 | unset (variants honoured) |
| P_off, P_on, P_off2 | Europolis 1024 test city (`verify/perf1024/europolis1024_v2_test.sc3`) | 0 / unset / 0, perf.ini with traffic_mt_smooth=0 (sc3perf logs ms per trip), 5 minutes each, one game at a time |

Noise = N1 vs N2. Per-tile metric: mean over months 3..14 of `+0x60` per road tile (tiles whose stock piece is in
the road network), then |difference| per tile; summary = mean |diff| over road tiles, and the 99th percentile.

## Predictions

(a) Stock behaviour preserved.
- A1: honoured steps = 0, neighbours closed = 0, wrong-way fails = 0, arrivals refused = 0 in sc3netmod.log.
- A1 vs N1: mean |diff| per road tile <= 1.25 x the N1-vs-N2 mean |diff|, and the 99th percentile likewise.
- B_ctl vs B_off: same criterion against the noise (count mode filters nothing).

(b) One-way piece and roundabout: the router follows the lanes.
- B_on: through the eleven 20430 cells, steps leaving by the x- side = 0 (every step exits x+); steps entering by
  x+ that continue = 0 (wrong-way fails > 0 or arrivals refused account for them). B_ctl: steps exiting x- > 0, at
  least 10% of the steps through those cells.
- B_on: through the four 20400 cells, steps whose (entry, exit) pair is not in the piece's lanes (world frame:
  local x- is the ring EXIT side, entering by it is not allowed; allowed local pairs z+ -> x-, z- -> x-,
  z+ -> z-) = 0. B_ctl: > 0.
- Density: mean `+0x60` over months 3..14 summed over the eleven one-way cells is lower in B_on than in B_ctl, by
  more than the N1-vs-N2 spread of the same sum over the same cells.

(c) Performance.
- P_on vs P_off: ms per trip (sc3perf TRAFFIC_MT line, 5 minutes) within the P_off vs P_off2 spread, or at most +5%.
- No faults in sc3perf logs in any arm.

Coordinate check (not a prediction, recorded): the cells the DLL logs (SimTransit node x, z) must be the edited save
coordinates; if they come out transposed, the analysis indexes the probe grids accordingly and says so.

## Addendum 1 (2026-10-13, after N1 / N2 / A1, before any B2 arm)

The pre-registered roundabout site (lanekit's (25..26, 181..182)) carries no traffic density in stock Berlin: the sum
of the 12-month means over its four cells is 0.0 in N1 and N2 (1.2 in A1). So it cannot show a density effect; the
B arms keep it (their router-step counters still apply), and three more arms use a busier site:

- `berlin_lanes2.sc3` = stock Berlin + the same one-way run (147..157, 46) = 20430/0 + roundabout at (61,95) 20400/3,
  (62,95) 20400/0, (61,96) 20400/2, (62,96) 20400/1 (was 11213/1, 11211/1, 39/2, 39/1). Found by a search over every
  2x2 block of road cells in Berlin: the only one whose four outside road neighbours are exactly the pinwheel's exits
  ((60,95), (62,94), (61,97), (63,96)) with no other road touching the block. Stock density over the block: 143.5
  (sum of N1's 12-month means).
- Arms B2_off (0), B2_ctl (count), B2_on (unset), same protocol as B.
- Predictions for B2 = the B predictions (one-way and roundabout), on these cells. Ring order in world cells:
  (62,95) -> (61,95) -> (61,96) -> (62,96) -> (62,95); B2_on: steps against it = 0, entries through a quarter's ring
  exit side continue = 0; B2_ctl: > 0.

## Addendum 2 (2026-10-13, after arm B_on hung, before any re-run)

Arm B_on (PID 3556) never published a month: a wrong-way entry cleared the cell's visited mark and failed, the DFS
retried the node it came from, which picked the same cell again, for ever (sc3netmod.log: 6.3e8 wrong-way fails in
19 minutes, counters wrapped). Killed by PID. Fix (sc3netmod_lanes.c): the refused transition (from cell, to cell) is
kept per thread for the rest of the trip and closed in every later scan from that cell (any network node type, the
highway branch FUN_100086e7 reads the same visited grid); the list is cleared when a trip's start node (type 0x80)
is scanned; when full (32) the cell keeps its visited mark. Every arm that runs the hook (A1, B_off, B_ctl, B_on, B2_*)
is re-run with the fixed build; N1 / N2 (block off) are kept. Predictions unchanged.

## Addendum 3 (2026-10-13, after a 6-month debug run, before the re-runs)

Debug run (`inst_ld_dbg`, berlin_lanes, 6 months, not an arm) found steps from a one-way cell to ITSELF: a node entered
from a lot has its cell marked with the lot's bits (0x80), so the ring scan offers its own cell; the copy gets entry
side 2 (SimTransit 0x100083e4, same rect) and then read as a wrong-way entry. Fix: an honoured node closes its own cell
for the call; the cell statistics skip self-steps. Second debug run: every step through the eleven 20430 cells exits
x+. Final build for all re-run arms: this commit.

## Addendum 4 (2026-10-13, after the B / B2 re-runs, before arms P2_*)

Result that prompted this: the router-step counters show 0 steps against the lanes in B_on / B2_on, but the 12-month
density sum over the one-way run moved only -15% (B_on vs B_ctl) and -0.5% (B2_on vs B2_ctl), inside the spread of
the four unfiltered arms on that sum (1,300-1,489). Step counters include DFS exploration that is backtracked; density
is deposited only along final paths. New witness, `ld_paths.py`: a Frida hook on the deposit FUN_10006edd that recovers
the forward direction of every final path through watched cells (deposits of one trip come in reverse path order).

Arms P2_ctl (count) and P2_on (unset), berlin_lanes2.sc3, same protocol, `ld_paths.py` attached for 50 s from 10 s
after the unpause, watched cells = the one-way run (147..157, 46) and the roundabout (61..62, 95..96).

Predictions:
- P2_on: final-path steps inside the run in -x (x -> x-1, both cells in the run) = 0; final-path steps (158,46) ->
  (157,46) = 0; final-path steps between roundabout cells against the ring order = 0.
- P2_ctl: final-path steps inside the run in -x > 0 and >= 20% of all final-path steps inside the run; against the
  ring > 0.

## Addendum 5 (2026-10-13, after P_off / P_on / P_off2, before the v3 arms)

Perf result (c) failed: ms per trip P_off 0.04592, P_off2 0.04577 (0.3% apart), P_on 0.05599 (+22%), with 0 honoured
evaluations: the cost is the C wrapper on every router step. P_cnt died at startup (another session's game started
20 s before it) and is void. Build v3 (commit above) adds an asm filter at the entry that jumps to the game unless the
node is a road / bus node on an honoured piece (trusted vtable -> piece id -> table), some thread holds refused
transitions, or count mode. Semantics unchanged (the C path is the same). Re-run with v3: P_on3, P_off3, P_on4
alternating (same criterion: within the off-off spread or <= +5%), then A1 and B2_on (+ ld_paths) for the record.

## Addendum 6 (2026-10-15, session lanedensity2, before any Q arm)

P_on3 / P_off3 / P_on4 (addendum 5) never ran the sim and are void (RESULTS, Deviations). A series "Q*" was started on
2026-10-14 without being written here; none of it is used. This addendum registers its replacement.

Setup (the 2026-10-13 tree no longer exists): tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_lanedensity2` =
hard links of MAIN `Apps`, `Buildings`, `Cities`, `Scripts` (3,475 linked, release mod files skipped),
`GZGraphicD.dll` / `SIMSPR.DLL` = `original\modules` copies, `*.ini/*.cfg/*.txt` in Apps / Cities de-linked. SHA-256
prefixes: SC3U.exe 49dd55e1 (anchor), SIMNTWRK 693f6572, SimTransit b478ded4, GZGraphicD 48201f47, SIMSPR eec71500.
Packages `example_oneway` (20430) and `example_roundabout` (20400) from this branch, overlay. DLLs = the 2026-10-13
builds of this branch: sc3netmod v3 48bd8545, sc3perf 0c1d8b5f, sc3resize f7d307fd, sc3bigcity e12ce12c, mods_launch
88f3a974; bigcity.ini of combo; perf.ini = combo's (same bytes as on 2026-10-13) with traffic_mt_smooth=0 (32328e3f).
City `MAIN\verify\perf1024\europolis1024_v2_test.sc3` (9ce07478). Driver: load, dismiss tips, unpause, speed 3,
300 s, kill by PID (same steps as the P arms), plus a census of SC3U processes every 10 s.

Arms, in this order, one game at a time: Q_off1, Q_on1, Q_off2, Q_on2, Q_off3, Q_on3 (off = SC3NETMOD_LANEDENSITY=0,
on = unset).

Metric: ms per trip = routing ms / trips of the last `TRAFFIC_MT> N batches, T trips, R ms routing` line in sc3perf.log.

Validity (decided before reading any metric): the census shows no SC3U process other than the arm's own at launch and
at every sample, and T >= 500,000. An invalid arm is re-run at the end of the series and reported.

Prediction (c), the bound of the PRE unchanged: every Q_on arm's ms per trip <= the largest Q_off value, or <= 1.05 x the
mean of the Q_off values. Also reported: mean(Q_on) / mean(Q_off), and sc3perf faults (prediction: 0 in every arm).

After the Q series, for the record (no bound): QB_off1, QB_on1, QB_off2, QB_on2, `berlin_lanes2.sc3` (rebuilt with
the addendum 1 edits, diff = the same 15 tiles), 300 s, speed 3, same validity: the cost where pieces are honoured.

If the bound is missed: a profiling run and any new build are registered here before they run.

## Addendum 7 (2026-10-15, after the Q series, before any ALT or merge-check run)

Q series result (all six arms valid by addendum 6): ms per trip off 0.04919 / 0.13377 / 0.05580, on 0.11240 / 0.05925 /
0.11540. The bound as worded is met (every on arm <= the largest off arm), but the arms fall in two states, ~0.05 and
~0.11-0.13, in both conditions (off-off spread 172%), so between-game comparison cannot resolve 5%. The lanedensity
counters in the on arms read 0 evaluations (Europolis has no variant piece): the only work of the block there is the
asm filter and the arrival wrapper. A passive CPU log (other processes' CPU every 10 s) was added from Q_on2 on and
showed no outside load above 0.6 cores. The registered QB arms (record only) are dropped, not run: they would be the
same between-game comparison.

New measurement, ALT (in-game, paired). Build change: `sc3netmod_ld_set(int)` exported from sc3netmod (code in
`sc3netmod_lanes.c`): 0 writes SimTransit's shipped bytes back at both patch sites (entry 0x1000755e, arrival call
0x100071eb), 1 writes the detours again, with every other thread of the process suspended and the write retried until
no thread's EIP is inside the bytes written or the trampoline. The stub and the C path are unchanged, so ON runs the
same code as v3, and OFF runs SimTransit's own bytes (sc3netmod's install work having been done). Driver
`re/tools/netmod/ld_alt.py`: reads sc3perf's trip counter and routing-ms double at each window edge (addresses taken
from sc3perf's own log call, opcodes checked), switches with the export. Schedule: switch OFF, 60 s warm-up, then 10
ABBA blocks (off on on off) of 30 s windows, 2 s settle after each switch excluded. Same launch / keys / census / CPU
log as the Q arms, game at speed 3.

Builds:
- v3a = this branch at 0449aed (v3 code) with `sc3netmod_lanes.c` replaced by the ALT version (no other file changed);
  sc3perf / sc3resize / sc3bigcity / mods_launch = the 2026-10-13 builds of addendum 6.
- m1 = the merge of round/1012 (f3a129f) plus the ALT commit: sc3netmod and sc3resize built from it; sc3perf /
  sc3bigcity / mods_launch = the same builds (their sources are identical between the two commits).

ALT runs (one game at a time, nothing else heavy):
| run | build | tree | city |
|---|---|---|---|
| ALT_v3_euro | v3a | Simcity_stock_lanedensity2 (addendum 6) | europolis1024_v2_test.sc3 |
| ALT_v3_b2 (record) | v3a | same | berlin_lanes2.sc3 (one-way run + roundabout honoured in ON windows) |
| ALT_m_euro | m1 | Simcity_stock_lanedensity2m (below) | europolis1024_v2_test.sc3 (RBT on: any qualifying block converted is honoured in ON windows) |
| ALT_m_berlin (record) | m1 | same | berlin.sc3 (RBT converts its 2x2 blocks on load) |

Metric: pooled ms per trip = sum of routing ms / sum of trips over the ON windows, divided by the same over the OFF
windows. Also reported: the 10 per-block ratios (median, mean).
Validity: census as in addendum 6; every switch logged by sc3netmod (`lanedensity: ALT ON|OFF`) with no `NOT switched`;
trips > 0 in every window; the game alive at the end.
Prediction (c), the +5% part of the PRE bound: pooled ON / OFF <= 1.05 for ALT_v3_euro and for ALT_m_euro. No bound
for the two record runs. 0 sc3perf faults in all four.

Merge check, tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_lanedensity2m`: built like addendum 6's, packages
`roundabout` (4.0.0, examples/roundabout of the merged branch) and `example_oneway`, instances with the m1 DLLs and
the addendum 6 perf.ini (smooth=1 for the probe arms, as the 2026-10-13 B arms) / perf_batch.ini (ALT). City
`berlin.sc3` = stock Berlin (sha256 9932777587b602f1). Per arm: load, dismiss tips, `ld_probe.py --start 4 --months
14` (as addendum 1 arms), sc3netmod.log counters.

| arm | SC3NETMOD_LANEDENSITY | SC3NETMOD_RBT |
|---|---|---|
| MN1, MN2 | 0 | 0 |
| MA1 | unset | 0 |
| MR_ctl | count | unset (on) |
| MR_on | unset | unset (on) |

MR_ctl / MR_on also run `ld_paths.py` for 120 s from 10 s after the unpause on the cells of Berlin's three RBT blocks
(29..30, 86..87), (57..58, 167..168), (145..146, 102..103) (roundabout4 RESULTS arm A).

Predictions:
- Stock preserved (merged build): MA1 vs MN1 mean |diff| per road tile and p99 <= 1.25 x MN1 vs MN2 (same metric as
  (a)); MA1 counters: honoured steps 0, wrong-way 0, arrivals refused 0.
- RBT in both MR arms: sc3netmod.log reports 3 qualifying blocks converted.
- Router honours the RBT pieces: MR_on final paths: steps between two ring cells of a block against the ring order
  ((X+1,Z) -> (X,Z) -> (X,Z+1) -> (X+1,Z+1) -> (X+1,Z) for anchor (X,Z); states 3/0/2/1 as placed by RBT, the same
  layout whose lanes were checked in (b)) = 0 at every block; steps between the 20401 quarter and the outside cell
  beyond its closed side = 0. MR_ctl: steps against the ring order > 0 summed over the three blocks. A block with no
  final-path ring step in either arm is reported as carrying no traffic, not as evidence.

## Addendum 8 (2026-10-15, after MR_ctl / MR_on, before MR_ctl2 / MR_on2)

Two faults in addendum 7's ring check, found in the MR arms:
1. The registered ring order ((X+1,Z) -> (X,Z) -> ...) was taken from the 2026-10-13 package (lanekit's
   example_roundabout, quarter ring z+ -> x-). Package roundabout 4.0.0 (the one RBT places) runs the ring the other
   way: `examples/roundabout/quarter.lanes.json`, state 0, ring lane x- (0,80) -> z+ (175,255) ("counter-clockwise for
   right-hand traffic"); `closed.lanes.json` (20401) the same lane. With the pinwheel states (3, 0 / 2, 1) the world
   order is (X,Z) -> (X+1,Z) -> (X+1,Z+1) -> (X,Z+1) -> (X,Z): quarter (X+1,Z) at state 0 is entered from x- (from
   (X,Z)) and left through z+ (to (X+1,Z+1)). That order is read from the package files, not from the runs.
2. `ld_paths.py` paired every deposit of FUN_10006edd, whatever its network mask (4th argument: 0x15 road / rail /
   bus, 2 highway, 8 subway [CONFIRMED @ SimTransit 0x10006edd and its five calls in 0x100070d0]). Berlin's subway
   (network instance 3) runs under block (57,167) along x = 58, z 165..169 (pieces 16013, 16037, 11612), and (58,169)
   has no surface road, so north-south pairs there come at least in part from subway trips.

MR_ctl / MR_on are reported as run (registered order and unfiltered). New arms, same protocol as MR_ctl / MR_on:
MR_ctl2 (count), MR_on2 (unset), `ld_paths.py --mask 0x35` (only deposits into the surface grid +0x6c; a deposit of
another mask breaks the per-thread chain), checked with `ld_ringcheck.py --ring400`.

Predictions:
- MR_on2: final-path steps between two ring cells against the 4.0.0 order = 0 at each of the three blocks; steps
  between the 20401 quarter and any cell outside its block = 0.
- MR_ctl2: steps against the 4.0.0 order > 0 summed over the three blocks.
- Both: 3 blocks converted by RBT; 0 `step through a closed side` lines.
