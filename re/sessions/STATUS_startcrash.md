# STATUS startcrash (startup crash at GZGraphicD+0x14904), child of the 2026-10-29 round

## goal
2 of 6 launches in dev\hwyscurve crashed 1..6 s in: 0xC0000005 READ 0 at GZGraphicD.dll+0x14904 (FUN_10014894, blit
dispatcher, null dest +0x44). Reproduce with a startup loop, find which surface is null and why, fix with an off switch,
show the rate drops to 0. RESULTS: `verify/startcrash/RESULTS.md` (in the worktree).

## verdict + deciding RVA (milestone 2: fixed, 2026-10-29)
- Null surface = the 800x600 SCREEN device's render raster (device+0x44). The crash is the loading window's WM_PAINT:
  GZGraphicD wndproc FUN_10017e2f -> FUN_10011e76 -> GZWIND draw -> SC3U FUN_004413ef -> FUN_0043d489 blits image
  [win+0xac] into target [win+0x5c] = screen device via vt+0x118 = FUN_10014894, +0x70 `mov eax,[ecx]`, ecx =
  [ebx+0x44] = 0 [CONFIRMED @ GZGraphicD 0x100148fa, SC3U 0x0043d4f1, traced live].
- +0x44 is NULL only after the device's release-all (vt+0x20c FUN_1001673b -> FUN_10014410) or a failed raster create
  (FUN_1001420d after both CreateSurface calls of FUN_10019273 fail). In a normal start the screen device is made once
  at ~0.8 s and never released. No sc3resize code touches it at startup.
- `GZGraphicD+0x1F328` on the stack = the device vtable. `sc3resize+0x30E8D` (= rz_mb_present+0xCD in the 584ab1f
  build) = stale slot: the 10-07 simrun crash log has the same stack without it.
- Natural trigger NOT reproduced: 0 of 50 natural launches (fresh-hash DLLs, second game running, paint storm, fixed
  build). Proven by forced null on the real path instead: NULLBLIT=0 crashes at 0x14904 with the reported stack,
  NULLBLIT=1 skips 1 blit, logs, recovers, reaches the city.
- Orchestrator follow-up (does it stay broken?): with a REAL teardown (GZ's own release-all on the screen device at
  the first paint), skip-only (NULLBLIT=2) crashes on the next present (GZGraphicD+0x16C3D, freed primary cached in
  device+0xb0). GZ never rebuilds the screen device after startup. Default NULLBLIT=1 now rebuilds it (vt+0x20c +
  vt+0x204) and re-reads the present target (FUN_10016ba4, delta 0): game reaches the city, frames normal.

## built
- sc3resize block NULLBLIT (`SC3RESIZE_NULLBLIT=0` stock): wraps vtable slots +0x118 / +0x138 of device vtables
  0x1001f328 and 0x1001e894 (.rdata, from the EARLY loader notification). Skip + episode log (device, size, init
  flag, caller, window, display mode) + recovery log. Screen device recorded via vt+0x208 wrap; rebuild = vt+0x20c,
  vt+0x204, FUN_10016ba4(0), max 3 tries / episode, 2 s apart. `=2` skip only. Built into dev\startcrash\inst.
- `re/tools/startup_loop.py`: --tree (dev layout), --fresh, --mods, --paintstorm, FAULT summary per launch.
- `re/tools/frida_devtrace.py` (new): device INIT / raster create / release / null-blit trace from spawn, window
  background draws, screen device rebuilds, --failsurf (surface create fault injection), --nullat (forced null),
  --activate (WM_ACTIVATEAPP).

## proven game-side vs static only
Game-side: forced-null A/B, forced-teardown A/B/C (0 / 2 / 1), 20/20 + 20/20 regression launches (no episode, no
fault), fault injection results, frames `MAIN\verify\startcrash\owner_shots\teardown_rebuild_t5/_t18.png` (RESULTS). Static only: the +0x138 wrap (FUN_10014918, mirror of +0x118, never seen null), the natural trigger.

## blocked on
Nothing.

## files owned (worktree dev\startcrash\wt, not committed)
- M `re/harness/src/sc3resize.c` (NULLBLIT block, 2 call sites, env parse)
- M `re/tools/startup_loop.py`
- new `re/tools/frida_devtrace.py`
- new `verify/startcrash/RESULTS.md`
- not for git: `MAIN\verify\startcrash\runs\`, `MAIN\verify\startcrash\trace\` (logs), `MAIN\verify\startcrash\owner_shots\`

## game-harness need
None running. Own tree only.

## asks of other sessions
None. Open (RESULTS): other unchecked +0x44 reads (GZGraphicD FUN_1001552e+0x4f, FUN_10014649+0x14) stay stock.
