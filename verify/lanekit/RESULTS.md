# lanekit: RESULTS (2026-10-13)

Pre-registration: `PRE.md`, committed `aba6825` before the first run. Tree `Simcity_stock_lanekit` (hard links of
`Simcity_stock`, `link_tree.py`: 3,488 linked). Instances `inst_lanekit` (arm) and `inst_lanekit_ctl` (control,
`SC3NETMOD_OVERLAY=0`), each with `mods_launch.exe` (sha256 `1ed3f8e4...`, the netramp build, which injects
sc3netmod.dll), `sc3resize.dll` (`d87e5b3f...`) and `sc3netmod.dll` (`7ebda2c7...`), both from
`Simcity_stock_netramp\re\harness\inst_netramp`. City: `Berlin, Germany.sc3`, a copy per instance, windowed, speed 4.
Probe: `re/tools/netmod/lk_probe.py` (read only). Every PID mine, stopped with taskkill /PID.

Deviation from PRE, setup: the first launch used `re\harness\bin\mods_launch.exe`, which injects sc3resize only (no
sc3netmod.dll, so no overlay); both PIDs (40420, 43784) were stopped after load, before any measurement.

## Arm H: the turn matrix steers the SimTransit router (PIDs 41668 arm, 17728 control)

Package `example_connects_hway_block` (overlay: one file, `OccupantAttribs.IXF` with props 310 of 73 and 15051 = 0).
The sc3netmod log of the arm reads `overlay: ON (1 file(s))`, the control's `overlay: off (SC3NETMOD_OVERLAY=0)`.
Three probe runs per instance (`probe_H*.jsonl`, `probe_C*.jsonl` in the instance folders), about 1,500 game days each.

| prediction | arm H | control | verdict |
|---|---|---|---|
| H1 `layer+0x54` = 1 | 1 (every sample) | 1 | **met**: the router asks the low half, which is the ENGLISH lanes' half |
| H2 router queries on 73 / 15051 all-false | 73: 7,026 of 7,026; 15051: 4,994 of 4,994 (last run) | 73: 0 of 21,338; 15051: 0 of 39,128 | **met** (100% vs 0%) |
| H3 highway density on the 514 straight cells <= 20% of control, pre-registered on grid `+0x6c` | `+0x6c`: 0 | `+0x6c`: 0 | **not measurable as registered**: highway nodes never deposit on `+0x6c` (below) |
| H3 on the grid highway trips deposit to, `+0x70` | 0, 0, 0, 0 (4 samples, 660 days) | 8,012 / 20,724 / 16,606 / 20,258 | met on `+0x70` (post hoc grid choice, see below) |
| control: no road-only piece queries the matrix | none (every queried piece is in HWAY_GRND_Set or is 73) | none, 87,158 calls over both first runs | **met**: plain road trips do not read it |

Whole-map `+0x70`: arm 63-289, control 21,493-45,809 (-99.4%). Whole-map `+0x6c` (surface) moved -13% in the same
samples (886,991 vs 1,024,314 at one read) and fluctuates ±15% between samples in both arms. Router queries per run:
arm 155,410 vs control 209,185 (fewer highway steps).

Why `+0x6c` was the wrong grid. `FUN_10006edd` deposits mask `& 0x35` into `+0x6c`, `& 2` into `+0x70`, `& 8` into
`+0x74`, and the route driver `FUN_100070d0` passes mask 2 for highway nodes (type 2), 0x15 for road, rail-station
and bus types, 8 for subway `[CONFIRMED @ SimTransit 0x10006edd, 0x100070d0]`. A deposit probe (60 s, both arms) saw
13,209 mask-2 deposits in the control and 120 in the arm. `transit_layer.py` labels `+0x70` "rail" from an `[iOS-HINT]`;
in this code it is the highway accumulator, and rail type 4 deposits into `+0x6c`.

Measurement trap found on the way: every SimTransit grid is `rows[save x][save z]` (the flags grid `+0x5c` reads 0x2,
"highway", on all 514 straight cells only in that order). `transit_layer.py` indexes `g[y*n + x]`, which is the
transpose: its whole-grid totals are right, its per-cell and `--rect` reads are not. The probe's second run used the
transposed order by mistake (its `cells_sum` values are not used here); the third run fixed it.


## Arm S: TrBlkAtt lanes steer the street sim (PIDs 31872 arm, 42072 control)

Package `example_lanes_t_exit_only` (overlay: the 7 TrBlkAtt containers, records of 39 states 0..3 replaced; every other
record unchanged, checked offline). Probe with `--all` (every street-sim cell transition, `FUN_1001c750`), 244 s
each, unpaused at the speed the game kept from the previous run (about 5.4 game days per second in both). Orientation of the hook's (param_1, param_2): save (x, z), settled by the exits
from T cells, which fall on the T's arms in that order (arm: 602 / 311 / 417 on arms x- / z- / z+, 46 on the side with
no arm) and not in the swapped one.

| | arm S | control |
|---|---|---|
| transitions recorded | 22,005 | 17,093 |
| into a T through its stem (local x-): ok / failed | **32 / 320** (9%) | **234 / 17** (93%) |
| into a T through z-: ok / failed | 672 / 6 | 428 / 4 |
| into a T through z+: ok / failed | 501 / 26 | 321 / 7 |
| into a T through x+ (no arm): ok / failed | 45 / 0 | 45 / 0 |
| out of a T through the stem | 602 | 374 |

- S1 (successful stem entries in the arm = 0): **not met as written**: 32, against 234 in the control. The side with
  no arm at all also returns "ok" 45 times in BOTH arms, so an "ok" return of `FUN_1001c750` is not always a lane entry:
  the arrival lookup `FUN_10020108` takes the nearest node of the class in the 72-unit bucket, which can be an exit node
  of the T. Which nodes the 32 found was not traced `[UNCERTAIN]`.
- S2 (entries through z- / z+ within 20 points of the control): **met** (99.1% vs 99.1%, 95.1% vs 97.9%).
- Not pre-registered: more cars leave T cells into the stem in the arm (602 vs 374), as the edited lanes allow.

Conclusion: the street sim's cars follow the TrBlkAtt lanes: removing the two lanes that start at the stem cut
successful entries through it from 93% to 9% while the other two arms were unchanged.


ARM_D_PLACEHOLDER
