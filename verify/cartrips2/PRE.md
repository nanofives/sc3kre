# cartrips2: PRE-REGISTRATION (2026-10-15, written before any game run of this task)

Task: milestones **M1 (trip tap)** and **M2 (lane routes)** of `re/analysis/CAR_TRIPS.md` 4.5, owner approved
2026-10-15. No visible change to the game; M3 (route cars) is out of scope. Branch `child/cartrips2` (from
`child/cartrips` + `round/1012`). Addresses are Ghidra VAs; every DLL is based at 0x10000000, so each names its module.

## Known before this file (static, cited)

- route_trip SimTransit `FUN_100070d0` (thiscall, `ret 0x1c`) pops its final path destination first: back()
  `FUN_10009e8e`, `rep movsd` into `*ebx` (`0x100072f3`), deque pop `call 0x10009eed` at **`0x100072f8`**, then the
  deposit switch on the node type, gated by the deposit flag `[ebp+0x14]` AND `FUN_10008c5b(occupant)`
  `[CONFIRMED @ SimTransit 0x100072d8..0x10007554]`. Deposits per node type, read from the switch: 1, 0x14, 4, 0x50 ->
  every cell of the node rect once, mask 0x15; 2 -> mask 2; 8 -> mask 8; 0x18 / 0x30 -> mask 0x15 then mask 8 (the
  0x18 / 0x30 branch falls into `LAB_100074ce`); 0x80, 3, 0x41, 0x42, 0x43 -> none `[CONFIRMED @ SimTransit
  0x1000731b..0x10007510]`. Deposit call sites `call 0x10006edd` (thiscall, stack x, z, amount, mask): `0x100073b2`,
  `0x100073f8`, `0x10007463`, `0x100074be`, `0x10007500`. The deposit loops reuse the arg slot `[ebp+0x20]`
  (`0x10007393`), so route_trip's args are read at the first pop.
- route_trip has two callers, `FUN_10006fe3` (trip function) and `FUN_1000706a` (trip from a cell), both with an
  `ebp` frame; their callers reach them through the layer vtable (no static caller in the exports).
- The STRTSIM layer's animation tick `FUN_10012e46` (game thread, `esi` = layer + 8) calls the car producer tick with
  `call 0x1001f44a` at **`0x10012e8a`**; the sim rect is layer `+0xb0..+0xbc`, its grown view box `+0x90..+0x9c`
  `[CONFIRMED @ STRTSIM 0x10012e46; CAR_TRIPS 1.1]`.
- Ring scan selection (`FUN_1000755e`, decompilation of the type-1 branch): a road candidate with congestion byte
  `+0x6c` below `DAT_1001f0c0` replaces the kept one **unless its byte is lower than the kept one's**; a station
  candidate (flags `& 0x10`) sets the kept byte to 0xff. Read mechanically: the most congested candidate under the cap is
  kept. PERFORMANCE.md Finding 22 says "least congested". Not checked live before this task `[UNCERTAIN]`.
- Phase 1 (verify/cartrips): a Frida native listener on the call instruction `0x100072f8` faulted the game even when
  empty; the capture cost measured offline was 10.0-10.5 ns per node (`capbench.c`).

## Build under test

`sc3cartrips.dll` (`re/harness/src/sc3cartrips.c`, built with `re/scripts/build_mod.ps1 -Mod sc3cartrips`), SHA-256
prefix **c392ccbc**; `mods_launch.exe` with `sc3cartrips.dll` added to its mod list, **88452c54**. Both built into
`Simcity_stock_pausetrips\re\harness\build_ct2`. What the DLL does (detail in the source header):

- **CAPTURE**: `0x100072f8` `call 0x10009eed` -> `call pop_stub` (one locked 8-byte exchange, shipped bytes checked
  `f3 a5 8d 4d 80 e8 f0 2b 00 00 80 7d 14 00`). The stub saves every register, appends the node copy in `ebx` to a
  per-thread buffer (TLS, up to 8,192 nodes), and jumps to `0x10009eed`. On the origin pop (type 0x80) the trip is
  counted, and a trip with a node meeting the sim rect (**viewport trip**, the phase-1 definition: node rect meets the
  rect, bounds inclusive) goes into a lock-free MPSC ring (1,024 slots; full -> counted drop) with its in-view window
  (+1 node each side, up to 256 nodes), the destination and origin nodes, the route_trip args (flag, dest kind, three
  mode bytes) and two return addresses (route_trip's caller, and that caller's caller).
- **DRAIN**: `0x10012e8a` -> `call tick_stub` (bytes checked `ff 75 08 e8 bb c5 00 00 53`): on the game thread it
  publishes the sim rect (empty rect -> a virtual 33 x 28 rect at the view centre, phase-1 addendum 2) and drains the
  ring into a 256-trip queue of the newest viewport trips, then jumps to `0x1001f44a`.
- **VERIFY** (`verify=1`, measurement): the five deposit call sites go through a stub that attributes each deposit cell
  to the node popped last on that thread. Per trip: `dep_outside` = deposits outside that node's rect; per node,
  `full` = deposit calls equal the table above (area, or 2 x area for 0x18 / 0x30), `gated` = 0 calls where the table
  expects some (`FUN_10008c5b` false), `bad` = anything else; an unflagged trip with a deposit is bad.
- **TIME** (`time_route=1`, measurement): route_trip's entry `mov eax, 0x100189b4` -> `jmp time_wrap`, which reads the
  TSC around the call (per-thread cycles and calls).
- **CHOICE** (`choice=1`, measurement): on unflagged trips, for each road step a -> b (both type 1, 1 x 1, adjacent),
  a's four neighbours' flags (`+0x5c`) and congestion bytes (`+0x6c`) are read at a's pop; the step is scored among a's
  road neighbours (flags & 1, not & 0x10) other than a's predecessor, under the cap: b is the max / the min / between /
  all equal / the only candidate / not a candidate.
- `sc3cartrips_set(0|1)` writes the shipped call or the stub call back at `0x100072f8` (one locked 8-byte exchange);
  `sc3cartrips_stats` returns the cumulative counters. Tool `re/tools/ctm_alt.py` (ABBA, the `ld_alt.py` method).
- Log `sc3cartrips.log`: every `log_s` seconds `STAT>` (paths, nodes, flagged, road-only / mixed / transit-only,
  viewport trips, commits, drops, drained, queue, drain latency, threads), `TYPES>`, `VERIFY>`, `CHOICE>`, `TIME>`;
  every 6th period `CALLER>` (trips by caller pair, dest kind and mode bytes). `dump=1` writes every drained trip to
  `cartrips_trips.bin` (reader `re/tools/ctm_read.py`).

## Setup

- Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips` (stock DLLs): SC3U.exe 49dd55e1, SimTransit
  b478ded4, STRTSIM c02ce38f.
- `inst_ct2_stock`: mods_launch 88452c54 + sc3resize 43cb5059 (P and speed keys) + sc3cartrips c392ccbc. Stock routing
  threads (no sc3perf).
- `inst_ct2_full`: mods_launch 88452c54 + sc3resize 43cb5059, sc3bigcity 76a83845, sc3overscroll a5b69ca3, sc3perf
  0f47ac9d (perf.ini 2b9708f0: traffic_mt=8, traffic_mt_smooth=1), sc3simrun 7ba79a07 (FREEZE, the owner-tested
  build), bigcity.ini 1eda071c, + sc3cartrips c392ccbc.
- Cities: `Berlin, Germany.sc3` 99327775; `Moscow, Russia.sc3` aad23a35; `London, England.sc3` 49d55241 (the
  shipped city with the most avenue tiles: 5,067 of piece 11204); `verify/perf1024/europolis1024_v2_test.sc3` 9ce07478
  (Europolis 1024; its Europolis source has no avenue).
- `cartrips.ini` per arm (below), written into the instance before its launch. Driver `re/tools/ct_run.py` (pt_run's
  launcher and key driver; `CT_GROUPS` selects the ct_probe hook groups, `none` = no hook, state reads only). One game
  at a time, `mods_launch.exe -multi`, harness claimed by `cartrips2`, only the started PID killed.
- First 3 s of each phase dropped. A fault = a non-`system` exception reported by the probe's handler, or the game
  gone before the end of its schedule.

## M1 arms

| arm | instance | city | cartrips.ini | probe | schedule (s) |
|---|---|---|---|---|---|
| K (smoke, not counted) | stock | Berlin | capture, verify, dump, choice, time_route | CT_GROUPS=none | `s3:40,s4:40,P:10` |
| A1 | stock | Berlin | capture, verify, dump, choice | CT_GROUPS=rt,pop (ct_probe's trip counters + 1-in-5 samples) | `s1:60,s2:60,s3:90,s4:90,P:30` |
| V2 | full (`--safe`) | Europolis 1024 | capture, verify, dump | none | `s3:120,s4:120` (settle 90) |
| F1 | stock | Berlin | capture only (production) | none | `s3:600,s4:1200` |
| F2 | full (`--safe`) | Europolis 1024 | capture only | none | `s3:900,s4:900` (settle 90) |
| C1 | stock | Berlin | capture, time_route | none; `ctm_alt.py` attached | `s4:1500`; ctm_alt `--warmup 60 --window 30 --settle 2 --blocks 10` |
| C2 | full (`--safe`) | Europolis 1024 | capture, time_route | none; `ctm_alt.py --perf` | `s3:1500` (settle 90); same ctm_alt |

### Predictions (M1)

1. **A1 count**: in every running phase, the DLL's viewport trips per second are within 5% of ct_probe's for the same
   seconds (same game, same definition); paused: 0 paths.
2. **A1 paths**: >= 99% of ct_probe's complete samples (paths <= 128 nodes) are found in the DLL's dump with the same
   destination, origin, length and identical node cells and types over the stored window.
3. **Deposits (A1, V2)**: `dep_outside` = 0, `nodes_bad` = 0, `unflagged_with_dep` = 0, so every trip is exact.
4. **Faults (all arms)**: 0; every game alive to the end of its schedule. `ARMED` line shows capture=1 drain=1 (and
   verify=5/5 where on).
5. **Threads**: V2 / F2 log >= 9 routing threads (8 workers + the sim thread); A1 / F1 one routing thread, or two
   when the trip-from-cell caller runs elsewhere.
6. **Ring**: drops = 0 in A1 and F1 (Berlin view, <= 25 viewport trips/s); V2 / F2 drops reported only.
7. **Cost (C1, C2)**: pooled routing TSC cycles per route_trip call, capture on / off, <= 1.05 (the task's bound; the
   design's A2 bound +2% is reported against too). C2 also reports sc3perf's worker ms per trip on / off.

Measured only (no prediction): paths/s, nodes/s, viewport paths/s, by mode, drain latency, trips by caller pair and
flag (the unflagged ~60%, CAR_TRIPS 5), the CHOICE scores (A1).

## M2 (lane routes), registered now; the solver and its exact rules are written before the arms that test them

- Data: the dumped trips of A1 / V2 and of two more arms, **M2a** (Moscow) and **M2b** (London), both
  `inst_ct2_stock`, `capture, dump`, CT_GROUPS=none, `s3:120,s4:120`, default camera.
- A route = the in-view window of a dumped trip, travel order (origin first), road / highway / ramp nodes (types 1, 2,
  3); a mixed trip contributes each maximal road run. "Fully drivable as routed" = every middle step passes the
  piece's lane turns (the phase-1 rule, `ct_lanefeas.py`). "Drivable after corridor solving" = the solver finds a lane
  path from a lane entering the first route cell to a lane leaving toward (or ending in) the last one, through cells of
  the corridor only.
- An addendum before the M2 arms fixes: the lane-graph source (in-memory dump from the DLL, or TrBlkAtt + the save's
  network layer), the corridor definition, the failure reasons, and the in-DLL vs offline match test.
