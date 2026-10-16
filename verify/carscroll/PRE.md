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
