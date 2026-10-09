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

## Finding 16 - crash one second after maximizing the 1024 city (SIMDIRT rasterizer) - guarded, root cause open

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
