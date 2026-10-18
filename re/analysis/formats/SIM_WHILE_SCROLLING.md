# The simulation keeps running while the camera moves (`sc3simrun`)

Status: automated A/B and a 3.5 min soak passed 2026-10-06 (`verify/simrun/RESULTS.md`). Owner hand test
pending. Source `re/harness/src/sc3simrun.c`, build `re/harness/build_simrun.ps1`, ships through
`mods_launch.exe` (fourth DLL in its list). Patched in memory after a shipped-bytes check. No game file
is modified.

## Why the stock game stops the sim when you scroll

Measured, not inferred: a sampler read the coordinator and the sim clock 20 times a second while
`sc3io` drove a right-drag, a held right button and arrow scrolling, and hooks logged the caller of
every hold and clock pause.

- **Not the user pause.** Coordinator suspend depth `+0x140` (the `0xc2a35d7e`/`0xc2a35d80` pair,
  `BIGGER_CITIES.md`) stays 0 the whole time.
- **The clock's own pause count** (clock = coordinator `+0x130`, count at clock `+0x54`, `FUN_1000a0ec`
  Pause / `FUN_1000a145` Resume, clock vtable `0x10013988` slots `+0x2c`/`+0x30`) goes to 1 for the span
  of each camera move. The tick cursor `+0x4c` does not advance while it is non-zero.
- The pause comes from the coordinator's **camera hold**: `vt+0x21c` = `FUN_100058ac` (`+0x144 += 1`,
  clock Pause, notifies a service `vt+0x1c(1)`), released by `vt+0x220` = `FUN_1000590e`.
  `[CONFIRMED @ SIMCITY 0x100058ac, 0x1000590e; PE vtable 0x13260 slots +0x21c/+0x220]`
- **One caller takes it for every camera move.** SIMSPR `FUN_10043daf` (the view's scroll step) runs
  `if (!outer[+0x174]) { outer[+0x174] = 1; coord->vt+0x21c(); }` at `0x1004400e..0x10044028`. The view
  tick `FUN_10042a95` (`this` = outer + 4, so the same byte is inner `+0x170`) releases it with
  `vt+0x220` at `0x10042b23`, but only when every camera-busy byte `+0x1dd..+0x1e2` is 0. Otherwise it
  calls `FUN_10043daf` again. So the sim stays held from the first scroll step until the camera is idle.
  In the logged run 3 of 3 camera phases (drag, held button, arrows) were exactly this pair:
  hold returns to `0x1004402e`, release returns to `0x10042b29`.

The coordinator has three independent counters with the same shape: `+0x140` (`vt+0x20c`/`+0x210`,
the user pause, posts `0xc2a35d7f`/`0xc2a35d81`), `+0x144` (`vt+0x21c`/`+0x220`, camera and UI holds) and
`+0x148` (`vt+0x22c`/`+0x230`, the **month-pass bracket**: SIMCITY's sim-thread command switch `FUN_10001675`
wraps command 7, the first-day-of-month pass, in `vt+0x22c` = `FUN_100059cf` / `vt+0x230`
`[CONFIRMED @ SIMCITY 0x100016c9, 0x100016ea, 0x100059cf]`, `verify/pausetrips/RESULTS.md`). All three pause the
same clock. While the clock is paused its 1000 ms callback skips every minute/hour/day fire
(`cmp [esi+0x54],0; jne` at `0x1000a885`) and Resume `FUN_1000a145` restarts the time base, so paused time is dropped,
not replayed `[CONFIRMED @ SIMCITY 0x1000a885, 0x1000a0ec, 0x1000a145]`.

## The mod: one byte

SIMSPR `0x1004401a` `75 12` (`jne` past the hold) becomes `EB 12` (`jmp`). The scroll step never sets
the flag and never holds. The view tick then never sees the flag and never releases, so `+0x144` and
the clock count stay balanced. Expect-or-refuse: the 17 bytes at `0x1004400e` must be the shipped
sequence, otherwise the mod logs and changes nothing.

Left stock on purpose: the zoom/rotate-style brackets (`FUN_10042d8a`, `FUN_10042f27`, `FUN_100430c4`,
`FUN_100432aa`, `FUN_100433f5`, `FUN_10043540`, `FUN_10043662`, `FUN_10043844`). Each takes and
releases the same hold inside one call, so the sim stops for one frame at most. The SIMUI holds
(dialogs, panels) are not camera moves.

Config: `simrun.ini` beside the DLL, `[sim] run_while_scrolling=1` (0 = stock). Env for runs:
`SC3SIMRUN_LOG=<absolute path>`, `SC3SIMRUN_TRACE=1` (sampler + caller log).

## Measured effect

| | stock | mod |
|---|---|---|
| right-drag 8 s | 0 ticks | 4 ticks |
| right button held 6 s | 0 | 3 |
| arrows 8 s | 1 | 4 |
| idle reference | 0.5/s | 0.5/s |

Soak with the mod: 180 s of continuous drag at 0.50 ticks/s, process alive, frame normal.

## Open

- Owner hand test, and the four mods together through `mods_launch.exe`.
- The stock hold may have been there to keep a full-speed sim from competing with scroll redraws on
  2000-era CPUs. No race showed in 3.5 min of drag at the default speed. Fastest speed not soaked.
- ~~`+0x148` driver~~: the month pass (above). The cursor jumps seen during it are still unexplained.
- ~~Vehicles still freeze while scrolling with the mod~~: fixed by `animate_while_scrolling` (below, task carscroll).

## Street agents keep moving while the camera moves (`animate_while_scrolling`, task carscroll 2026-10-16)

Evidence `verify/carscroll/PRE.md` (+ addenda 1, 2) -> `RESULTS.md`. With the hold gone, days and trips ran during a
camera move but every street agent still froze. Cause, decoded:

- The scroll step `FUN_10043daf` does render a frame each tick: it moves the camera (`vt+0x34`), then calls the render
  view's frame `[+0xb8]->vt+0x20` = `FUN_1001cab9` itself (`0x1004403d`). The frame calls the heartbeat
  `[+0x15c]->vt+0x18` (SC3U `FUN_00426140`, which ticks every agent) **only while render-view byte `+0x2b` is set**.
  `+0x2b` is written by render-view `vt+0x7c` = `FUN_1001d65d(&rate)`: `+0x70 = rate`, `+0x2b = rate >= 0.1f`
  (`0x10063504`) `[CONFIRMED @ SIMSPR 0x1001cab9, 0x1001d65d]`. The idle view tick passes 60.0 before every frame; the
  scroll step passes **0.0** before its frame. The compiler kept three copies of that write, one per branch
  (`0x10043de7` drag / held button, `0x10043f60` one direction, `0x10044003` two directions; Ghidra's text shows one).
- Zoom and rotate (`FUN_10042d8a` ...) pass 0.0 then 60.0 inside one call with no frame between: nothing to change.
- Edge scroll and overscroll are the same scroll step (busy bytes outer `+0x1e1..+0x1e6`).

The mod (sc3simrun, `[sim] animate_while_scrolling=1`, default on; needs `run_while_scrolling=1`):
1. **ANIMATE**: the three `fldz; fstp [ebp-8]` become calls that write 60.0, so scroll frames run the heartbeat.
2. **STRIPS**: once agents tick during a move, the camera's car churn shows. UpdateVehicleView (STRTSIM `FUN_10015415`)
   queues the cars on strips leaving the sim rect for removal, carried out in their next tick (so today nothing is
   removed until the camera stops), and refills with PutVehiclesInRect `FUN_1001f040` on the **whole** new rect once
   per new strip. While animating, that refill gets the strip instead, so new cars land on ground just revealed.
3. **TICKSTRIP**: the stock producer tick `FUN_1001f44a` then fills the deficit at random cells of the producer rect;
   while the camera is moving it runs with the rect set to the last revealed strip.
4. **CARMARGIN** (`[sim] car_margin=5`, 2 = stock): the street agents' sim rect = view box + 5 cells instead of + 2
   (`push 2` at STRTSIM `0x10013fc9`), so short camera steps delete nothing next to the screen (route-car work, task
   carscroll; `CAR_TRIPS.md` 8).
FREEZE (user pause) still wins: it skips the street agents inside the agent loop whatever drives the heartbeat.
Measured results: `verify/carscroll/RESULTS.md`.
