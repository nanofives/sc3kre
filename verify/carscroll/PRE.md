# carscroll: PRE-REGISTRATION (2026-10-16, written before any game run of this task)

Owner request 2026-10-16: "can we work on keep the car movement when the camera is moving?" Today every street agent
(cars, trains, subway, people, boats, aircraft) freezes while the camera moves, even with sc3simrun (days and trips keep
running). Branch `child/carscroll` (from `child/cartrips2`). Addresses are Ghidra VAs; module named on each.

## Known before this file (static, cited)

- Chain that animates the agents (STRTSIM.md 8): SIMSPR view tick `FUN_10042a95` -> render view `[+0xb4]->vt+0x20` ->
  SC3U heartbeat `FUN_00426140` -> agent loop `FUN_00425a10` -> each agent's `vt+0x100`.
- **The render view is SIMSPR vtable `0x10063390`.** Slot `+0x20` = `FUN_1001cab9` (the frame): it calls the heartbeat
  `[+0x15c]->vt+0x18` (return `0x1001cb09`, the frame the pausetrips backtraces show) **only while byte `+0x2b` is set**,
  then renders `[CONFIRMED @ SIMSPR 0x1001cab9]`. Slot `+0x7c` = `FUN_1001d65d(&rate)`: `+0x70 = rate`,
  `+0x2b = (rate >= 0.1f)` (`0x10063504` = 0.1f) `[CONFIRMED @ SIMSPR 0x1001d65d]`.
- The idle branch of the view tick passes rate 60.0 (`0x42700000`) to `+0x7c`, then calls `+0x20`
  `[CONFIRMED @ SIMSPR 0x10042a95]`. **The scroll step `FUN_10043daf` passes 0.0** (`fldz; fstp [ebp-8]` at
  `0x10044003`, `call [eax+0x7c]` at `0x1004400b`) after moving the camera (`vt+0x34`), then calls `+0x20` itself at
  `0x1004403d` `[CONFIRMED @ SIMSPR 0x10043daf, bytes 0x10043ffa..0x1004400e]`. So during a camera move the frame is
  rendered every tick but without the heartbeat. This is the second cause in the brief, made precise: the view tick's
  busy branch does render (inside the scroll step); what it skips is the heartbeat, through `+0x2b`.
- Every camera-scroll kind goes through that one scroll step: drag / held right button (outer `+0x1e6`, deltas
  `+0x1f4/+0x1f8`), arrows and edge bands (outer `+0x1e1..+0x1e4`, polled keys `0x25..0x28` and band flags) — the busy
  bytes the view tick tests (`+0x1dd..+0x1e2` inner = outer `+0x1e1..+0x1e6`). Overscroll (sc3overscroll) and bigcity
  only change the camera bounds; their camera moves are the same scroll step.
- **Zoom and rotate** (`FUN_10042d8a`, `FUN_10042f27`, `FUN_100430c4`, `FUN_100432aa`, `FUN_100433f5`, `FUN_10043540`,
  `FUN_10043662`, `FUN_10043844`) each pass 0.0 and then 60.0 to `+0x7c` inside one call, without calling `+0x20` in
  between `[CONFIRMED @ SIMSPR, each function]`: no frame is rendered with the rate at 0, so nothing to change. (Their
  own momentary camera hold is left as sc3simrun leaves it; zoom below the birth zoom still removes every car, stock.)
- The first cause (stock camera hold suspends the heartbeat, `+0xb0`) is already removed for scroll steps by
  sc3simrun's `0x1004401a` patch. So the change needs `run_while_scrolling=1`.
- Camera-driven car changes (STRTSIM, `CAR_TRIPS.md` 1.1/1.3): ProcessViewChange `FUN_10013e66` runs only when the
  view's centre cell moved by 2 or more (or zoom/rotation changed); UpdateVehicleView `FUN_10015415` removes the cars on
  the strips that left the sim rect (AnimOccMan `vt+0x58`, outside the new view + 2 cells) and calls PutVehiclesInRect
  `FUN_1001f040` **over the whole new rect** once per new strip; it places cars row by row from the rect's first corner
  until `alive > target` or 200 `[CONFIRMED @ STRTSIM 0x10015415, 0x10014d85, 0x1001f040, 0x1001f112]`. sc3cartrips
  replace mode skips both PutVehiclesInRect calls. None of this depends on the heartbeat, so the patch should not
  change it; what changes is that cars now also drive (and stock cars density-despawn, route cars spawn) during moves.

## The change (build under test)

sc3simrun: new ini key `[sim] animate_while_scrolling=1` (default on; 0 = today). When on (and `run_while_scrolling=1`),
the 5 bytes at SIMSPR `0x10044003` become `call anim_stub`, which writes `g_scroll_rate` (60.0, the idle tick's value)
into `[ebp-8]`. Expect-or-refuse on the 20 bytes at `0x10043ffa`. FREEZE is untouched: it skips frozen agents inside the
agent loop whatever drives the heartbeat. Measurement exports: `sc3simrun_animate(on)` switches the written rate between
60.0 and 0.0 at run time (0.0 = exactly today's value); `sc3simrun_stats(out[3])` = scroll frames, agent ticks, frozen
agent ticks. Source `re/harness/src/sc3simrun.c`; build **291dcec9** (`Simcity_stock_pausetrips\re\harness\build_cs`).

## Instruments

- `re/tools/cs_probe.py` (Frida; read-only except the A/B call), driven by `re/tools/cs_run.py`, summarised by
  `re/tools/cs_summary.py`. Per second: frames (view tick calls) and the longest gap between two frames; scroll frames
  (scroll step calls, and the stub's count); agent-loop passes and their ms; agent ticks and frozen ticks (sc3simrun);
  car cell moves (STRTSIM `FUN_1001c750` returning a path); car placements (SetProducer `FUN_1001c990` with the car
  producer; context `view` = inside UpdateVehicleView, `tick` = stock producer tick, `mod` = sc3cartrips' spawn) and
  removals (`FUN_1001f610`; context `view`, `produce-off`, `drive`), each with draw history from the car Draw functions
  `FUN_100199b0` / `FUN_10019a30` counted in frames.
- **Visible** removal = the car was drawn in one of the 2 frames before it. **Visible pop-in** = a placed car first
  drawn within 3 frames of its placement. Frames, not agent passes, so the rule holds when agents are frozen.
- Camera kinds (posted input, no focus, no cursor): `H` right-drag back and forth (pt_run's hold), `HB` right button
  held still, `AR` arrows (sc3io's GZWIND key-state hook) left/right every 0.4 s, `ED` edge bands (posted moves at
  x = 8 / 696), `OS` arrow held one way past the map edge with sc3overscroll loaded (then back), `PH` user pause + drag.
- In-game A/B (`A0` / `A1` tokens) so both sides share one game (memory note: games land in fast/slow states at random).
  A phase's first 2 s are dropped. Speed 3 unless named.

## Setup

Tree `Simcity_stock_pausetrips` (SC3U 49dd55e1, SIMSPR eec71500, STRTSIM c02ce38f, untouched). Instances:
- `inst_cs_stock`: mods_launch 88452c54, sc3resize 43cb5059, sc3simrun **291dcec9**, sc3cartrips 33ef673e.
- `inst_cs_full`: + sc3bigcity 76a83845, sc3overscroll a5b69ca3, sc3perf 0f47ac9d with perf.ini 2b9708f0
  (traffic_mt=8, smoothing), bigcity.ini.
- `cartrips.ini` per arm: `off` (stock cars), `replace`, `filler`.
- Cities: Berlin 99327775 (default camera, zoom 3); Europolis 1024 `verify/perf1024/europolis1024_v2_test.sc3`
  9ce07478 (loads at zoom 0, below the cars' birth zoom: `Z:2` first). `--safe` with sc3perf.
- Harness claimed by `carscroll` for every build/launch; one game at a time; only own PIDs killed.

## Arms

Block for kind K: `A0, I:15, K:20, I:10, A1, I:15, K:20, I:10` and the same with A1 first (ABBA), so each kind has
2 x 20 s of moves and 2 x 15 s of idle per side.

| arm | instance | city | cartrips | schedule |
|---|---|---|---|---|
| K0 smoke (not counted) | stock | Berlin | off | `s3:10,A0:0,H:8,I:5,A1:0,H:8,HB:6,AR:6,ED:6,I:5` |
| S1 | stock | Berlin | off | `s3:10` + ABBA blocks for H, HB, AR, ED + `A1:0,P:15,PH:20,P:10,s3:15` |
| S2 | stock | Berlin | replace | same as S1 |
| S3 | stock | Berlin | filler | `s3:10` + ABBA blocks for H, AR |
| F1 | full | Europolis 1024 | replace | `Z:2,s3:20` + ABBA blocks for H, AR + `A1:0` + `OS:6,I:10` x 4 + `A0:0` + `OS:6,I:10` x 4 |
| F2 | full | Berlin | replace | `s3:10` + ABBA blocks for H, AR + `A1:0` + `OS:6,I:10` x 4 + `A0:0` + `OS:6,I:10` x 4 |
| N0 | stock, `animate_while_scrolling=0` | Berlin | off | `s3:15,H:20,I:15,AR:20,I:15` (no A tokens) |
| L1 soak | stock | Berlin | replace | `s3:10` + (`H:60,I:5,AR:60,I:5,HB:30,I:5`) x 6 at speed 4 (~17 min), A1 |
| L2 soak | full | Europolis 1024 | replace | `Z:2,s4:10` + the same cycle x 6, A1 |
| V1 pictures (not counted) | stock | Berlin | off, then replace | `A0:0,H*:6,I:3,A1:0,H*:6,I:3,AR*:4` with `CS_FRAMEDUMP` |

## Predictions

1. **Agents keep moving (target).** For each kind in S1, S2, F1, F2 (A1): agent ticks per second during the move within
   10% of the same arm's A1 idle phases (pooled); car cell moves per second during the move within 25% of idle (cars
   only; counts vary with the view).
2. **Today, reproduced.** A0 moves and N0's moves: agent ticks per second <= 5% of idle, car cell moves 0 (the 2 s drop
   and a frame at the boundary allowed: <= 5% of idle). N0's log reads `ANIMATE: animate_while_scrolling=0 armed=0`.
3. **Kinds covered.** Scroll frames > 0 in every second of each counted move phase, and the stub's count equals the
   scroll-step count's scrolling part (stub <= scroll step calls). If `ED` (posted edge bands) never produces a scroll
   frame, it is reported as not drivable with posted input (the bands only steer a scroll already running,
   `verify/resize_edgescroll` Finding 2) and covered by the shared code path only.
4. **Frame rate.** Frames per second during moves, A1 >= 90% of A0 pooled per kind; mean longest frame gap A1 <=
   1.25 x A0. Agent-loop ms per second during moves A1 reported (idle level expected).
5. **Camera-driven car changes are not made visible by the change.** Visible removals in context `view` <= 2 per
   minute on both sides of every kind. Visible pop-ins in context `view` (stock cars and filler only; 0 by construction
   in replace) measured on both sides; prediction: A1 within 50% of A0 or both <= 2 per minute (the mechanism does not
   depend on the heartbeat). Visible removals in context `drive` during A1 moves: within 50% of the A1 idle rate (the
   ordinary density despawn / route-car ends keep happening as when idle, nothing extra from moving).
6. **FREEZE wins.** In S1/S2 `PH` (A1): car cell moves 0, removals in context `drive` 0, frozen ticks > 0 every second;
   same as the `P` phases.
7. **Faults 0**, every game alive to its end, in every arm; L1 and L2 alive after ~17 min of continuous camera moves.

Owner material (not counted): GIF before/after from V1 frames in `MAIN\verify\carscroll\owner_shots\` + captions.md;
the frames are also inspected for smears/ghosts (agents drawn off their roads, trails) and the finding is written down
either way. Hand-test build staged in `MAIN\re\harness\handtest_carscroll\` with a README when the arms pass.

## Addendum 1 (2026-10-16, after smokes K0..K0g and K1; before every counted arm)

Smokes (tooling and build checks, not counted): K0 (relative city path: game stayed at the menu, then a slow load),
K0c, K0d, K0e, K0f, K0g (stock instance, Berlin), K1 (full instance, Berlin, replace).

**Build changes (both found by the smokes):**
1. **Three rate writes, not one.** K0: with build 291dcec9 the stub ran 0 times while the scroll step ran 20-80 times a
   second, and agent passes stayed 0 during every A1 move. The compiler kept three copies of the 16-byte block
   `mov ecx,[esi+0xb8] / lea edx,[ebp-8] / fldz / fstp [ebp-8] / mov eax,[ecx]` before `call [eax+0x7c]` at
   `0x1004400b`: drag / held button at `0x10043dde` (then `jmp 0x1004400a`), one direction at `0x10043f57` (`jmp
   0x1004400a`), two directions at `0x10043ffa` `[CONFIRMED @ SIMSPR bytes]`. Ghidra's text shows one. All three are
   patched (expect-or-refuse on all three, or none). K0c: agent passes = frames during A1 drag (106 / s).
2. **STRIPS** (same switch). K0c/K0d: with the agents ticking during a move, the camera's car churn became visible.
   UpdateVehicleView queues the cars on the strips leaving the sim rect for removal (AnimOccMan `vt+0x58`), and the
   removal happens in each car's next tick, so today (frozen agents) nothing is removed until the camera stops and
   the count climbs (K0c A0 drag 159 cars). Then it refills with PutVehiclesInRect on the **whole** new rect once per
   new strip (loop `0x1001556c..0x1001557c`, `edi` = index, strips `[ebp-0x44]`, count `[ebp-4]`) `[CONFIRMED @
   STRTSIM 0x10015415]`. Measured with animation on (K0d, arrows): ~50 placements / s over the whole rect, 52 of 197
   drawn within 3 frames. Change: while animating, a refill called from that loop (return address `0x10015578`) gets
   strip `edi` instead of the whole rect, so cars are placed only on ground the camera has just revealed. Hooked at
   FUN_1001f040's entry (6 bytes): sc3cartrips patches and checks the call site, and in filler / off jumps to the
   function with the return address intact; in replace mode the call never reaches it. Expect-or-refuse on the entry,
   the loop and the strip computation bytes. `sc3simrun_stats` gains `out[3]` = strip refills.
   **Build under test from here: sc3simrun f3d94920** (both instances).

**Instrument changes:**
- Draw runs on the car's third vtable: the per-car draw history is keyed on `ecx - 0x1c` (K0..K0c read 0 visible).
- Counters the JS reads are u32 (a torn 64-bit read gave a 2^32-tick "frame gap" in K0c).
- **On-screen rule (primary for prediction 5):** a placement is an on-screen pop-in when the car is drawn within 3
  frames **and** its cell lies inside the view box shown before the placement (for a `view` placement the box of the
  previous view update, since ProcessViewChange stores the new box before UpdateVehicleView runs; otherwise the
  current box). A removal is on screen when the car was drawn in one of the 2 frames before it and its cell is inside
  the current view box. Reason (K0e): at arrow speed (~2,500 px/s, sc3io) a car placed off screen is scrolled into view
  within 3 frames, so "drawn within 3 frames" alone counts cars the camera reaches, not pop-ins. The view box contains
  the screen (it is the screen's cell bounding box), so the rule can over-count, not miss. The raw draw-only counts are
  reported too.
- `CS_LITE=1`: only the native counters (frames, longest frame gap, scroll frames, agent passes and time, agent ticks
  from sc3simrun); no JS hooks. The car-event hooks run only when cars are placed or removed, which happens almost
  only in A1 moves, so the full probe slows A1 moves more than A0 ones (K0e: A1 frames 25-38% below A0; lite K0g: drag
  29.1 vs 28.0, held 45.2 vs 31.2, arrows 41.9 vs 56.6). Frame rate is measured in lite arms only.
- cs_run waits for the city (state with speed and view) before the schedule; `--settle 90`.
- Token `HD` (slow one-way drag) dropped: the right-drag pans by offset from the press point, and the one-way drag ran
  the camera to the map edge in A0 and produced 5.6 scroll frames / s. `H` (pt_run's +-60 px drag) and `HB` stay.
- **`ED` dropped from the arms:** posted edge-band moves gave 0 scroll frames in K0 and K1 (stock and full set),
  as `verify/resize_edgescroll` Finding 2 predicts. Prediction 3's fallback applies: edge scroll is the same scroll step
  (outer `+0x1e1..+0x1e4`), covered by the code path only, and listed for the owner's hand test.

**Revised arms** (ABBA block for K as before; full probe unless lite):

| arm | instance | city | cartrips | schedule |
|---|---|---|---|---|
| S1 | stock | Berlin | off | `s3:10` + blocks H, HB, AR + `A1:0,P:15,PH:20,P:10,s3:15` |
| S2 | stock | Berlin | replace | as S1 |
| S3 | stock | Berlin | filler | `s3:10` + blocks H, AR |
| C1 lite | stock | Berlin | replace | `s3:10` + 3 x (`A0` H:10,I:8,AR:8,I:8,HB:8,I:8; `A1` same; `A1` same; `A0` same) |
| C2 lite | full | Europolis 1024 | replace | `Z:2,s3:20` + 2 x the C1 cycle |
| F1 | full | Europolis 1024 | replace | `Z:2,s3:20` + blocks H, AR + (`A1` OS:5,I:8 x 3; `A0` OS:5,I:8 x 3; `A0` x 3; `A1` x 3) |
| F2 | full | Berlin | replace | `s3:10` + blocks H, AR + the same OS blocks |
| N0 | stock, `animate_while_scrolling=0` | Berlin | off | `s3:15,H:20,I:15,AR:20,I:15` |
| L1 soak lite | stock | Berlin | replace | `s4:10` + (`H:60,I:5,AR:60,I:5,HB:30,I:5`) x 6 |
| L2 soak lite | full | Europolis 1024 | replace | `Z:2,s4:10` + the same x 6 |
| V1 pictures | stock | Berlin | off / replace | frames during A0 and A1 drag and arrows |

**Revised predictions** (others unchanged):
- P1 adds agent ticks per frame (moves vs idle, within 10%) next to per second, because ticks per second follow the
  frame rate.
- P4 (frame rate, C1 / C2 only): pooled per kind, A1 frames per second during moves >= 90% of A0; mean longest frame
  gap A1 <= 1.25 x A0.
- P5: on-screen pop-ins in context `view` <= 2 per minute during A1 moves (by construction of STRIPS, none should be
  inside the previous box); on-screen removals and pop-ins of any context during A1 moves <= the A1 idle rate + 50%
  (the stock churn that runs while the camera is still: tick spawns, density despawn, route-car ends). A0 reported.
- P6: also `PH` frozen ticks > 0 and agent passes continue (the heartbeat runs, FREEZE skips the street agents).

## Addendum 2 (2026-10-16, after S1; before S1b, S3b, L3 and V1, which run after the queued arms)

S1 (stock cars, f3d94920) showed one effect left: during the drag, on-screen pop-ins 219 a minute against 98 with the
camera still, all in context `tick`. Cause: the strip cars leave in their own tick, so the stock producer tick
`FUN_1001f44a` sees alive < target during a move and places cars with PutAVehicleInRect `FUN_1001ef25` at random cells
of the producer's rect `+0x24..+0x30` `[CONFIRMED @ STRTSIM 0x1001f44a, 0x1001ef25]`.

**TICKSTRIP** (same switch, build **sc3simrun ede5732a**): while the camera is moving (a scroll frame in the last 300 ms)
and a strip was revealed in the last 300 ms, the producer tick runs with the producer's rect set to that strip, and the
rect is restored when it returns. Hooked at `FUN_1001f44a`'s entry (6 bytes, expect-or-refuse on 12); sc3cartrips
replace mode never calls the function, so the queued replace arms (S2, C1, F1, F2, C2, L1, L2 on f3d94920) measure code
that is identical in what runs. `sc3simrun_stats` gains `out[4]` = ticks run on the strip. cs_probe allocates 32 bytes
for the stats and zero-fills them (old builds leave `out[4]` at 0); the queued arms after S1 load this probe.

New arms (after the queue, final build ede5732a in both instances):

| arm | instance | city | cartrips | schedule |
|---|---|---|---|---|
| S1b | stock | Berlin | off | as S1 |
| S3b | stock | Berlin | filler | as S3 |
| L3 soak lite | stock | Berlin | off | `s4:10` + the L1 cycle x 4 (~11 min) |
| V1 pictures | stock | Berlin | off, then replace | `s3:10,A0:0,H*:6,I:4,A1:0,H*:6,I:4,A0:0,AR*:3,I:4,A1:0,AR*:3,I:4` with CS_FRAMEDUMP |

Prediction for S1b and S3b: P5 as revised in addendum 1 for every kind (on-screen pop-ins and removals of any context
during A1 moves <= the A1 idle rate + 50%); everything else as S1 / S3.

## Addendum 3 (2026-10-16, after L1; before C3)

L1 (lite, Berlin, replace, speed 4, A1 only, 17 min): alive, 0 faults, but the frame rate fell from 113 fps in its
first seconds to 18-27 fps pooled for the rest of the run, idle phases included (26.6 fps), with single seconds at 0-3
frames, agent passes up to 290 ms and frame gaps up to 9 s, while the sim ran ~5 days per second. L1 has no A0 side,
so it cannot say whether animating during moves adds to that. New arm, final build ede5732a:

| arm | instance | city | cartrips | schedule |
|---|---|---|---|---|
| C3 lite | stock | Berlin | replace | `s4:10` + ABBA blocks H, AR (as S1's blocks), speed 4 |

Prediction (P4 at speed 4): pooled per kind, A1 frames per second during moves >= 90% of A0; mean longest frame gap
A1 <= 1.25 x A0. Also reported: idle A0 vs A1 (same code; the spread is the noise floor of the arm).

## Addendum 4 (2026-10-16 13:20, after S1b; before V1o, V1r, F1r, C3 and the new arms S1c, S3c)

S1b (final build ede5732a, stock cars): on-screen pop-ins during the drag 187 a minute against 87 with the camera
still, all in context `tick`, while the producer tick ran on the strip 15 times a second. Two things the instrument
could not separate: (a) the on-screen rule judged a `tick` placement against the **current** view box, and after a
camera step the current box already contains part of the strip just revealed (the strip runs from the old rect's edge,
old box + 3, to the new rect's edge, new box + 2), so a car placed on just-revealed ground counted as a pop-in; (b) a
producer tick that ran on the full rect (no strip within 300 ms) can place anywhere.

Probe change (applies to every arm launched from now: V1o, V1r, F1r, S1c, S3c; L3 and C3 are lite and record no
placements): each placement records `sw` = the producer's rect differed from the layer's sim rect at that moment (the
tick ran on a strip), and the on-screen rule for placements of every context uses the ground that was inside the view
box both before and after the last camera step (box before the last view update intersected with the box after it;
the current box when the camera has not moved). Removals unchanged. The S1, S2, S3, S1b, F2 tables keep the old rule
and are reported with it.

New arms (final build, after C3): **S1c** = S1b's schedule (stock cars), **S3c** = S3b's schedule (filler).
Prediction for S1c and S3c: P5 as in addendum 1 (on-screen pop-ins and removals of any context during A1 moves <=
the A1 idle rate + 50%), with on-screen pop-ins on a strip-run tick (`sw` = 1) reported separately; everything else
as S1 / S3.

## Addendum 5 (2026-10-16 14:20, after S1c; before S1d, S3d, L4)

S1c (new on-screen rule): of 49 placements made by a tick run on a strip, 0 popped in on screen. Every on-screen
pop-in during the drag (118 a minute against 72 idle) came from ticks run on the full rect, i.e. the camera was
moving but no strip had been revealed in the last 300 ms (the drag reverses; `H` moves the press offset back and
forth).

**TICKSTRIP change, build sc3simrun 5eaa8a2e:** while the camera is moving (a scroll frame in the last 300 ms) the
producer tick runs on the last revealed strip if that strip still lies inside the producer's rect, whatever its age,
and is skipped otherwise; after 300 ms without a scroll frame it runs as stock. `sc3simrun_stats` `out[5]` = ticks
skipped; the probe reads it (zero on older builds). Replace mode never calls the tick: replace-mode arms stand.

New arms (5eaa8a2e in inst_cs_stock, after V2o / V2r): **S1d** = S1's schedule (stock cars), **S3d** = S3's schedule
(filler), **L4** lite soak, stock cars, speed 4, `s4:10` + the L1 cycle x 3.
Prediction for S1d and S3d: P5 (addendum 1, on-screen rule of addendum 4) for every kind; everything else as S1 / S3.
L4: alive, 0 faults.

## Addendum 6 (2026-10-16 14:45, after S1d; before S1e)

S1d is void. From its second 160 the game ran at 1,200-4,600 frames per second in every phase, idle included, with
agent passes at the same rate: the monitor had gone to sleep (Win32_DesktopMonitor Availability 8, workstation not
locked), and with nothing presented the frame loop spins. That breaks the frame rate columns and also the visibility
rules, which count frames (3 frames ~ 2 ms there). From 14:41 a helper keeps the display on
(`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)`, released when it exits, 2 h);
S3d's first minute read 69-161 frames per second. Every arm is checked for this from now (frames per second at idle in
the range of the arm's first phase).

**S1e** = S1d rerun (5eaa8a2e, stock cars, S1's schedule), after V3o / V3r. Same predictions as S1d.

## Addendum 7 (2026-10-16, owner decision: fix route-car thinning; before B0)

Owner decision (orchestrator, 2026-10-16): with cartrips `mode=replace`, the number of route cars on screen during and
right after any camera move must stay close to the still-camera count, with no visible mid-screen pop-ins beyond what
stock cars show, 0 faults, no frame-rate regression in the owner's setup, cartrips' own tests kept.

**Decode (sc3cartrips source, cited functions in this branch):**
- Capture keeps a trip only if a node meets the sim rect published at routing time (`on_pop`, rect from `on_tick`);
  `solve_trip` keeps only the road cells inside that rect, so **every route ends at the old view edge**.
- `spawn_tick` pops the newest route (`route_pop`, consumed whether it places or not); `spawn_at` refuses a route whose
  first drivable cell is outside the current producer rect (`outrect`); placements fail when the start lane is taken
  (`placefail`, up to 3 starts per route).
- Route cars end at their path's last node (`my_seledge` -> `ended`, then `my_need` true), at the current rect edge
  (STRTSIM `FUN_1001c750`), or when their strip leaves the rect (AnimOccMan).
- From S2's CARS> lines (5 s intervals), back-and-forth drag with animation: route cars 7.9 vs 32 still; edge ends
  2.4 / s; spawns 2.05 / s; queue empty; routes in 3.1 / s; placefail 2.0 / s; outrect 0.43 / s.

**Instrument additions:** cs_probe counts the cars drawn in each frame (each car once per frame) and reports the mean
per second (`onscreen`; in replace mode every car is a route car). `re/tools/cs_ctlog.py` assigns sc3cartrips' CARS>
counters (`log_s=1`) to phases.

**Arm B0 (baseline, current builds: sc3simrun 5eaa8a2e, sc3cartrips 33ef673e):** inst_cs_stock, Berlin, replace,
`log_s=1`, `s3:10` + ABBA blocks H, HB, AR (A0 = animation off = today, A1 = on). Reported, no prediction: on-screen
route cars per second during each move and in the 10 s after it, against the 15 s of still camera before it; loss and
supply counters per second.

## Addendum 8 (2026-10-16, after B0 and smokes R0-R0d; before every counted route-car arm)

**B0 (baseline, counted as reported data):** route cars, animation on, current builds. During arrows and the test drag
the route-car count fell to 8-12 against 31 still; cars drawn per frame fell to 8-25% of the still-camera value. Losses
during moves were camera-edge removals at 1.7-2.8 / s (0.05 still), refilled at 1.3-2.7 / s from an empty route queue.
With animation off (today) the count stays up because nothing is removed until the camera stops.

**Instrument findings (smokes):** (1) with frozen cars the car Draw functions are hardly called during scroll frames
(B0 A0: 0.4-0.8 cars per frame): the scroll path moves the drawn picture and redraws only cars that move or appear, so
"cars drawn per frame" counts moving visible cars, with the same meaning at idle and in animated moves. A geometric
count is added: route cars whose cell lies inside the view box (sc3cartrips `inbox`, every 250 ms, CARS> line). (2)
pt_run's drag `H` swings the view 15-30 cells a second (most of a screen width) and drifts; a gentler drag `HG` (+-30
px triangle wave, 1 px per 50 ms) moves it +-3-6 cells (R0d). Both are kept: `HG` as a hand drag, `H` as the extreme.

**The fix (both switchable at run time, `X0` / `X1` in cs_run, a warm-up drag `W:3` after each switch, not counted):**
- sc3simrun **CARMARGIN** (`[sim] car_margin=8`, 2 = stock; build **74901709**): the sim rect = view box + 8 cells
  instead of + 2 (`push 2` at STRTSIM `0x10013fc9`), so camera steps under 6 extra cells delete no car, and new ground
  is taken in 8 cells before it shows.
- sc3cartrips **scroll_fill** (`[cartrips] scroll_fill=1 margin=8`; build **053963fa**): capture and solve over the sim
  rect + 8 cells; solved routes kept as a 256-route history; stock-rate spawns take the newest unused route of the last
  30 s that has a step in the rect and enter it there; when the rect takes in new ground, each new strip gets a quota at
  the still-camera route-car density, filled (<= 8 a tick, never above the still-camera count) from recent routes
  crossing the strip, entering mid-path at the first step inside the strip and outside the view box (off screen); while
  the camera moves and 3 s after, cars are topped up to the still-camera count the same way (<= 2 a tick); a car whose
  route was cut by the capture rect keeps driving on stock choices past its end and leaves once it is off screen.
  Replace-mode random cars stay off; no density despawn for route cars.

**Bound (pre-registered, fix on = X1, per kind):** route cars inside the view box: the median over the moves of
(median during the move / median over the 15 s still before it) in [0.75, 1.25], and the same for the 10 s right after
the move; no single move below 0.60. Cars drawn per frame reported the same way (secondary). On-screen pop-ins
(addendum 4 rule) during X1 moves <= 76 a minute (stock cars with the camera still, S1e). X0 reported as the reference.

**Arms (inst_cf_*: sc3simrun 74901709, sc3cartrips 053963fa, `log_s=1` unless lite):**

| arm | instance | city | schedule |
|---|---|---|---|
| R1 | stock | Berlin | `s3:10` + 2 blocks each of HG, H, HB, AR, block = `X0,W:3,I:15,K:20,I:10,X1,W:3,I:15,K:20,I:10,X1,...,X0,...` + `X1:0,P:15,PH:20,P:10,s3:15` |
| R2 | full | Europolis 1024 | `Z:2,s3:20` + 1 block each of HG, H, AR, OS |
| C4 lite | full | Europolis 1024 | `Z:2,s3:20` + 2 x (`X0` W:3,I:8,HG:10,I:8,H:10,I:8,AR:8,I:8; `X1` same; `X1` same; `X0` same) |
| L5 soak lite | full | Europolis 1024 | `Z:2,s4:10` + `X1` + (`HG:60,I:5,H:60,I:5,AR:60,I:5,HB:30,I:5`) x 4, `log_s=5` |
| V4 pictures | stock | Berlin | frames of the same drag: today (A0), animation without the fix (A1 X0), fixed (A1 X1) |

**Other predictions:** cartrips' own tests in R1/R2 (X1): lane decisions answered from the path >= 95% of route-car
decisions; `need_true` <= ended + lost + roam ends (no density deletion); FREEZE (`P`, `PH`): 0 car cell moves, 0 spawns
and 0 route-car ends. Frame rate (C4, owner setup): X1 >= 90% of X0 during moves and at idle, mean longest gap <= 1.25x.
0 faults everywhere; L5 alive.

## Addendum 9 (2026-10-16 18:00, after R1; before R1b, R2b, L6)

R1 (053963fa), route cars in the view box, fix on: gentle drag 1.08 during / 1.16 after (worst 0.71 / 0.90) and held
button 1.04 / 1.00 (worst 0.93 / 0.87), inside the bound; arrows 1.38 / 1.29, above it; extreme drag 0.76 / 0.46
(worst 0.34 / 0.39), below it. 0 faults; pause phases 0 car moves, 0 spawns. **But the camera sat at the map's west
corner (view box x0 = 0, z 156-180) before most drag and arrow moves**: the extreme drag swings 15-30 cells a second,
hits the map edge and clamps there, so before / after compared different, half off-map places. R1 is reported as run.

Changes for the rerun:
- cs_run token `C`: re-centre the camera with a posted left click on the minimap centre (718, 508 at 800 x 600); the
  view before and after is logged. Each move is preceded by `C` and 30 s of still camera (the cars settle at the
  centre), then 15 s still (the "before" window), the move, 10 s still ("after").
- The warm-up `W` after a switch is a gentle drag (no drift) instead of the extreme one.
- sc3cartrips **cb74f872**: while the camera moves (and 3 s after) stock-rate route spawns stop at 1.05 x the still
  count too (R1's arrows overfilled through them; the strip fill already stopped there).

Arms (inst_cf_*: sc3simrun 74901709, sc3cartrips cb74f872): **R1b** Berlin, per move `X?,W:3,C,I:30,I:15,K:20,I:10`,
ABBA, 2 blocks each of H and AR, 1 block each of HG and HB, then `X1,P:15,PH:20,P:10`; **R2b** Europolis 1024 (full
set), 1 block each of HG, H, AR, OS the same way; **L6** lite soak, full set, Europolis 1024, speed 4, X1, the L5 cycle
x 3. Bound and other predictions as addendum 8; R1b / R2b replace R1 / R2 for the bound; C4 (frame rate) and L5 (soak)
stand on 053963fa (the change only stops spawns).

## Addendum 10 (2026-10-16 18:25, after R2; before R1b, R2b, L6)

R2 (Europolis 1024, full set, 053963fa, full probe): during the fix-on phases the game thread stopped for up to 16-20 s
at a time (0 frames, sc3cartrips counters frozen), which the fix-off phases did not show. Measured costs that grew
with the fix: the route solver's slowest trip 260 ms (F1r without the wider capture: 8 ms), average ~5 x; route
scans walk every step of up to 256 routes per spawn attempt. Also suspect: the probe's car hooks run in JavaScript on
the game thread and each removal scanned the list of pending placements (quadratic under heavy churn). C4 (lite probe,
same build) tells the probe's share apart.

Changes, **sc3cartrips dba17e77** (replaces cb74f872 for R1b, R2b, L6): capture margin 8 -> **4** (the car rect is
already view + 8); solver state limit 200000 -> 40000 while scroll_fill is on; each route keeps its path's bounding box
and the scans skip routes whose box misses the rect or strip. cs_probe: pending placements looked up by car address.
Predictions unchanged (addendum 8 / 9); added: no frame gap above 1 s in R1b / R2b / L6 fix-on phases.
