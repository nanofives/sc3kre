# avflow: avenues and boulevards carry more traffic (2026-10-24)

Owner request: "make a 2-road avenue and 3-road avenue (boulevard) increase traffic flow". Owner's choice: AVENUE-FIRST
routing plus LIGHTER TRAFFIC PER TRIP on avenue and boulevard cells, together. The one-way boulevard middle row is
not part of this.

**Verdict:** both blocks are built and on by default. In one Seoul game with the blocks switched by month (24 months
per arm), avenue cells went from 27.7% to 38.1% of the road cells on trip paths. Side streets near the avenues lost
9% of their traffic density, and the game's own traffic average fell 6.4%. Failed trips did not change
(2.02% -> 1.97%). The cost: paths are 5% longer (45.4 -> 47.9 cells) and routing takes 5.7% more time per trip.
A second game on a Seoul save with a 39-cell boulevard repeats the avenue result (28.0% -> 39.1%). The boulevard
itself gained nothing: 0.59% of arrived trips used it with the blocks off, against 0.44% (AVFIRST) and 0.50% (both),
and the window ranges overlap (2.6). Commute time could not be read: SC3U shows no commute statistic, and no "commut" string exists in SimTransit or
SIMCITY. Path length per trip is the nearest number measured.

## 1. What was built (`re/harness/src/sc3netmod_avflow.c`)

Facts it relies on, from SimTransit (base 0x10000000):

- Road / bus nodes (type 1 / 0x41) pick their next cell with the ring scan `0x10007a63`. The keep rule `0x10007db4`
  takes the busiest road candidate below TrafficAnnoyanceLevel (`DAT_1001f0c0`, 165 live). It does this the same way
  for every road piece, avenues included (HIGHWAY_TRIPS.md 1.2).
- On arrival, route_trip `FUN_100070d0` pops the final path. For every type-1 (and 0x50) node it calls
  `FUN_10006edd(layer, x, z, amount, 0x15)` at **0x10007463** (push x = [ebp+0x20], z = edi, amount = [ebp-0x18],
  0x15). `amount = (char)(start-lot area x TripDensityAdder)` (`DAT_1001f0be` = 3) `[CONFIRMED @ 0x100070d0,
  0x10007463]`. The other four deposit calls (0x100073b2, 0x100073f8, 0x100074be, 0x10007500) serve station, highway
  and subway nodes.
- `FUN_100093e9` (the monthly publish) copies the decayed live grid +0x6c to the snapshot +0x60. It reads the month
  counters +0xb0 (trips routed) and +0xb4 (failed), writes +0xb8 = failed / routed, and then zeroes +0xb0 and +0xb4.
  +0xc0 = the published traffic average `[CONFIRMED @ 0x100093e9]`.

| part | how |
|---|---|
| class grid | One byte per cell: 0 other, 1 avenue, 2 boulevard. Filled on the game thread at the end of RBT's edit pass (`rb_pass`, box + 3) and load pass (`rb_load_pass`, whole map), after every other road block has written its pieces. Boulevard = a BV piece that is not a BVX junction box, or a DBV piece. Avenue = stock 11204 or any variant of it, stock 11203, an AVL piece, a cell an AVL band claims, or a DAV avenue piece that is not a junction. AVX boxes and corners stay 0 (some have base 11204), and AVX median noses count as avenue. Junctions (stock 39 / 43, BVX, DAV junctions) stay 0. The class is cached per piece id. |
| AVFIRST | In `ld_select` (LANEDENSITY's detour of `FUN_1000755e`), right after `rf_close` at both call sites, so an offered on-ramp still wins. For a 1x1 road / bus node with an open class-1/2 road candidate (not visited by the node type, density +0x6c below the live TrafficAnnoyanceLevel), every other road candidate is closed in the visited grid for that one call. The bits are cleared after the call. The stock rule then takes the busiest such avenue cell. On a retry the avenue cells are visited and the stock order applies. `ld_stub` sends road steps to the C path while AVFIRST is on. |
| AVDEPOSIT | `retarget_call` at 0x10007463 -> `avd_dep`. On a class-1 cell the amount x 2/3, on class 2 x 1/3. The remainder is kept per cell (a CAS on one LONG per cell), so the long-run deposit is exact, then the call goes on to the original target. sc3perf's TRAFFIC_MT `jmp` at the 0x10006edd entry is untouched (different bytes), so the atomic deposit still applies. |
| switches | Both on by default. `SC3NETMOD_AVFIRST=0`, `SC3NETMOD_AVDEPOSIT=0` turn one off. `SC3NETMOD_AVDEP_AV=n/d`, `SC3NETMOD_AVDEP_BV=n/d` change the scales. Live exports (measurement): `sc3netmod_avf_set`, `sc3netmod_avd_set`, `sc3netmod_avflow_set` (both), `sc3netmod_avf_grid(&w, &h)`. A stats line comes with LANEDENSITY's every 10 s. |

Shared files: `sc3netmod_lanes.c` (include, both `avf_close` calls, the stub check, `avf_init`, `avd_install`, stats,
`added[]` 10 -> 16 + LD_TRIPMAX) and `sc3netmod_rbt.c` (declaration plus the two `avf_pass` calls). All marked
`/* task avflow */`.

## 2. Measurements

Setup: tree `Simcity_stock_avflow`, all eight mods built from this worktree into `inst_avflow`. sc3perf runs as the
owner has it (8 workers, smooth mode). City: Seoul, 256x256, 3,025 avenue cells after the AVL pass (124 bands one-way),
0 boulevard cells. Every class cell is a road cell in SimTransit's flags grid, so the SIMNTWRK and SimTransit
coordinates match. At speed 4 a month takes 5.2 s.

### 2.1 Baseline (game PID 19672, blocks off, never switched, 4 months)

Trips routed 3,405..3,827 per month, failed 1.76..2.38%. 35.5..36.9% of arrived trips touched an avenue cell. Avenue
cells were 17.8..21.1% of the road cells on trip paths, at 42.8..46.7 cells per trip. Monthly density: avenues
34.8..44.6, side streets 2..4 cells from an avenue 55.7..63.9, other roads 60.8..69.1. Avenues are quieter than the
streets around them, so the busiest-below-level rule sends trips away from them. (`data/seoul_baseline.json`)

### 2.2 Arms in one game (same PID, `avflow_probe.py --blocks 4 --mpw 4 --settle 1`)

The arm switched at the game's own month publish, so each month ran under one arm. The order was 4 x (off F FD FD F
off), 4 months per window (~21 s), and the first month of each window was dropped (settle). That leaves 24 months
per arm. (`data/seoul_abba.json`, `re/tools/netmod/avflow_report.py`)

| arm | trips / month | failed | arrived trips touching an avenue | avenue share of path road cells | cells / trip | game traffic avg (+0xc0) | density avenues | side streets (2..4) | beside avenues (1) | other roads | avenue cells >= 165 / month |
|---|---|---|---|---|---|---|---|---|---|---|---|
| off | 3,769 | 2.02% | 39.3% | 27.7% | 45.4 | 60.5 | 52.9 | 48.6 | 62.4 | 55.7 | 17.8 |
| F (AVFIRST) | 3,757 | 1.99% | 40.6% | 34.9% | 47.2 | 60.5 | 59.3 | 46.0 | 62.1 | 53.0 | 23.9 |
| FD (both) | 3,758 | 1.97% | 41.4% | 38.1% | 47.9 | 56.6 | 51.1 | 44.3 | 61.5 | 51.1 | 7.2 |

Ranges of the 8 window means per arm:

- Avenue share of path road cells: off 25.7..29.6, F 33.1..36.4, FD 37.4..39.7. The ranges do not overlap.
- Failed: off 1.80..2.24%, F 1.83..2.19%, FD 1.79..2.22%. Same range.
- Traffic average: off 57.0..65.7, FD 53.3..60.3.
- Side-street density: off 44.3..52.6, FD 40.3..48.9.

Reading:

- AVFIRST alone moves trips onto the avenues. They get busier (52.9 -> 59.3) and more avenue cells reach the
  annoyance level (17.8 -> 23.9 a month), so they start to fill up. The lighter deposit keeps them below the level
  (7.2 a month) and still draws more trips (38.1%). The traffic average drops only when both run.
- The "off" arm is not stock. Density stays from the previous windows: avenue cells that got busy under F / FD keep
  winning the stock ranking for a while. Against the never-switched baseline (2.1), off reads 27.7% instead of
  17.8..21.1%. So the switched comparison understates the change from stock.
- Trips per month barely move. AVFIRST does not change how many trips the city makes, only where they go.

### 2.3 Traffic density per cell, and the game's traffic layer

Same game: 6 months off, then FD, 6 months recorded after a 9-month settle, then off again (`ld_probe.py`;
`data/seoul_dens_off.npz`, `seoul_dens_fd.npz`, `seoul_dens_off2.npz`, class grid `data/seoul_class.npy`). Mean
density: avenue cells 43.7 (off) / 50.1 (FD) / 48.2 (off again), other used road cells 76.1 / 66.8 / 69.1.

Owner sheet `MAIN\verify\avflow\owner_shots\avflow_sheet.png`: where the avenues are, density off / on, on - off
(blue = less traffic), and the game's own traffic layer ("Capas de la ciudad > Vista de capas > Tráfico", camera
held fixed) off and on. Frames: `traffic_off.png`, `traffic_on.png`, `traffic_off2.png`. In the difference panel the
side streets turn blue and the avenues red.

### 2.4 Router cost per trip (`ld_alt.py`, batch mode)

ld_alt reads sc3perf's TRAFFIC_MT batch counters, which smooth mode does not update. So these runs used a second
instance `inst_avflow_batch` (same DLLs, `traffic_mt_smooth=0`), PID 16432, on bvlanes' Seoul save with a 39-cell
boulevard (`seoul_bv2_saved.sc3`). ABBA, 20 s windows, 6 blocks each:

| toggle | ms / trip off | on | on / off | per-block ratios |
|---|---|---|---|---|
| AVFIRST (`sc3netmod_avf_set`) | 0.03197 | 0.03444 | 1.078 | 1.004 .. 1.153, median 1.080 |
| both (`sc3netmod_avflow_set`) | 0.03337 | 0.03525 | 1.057 | 1.026 .. 1.075, median 1.056 |

Part of this is the longer paths (+5% cells per trip in 2.2). The rest is the C path on every road step.
(`data/seoulbv_alt_avfirst.json`, `seoulbv_alt_both.json`)

### 2.5 Checks

- Deposit arithmetic: avenue cells out / in = 3,189,364 / 4,784,046 = 0.66667 (1.0 M deposits, PID 19672).
  Boulevard cells 10,215 / 30,645 = 0.33333 (4,968 deposits, PID 16432).
- Class grid on the boulevard save: 3,025 avenue cells and 39 boulevard cells (the boulevard bvlanes drew on row 206).
- Faults: TRAFFIC_SMOOTH 734,472 worker trips with 0 faults (PID 19672, 32 min). TRAFFIC_MT batch 867,392 trips with
  0 faults (PID 16432). No `### avflow` exception lines.
- Default on (rebuilt, PID 20532, no env vars): the log reads `avflow: avfirst on, avdeposit on` at load, the class
  pass found 3,025 avenue cells, and deposits ran at 2/3 while the sim advanced. Frame rate in that game was 3..24
  fps: Present took 240..690 ms per second (sc3perf CSV) while SC3U used 0.36 cores and other processes on the PC used
  ~5. The same blocks ran at a median 60 fps in both earlier games (CSV), so this is the display, not the blocks.

### 2.6 Boulevard arm (parent's request: a save with a boulevard)

The only boulevard save the boulevard streams left is bvlanes' `seoul_bv2_saved.sc3`. It has one 39-cell boulevard on
row 206, x 143..159, built from the busiest road row (mean monthly density 88.6, verify/bvlanes/RESULTS.md). The other
`seoul_*` files in `inst_bvlanes` are its copies from the freeze bisect. Copy: `inst_avflow\seoulbv1.sc3`, smooth mode,
game PID 18944, launched with `SC3NETMOD_AVFIRST=0 SC3NETMOD_AVDEPOSIT=0` so the first months are stock.

Baseline, never switched (4 months, `data/seoulbv_baseline.json`): 0.53..0.63% of arrived trips used a boulevard cell,
boulevard cells were 0.21..0.27% of path road cells, density on the boulevard 40.5..42.4, 0 cells at the level.

Arms in one game, same protocol as 2.2 (24 months per arm, `data/seoulbv_abba.json`):

| arm | failed | avenue share of path road cells | game traffic avg | side streets | trips using the boulevard (24 months) | boulevard share of path road cells | boulevard density |
|---|---|---|---|---|---|---|---|
| off | 2.01% | 28.0% | 52.4 | 50.4 | 516 of 87,261 (0.59%) | 0.26% | 38.6 |
| F | 2.05% | 35.6% | 51.5 | 45.8 | 395 of 88,918 (0.44%) | 0.18% | 34.0 |
| FD | 2.06% | 39.1% | 48.3 | 44.0 | 444 of 88,928 (0.50%) | 0.21% | 19.1 |

Window ranges:
- Boulevard use: off 0.42..0.84%, F 0.22..0.61%, FD 0.35..0.63%.
- Failed: off 1.61..2.22%, F 1.86..2.18%, FD 1.94..2.21%.
- Avenue share: off 21.6..31.2, F 33.7..38.9, FD 37.3..42.0.

Reading: the avenue numbers repeat 2.2. The boulevard numbers do not move up. The 1/3 deposit halves the boulevard's
density, as built, and the deposit arithmetic holds (6,614 / 19,842 = 0.33333). But AVFIRST and the lighter deposit
do not bring more trips onto this boulevard, and the pooled share is lower with them on. About 20 trips a month use
it, so a 39-cell boulevard is a small sample. Why the share does not rise is not isolated `[UNCERTAIN]`. AVFIRST
ranks avenue and boulevard cells alike, and the trips that now stay on the 3,025 avenue cells may arrive before
they reach row 206. A per-trip trace through the boulevard's neighbours would settle it. One lever not built: rank
boulevard cells ahead of avenue cells inside AVFIRST.

### 2.7 BVFIRST: boulevard cells ranked above avenue cells (owner follow-up, 2026-10-24)

Built as a third switch inside AVFIRST (`sc3netmod_avflow.c`, `SC3NETMOD_AVF_BVFIRST=1`, live `sc3netmod_avf_bv_set`,
**off by default**). When an open boulevard candidate below the level is offered, the open avenue candidates are closed
too. With only avenue cells open, AVFIRST runs as before. Stats: `bvfirst offers` (steps with an open boulevard
candidate while it is on) and `avenue cells closed` (the steps it changed).

**Per-trip trace first** (`re/tools/netmod/bvtrace_probe.py`, both blocks on). It covers every router step at a road
cell beside the boulevard: what was offered (before ld_select closes anything) and what was taken. It also takes the
final paths that pass within 3 cells.

| save | boulevard cells | entry cells (road cells beside it) | steps there | of them with an open boulevard cell | ... and an open avenue cell too | arrived trips on the boulevard |
|---|---|---|---|---|---|---|
| seoulbv1 (bvlanes, x 145..157), 90 s | 39 | 2 (its two ends on row 206) | 1,377 | 1,193 | **0** | 186 of 26,375 (0.71%) |
| seoulbv2 (extended, x 126..188), 90 s, BVFIRST off | 189 | 7 (both ends, crossing arms at x 142 / 163 / 178) | 5,627 | 5,247 | **0** | 105 of 24,179 (0.43%) |
| same, BVFIRST on | 189 | 7 | 5,470 | 5,154 | **0** | 144 of 23,159 (0.62%) |

BVFIRST can only change a step whose node has a boulevard cell and an avenue cell as open candidates at the same time.
No such step happened. The boulevard is reached only through its two ends and its crossing roads, which are plain
roads. BV keeps an end one plain cell away from an avenue it meets side-on: the west end tapers into row 206, and
x 124 is plain road between the taper and the avenue at x 123. A first try ran the outer rows up to the avenues, and
BV refused the whole 71-column run ("an avenue arm that would stay two-way"), so it stayed with the stock tiler.

seoulbv2 (`inst_avflow\seoulbv2.sc3`, not in git) was made from seoulbv1 in game PID 21840. Rows 205 and 207 were
demolished from x 124 to 142 and from 158 to 190 (whole buildings went, some wider than the rows). Rows 205, 206 and
207 were dragged from x 124 to 190, then x 124..125 and 189..190 were demolished on rows 205 / 207 so the ends taper
into row 206. BV: "boulevard axis 0, columns 126..188 at row 205, 189 cell(s)". Saved 6/5/2000.

**ABBA, seoulbv2, one game (PID 25388), both on vs both on + BVFIRST**: blocks (FD FDB FDB FD) x 4, 4 months per
window, first month dropped, 24 months per arm (`data/seoulbv2_abba_bvfirst.json`).

| arm | failed | avenue share of path road cells | cells / trip | side streets | trips using the boulevard | boulevard share of path road cells | boulevard density |
|---|---|---|---|---|---|---|---|
| FD | 2.23% | 39.4% | 45.6 | 41.1 | 0.43% | 0.17% | 1.6 |
| FD + BVFIRST | 2.20% | 39.9% | 46.1 | 40.7 | 0.38% | 0.16% | 1.3 |

Every window range overlaps (boulevard use 0.24..0.52% in both arms, failed 2.08..2.44 vs 2.04..2.46). Over the
whole game the counter read `bvfirst offers=282,047, avenue cells closed=0`, so the router made the same decisions in
both arms. This run is an A/A test: the differences above are the noise floor of the method at 24 months per arm.

**Recommendation: BVFIRST off by default.** It cannot act where boulevards meet avenues side-on or end on plain roads,
which is every layout BV builds here. It would act only where a boulevard narrows straight into a one-way avenue
(narrowing pieces next to avenue cells), and no save has that.

What limits this boulevard is not ranking. With the blocks on, 0.4% of trips use it, and its monthly density is
1.3..1.6 against 48 on avenues. Trips enter it only at 7 cells. At those cells, 52% of the steps that offered an open
boulevard cell ended with no step at all, and 26% took a plain road. The trace reads the candidates before
sc3netmod's per-trip refused-transition list and lane closes apply, so these are likely entries against the one-way
outer rows being refused. That is not confirmed `[UNCERTAIN]`.

**Class grid fix found on the way.** Blocks write outside the edit box: BV re-runs over the whole map when a run
reaches the read border, and AVL writes a band to its far end. The class pass only re-read the edit box + 3, so after
building seoulbv2 it saw 27 of 189 boulevard cells. Now every edit pass also starts a background SWEEP of the whole
grid on the game thread, 16 rows per window message (`RB_WM + 1`, `avf_sweep_step`), restarted by each new edit.
Checked in game: demolishing one cell at (170,205) made BV revert most of the run. The edit-box pass left 132
boulevard cells and the sweep corrected that to 24 ("sweep rows 192..207: avenue cells 3126, boulevard cells 24").
After a load the class grid is exact (189 cells).

**Incident.** Game PID 14180 crashed during `rb_lab.py cam` (Frida camera call: rotate / zoom queued onto the game
thread): `VEH FAULT 0xC0000005 at 0x00002B7C`, main thread, stack SIMSPR+0xDF01 < SIMSPR+0x1CBE3, sc3overscroll on
the stack. Logs in `inst_avflow\crash_14180\`. The camera was then steered without Frida (zoom buttons, sc3io
scroll), and its state was read with nramp_cam's `hascam` after a zoom-in / zoom-out pair, with no queued call.
Not investigated further.

## 3. Not covered / open

- Commute time: not read, no such statistic found (see the verdict).
- Boulevards: measured on a 39-cell and a 189-cell boulevard (2.6, 2.7). No gain in use, and BVFIRST has nothing to
  act on there. A boulevard that narrows into a one-way avenue was not measured (no save has one).
- One city (Seoul) and one size (256). A 1024 city (Europolis, no boulevards) was not run.
- The class of a cell changed by a highway-only pass (`rb_pass` net 4, e.g. an HWAVE transition onto an avenue) is
  refreshed only by the next road pass or load.
- Long unattended runs stall at the yearly budget dialog. `re/tools/netmod/budget_closer.py` (frame dump + patch
  match + posted click) closed 21 of them in these runs.

## 4. Tools

- `re/tools/netmod/avflow_probe.py`: month-aligned arms (off / F / FD / D), final-path class share, month counters,
  density groups. Also `--set ARM`, `--grid out.npy`, `--baseline N`.
- `re/tools/netmod/avflow_report.py`: pools a run per arm, with window ranges.
- `re/tools/netmod/avflow_sheet.py`: the owner sheet.
- `re/tools/netmod/budget_closer.py`: closes the January budget dialog during long runs.
- `re/tools/netmod/bvtrace_probe.py`: router steps at the boulevard's entry cells (offered / taken) and final paths
  near it.
