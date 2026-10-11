# PERFORMANCE — profiling SC3U and making it faster (2026-10-08)

Owner request (2026-10-08): profile the game, add an FPS counter, improve performance overall, especially in
1024 cities. Instrument: `re/harness/src/sc3perf.c` (mod DLL, loaded by `mods_launch.exe`), report tool
`re/tools/perf_report.py`, run scripts in `re/harness/simrun/scripts/` (`perf_run.py`, `perf_summary.py`,
`resize_stress.py`). Machine: NVIDIA GPU (nvd3dum.dll), 2560x1351 desktop at 125% (game sees 2048x1081 maximized).

## sc3perf, what it measures

- **Frame** = one FINAL present (a Blt whose destination covers the client, the same test sc3resize uses).
  Chained on the IDirectDrawSurface v1 vtable (Blt +0x14, BltFast +0x1c, Lock +0x64) AFTER sc3resize has hooked
  (sc3resize refuses a Blt slot that no longer points into ddraw.dll, so sc3perf waits for it, max 120 s).
  The vtable comes from a throwaway 1x1 system-memory surface on sc3perf's own DirectDraw object; that it is the
  game's vtable is confirmed at runtime (slot +0x14 points into sc3resize.dll once resize has hooked).
- Per-second CSV in the log: fps, frame time avg/max, time inside the final present, count and time of other
  Blts, BltFast, Lock, client size, time spent in the frame cap, cap.
- **Profiler**: suspends the game thread ~1000x/s (1 ms timer via `timeBeginPeriod(1)`), exclusive = Eip,
  inclusive = Eip plus every validated return address found by a STACK SCAN (a heuristic: stale return
  addresses can appear, and a function with several call sites on one stack counts more than once).
  SIMCITY-class threads (stack holds SIMCITY+0xd0a5, the thread class `FUN_1000d036 -> _beginthreadex`) are
  sampled into a second table. Control file `sc3perf.cmd`: `reset`, `dump <tag>`, `mark <text>`.

## Finding 1 — the game thread spends most of its time waiting on the GPU inside DirectDraw

Moscow, stock surfaces (video memory), uncapped, sc3resize + bigcity + overscroll + simrun loaded:

| phase | fps | frame | final present | other Blts |
|---|---|---|---|---|
| idle 800x600 | 374 | 2.72 ms | 309 ms/s | 3,454/s, 571 ms/s |
| idle maximized 2048x1081 | 185 | 5.45 ms | 317 ms/s | 1,837/s, 683 ms/s |
| scrolling maximized | 183 | 5.55 ms | 376 ms/s | 2,012/s, 640 ms/s |

Profile (maximized idle): 44% of samples in `ntdll!ZwWaitForSingleObject` under the Blt hooks and
`GZGraphicD FUN_10014894` (blit dispatch), 29% in the NVIDIA user-mode driver, 9% in `win32u` DXGK calls
(`NtDxgkSubmitPresentToHwQueue`, `NtGdiDdDDIWaitForSynchronizationObjectFromCpu`). All game DLLs together ~10%.
On this Windows, DirectDraw runs on a D3D emulation layer and each small Blt on a video-memory surface pays a
GPU round trip. This matches the 2026-09-01 HUD finding (`RESIZABLE_WINDOW.md`: a 6x smaller blit was 7.7x
slower, a fixed per-call cost).

**The game has no frame limiter.** The main loop (SC3U 0x0046135a) never sleeps; the only pacing is the
fullscreen `Flip(DDFLIP_WAIT)` at GZGraphicD 0x10019a77. Windowed, it spins at 100% of a core.

## Finding 2 — the game's own system-memory path triples throughput

GZGraphicD `FUN_10019273` (surface create) asks for video memory only while the byte `GZGraphicD+0x6cbcd` is 0;
otherwise it sets `DDSCAPS_SYSTEMMEMORY` (0x800). The byte is written once, at 0x100140fe
(`mov [0x1006cbcd], al`, the result of a device query in `FUN_10014078`), and read at 0x10015d50, 0x10018f2d and
0x10019370 `[CONFIRMED @ 0x10019273, 0x10014078]`. `sysmem=1` presets it to 1 and redirects that one store to a
dummy byte (the imm32 is relocated with the module, the patch checks `gz + 0x6cbcd`). Logged "in time" (before
graphics init) in every run.

| Moscow, uncapped | video memory | system memory |
|---|---|---|
| idle 800x600 | 374 fps, 2.72 ms | 1,056 fps, 0.95 ms |
| idle maximized | 185 fps, 5.45 ms | 548 fps, 1.98 ms |
| scrolling maximized | 183 fps, 5.55 ms | 668 fps, 1.68 ms |

Run-to-run noise measured as about +-20% (two unpatched runs, because the first sysmem attempt did not patch a
relocated module). Picture compared side by side at 800x600: identical apart from sim progress.

**Arrow scrolling moves a fixed step per FRAME**: the uncapped sysmem run scrolled off the map in the same 15 s
the stock run stayed inside it. Uncapped sysmem would change how the game plays.

## Finding 3 — a frame cap needs system memory

`fps_cap=N` holds each final present until 1000/N ms after the previous one (Sleep, then spin the last ~1 ms).

| Moscow, cap 60 | video memory | system memory |
|---|---|---|
| idle 800x600 | **11.7 fps**, worst frame 2.3 s | 59.9 fps, worst 59 ms |
| idle maximized | 26.9 fps, worst 933 ms | 60.0 fps, worst 30 ms |
| scrolling maximized | 47.6 fps, worst 377 ms | 59.1 fps, worst 73 ms |
| work per frame | 13-38 ms | 1.7-4.1 ms |

With video memory, sleeping between frames makes every GPU wait much longer `[UNCERTAIN]` why (GPU power state is
one candidate, not measured). With system memory the game thread is 77% asleep at 60 fps maximized: frames cost
~2.7 ms of a 16.7 ms budget.

## Finding 4 — sc3resize deadlocked with the sim thread (fixed: DEFERRESIZE)

Found by sc3perf (a run froze after maximizing, 0 fps for 5 minutes). cdb non-invasive attach:
the game thread held CS `...220` and waited on `...1fc`; the SIMCITY sim thread (SIMCITY thread class ->
SIMRCI -> SIMGEOM -> GZServiceD -> SIMCITY lock helper `FUN_1000d310`) held `...1fc` and waited on `...220`.
Game-thread chain from the raw stack: GZWIND paint -> SIMSPR city view -> Plot (0x1001cab9) -> dirty-rect blits ->
GZGraphicD blit wrapper -> **sc3resize heartbeat -> rz_poll -> rz_do_resize step 7/11 -> SIMSPR FUN_10018cdf ->
FUN_100184d9 -> SIMCITY lock**. sc3resize ran its whole resize pass inside a blit made while the city view was
drawing. The game calls FUN_10018cdf only from UI handlers (message dispatch, no drawing locks held).

Fix in sc3resize (`SC3RESIZE_DEFERRESIZE`, default 1): the poll POSTS `WM_APP+0x5C3`; the pass runs from
`rz_wndproc`. Stress (`resize_stress.py`, Moscow, sim speed 3, sysmem uncapped, maximize/restore every 6.5 s):

| build | result |
|---|---|
| old path (`DEFERRESIZE=0`) | froze on the 11th resize; an earlier run froze on the first maximize |
| fixed | 24 of 24 resizes, then 50 of 50 in a second run (74 total), no freeze |

This affects the stock-speed build too (same code path); the faster render only raised the odds.

## Finding 5 — cap at the monitor's refresh rate (owner call 2026-10-08)

Owner chose the monitor's refresh rate over a fixed 60. `fps_cap=-1` (the default) reads the refresh of the monitor
the window is on (`MonitorFromWindow` -> `EnumDisplaySettings`), once a second, so moving the window follows it.
Dev PC: 165 Hz main monitor. The wait uses a high-resolution waitable timer (Win10 1803+, resolved at runtime);
sleep-then-spin is the fallback. Minimized there is no final present to pace on (client 0x0), and the game kept
rendering at ~12,000 blits/s and 96% of a core; the Blt hook now sleeps 90 ms of every ~100 while minimized.

| Moscow, sysmem, cap = 165 Hz monitor | fps | worst frame | work/frame | game thread CPU |
|---|---|---|---|---|
| idle 800x600 | 165.0 | 12.0 ms | 0.97 ms | 18% |
| idle maximized | 164.8 | 13.5 ms | 1.94 ms | 33% |
| scrolling maximized | 165.0 | 13.5 ms | 1.95 ms | 34% |
| minimized | - | - | - | 10% (was 50-96%) |

## Overlay trail (owner hand test 2026-10-08, fixed)

Drawing the counter into the present's source surface left a trail down the screen while scrolling and tore the
city under it: the game scrolls by shifting the pixels already in its back buffer and redraws only the strip that
came into view. The counter now saves the pixels under it (Lock, copy out), draws, presents, then copies them
back, so the back buffer the game reads is never changed. Verified: scrolling grab clean (`perf_moscowD_*`).

## Finding 6 — the simulation is not CPU-bound in any city measured

The sim runs on a SIMCITY-class thread woken by its clock timer (SIMCITY 0x1000c8db; SetSpeed 0x1000a066 sets ms
per day). Its pace is the clock, not the CPU. sc3perf sampled that thread (sysmem, cap 165, maximized, 30 s):

| city, speed index | sim thread busy | top work |
|---|---|---|
| Moscow (256, pop ~950k), 3 | 2.9% | SIMCITY list walk, SIMGEOM occupancy/grid queries, SimTransit routing |
| fresh 1024 map (empty), 3 | 1.8% | SIMRCI land value 0x1001deca, SIMECO pollution, SimTransit stats 0x100093e9 |
| Moscow, 4 (fastest) | 11.5% | 5.4% lock waits (`ZwWaitForAlertByThreadId`), SIMCITY 0x10001db0 / 0x10001c63 |

No sim DLL shows up on the game thread (STRTSIM ~1% there is the vehicle/pedestrian animation).

Small inefficiency found: SIMCITY `FUN_10001c63` removes an entry from a registry list under its lock, then calls
`FUN_10001db0`, which COUNTS the list by walking every node, only to test whether it is empty
`[CONFIRMED @ 0x10001c63, 0x10001db0]`. Quadratic over many removals. 1.9% + 0.8% of the sim thread at speed 4 in
Moscow (~0.3% of a core) - not worth a patch at these sizes.

`[UNCERTAIN]` a DEVELOPED 1024 city. No such save exists. Some per-tick budgets scale with map area (worker
report: SIMMISC land-value aura, SIMSERV service spread, SimTransit 0x100093e9 full-grid pass), others with
buildings and population, so Moscow's numbers cannot be scaled by 16 honestly. Needs a real developed 1024 save.

## Finding 7 — the game could not load its own 1024 save (sc3bigcity bug, FIXED: QFS24)

Goal was a developed 1024 test city (zones + roads copied 4x4 from Moscow into an empty game-written 1024 save,
then grown in-game). Step 1, an empty 1024 save written by the game (`verify/perf1024/empty1024_hilly.sc3`,
3,831,914 bytes), exposed this:

- The city record is 24,134,028 bytes uncompressed. A QFS stream stores its size in 3 bytes, so the stream
  says 7,356,812 (= mod 2^24); the 24-byte record header keeps the full size. Our tools refused the file
  (`city_parse.py` size check) and could not have written it (`qfs_encode.py` `to_bytes(3)` overflow). Both
  fixed to mirror the game (low 24 bits). The save round-trips byte-identical at L0-L4, and all 59 stock
  cities still do.
- **Stock loads it as blank water with $0 funds.** GZResourceD record loader `FUN_1001053e` allocates the header
  size (+0x68), decompresses through the compressor object (vtable 0x1001dce4, Decompress = slot +0x10 =
  `FUN_10015b5d`), then REJECTS the record unless the reported output length equals +0x68. The decompress loop
  `FUN_10015cb1` writes the whole stream but returns its 24-bit declared size, and `GetDecompressedSize`
  (slot +0x1c, `FUN_10015bcf -> FUN_10015c5f`) does the same `[CONFIRMED @ 0x1001053e, 0x10015cb1,
  0x10015c5f]`. Every record over 16 MB is discarded. At ~23 bytes per cell that is any map above roughly
  850x850; 512 (about 6 MB) is unaffected.
- **Fix: sc3bigcity `QFS24`** (`SC3BIGCITY_QFS24=0` disables). The only call of each (0x10015b80, 0x10015beb)
  goes to a wrapper that computes the true size by walking the stream's control bytes, used only when it agrees
  with the 24-bit field mod 2^24. Both originals are **stdcall** (`ret 0xc`, `ret 4`, read from the bytes;
  Ghidra shows cdecl). The first build used cdecl hooks: the stack came back 12 bytes off and execution
  returned into the 24 MB output buffer (cdb: EIP = the destination argument, `!address` = a 23 MB private RW
  block). With stdcall hooks: the 1024 save loads with its terrain, minimap and $50,000; Moscow loads unchanged.

Side notes from the same session: the game window has twice come up minimized for no measured reason; one
launch crashed at 10 s with a call from GZGraphicD+0x1490D into unmapped memory (not reproduced on relaunch);
sc3overscroll writes a jump into GZGraphicD+0x19349 (bigcity's FIX16 site) on a read-only page and takes a
handled access violation (both mods carry the windowed/FIX16 patch code). With a modal dialog open the frame
rate drops from 165 to 24 fps (39.6 ms per frame).

## Finding 8 — test-city tooling: flat 1024 map, roads and zones written offline (2026-10-08)

- **Terrain section** (DirtBag `0x21737de5`, inst 0), read from data on Moscow and a game-written 1024 map:
  frame(8) | 4 bytes `25 06 51 40` | grid A (N+1)^2 bytes = corner heights | grid B (N+1)^2 bytes = one value,
  the water level (19 / 30) | N^2/8+1 bytes, almost all zero. `re/tools/city_flatten.py` sets grid A to one
  value above the water level: the game loads it as a flat, dry map (river gone, no contours, no faults).
  `[UNCERTAIN]` corner-to-tile alignment on slopes (no shift/transpose matched road z better than 77%).
- **Road pieces on level ground** (all 59 stock cities): `state` is always 0x3000 and the save's `flg` bits are
  the rotation. Straight 29 (W-E flg0, N-S flg1), crossroads 43, T 11204 (flg by orientation), corner 35,
  dead end 11225. `re/tools/city_grid.py` lays a lattice from the 4-neighbour mask and zones the blocks.
- **First edited road network ever loaded by the game** (`verify/perf1024/patch1024.sc3`, 64x64 patch at the
  map centre): roads render with correct straights, crossroads and T-junctions; zones show in their colours.
- Network instance 3 in saves holds HIGHWAY pieces (16012/16013, 116xx), not power lines; power lines are not
  in the network section and cannot be written offline today.
- Power: a plant beside the patch's border road powered nothing (no growth in 18 game months). The second
  patch (`patch1024b.sc3`) leaves a 1-tile gap in every road segment, zoned, so blocks touch, plus a 4x4 hole
  for a plant; lots then started showing development markers. Scripted plant placement failed there.
- **Scripted in-game building is fragile:** posted left-drags register as a click only (map tools likely read
  the real button state), the camera drifts between steps, and the game window was minimized repeatedly while
  the script ran (logged by sc3perf `CAP> window minimized`), which drops clicks.

## Finding 9 — zones never developed outside the 256x256 corner on big maps (sc3bigcity bug, FIXED: TRAVERSE)

Symptom: on the generated 1024 grid, and on zones drawn by hand mid-map, nothing grew although the query tool
said "powered". A Frida counter on the per-tile developer checks (SIMRCI `FUN_10028f12` res, `FUN_1000fd53` com,
`FUN_10017fc0` ind) showed **0 calls in 30 s**; Moscow, same build: ~48,000.

Cause `[CONFIRMED @ 0x100318e8, 0x10031a78]`: the zone layer's traversal object (layer+0x280) fills a vector of
u16 entries packed as `(x & 0xff) << 8 | (y & 0xff)` and `FUN_10031a78` (thiscall, ret 8) unpacks them, so both
coordinates wrap at 256. A game-written 1024 save holds 1,048,576 entries with 65,536 distinct values. Only the
256x256 corner at the origin is ever offered to the developers on any map above 256.

Fix, sc3bigcity `TRAVERSE` (`SC3BIGCITY_TRAVERSE=0` disables): `FUN_10031a78` replaced by a C function that keeps
the original logic for maps of 65,536 tiles or fewer and for T's stride mode, and above that walks all N tiles as
`v = (c*stride + offset) mod N` (stride odd, near 0.618*N, coprime to N), reusing the cursor T+0x2c and the
"pass finished" state, so the game's own rebuild/reset still drives passes. Save format unchanged.

Measured: full 1024 grid, no plant: **1,135,000 developer checks in 30 s**, all code 0xe (no power), so every
tile is now visited and demand (gate 1) passes. 64x64 patch at tiles 480-543 with one coal plant, fastest speed:
**population 19,979 after ~2 game years**, buildings across every block (power crosses the road grid).
Agent notes kept for later: the shuffle in `FUN_10033d91` uses `rand() % (i+1)`, and the stride-mode prime table is
capped at 130,444 tiles; neither is used on the fixed path.

## Finding 10 - the date jumps 5-6 days at a time because the clock is polled once a second (fixed: SIMCLOCK)

Owner report: at speed the date advances in steps of 3-6 days instead of one by one. Not a CPU bottleneck.

- The clock (SIMCITY vtable `0x10013988`, ctor `FUN_10009b35`) is driven by ONE periodic timer callback,
  `LAB_1000a854`, registered by its Start `FUN_10009d5a` with period **1000 ms** (`push 0x3e8` at
  `0x10009d98`) `[CONFIRMED @ 0x10009d98]`.
- The callback adds the real time since its last run to `+0x5c` (skipped while the pause count `+0x54` is
  non-zero) and then fires every whole day that fits (`+0x60` = ms per day) in a loop, `FUN_1000aa4d` per day.
  With minute/hour listeners it ticks `FUN_1000a915` / `FUN_1000a9b1` instead, floor 50 ms (`DAT_10017278`).
- Speeds from `FUN_10005ada` -> SetSpeed `FUN_1000a066` (game minutes per real day, ms/day = 86400000/N):
  pause 120, 1 = 10080 (8571 ms/day), 2 = 43200 (2000), 3 = 129600 (667), 4 = 525600 (164).
- So at speed 3 the date steps 1,2,1,2 and at speed 4 it steps 5-6, once a second, and every daily sim
  pass runs in that burst.

Fix: sc3perf `clock_ms` (default 50, 0 = shipped) rewrites the 1000 to N before the clock starts. The
accumulator is untouched, so game time per real second is set by the same code.

A/B, Moscow, combo build (sysmem, 60 fps cap), 30 s each after a 10 s settle (`clock_ab.py`, scratchpad):

| run | days/s | date steps | CPU (all threads) | fps avg / min | worst frame |
|---|---|---|---|---|---|
| speed 4 shipped | 5.27 | 6 x9, 5 x20, 4 x1 | 22% | 60.0 / 59.8 | 21 ms |
| speed 4 clock_ms=50 | 5.83 | 1 x175 | 25% | 60.0 / 59.8 | 28 ms |
| speed 3 shipped | 1.50 | 2 x15, 1 x15 | 18% | 57.9 / 28.0 | 1069 ms (one hitch) |
| speed 3 clock_ms=50 | 1.50 | 1 x45 | 18% | 60.0 / 59.8 | 27 ms |

Speed 3 is exact in both (nominal 1.50). Speed 4 nominal is 6.08 days/s: shipped reached 5.27, the fix 5.83,
so the fast-forward is now 11% faster and closer to the design value. `[UNCERTAIN]` where the shipped build
loses that time (candidate: clock pauses from the sim bracket `city+0x148` overlapping the 1 s polls; not
traced). The single 1069 ms frame in the shipped speed-3 run is one sample, not shown to be clock-caused.

## Finding 11 - buildings stay as light-blue boxes because the sprite loader is throttled to ~240/s (fixed: SPRITES)

Owner report: on big maps buildings take a long time to replace their light-blue boxes and loaded areas seem
to be forgotten. Static map by the worker (SIMSPR), key values read live in Moscow.

- The blue box is a real placeholder sprite per footprint size (5 objects at `iso+0x490..0x4a0`, created in
  `FUN_10005b42`). A cell draws the placeholder while its per-zoom bit `DAT_100624f0[zoom]` (0x10..0x100) is
  clear in `cell+0x10` `[CONFIRMED @ SIMSPR 0x1000be25]`.
- One background thread realizes sprites: `FUN_10008a81`, started by `FUN_10008156` at priority 2, spiral
  outward from the camera centre. Per wake it works until a cost sum reaches the float at `iso+0x3d4`, then
  `SleepEx(20)` (`push 0x4e20` at `0x10008cd5`; `FUN_10054c5e` takes microseconds) `[CONFIRMED]`.
- Live: `iso+0x3d4` = **5.0**; costs realize 1.0, release 0.3, empty tile 0.03 (`.rdata 0x100628ec/f4/f0`).
  So about 5 buildings per wake, measured **~240 realizes/s** steady, independent of the CPU.
- The game profiles this PC as 180 MHz (detection floor) and **2048 MB** (`app+0xfc/0xfe`, `iso+0x35c` points
  at it). In the top tier (>= 46) `FUN_100071a3` queues WHOLE-MAP realize passes for the current zoom and
  its neighbours, and release passes for the far zooms, on every zoom/rotation change. A 1024 map is 16x
  the tiles at the same trickle.
- There is no size-limited sprite cache: decoded sprites are refcounted and freed only on shutdown
  (`FUN_100123ff`). "Forgotten" areas are the per-zoom release passes plus the queue reset on zoom change.

Fix: sc3perf `spr_budget` (default 40) points the loop compare at the mod's own float (`d8 9e d4 03 00 00`
-> `d8 1d imm32` at `0x10008aaf`, same length) and `spr_sleep_us` (default 1000) replaces the sleep.

Cold start A/B, Moscow, fresh launch, 90 s from SIMSPR load (`spr_cold.py`, scratchpad):

| run | realize / release | loader active | rate | worst frames |
|---|---|---|---|---|
| shipped | 20,980 / 0 | still running at 90 s | ~240/s | 554, 182, 57 ms (load) |
| spr_budget=40, 1 ms | 82,859 / 53,933 | done 4.3 s after first realize | ~24,800/s | 538, 168, 55 ms (load) |

The two load-time spikes are in both runs. Steady-state worst frame 17-19 ms in both, RSS equal (158 MB).
Warm A/B (zoom 4 -> 0 in the same session): shipped still realizing at 30 s at 240/s, budget 50 finished
9,545 realizes and 163,509 releases inside 0.25 s, 60 fps, worst 18 ms.

`[UNCERTAIN]` a developed 1024 city was not measured (no save exists). Extrapolation only: the same work at
16x is ~1.5 h shipped vs ~1 min patched. Lock note: the loader holds `iso+0x46c` for one budget, so the
budget bounds the game thread's wait on that lock; at 40 no frame-time change was seen.

## Finding 12 - +40 MB/min leak and crash at ~1.6 GB with a dialog open (sc3resize SIDEFIT bug, FIXED)

Symptom: growing the 1024 lattice city, private bytes rose linearly from 232 MB to 1,600 MB in 34.5 min
(+40 MB/min), then `C0000005` in `GZGraphicD+0x18C74` with ESI = 0 (game's `Apps\SC3U_stkdmp.txt`): the
known null-surface Blt, reached once the address space could no longer back the side panel's surface.
Owner spotted the context: the year-end budget dialog was open the whole time (the save starts at -$16,096).

Not the sim and not the sprite fix: same rate paused, at speed 1 and at speed 4, and with spr_budget on or off
(0 sprite loads in each window). Frida on `RtlAllocateHeap` -> 80 x 80,072-byte blocks per 10 s from DDRAW;
on `IDirectDraw::CreateSurface` -> 80 x 96x417 system-memory surfaces per 10 s, called from sc3resize.

Cause: `rz_side_fit_child` returns early only when `liveH == oldh`. The request is `target - RZ_SURFACE_SLACK`
(409) and `rz_recreate_raster` pads by the same 8 rows, so the surface reads back 417 and the test never holds.
The periodic re-assert pass calls the fit every poll; while the dialog holds the panel at its native 442 the
pass ran every ~120 ms, re-creating the background each time, and each re-create leaked the previous surface.
20,450 SIDEFIT log lines in one session (the default log also landed in `Apps\`, moved to
`verify/memleak1024/`).

Fix (`sc3resize.c`): treat `oldh == liveH + RZ_SURFACE_SLACK` as fitted; the re-assert pass logs quietly;
the default log goes beside the DLL instead of the process CWD (`Apps\`).
Verified: same city, dialog open, private bytes flat at 178 MB for 5 min (was +40 MB/min). Moscow maximize /
restore x4: panel fills the full height and returns, 18 refits total, no growth after.

## Tooling - city_tile.py: a real city's layout repeated on a 1024 map (2026-10-09)

`re/tools/city_tile.py <src 256> <flat target> <out>` copies the source's roads verbatim (piece, flg, state; z
forced to the target level) and its zone slots (not 22, plopped) into each 256 block, adds seam roads at every
block's x/y = 0 line so the copies connect, recomputes the pieces at the seams from the 4-neighbour mask, and
lists 4x4 empty squares next to zones for power plants. Not copied: terrain, water, rail, highways, buildings.
Europolis (flat, all roads at z 75) -> `verify/perf1024/europolis1024.sc3`: 158,832 road tiles (9,520
recomputed), 624,096 zoned tiles, 48 plant spots. Loads and renders; 48 coal plants placed with place_direct.

## Finding 13 - on 1024 maps buildings stayed as blue boxes until a zoom change (sc3bigcity SPRJOURNAL, FIXED)

Owner on the Europolis 1024 city: scrolling, buildings never load; zooming loads them at once. Measured in that
state: queue empty, zoom 1 marked complete (`iso+0x430` = 2), but only 2,649 of 4,329 occupied cells in view
had the zoom-1 realized bit.

Cause: the loader journals each realize/release as a 4-byte record `{op, x, y, zoom}` with **x and y as bytes**
(writers SIMSPR `0x10008c46` realize, `0x10008b94` release, vector `iso+0x448`). The game thread applies it in
`FUN_10008dd4` (set/clear `DAT_100624f0[zoom]` in `cell+0x10`, or iso vt+0x78 for the live zoom), so on a
map wider than 256 the bit lands on `(x & 0xff, y & 0xff)`. The sprite is loaded, its own cell is never marked.
A zoom change goes through another path, hence the owner's observation `[CONFIRMED @ SIMSPR 0x10008e37]`.

Fix (`sc3bigcity.c`, SPRJOURNAL): both writers call `spr_build_rec`, which packs op (2 bits), zoom (3), x (11),
y (11) in the same 4 bytes; `FUN_10008dd4` is replaced by a C copy that decodes it. Verified: after zoom out/in
and a scroll onto a built block, buildings drawn within 1 s (shipped: still boxes at 15 s); 4,472 of 4,472
cells in view realized for zooms 0, 1, 2.

Also added, sc3perf `spr_follow` (default 1): the loader spiral (`iso+0x3e8`, seeded from the camera rect
`iso+0x340` only when a job starts) is re-seeded at the camera when it moved >= 8 tiles, via the loader's sleep
call `0x10008cda`, under the loader lock, clamped into the spiral bounds. On its own it changed nothing in the
A/B because the journal bug hid every result; it keeps the visible area first on 1024 maps.

## Finding 14 - side-panel icons 158 px below their buttons after the leak fix (sc3resize, FIXED)

The panel stops above the docked minimap (923 local at 2048x1081). `rz_side_fit_child` placed the art at
`panelH - 442 - dy` reading the panel's CURRENT local height, which SetRect still clamps to the old art sum
(1081) at that moment; `rz_side_children_bottom` then moved the buttons for the final 923. Art at row 639,
buttons +481. Before Finding 12's fix the leaking refit re-ran every poll and the second pass corrected it.
Fix: `rz_side_fit_surface` passes the height it is about to set (`target + capH`); log now reads art row 481,
buttons +481, and the lower button cluster sits above the minimap.

## Note - mods patching the same page must not restore its protection

sc3perf (SPRITES/SPR_FOLLOW, `0x10008aaf..0x10008cdf`) and sc3bigcity (ANCHOR16 and SPRJOURNAL,
`0x10008b4a..0x10008dd8`) patch the same SIMSPR page from their own watcher threads at module load. One of them
restoring the page to read-only while the other was writing faulted the game at start (`sc3bigcity+0x5B89`,
a memcpy, 1 of 3 launches). Both mods now leave patched pages RWX.

## Measured, not yet fixed

- Maximize on the 1024 city freezes 2.9 s (unmaximize 1.4 s): sc3resize steps 7 and 11 each call
  `FUN_10018cdf` (map-wide refresh), about 1.2 s each on 1024 vs ~50 ms on 256; step 8c re-show of all 1,048,576
  cells 0.1-0.3 s. Minimize/restore does not stall (max 0.26 s, sim running).
- Simulation on the Europolis 1024 city with ~240k placed buildings: one sim thread at 83% of a core
  (8% of 16), clock paused waiting for it. EIP samples: SimTransit `sc3_transit_select_next_cell` 18%,
  SIMGEOM `get_occupant_at_cell` 12%, msvcrt 30% + ntdll 17% (allocation/copies inside routing),
  `route_trip` 4.5%. Traffic routing, single-threaded.

## Finding 15 - 1024 simulation speed: traffic routing, no 256 bug in the hot path (2026-10-09)

Europolis 1024 (~240k placed buildings), speed 4: one sim thread at 93-99%, the clock waits on it.

- Trip router SimTransit `FUN_100070d0` (DFS with an explicit stack, greedy next hop `FUN_1000755e`, visited
  marker grid `layer+0x78`). Budget = `DAT_1001f0b0 * param_3` `[CONFIRMED @ 0x100070d0]`, and param_3 is the
  MAP WIDTH: measured 256 on Europolis, 1024 on the 1024 city (all trips, caller `FUN_10006fe3` <- outside module).
- Trips per minute and search steps (hook counts, 60 s):

| city | trips | arrived | steps/trip | trips >= 10k steps |
|---|---|---|---|---|
| Europolis 256 | 51,368 | 99% | 473 | 0 |
| Europolis 1024 | 27,092 | 98% | 3,297 | 12% |

  Long trips (type 0x80) flood ~5,700 distinct cells over a ~270x220 box, no wrap or jump, max cost ~4,108.
- Worker audit of 8-bit narrowing (`worker_transit256_out.md`, scratchpad): the only coordinate truncation is the
  cell iterator's LIST mode (`FUN_10008485` packs `(x&0xff)<<8|(y&0xff)`, `FUN_10008642` unpacks)
  `[CONFIRMED @ 0x10008642]`. Live: 1,452,192 iterator calls in 30 s, ALL in mode 1 (full-int probe), 0 cells
  outside their rect. Latent, not hit. The volume formula's `(char)` casts affect congestion amount only.
- Capping param_3 (Frida, live A/B, 40 s windows): 256 -> arrivals 98% -> 70-81%; 512 -> 78-89%. Faster, but it
  changes which trips succeed, so it is not a neutral fix. Not shipped.

Shipped anyway (correct, small): sc3perf `transit_clear` (marker grid cleared by write-watch pages instead of
1 MB per trip; grid moved into a MEM_WRITE_WATCH buffer, destructor `FUN_1000ab16` replaced to restore rows) and
`fast_ftol` (msvcrt!_ftol -> FISTTP; the system _ftol's fldcw pair was ~17% of sim samples). Measured together
1,838 -> 1,901 trips/s (+3%, inside the window-to-window spread of 12k-28k trips per 10 s). Days-per-second over
90 s is NOT a usable metric here: it swung 0.15-0.76 with the same build, depending on the sim phase.

## Finding 16 - crash one second after maximizing the 1024 city (SIMDIRT rasterizer) - FIXED 2026-10-11 (CELLFIX + DIRTCLIP)

Owner, 2026-10-09 15:17: maximize at 697.5 s, sc3resize finished at 699.1 s, game dead at 700.2 s with a write
AV at SIMDIRT `0x10013A8F` (`mov word ptr [ecx],ax`, ECX=0x18604496) in `FUN_10013556`
(sc3_dirt_render_gouraudpoly_flat), called from SIMSPR's view draw. The same address crashed on 2026-08-21, when
the cause was the surface lock not taken (LAUNCH_CONTROL.md 33.2 defect 5); the August log also has the sibling
rasterizer sites 0x11EAB / 0x12EC2 / 0x4AE1. Pre-existing, not from the day's changes.

Not reproduced: 29 maximize/restore cycles (sim paused and running), a per-call check of surface vs rectangles
(no rectangle outside the surface) and a per-store probe at `0x10013a85` over 6.4M stores (0 outside the
surface). (A first probe at `0x10013a8f` itself crashed the game: `0x10013a92` is a branch target inside the
5 patched bytes.)

Guard (sc3resize DIRTGUARD, default on): `FUN_10013556` and the per-tile dispatch `FUN_10012cb7`
(sc3_dirt_draw_dispatch, vtable +0x40 of all six terrain classes) run their original code through a trampoline
inside __try; an access violation skips that polygon / tile for one frame and is logged with context. Forced
test: the surface pixel pointer replaced with the read-only page 0x7FFE0000 for 30 SIMDIRT calls -> 12 faults
caught (rasterizers 0x10013556 and 0x100148d7), game kept drawing at 165 fps, the lock at SIMDIRT 0x100249f0
free afterwards (LockCount -1, RecursionCount 0). The next real occurrence logs surface, pixel pointer and
rectangles in sc3resize.log for the root cause.

Root cause (2026-10-11, re/analysis/DIRTCRASH.md): reproduced with DIRTGUARD off on the 7th maximize. The tile
clip was [1672 984 1680 988] on the 1680x987 render target (lock depth 1, live pointer): a clip below the
surface, not a stale surface. SIMSPR sizes the dirty grid with FUN_100059fb (falls back to 8 cells when no even
count 12..24 divides the size, 979 is odd) and FUN_1000e2c0 (cell = extent / count, truncated, 979 / 8 = 122).
FUN_1000d725 then maps rows 976..978 to cell row 8 of an 8-row grid: it writes the grid byte past the block and
passes cell rows 976..1098, which the display items use as the rasterizer clip. Fixed in sc3resize: CELLFIX
rounds the cell size up after each resize, DIRTCLIP clamps cell rects to the view at SIMSPR FUN_1000d0c5.
30 maximize cycles with the fix and the guard off: 0 faults. The same build with both fixes off faulted on cycle 8.

## Finding 17 - pollution only on the top-left quarter of a 1024 map (sc3bigcity ECOCURSOR, FIXED)

Owner: pollution shows on 4 of the 16 Europolis copies. Measured: the pollution grid is sized right (SIMECO
cISC3PollutionLayer, 512x512 cells of 2x2 tiles, shift 1), but air was non-zero only in cells 0..255 x 0..255,
and there in 100% of cells.

Cause (worker audit, re-read locally): the per-tick pass `FUN_10008249` walks the grid with a cursor at layer
+0x498 that init `FUN_10005844` forces into LIST mode. `FUN_1000a3eb` builds the list as one ushort per cell,
`(z & 0xff) | (x & 0xff) << 8`, and shuffles it (`FUN_1000af46`); `FUN_1000a5a7` unpacks the two bytes
`[CONFIRMED @ SIMECO 0x1000a3eb, 0x1000a5a7]`. On a 512-cell grid every coordinate wraps mod 256, so all 16
copies' cells fold onto the first quarter, four visits each. Air, water and garbage share the cursor. The same
cursor class exists in SimTransit (Finding 15) but there it runs in arithmetic mode and is not affected.

Fix (`sc3bigcity.c`, ECOCURSOR): `FUN_1000a3eb` runs as shipped (its ushort list stays built and sized), then for
a list-mode cursor wider than 256 a parallel list of full coordinates is built, same order, shuffled when the
game shuffles; `FUN_1000a5a7` is replaced by a C copy of both modes that reads that list. Callers are only the
pollution layer's init and tick.

Verified on the Europolis 1024 city, sim at speed 4, air-polluted share of cells per 256x256 block:
after 4 game-minutes every block with buildings is at 100%; the five copies left without buildings
(23, 30-33) are at 1-18% (spill-over from neighbours). Before: 100% in the four top-left blocks, 0% elsewhere.
Note: this is a balance change on big maps - garbage and pollution now come from the whole city, about 4x the
cells, so landfill/incinerator demand rises accordingly.

## Finding 18 - the 1024 freezes were a quadratic registry list in SIMCITY (fixed: LIST_COUNT + LIST_FIND)

Europolis 1024 (re/tools/city_clone.py, ~369k occupants): the date stood still for minutes at a time (one stall passed 12
minutes, then the game exited with no fault logged), the first month-end froze the window for 211 s, and the city took
97 s to load. Address space was not the cause (sc3perf now logs it: 620 MB used, 896 MB largest free block, flat).

sc3perf sampled the sim threads during a stall: 72% of the busy samples were in SIMCITY `FUN_10001db0` and 11% in
`FUN_10001c63` `[CONFIRMED @ 0x10001db0, 0x10001c63, 0x10001bec]`:
- SIMCITY keeps per-category registries of sim objects as VC6 `std::list`s (heads at `this+0x44+4*i`, i < 6; node
  +0 next, +4 prev, +8 value, erase `FUN_10001df7`). Category 3 holds every building: 348k nodes on this city.
- Add `FUN_10001bec` pushes to the back (`FUN_10001dc0`), then calls `FUN_10001db0`, which counts the list by walking
  every node, only to test `== 1`. Remove `FUN_10001c63` searches from the front for the node, erases it, and counts
  again only to test `== 0`. `FUN_10001db0` has no other caller. So every add or remove walks the whole list, and a
  remove walks it twice. Measured with Frida: 2,450 removes a minute, the removed node on average 303k from the front.
  This is Finding 6's "small inefficiency" at 1024 scale.

Fix (sc3perf, default on):
- `list_count`: JMP at `FUN_10001db0` to a constant-time version returning min(count, 2), exact for both tests.
- `list_find`: hash index (list head, object) -> node. Hooks: the push_back call at `0x10001c15` (new node =
  head->prev), the remove's search loop `0x10001c80..0x10001c96`, and the range erase `FUN_10002120` (teardown:
  wipes the index). A list is indexed by one walk at its first search; every hit is checked against the node's links
  (value, next->prev, prev->next) and any mismatch or duplicate drops back to the walk.

| Europolis 1024, speed 3, 10 min | days simulated | longest date stall | load |
|---|---|---|---|
| before | (stalls of 224 s and 722 s; one run exited) | > 12 min | 97 s |
| list_count | 206 | 3-7 s | 48 s |
| list_count + both-ends search (tried, replaced) | 222 | 3-10 s | 21 s |
| list_count + list_find (index) | 519 | 2.7-7.6 s (weekly traffic batches) | 21-25 s |

Index counters over the 10 minutes: 400,367 lookups, 0 fallback walks, 1 build, 0 drops. Worst frame 35 ms across
about 17 month-ends (the 211 s month-end freeze was the game thread waiting on the registry lock). Regression on
Moscow (256), speed 4, 4 min: 1,358 days = 5.9 days/s (nominal 6.08), worst frame 7 ms, 64,290 lookups, 0 walks.

What is left on the 1024 sim thread: traffic routing (56% of the stall samples) and SIMGEOM occupant queries (21%),
in weekly batches (SimTransit `FUN_100097b9`, one trip per building per month in four weekly groups). A threading
study (scratchpad worker_transit_mt.md) found the trips can be farmed out to worker threads with per-thread copies of
the marker grid and iterator, but results would differ from serial (each trip's congestion feeds the next) and every
routing step takes SIMGEOM's occupant-manager lock (mgr+0x90), so the speedup must be measured before it is worth it.

## Finding 19 - sim-busy indicator (sc3perf `busy=1`)

Owner request: a visible cue when the date stops for a reason. A 10-byte hook at SIMCITY `FUN_1000aa4d` (day fire,
ecx = clock: +0x50 speed, +0x54 pause count, +0x60 ms per day `[CONFIRMED @ 0x1000a066, 0x1000a0ec]`) timestamps
every day. When a day is more than 1 s late, the speed is not the paused one and the city is neither user-paused nor
camera-held (city+0x140/+0x144), the overlay shows a red line with how late the date is, the sim threads' CPU use and
which modules their samples fall in ("SIM BUSY 12.4 s CPU 79% traffic 62% map grid 18%"), or "sim idle, clock held"
when the sim is not working. The stack probes use VirtualQuery, not IsBadReadPtr (whose first-chance faults filled
sc3resize's crash log with 88k lines in 3 minutes).

## Finding 20 - traffic routing on worker threads (sc3perf `traffic_mt=N`, default 8 since 2026-10-09)

Owner question: can the 32-bit game use more cores? 32-bit is not the limit (a 32-bit process runs threads on every
core; its limit is 2 GB of address space, SC3U.exe is not large-address-aware). The limit is that the sim runs on
one thread and its state is shared. After Finding 18 the 1024 sim thread is mostly traffic routing in weekly bursts.

Design (static study: scratchpad worker_transit_mt.md): the per-building issuer SimTransit `FUN_100097b9` (iOS
`BuildingTrafficMonthly::Apply`) calls the trip function `FUN_10006fe3` and discards the result. Those calls are
queued (occupant AddRef'd); a flush routes the queue on N workers, each on a SHADOW of the 0x110-byte traffic layer
with its own visited-marker grid (write-watch cleared), cell iterator and counters. The two shared writers are replaced
for every caller by atomic versions with the same arithmetic: congestion `FUN_10006edd` (CAS saturating byte add) and
trip-result bits `FUN_10006a72` (InterlockedOr/And). Flush points: queue full (4096), 500 ms after the first queued
trip, the trip-from-cell entry `FUN_1000706a`, the stats pass `FUN_10009242`, and any other caller of the trip function.

Results, Europolis 1024 (`city_clone.py`), speed 3, Ryzen 7 5800X (8 cores / 16 threads):

| run | days | trips | arrived | notes |
|---|---|---|---|---|
| 10 min, traffic_mt=0 (Finding 18) | 519 | | | |
| 10 min, traffic_mt=8 | 850 (+64%; nominal 900) | 2,420,680 routed by workers, 0 faults | | median date stall 2.7 s, window minimized after 400 s |
| 4 min, traffic_mt=0 | 203 | 610,853 | 90.7% | |
| 4 min, traffic_mt=8 | 257 (+27%) | 737,996 | 89.7% | |

Trips in one batch see the congestion other workers leave as they go, not a fixed serial order, so arrivals moved by
1 point. 3 maximize/restore cycles with 8 workers: no fault. Owner turned it on by default (8 workers, capped at logical CPUs - 1).

## Open: resize step 7 faults in SIMSPR on the 1024 city

With or without traffic_mt, the map-wide refresh in sc3resize's resize step 7 (`FUN_10018cdf`) faulted on a null read in
SIMSPR (`+0x2D102` once fatal after 2.5 game years of play, `+0x5AFDA` once caught by sc3resize's guard). Not
investigated yet.

## Finding 21 - what else can run on worker threads (owner question, 2026-10-09)

Profiled the sim thread with traffic_mt=8 (10 min, Europolis 1024, speed 3): it is busy 9% of the time; 38% of its
samples are the wait for a traffic batch. No other pass is above 1.5% (SIMGEOM `grid_query_point_in_window` 1.45%, the
registry iteration `FUN_10001914` 0.2%), so on this city nothing else is worth moving to workers yet. The cost left is the
traffic batches themselves.

Profiling the 8 workers (sc3perf now samples them as sim threads) showed most of their routing time waiting on locks:
| lock | where | share of worker samples (inclusive) |
|---|---|---|
| SIMNTWRK network-piece AddRef/Release, one global CRITICAL_SECTION 0x100325f8 | `FUN_10023886` / `FUN_100238cc` via `FUN_10026584` | ~15% |
| SimTransit STL node allocator spinlock DAT_1001fe00, backs off with Sleep() up to 128 ms | `FUN_10009f58` / `FUN_1000a08f` / `FUN_10009fcf` | ~11.5% |
| SIMGEOM occupant manager CRITICAL_SECTION mgr+0x90 | `get_occupant_at_cell 0x1000ec60` via `FUN_1001adf5` | ~10.5% |

sc3perf `mt_locks=1` (default, with traffic_mt) removes the first two: worker threads get their own allocator free
lists (TLS; other threads run the original code with the original lock), and the piece refcount (low 16 bits of
piece+0xc) plus the stats counter (`FUN_100010a6()`+0x20) become CAS loops with the same arithmetic. The SIMGEOM lock is
left: the UI thread edits the occupant grids under it, and it is now ~20% of the remaining stall samples.

| 5 min, speed 3, traffic_mt=8 | days | routing ms per trip | stalls | stall total |
|---|---|---|---|---|
| without mt_locks | 322 | 0.09 | 45 | ~160 s |
| mt_locks | 374 | 0.04 | 16 | 38.5 s |
| mt_locks + traffic_mt_async | 380 | (overlapped) | 17 | 36.8 s |

`traffic_mt_async=1` lets the sim thread continue while a batch routes (double-buffered queue); it gained 2% because the
weekly trip burst refills the queue faster than a batch routes, so the sim thread waits anyway. Default off.
Arrivals (4 min): serial 90.7%, traffic_mt 89.7%, traffic_mt + mt_locks 88.9% (849,932 trips, 299 days vs 203 serial).
Remaining ceiling: routing throughput (~27k trips/s on 8 workers) and the SIMGEOM lock.

### Finding 21b - the SIMGEOM occupant-manager lock (sc3perf `geom_held`, default off)

Tried at the owner's request. For a synchronous batch the sim thread takes the locks of the traffic layer's two occupant
managers (layer+0x94 / +0x98, lock object *(mgr+0x90), vt+4 / vt+8) once, releases the workers, and drops them after the
batch; worker threads read through a lock-free copy of GetOccupantAtCell `0x1000ec60` (same logic, from its disassembly).
Lock order is the original one (the sim thread took that lock while routing). 5 min, Europolis 1024, speed 3: 377 days
(374 without), routing 39.4 s (41.3 s), 400,620,199 lock-free reads, 0 faults. An uncontended CRITICAL_SECTION costs
nanoseconds; the wait seen before was mostly the two locks mt_locks removed. Left off by default: ~1% gain, and player edits
would wait for a whole batch. Worker profile after it: no lock waits left; the busy time is routing itself
(`route_trip`, `select_next_cell`) plus ~3% in sc3perf's replacement functions.

## Finding 22 - cheaper routing per trip (owner request): FAST_CEIL, and what is left

The DFS router (`route_trip 0x100070d0`) does per step: arrival test `FUN_10008a94`, push a 32-byte cell record,
`select_next_cell 0x1000755e` (scan the ring around the current piece: marker grid, network flags +0x5c, congestion
bytes; keep the least congested; GetOccupantAtCell on the pick; mark its footprint visited; step cost), backtrack with
Release of the piece on failure. The step cost ends with `ftol(ceil((double)cost))` `[CONFIRMED @ 0x100083a6]`, and
msvcrt's ceil switches the x87 rounding mode with fldcw and back (msvcrt+0xa9024, the same helper FAST_FTOL removed
from _ftol) - it was the largest single item in the workers' routing samples.

sc3perf `fast_ceil=1` (default) points SimTransit's ceil import (IAT 0x1001a0ac) at a FISTTP version (truncate, +1 when
below the input; |x| >= 2^31 and NaN go to msvcrt). All three SimTransit call sites convert the result to an integer
at once. Offline check against the CRT ceil: edge cases plus 10,000,000 values in the game's range, 0 mismatches.
Also: the SIMNTWRK stats object pointer used by the lock-free AddRef/Release is cached (was a call per step), and the
profiler's stack copies are guarded (a copy past a worker's stack top read memory freed after VirtualQuery and took
the game down once).

| 5 min, Europolis 1024, speed 3, traffic_mt=8 + mt_locks | trips | routing | ms per trip | stall total | days |
|---|---|---|---|---|---|
| before | 1,060,792 | 41.3 s | 0.039 | 38.5 s | 374 |
| fast_ceil | 1,123,202 | 35.4 s | 0.032 | 33.7 s | 375 |

Days hardly move now: stalls are ~11% of the run, and speed 3's ceiling is 450 days per 5 minutes. Routing cost per trip
since the first threaded version: 0.09 -> 0.032 ms. What is left inside a trip (worker samples): select_next_cell's own
scan ~40%, occupant lookups + their lock ~22% (geom_held removes the lock, +1%), the lock-free piece refcounts ~16%
(cache-line traffic between workers on shared road pieces), the marker grid's write-watch syscalls ~13% (2 per trip).

## Finding 23 - where the rest of the daily sim pass goes (10 min profile, all optimizations on)

Europolis 1024, speed 3, traffic_mt=8 + mt_locks + fast_ceil: 754 days in 600 s (speed 3 nominal: 900). sc3perf now
logs day lengths once a minute (`DAYS>`) and samples the TRAFFIC_MT workers into their own tables (E3/I3,
`perf_report.py --thread workers`; the thread finder's 8-thread cap had hidden the real sim threads behind the workers).

Day lengths (the sim pauses the clock while it works, so every ms of sim work lengthens a day): median 657 ms on a
666 ms nominal day, mean ~790 ms, p90 1.1-1.3 s, max 2.2-2.3 s. Ordinary days are on time; about one day in ten
carries the loss.

The slow days are traffic-batch days: all 29 stalls >= 1.7 s in the 10 minutes were dominated by routing chains
(`select_next_cell < route_trip < FUN_10006fe3`, occupant lookups). Roughly 87k trips come due on such a day; at
0.032 ms wall per trip on 8 workers that is ~2.8 s, during which the sim keeps the clock paused.

Sim threads outside the traffic waits: busy 11.3% of samples. Inclusive, mostly zone development: SIMRCI
`FUN_1003372a` / `FUN_10031499` ~9.6% (tile evaluation `inddev/resdev/comdev_evaluate_tile`, building placement
`zonelayer_place_building_attrib` / `_reskey`, removals `occmgr_remove_occupant_*` ~4%, `zonelayer_is_near_transport`
~2.5% driving SIMGEOM region scans `grid_query_point_in_window` 1.8% exclusive, the top exclusive item). Order-dependent
(each placement changes the map), so not a worker-thread candidate. Also seen on the sim thread, not threaded: a trip
issued from SC3U.exe `FUN_004bfe89` and a second router path through `FUN_100140f4`.
Correction 2026-10-11: `FUN_100140f4` is SimTransit.dll (the only module with a tracker row there, and the only one
with samples at +0x140f4..+0x14100 in the profile dumps). It is not a router: `push 0x200; call
sc3_transit_alloc_node; pop ecx; ret`, the deque buffer allocator of the router's work queue, now
`sc3_transit_alloc_dequebuf` (its pair `FUN_10014100` = `sc3_transit_free_dequebuf`) [CONFIRMED @ SimTransit 0x100140f4].
In `sc3perf_prof_mtprof.txt` the return address after the allocator call (+0x140fe) is on the stack in 2508 worker
samples (I3) and 3 sim-thread samples (I2); the free call's (+0x1410e) in 1309 worker samples. So that cost is
STL node allocation inside routing, not a second routing path.

Next lever (not built): smooth the traffic batch instead of routing it all on one day - keep an unbounded queue that the
workers drain in the background while the clock runs, and flush only before the monthly stats pass `FUN_10009242`. It
keeps which trips happen but applies their congestion and result bits up to a few days later (the congestion grids
are a decayed monthly accumulator), and the workers would run concurrently with the sim thread's own day passes,
which the synchronous design avoids.

## Finding 24 - traffic smoothing: the trip queue drains in the background (sc3perf `traffic_mt_smooth=1`, default)

The monthly per-building trips go into a 524,288-slot ring; the 8 workers take chunks of 32 continuously while the sim
thread and the clock carry on. Each chunk runs on the worker's shadow layer refreshed from the live layer; counters go
into shared accumulators the sim thread adds to the layer; finished trips' occupants come back through a second ring
and are Released on the sim thread (a building's last Release must not run its destructor on a worker).

Drain points, found by measurement: the first version also drained before every other trip call and lost (709 days):
`FUN_1000706a` (trip from a cell) is called ~17 times a second by zone development, and SIMECO+0x423c calls the trip
function too - 8,871 waits in 10 minutes. Those callers now route at once on the sim thread on the real layer and its own
marker grid, alongside the workers (all shared writes are atomic or lock-free; they see congestion without the queued
trips, the same lag the queued trips have). Only the monthly stats pass `FUN_10009242` (it decays and publishes the
congestion grids), a full ring, and city teardown drain. Teardown signal: at exit the traffic layer object is never
deleted (a destructor hook on `FUN_1000154e` never fired in 5 closes) but its marker grid is, so the grid destructor
(sc3perf's `tr_dtor`) drains first; this is why smoothing requires transit_clear.

| 10 min, Europolis 1024, speed 3 | days | stalls >= 1.7 s | sim thread waiting on traffic | p90 day |
|---|---|---|---|---|
| synchronous batches (Finding 23) | 754 | 29 | ~38 s | 1.1-1.3 s |
| background queue | 849 / 853 | 2 / 0 | 2.2 s / 1.2 s | 0.76-0.81 s |

2.39 million trips routed by the workers per 10 minutes, 0 faults. Arrivals (4 min): 88.7% (synchronous 88.9%, original
serial routing 90.7%); 340 days in 240 s vs 203 for the original routing.

Exit-time crash seen while testing (separate bug, not the queue): closing the game faulted in SIMSPR during shutdown in
4 of 5 runs with traffic_mt on and 1 of 3 with it off (`SIMSPR+0x2D112`, `+0x40B9F`). `0x1002d0e2` walks SIMSPR's
sparse sprite-cell map (row list -> cell list) and read a null `next`: the map was being changed while walked. The sim
thread changes it when buildings are replaced (`sc3_spritecellmap_insert` in the sim profiles) while the game thread
walks it in map-wide refreshes and at teardown - the same family as the 1024 maximize crash (`+0x2D102`, Finding 16
area). A faster sim replaces buildings more often per second, so it hits more often. To fix in SIMSPR (locking), not in
the queue.

## Finding 25 - the maximize / exit crashes: non-atomic reference counts and an unlocked map walk (fixed)

Crashes after maximizing the 1024 city and on quitting it (SIMSPR `+0x2D102` / `+0x2D112` / `+0x40B9F` / `+0x5AFDA`,
SIMSERV `+0xCAD3`, SIMCITY teardown `+0x69BB` calling a dead object) - more frequent with traffic_mt, also seen without.
Live probe: the sparse-map methods behind `0x1002d0e2` run only on the game thread, so it was not two threads editing
one list. Static read (scratchpad worker_sprmap.md) and teardown probes found two original-game bugs:

1. Non-atomic reference counts on objects that receive message fan-out from the SIM thread while the GAME thread also
   references them (GZServiceD MessageSend Releases each target after dropping its lock, on the sending thread). A lost
   update frees the object while in use; the walk then reads freed memory (the "null next"), or a later Release destroys
   it twice. Replaced by atomic versions with the same results (sc3perf `spr_refcount=1`, default; no lock added):
   - SIMSPR AddRef `0x10021551` (+8, shared by five classes: view overlays 0x10064390 at bridge+0x110/+0x114/+0x118 and
     vtables 0x10064194, 0x10065f24, 0x10066618, 0x10066a24) and their Releases `0x1002209c`, `0x10021558`,
     `0x10035433`, `0x1002e929` (destroys at <= 1 via vt+0x20), `0x10037c93` (vt+0x28); effect manager 0x10067264
     (bridge+0x108) AddRef `0x1003cf95` / Release `0x1003cf9c` (+0xc).
   - SIMSERV class 0x1001f2c8: AddRef `0x1000c3df` / Release `0x1000cab6` (+0x38, destroy vt+0x44).
   - SimTransit traffic layer: AddRef `0x1000526c` / Release `0x10005237` (+0xc, plus the module stats counter;
     destroy vt+0xc4). Teardown probe: index 19 of city+0x94, released by SIMCITY `0x100069b8` with its vtable already
     overwritten by text ("dern"). Same fault with traffic_mt=0, so this is the game's bug.
2. The resize pass's map-wide refresh (SIMSPR FUN_10018cdf, sc3resize steps 7 and 11) ends by walking every cell's
   occupant chain holding only the view's data lock, while zone development replaces buildings under the city's tick
   lock L1 (city+0x1a8): it met a half-destroyed building (forwarder FUN_1005afd3, null inner object, SIMSPR+0x5AFDA).
   sc3resize `SIMLOCK` (default; SC3RESIZE_SIMLOCK=0 off) holds L1 for the whole pass: same order as the sim
   (L1 -> data lock -> view), L1 is re-entrant for its owner, and the pass runs from the window procedure with no locks.

| 1024 city | exits faulted (traffic_mt=8) | exits faulted (traffic_mt=0) | maximize/restore cycles faulted |
|---|---|---|---|
| before | 4 of 5 | 1 of 3 | step-7 faults, one fatal |
| after | 0 of 6 | 1 of 6 (heap corruption freeing in another module) | 0 of 5 |

The one remaining kind of exit fault (heap corruption detected during teardown frees, seen once in SIMADV and once in
ntdll from a free) is not explained yet. The crash logger also records handled first-chance faults from IsBadReadPtr
probes (KERNEL32+0x2CC02); those are not crashes.

### Finding 25b - the remaining exit heap corruption: the same bug, engine-wide (fixed: LAYER_REFCOUNT)

Both heap-corruption exits had one stack: city teardown (SIMCITY `0x100069bb`) -> SIMADV Release `FUN_1002ba93` ->
deleting destructor `FUN_1002baec` -> `free(this)` on an object already freed. FUN_1002ba93 is again a plain
decrement-and-destroy, with the module stats counter. A survey of every game DLL (scratchpad refsurvey.py) found ~600
AddRef bodies with an unlocked `inc`; the ones that matter are the layer/agent objects that get sim-thread message
fan-out, and their AddRef/Release come from four compiler templates (AddRef with stats; Release always-decrement;
Release if-nonzero, two encodings). sc3perf `layer_refcount=1` (default) matches them byte for byte in every game DLL
as it loads (only the field offset, the stats-getter call and the destroy slot vary; branch distances must match) and
routes each through a 16-byte stub to one atomic implementation with the same results: 51 AddRef + 61 Release in 21
DLLs, as the static scan predicted. SimTransit's layer keeps its own atomic version (it drains the trip queue).

| 1024 city exits | traffic_mt=8 | traffic_mt=0 |
|---|---|---|
| before Finding 25 | 4 of 5 crashed | 1 of 3 |
| after 25 (SIMSPR/SIMSERV/traffic layer) | 0 of 6 | 1 of 6 (SIMADV heap) |
| after 25b (all layer templates) | 0 of 8 | 0 of 8 |

Two runs logged a fault at KERNEL32+0x2CC02: that is sc3resize's own IsBadReadPtr probe (sc3resize+0x8767/+0x87CC)
raising and handling a first-chance fault during teardown; the exit completed normally in both.
Play check after the patch: 84 days per 60 s at speed 3, median day 657 ms, no faults.
