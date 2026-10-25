# bventry: why trips do not use the boulevard (2026-10-24 / 25)

Question from avflow 2.7: on seoulbv2 (189-cell boulevard on rows 205..207, x 126..188) the boulevard carries ~0.4% of
trips at monthly density 1.3..1.6, against 48 on avenues. At its 7 entry cells, 52% of the router steps that offered an
open boulevard cell ended with no step and 26% took a plain road. The guess was that entries against the one-way outer
rows, or the turn matrices at the ends / crossings, are refused.

**Verdict: no entry is refused.** The boulevard pieces let trips in and out the right way. The "no step" outcomes are
the DFS coming back after the boulevard branch failed, and through-trips fail there no more often than on a plain road
in the same district (86% of branches on the boulevard, 86% on the plain road six rows north, section 2.3). Two things
keep the boulevard empty. (1) Its neighbourhood: every cell lies inside the kind-0 destination radius and outside
kinds 1 and 2, so it is a through corridor for the trips that reach it. (2) The trip START, which is boulevard-specific:
a lot's first step takes the busiest road in range, so the empty boulevard loses most of its own neighbours' starts and
stays empty (section 2.5). The layout is already the realistic one: the blocks beside the boulevard are zoned and built
as in the original Seoul (section 2.4), so no seoulbv3 was needed.

Three levers were built, each with its own switch, and measured in one game, 24 months per arm (section 3):

| lever | trips using the boulevard | failed trips | default |
|---|---|---|---|
| none (main: AVFIRST + AVDEPOSIT) | 0.32% | 2.32% | |
| AVSTART: avenue-first at the trip start | 0.69% | 2.29% | off, **recommended on** |
| BVCOST: boulevard step cost x 1/2 | 0.40% | 2.38% | off |
| AVCOST: avenue step cost x 1/2 | 0.50% | 1.97% | off (owner call) |

Tree `Simcity_stock_bventry`, instance `inst_bventry`, all eight mods built from the worktree (main a4e45fb + this
task), sc3perf as the owner has it. City `Cities\seoulbv2.sc3`. Addresses: SimTransit.dll, Ghidra VAs.

## 1. What the router does on and beside the boulevard

`re/tools/netmod/bventry_probe.py` (Frida, read-only) hooks select_next `FUN_1000755e` behind sc3netmod's detour. It
records every call for a 1x1 road node within 3 cells of the boulevard: the cell, the entry side and the outcome. The
outcome is the exit side taken, `budget` (param_3 < node cost +0x18, the function's first test, goto 0x1000847c) or no
step. For every boulevard cell it also reads the piece id, its state and the four matrix rows, with the same call
sc3netmod's ld_eval makes (QI 0x41658d28, piece vt+0x4c(0, layer+0x54, entry side)). Game PID 23140, 60 s, both avflow
blocks on (`data/trace1.json`).

Matrix rows, world frame (entry side -> allowed exits; x- = from x-1):

| cells | piece | rows |
|---|---|---|
| row 205, x 128..186 | 20700 (state 2) | from x-: x+ only |
| row 206, x 128..185 | 20701 / 20702 (state 0), 20721 / 20702 (state 2) | from x-: x+; from x+: x- |
| row 207, x 128..186 | 20700 (state 0) | from x+: x- only |
| (142,205) T | 20707 | from x-: z-, x+; from z-: x+, z+; from z+: z- |
| (142,206) T | 20708 | from x-: x+; from z-: x-; from x+: x-, z- |
| (163,205), (178,205) crossing | 20710 (state 0) | from x-: z-, x+, z+; from z-: x+, z+; from z+: z- |
| (163,206), (178,206) crossing | 20711 | from x-: x+, z+; from z-: x-, z+; from x+: x-, z-; from z+: z-, x+ |
| (163,207), (178,207) crossing | 20710 (state 2) | from z-: z+; from x+: x-, z-, z+; from z+: x-, z- |
| west taper (126..127, 205..207) | 20725, 20724, 20727, 20723 | (125,206) -> (126,206) -> (127,206) -> row 205 or middle; row 207 -> (127,206) -> (126,206) -> (125,206) |
| east taper (186..188) | 20720, 20723, 20724, 20727, 20722, 20725 | row 205 -> (187,206) -> (188,206) -> (189,206); (189,206) -> (188,206) -> (187,206) -> row 207 or middle |
| corner caps (188,205), (188,207) | 20726, 20728 | all rows 0 = no lane data, unconstrained (ld_eval) |

Every entry the router made onto a boulevard cell was allowed by these rows. Over 60 s, the boulevard cells took
x+ 9,265, x- 9,859, z+ 1,089, z- 876 steps. The other outcomes were 20,301 calls with no step, 1,242 over budget
and 0 wrong-way refusals on cells with lane data (section 5 on the 9 calls the probe labels `wrong` at the two corner
caps). sc3netmod logged no "step through a closed side".

The no-step calls pair one to one with the steps: on every plain boulevard cell, steps out = calls with no step (for
example (150,205) from x-: 94 steps x+, 89 + 2 budget no step). The DFS stack in route_trip `FUN_100070d0` retries a
node after the branch below it failed, and on the retry the cell it took is visited, so a corridor cell has nothing
left. At the entry cells it is the same: (142,204) from z- has 94 steps onto the boulevard and 93 retries with nothing
left. The "26% plain road" are retries where the entry cell had another road to try. So the 52% / 26% split from avflow
2.7 measures how often the boulevard branch failed, not refusals.

## 2. Why the boulevard branch fails

`re/tools/netmod/bvbranch_probe.py` (Frida, read-only) follows each trip. A branch starts when a step goes from a
non-boulevard cell A onto the boulevard. It ends when select_next is called again for A (the branch failed) or when
the trip arrives with the branch open (its final path uses the boulevard). Inside a branch every select_next outcome
is counted, and the cost / budget ratio is tracked. It also reads the destination bitmaps that the arrival test
`FUN_10008a94` uses: layer+0x84 / +0x88 / +0x8c, one per trip kind (route_trip param_2). `FUN_1000559e` sets a bit
for every cell within a per-kind radius (layer+0xc5 / +0xc6 / +0xc7) of a destination lot.

### 2.2 Boulevard vs the same corridor with stock pieces

Two games side by side for 90 s on the same save (`data/branch_bv_on.json`, `branch_bv_off.json`): PID 30112 with every
default, and PID 17912 with `SC3NETMOD_BV=0`. With BV off the three rows stay as the stock tiler left them (stock
pieces, two-way, sideways hops allowed; the class pass counted 3,139 avenue cells instead of 3,031). The corridor is
the same box, x 126..188, z 205..207, in both.

| | BV on (boulevard) | BV off (stock pieces) |
|---|---|---|
| trips routed / arrived | 14,979 / 14,681 | 16,000 / 15,665 |
| branches into the corridor | 756 | 971 |
| ... the trip arrived on it | 108 (14%) | 116 (12%) |
| ... failed back to the entry cell | 647 (86%) | 855 (88%) |
| failed branches that ran over the trip budget | 367 (57%) | 494 (58%) |
| select calls per failed branch | 188 | 209 |
| arrived trips with a final-path cell in the corridor | 65 (0.44%) | 87 (0.56%) |
| ... by kind 0 / 1 / 2 / 3 | 0 / 41 / 24 / 0 | 0 / 47 / 40 / 0 |
| trips entering, by kind 0 / 1 / 2 / 3 | 0 / 72 / 684 / 0 | 0 / 76 / 895 / 0 |

Destination bitmaps (radius 4 / 3 / 5 cells for kinds 0 / 1 / 2): all 189 corridor cells have the kind-0 bit and none
has the kind-1 or kind-2 bit. Over all road cells: kind 0 69%, kind 1 42%, kind 2 13%.

Reading:

- Kind-0 trips (30% of trips) and kind-3 trips (7%) never reach the corridor. The cells around it already carry the
  kind-0 bit, so those trips arrive before they get there.
- Kind 1 and 2 trips have no destination within 3 / 5 cells of the boulevard, so for them it is only a way through.
  AVFIRST sends them onto it as soon as it is offered. 86% of those branches fail, more than half by running out of
  budget somewhere beyond the boulevard, and the trip then finds its destination through another branch.
- Building the boulevard took the 117 residential cells of rows 205 / 207 that lined row 206. Those lots started and
  ended the trips behind row 206's former density (88.6 a month). The blocks beyond them are still there (2.4).
- The BV pieces do not change this: the stock-piece corridor fails 88% of its branches and carries 0.56% of trips.
  The difference between the two games is within the between-game spread (memory perf-between-game-noise).

### 2.3 Control: a plain road in the same district

Same probe with `--box` on two plain roads parallel to the boulevard, same 63 columns, game PID 18280, 90 s
(`data/branch_row199.json`, `branch_row212.json`; both probes ran at once, so their final-path counts are not used):

| corridor | branches in | failed | over budget (of failed) | select calls per failed branch |
|---|---|---|---|---|
| boulevard rows 205..207 (2.2, PID 30112) | 756 | 647 (86%) | 57% | 188 |
| plain road row 199, 6 rows north | 787 | 679 (86%) | 72% | 221 |
| plain roads rows 212..213, 5 rows south | 518 | 276 (53%) | 65% | 304 |

Through-trips into this residential district fail at the same rate whether they enter the boulevard or a plain road.

### 2.4 The layout (the orchestrator's seoulbv3 request)

Zone rasters read with `re/tools/city_write.py`. The raster is transposed and flipped against game coordinates: game
(x, z) = `zone_get(z, 255 - x)`. Original `Seoul, Korea.sc3` vs `seoulbv2.sc3`: 117 cells differ, all residential
slot 2 -> 0, all on rows 205 / 207 between x 124 and 190. These are the cells under the boulevard's outer rows plus 8
taper-end cells. Rows 200..204 and 208..211 beside it are still slot 2 as in the original. `place_direct.py dump`
(occupants, game PID 18280) shows them built: buildings on nearly every cell, a few zoned empty cells on rows 203 / 204.
So seoulbv2 already is a boulevard through zoned, built blocks, which is what a player gets. A seoulbv3 could only
re-zone the 8 taper-end cells, so it was not made, and every measurement below is on seoulbv2.

### 2.5 The trip start (boulevard-specific)

A trip's start node (type 0x80, the lot) goes through FUN_1000755e's start branch. It scans every road cell within r
of the lot rect, corners excluded, where r = layer+0xc5 / +0xc6 / +0xc7 by the lot's kind from FUN_100057f6, else
+0xc8. The keep rule is the ring scan's: a road candidate below TrafficAnnoyanceLevel replaces the kept one unless its
density byte is lower `[CONFIRMED @ 0x1000755e, start branch]`. FUN_100057f6 is a thiscall on the layer (`mov edi, ecx`
... `ret 8`, `[CONFIRMED @ 0x100057f6]`). AVFIRST never acts there: sc3netmod's ld_select passes type 0x80 straight to
the game.

`re/tools/netmod/bvstart_probe.py` (Frida, read-only), game PID 5756, 40 s per arm (`data/start_bv2_fd.json`,
`start_bv2_fds.json`). It counts starts whose scan box holds a boulevard cell, almost all residential lots (radius 4).

| | starts with an open boulevard cell in range | took the boulevard | an avenue | a plain road | density taken / best boulevard cell |
|---|---|---|---|---|---|
| FD (main) | 483 | 183 (38%) | 125 | 172 | 57.6 / 10.2 |
| FD + AVSTART | 559 | 373 (67%) | 175 | 0 | 33.8 / 16.5 |

The houses that line the boulevard start most of their trips on busier roads nearby, so the boulevard stays empty.
A first version of this probe called FUN_100057f6 as cdecl, and its numbers were dropped.

## 3. Levers: AVSTART, BVCOST, AVCOST

All three live in `sc3netmod_avflow.c` (`/* task bventry */`) and hook into ld_select (`sc3netmod_lanes.c`).

- **AVSTART** (`SC3NETMOD_AVSTART`: 1 = avenue and boulevard cells, 2 = boulevard cells only, 0 = off; live
  `sc3netmod_avs_set`). For a start node, the game's own kind call gives the radius. When an open avenue / boulevard
  cell below the level is in range, every other open road cell in the box is closed in the visited grid for that one
  call (stations stay), and the bits are cleared after it. The stock rule then takes the busiest open avenue /
  boulevard cell. **Default off in code** (orchestrator call), recommended on.
- **BVCOST** (`SC3NETMOD_BVCOST=1`, scale `SC3NETMOD_AVCOST_BV=n/d`, default 1/2; live `sc3netmod_avc_set`). A step
  onto a 1x1 boulevard cell costs n/d of its stock cost (rounded up, at least 1). A road step costs density / 25 + 4
  (`DAT_1001f0c1` = 25, `DAT_1001f0b0` = 4, set at 0x10008468). The trip budget is `DAT_1001f0b0 x param_3`, checked
  first thing in FUN_1000755e `[CONFIRMED @ 0x1000755e, 0x100070d0]`. **Default off.**
- **AVCOST** (its own switch, `SC3NETMOD_AVCOST=1`, scale `SC3NETMOD_AVCOST_AV=n/d`, default 1/2; live
  `sc3netmod_avc_av_set`). Same for avenue cells. **Default off.**

### 3.1 ABBA, four arms, one game

Game PID 5756 on seoulbv2. Funds were set to $50,000,000 first (`set_funds.py`), because a previous run went bankrupt and
the mayor was fired at month 85. `avflow_probe.py --arms FD,FDC,FDA,FDS --blocks 4 --mpw 4 --settle 1`: windows FD FDC FDA
FDS FDS FDA FDC FD x 4, first month of each window dropped, 24 months per arm (`data/seoulbv2_abba4.json` / `.log`).
sc3perf routed 604,055 background trips with 0 faults. The probe also counts, per month, select_next calls that fail
on the budget (param_3 < node cost), trips that hit it at least once, and failed trips that did.

| arm | failed | trips using the boulevard | boulevard path share | boulevard density | trips touching an avenue | avenue path share | cells / trip | avenue density | game traffic avg |
|---|---|---|---|---|---|---|---|---|---|
| FD | 2.32% | 291 of 89,781 (0.32%) | 0.32% | 3.6 | 42.0% | 40.5% | 46.6 | 49.0 | 46.0 |
| FDC (BVCOST) | 2.38% | 356 of 89,809 (0.40%) | 0.47% | 4.3 | 42.2% | 40.3% | 46.1 | 50.0 | 46.6 |
| FDA (AVCOST) | 1.97% | 442 of 89,003 (0.50%) | 0.47% | 5.0 | 42.6% | 42.4% | 50.4 | 55.6 | 49.7 |
| FDS (AVSTART) | 2.29% | 622 of 90,378 (0.69%) | 0.75% | 8.8 | 47.4% | 41.5% | 46.7 | 52.1 | 47.1 |

Budget, citywide:

| arm | trips that hit the budget | failed trips that hit it | select calls failing on it |
|---|---|---|---|
| FD | 9.7% | 54.6% | 3.32% |
| FDC | 9.8% | 55.6% | 3.41% |
| FDA | 8.1% | 46.2% | 3.05% |
| FDS | 9.9% | 53.5% | 3.33% |

Window ranges (8 windows per arm):
- boulevard use: FD 0.17..0.61%, FDC 0.15..0.74%, FDA 0.27..1.00%, FDS 0.53..1.04%
- trips touching an avenue: FD 40.5..43.7%, FDC 40.7..43.3%, FDA 40.6..44.0%, FDS 46.2..48.6% (no overlap with FD)
- failed: FD 2.00..2.51%, FDC 2.10..2.57%, FDA 1.79..2.18%, FDS 1.94..2.60%
- trips hitting the budget: FD 8.3..10.7%, FDA 6.9..8.8%
- cells per trip: FD 44.9..48.9, FDA 47.8..53.4
- wall time per game month (probe attached, median): FD 12.4 s, FDC 12.8, FDA 12.9, FDS 12.6

Reading:

- **AVSTART** doubles the boulevard's use (0.32 -> 0.69% of trips, path share 0.32 -> 0.75%, density 3.6 -> 8.8). It
  also raises the share of trips that touch an avenue from 42.0 to 47.4%, with ranges apart. Failed trips, path
  length, the budget figures and month time stay the same. It meets the bar (more boulevard trips, no rise in failed
  trips), so the recommendation is **on**. The code default stays off until the orchestrator / owner decide.
  Start side: avenue density 49.0 -> 52.1 with fewer avenue cells at the annoyance level (9.5 -> 8.5 a month). For
  starts with a boulevard cell in range (2.5), starts with no first step were 9 of 507 (FD) and 14 of 714 (AVSTART).
  A citywide count of starts that fail was not taken.
- **BVCOST** at 1/2 moves the boulevard a little (0.32 -> 0.40%) with overlapping ranges, and failed trips rise 0.06
  point. The two earlier BVCOST-only games (below) agree. It stays **off**.
- **AVCOST** at 1/2 is a citywide change. It lowers failed trips (2.32 -> 1.97%) and budget hits (9.7 -> 8.1% of trips,
  failed trips that hit the budget 54.6 -> 46.2%). In exchange, paths get 8% longer (46.6 -> 50.4 cells), avenues get
  busier (49.0 -> 55.6, avenue cells at the level 9.5 -> 12.8 a month) and the game's traffic average rises 46.0 -> 49.7.
  The result is mixed, so it stays **off** for the owner to decide.

Earlier BVCOST-only ABBA (two games, FD vs FD + BVCOST, 24 months per arm, run before the fault counter was checked):
boulevard use 0.26 -> 0.36% (scale 1/2, PID 1880) and 0.36 -> 0.43% (1/4, PID 6164). Failed 2.04 -> 2.05% and 2.01 ->
2.10%. Every window range overlapped (`data/seoulbv2_abba_bvcost.json`, `seoulbv2_abba_bvcost14.json`).

### 3.2 Bugs found on the way (fixed before 3.1)

- AVSTART's 5 KB of buffers sat on ld_select's stack. With every switch off, sc3perf's background trips faulted from
  the first minute (32,014 faults by 164 s, PID 10760). With the buffers moved to a per-thread heap block there were 0
  faults (PID 22368). The first 4-arm run (PID 10760) was dropped for this.
- AVSTART first called FUN_100057f6 as cdecl. It is a thiscall that pops its own arguments (`ret 8`), so the call
  left the stack off and starts faulted (53,421 faults in two minutes). Fixed to thiscall on the layer.
- `re/tools/place_direct.py`: `Module.getExportByName` no longer exists in the installed Frida, so the script failed to
  load. It now uses `Process.getModuleByName(...).getExportByName`. Its game calls now use exceptions 'propagate'
  (memory project-rblab-cam-zoom-deadlock).

### 3.3 Owner frames

The game's traffic layer ("Capas de la ciudad > Vista de capas > Tráfico"), seoulbv2, camera on x 157, z 206, zoom 1,
in `MAIN/verify/bventry/owner_shots/`. The boulevard is the 3-cell band through the middle.
- `traffic_avstart_off.png` / `traffic_avstart_on.png` (game 5756): main defaults, then 6 months of AVSTART. Part of the
  band picks up colour. A density of 8.8 is still low on the game's scale.
- `traffic_bvcost_off.png` / `traffic_bvcost_on.png` (game 1880): BVCOST 1/2, no visible change.
- `boulevard_view.png`: the same view without the layer.

## 4. Open

- No launch check of the final build ran (AVSTART default off, recommended on). At 02:15 Windows Defender flagged the mod loader
  `Apps\version.dll` as `Program:Win32/Contebrew.A!ml` (ThreatID 251873) and now blocks reading it. The file is
  hard-linked, so `Simcity_stock_bventry`, `Simcity_stock_avflow` and `Simcity_release` are all affected, and
  mods_launch refuses to start ("not the sc3kre mod loader"). Reported to the orchestrator. Defender was not touched.
- AVSTART was measured on one city (Seoul, 256). A 1024 city was not run. Cost: no change in wall time per game month
  (12.4 vs 12.6 s). Router time per trip was not measured with ld_alt.
- Game PID 18280 exited at 00:34 with no fault line in any mod log and no Application error event. Not traced
  `[UNCERTAIN]`.
- Raising boulevard use further needs destinations along it: commercial or industrial zones within 3 / 5 cells (the
  kind 1 / 2 radii).

## 5. Tools and data

- `re/tools/netmod/bventry_probe.py`: per boulevard / neighbour cell and entry side, every router step outcome, and
  each boulevard piece's matrix rows read through the game's own call.
- `re/tools/netmod/bvbranch_probe.py`: per trip, branches into the boulevard (or a `--box`), how they end, budget
  headroom, final-path use by trip kind, and the destination bitmaps.
- `re/tools/netmod/bvstart_probe.py`: trip starts with a boulevard cell in range, what they were offered and what
  they took.
- `avflow_probe.py` / `avflow_report.py`: arms FDC, C, FDA, FDCA, FDS, FDS2, and the per-month budget counters.
- `re/tools/place_direct.py`: the Frida API fix above.
- Data (`verify/bventry/data/`): `trace1.json` (1); `branch1.json`, `branch_bv_on/off.json` + .txt (2.2);
  `branch_row199/212.json` + .txt (2.3); `start_bv2_fd.json`, `start_bv2_fds.json` (2.5); `seoulbv2_abba4.json` + .log
  (3.1); `seoulbv2_abba_bvcost.json`, `seoulbv2_abba_bvcost14.json` + .log (3.1, earlier runs).
- Note on bventry_probe's `wrong` label: it is set when the piece's row for the entry side is 0. On the two corner caps
  20726 / 20728 all rows are 0, which ld_eval treats as unconstrained, so their 9 `wrong` calls are plain no-step calls,
  not refusals.
