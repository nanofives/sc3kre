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
