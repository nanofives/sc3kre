# startcrash: startup crash 0xC0000005 READ 0 at GZGraphicD+0x14904 (child startcrash, 2026-10-29)

Logs (not in git): `MAIN/verify/startcrash/runs/` (startup loops, one folder per launch) and
`MAIN/verify/startcrash/trace/` (Frida traces). Relative `trace/...` names below are under that folder.

Report: 2 of 6 launches in dev\hwyscurve died 1..6 s in at GZGraphicD.dll+0x14904 (`re/sessions/STATUS_hwyscurve.md`).
Same site as the monitor-change crash (memory project-test-display-environment) and the mod-off crash in
`verify/simrun/RESULTS.md` (`re/harness/combo/crash_resize_0024.log`).

## Verdict

The crash is the loading window's WM_PAINT blitting into the 800x600 screen device while that device has no render
raster (device+0x44 = NULL). GZGraphicD's paint path never checks for that state. A device is in that state only after
its release-all, or after a failed surface create. In a normal start neither happens. The trigger on the hwyscurve
runs (a display change or a transient DirectDraw CreateSurface failure) was not reproduced naturally here: 0 of 50
natural launches. Fix: sc3resize block **NULLBLIT** (`SC3RESIZE_NULLBLIT=0` = stock) skips and logs a blit into a
device without a raster. When that device is the screen device, it also rebuilds it with GZ's own startup sequence and
refreshes the present's cached primary. GZ never rebuilds that device itself after startup, and skipping alone only
moves the crash to the next present. Forced teardown test (GZ's own release-all on the screen device at the first
loading-window paint):

| `SC3RESIZE_NULLBLIT` | result |
|---|---|
| 0 (stock) | crash at GZGraphicD+0x14904, the reported stack |
| 2 (skip only) | 100 blits skipped in 0 ms, then a crash on the next present: a jump through a freed object from GZGraphicD+0x16C3D (present FUN_10016bf1, Blt onto the released primary cached in device+0xb0), then the game's own crash reporter faulting at SC3U+0x143A |
| 1 (default: skip + rebuild + present refresh) | 1 blit skipped, rebuild ok in under 1 ms, device+0xb0 re-read, game reaches the city with 32,031 blits into the rebuilt device. Frames at 5 s and 18 s show the city drawn normally (`owner_shots/teardown_rebuild_t5.png`, `_t18.png`) |

## The code path `[CONFIRMED]`

Crash stack, mapped through the export and the disassembly, and traced live in a normal start (`trace/t3.txt`,
WDRAW at 1104 ms, same frames):

```
USER32 -> GZGraphicD 0x10017e11 (static WndProc stub, this = [0x1006cdb8]) -> FUN_10017e2f WM_PAINT branch
  (BeginPaint, FUN_1001a7ad()->vt+0x48) -> FUN_10011e76+0x3e -> FUN_10015aec (children vt+0x18)
  -> GZWIND FUN_10021680 / FUN_100200df / FUN_1001ed43 (window draw)
  -> SC3U FUN_004413ef -> FUN_0043d489: blit image [win+0xac] (640x480) into target [win+0x5c] (the 800x600
     screen device) via target vt+0x118 (SC3U 0x0043d4f1)
  -> GZGraphicD FUN_10014894 +0x66: mov ecx,[ebx+0x44] ; +0x70: mov eax,[ecx]   (ebx = target device)
```

- `GZGraphicD+0x1F328` on the reported stack is the device vtable (0x1001f328: +0x118 = FUN_10014894), not a frame.
- `sc3resize.dll+0x30E8D` (hwyscurve build, source 584ab1f rebuilt with /MAP) = `rz_mb_present+0xCD`, a stale stack
  slot. The 10-07 simrun crash log has the identical GZ/SC3U stack without it.
- Device+0x44 is written NULL only by FUN_10014410 (vt+0x1e8, reached from the release-all FUN_1001673b vt+0x20c, and
  from FUN_10009f63) and by FUN_1001420d when the raster create fails (FUN_10019273: video memory CreateSurface, then
  system memory, both failing) `[CONFIRMED @ GZGraphicD 0x10014410, 0x1001420d, 0x10019273, 0x1001611b]`.
- Normal start (`trace/t2.txt`, `t3.txt`): the screen device is created once at about 0.8 s (FUN_100114b8 ->
  FUN_10016106 -> FUN_1001611b -> INIT) and never released. Image devices are released and re-created all the time
  (GZResourceD loads, SIMUI, sc3resize's panel resize), always followed at once by a successful INIT.

## Reproduction attempts (startup loop, 8 mods, one 1536x864 display, `re/tools/startup_loop.py`)

| run | condition | launches | crashes |
|---|---|---|---|
| A | DLLs with a new hash every launch (`--fresh`), no other game | 10 | 0 |
| B | same, plus a second SC3U of mine running from the same tree | 12 | 0 |
| C | paint storm: InvalidateRect on the game's windows every 1 ms for 13 s (~50k per launch) | 8 | 0 |
| D | NULLBLIT build, skip only (first build, regression) | 20 | 0 |
| E | final NULLBLIT build: skip + screen rebuild (regression) | 20 | 0 |

Defender did not slow these starts the way the hwyscurve first starts were slowed (first start 1.1 s to GZGraphicD,
0.4 s warm), so the "24 s first start" condition was not recreated. In each run, 1 launch had not reached the city
14 s in (A01, B03, C06, D08: a slow load, ALIVE, no fault), with and without the block. E: 20 of 20 at the city.

Trace / fault injection (`re/tools/frida_devtrace.py`, logs in `trace/`):
- `--failsurf 800,600,1`: the screen device's first raster create made to fail. GZ retried (system memory) and the
  game reached the city. Absorbed.
- `--failsurf 800,600,2`: SIMSPR's 800x600 view device made to fail at 6 s. Died at a different NULL +0x44 read,
  GZGraphicD+0x1557D (FUN_1001552e). Not covered by this block (see open items).
- `--activate`: WM_ACTIVATEAPP 0/1 sent 4 times during the start. No screen device reset.

## The fix: NULLBLIT (re/harness/src/sc3resize.c, own block)

Wraps vtable slots +0x118 (FUN_10014894, target = this) and +0x138 (FUN_10014918, target = [esp+4]) in both device
vtables 0x1001f328 and 0x1001e894. These are data writes to .rdata, installed from the EARLY loader notification
before GZGraphicD's DllMain, and no code page is shared with another mod. No direct calls to either dispatcher exist
(byte scan of .text). A blit whose target has +0x44 = 0 returns 0 without reading it. The first skip of an episode
logs the device, its size, its init flag, the caller, the window state and the display mode. The return of the
raster logs how many blits were skipped. Hot path cost: one load and two compares.

Screen rebuild (`SC3RESIZE_NULLBLIT=1`, default; `=2` skips only). GZ never rebuilds the screen device after startup:
the only callers of its build slots vt+0x204 / +0x208 are the startup FUN_100114b8 and FUN_1001611b's own
system-memory retry. So the block records the screen device as GZ builds it (device vt+0x208 FUN_1001611b wrapped,
`this` kept on success). When a blit finds that device without a raster, the block runs, from inside the skipped blit
on the game thread:
1. vt+0x20c FUN_1001673b, release all (safe on a partial device);
2. vt+0x204 FUN_10016106, build primary + device + back buffers (GZ's startup sequence);
3. FUN_10016ba4 with a delta of 0 on the device's +0x6c interface. The present FUN_10016bf1 Blts onto the primary
   that interface caches in its +0x44 (device+0xb0), and only FUN_10016ba4 re-reads it (`this+0x44 = vt+0x78()`).
   Without this step, the rebuilt device still presented onto the freed old primary and crashed at GZGraphicD+0x16C3D.

At most 3 tries per episode, 2 s apart, each logged with its result. The window draw's begin/end (vt+0x1c/+0x20 with
flag 0x10, FUN_10014649 / FUN_1001467e) only touch counters, not the raster, so rebuilding between them is safe.
Other devices without a raster are skipped and logged only (no rebuild path known).

Forced-null A/B, first build (skip only, before the rebuild existed; `--nullat 0`: the first loading-window draw runs
with the screen device's +0x44 zeroed, put back at the draw's exit by the test itself, so it does not show what
happens without a restore. The teardown test in the verdict does):

| NULLBLIT | result |
|---|---|
| 0 | `VEH FAULT code=0xC0000005 at GZGraphicD.dll+0x14904` at 1329 ms. Trace NULL hit with bt SC3U+0x3d4f7, GZWIND+0x1edaa/+0x200f2/+0x21689, GZGraphicD+0x15aff/+0x11eb4/+0x17e84/+0x17e2c, USER32: the reported stack |
| 1 | `NULLBLIT> ### episode 1: device 0x049E51D0 (800x600, init 1) has no raster ... from SC3U.exe+0x3D4F7 skipped`, then `has a raster again after 1 skipped blit(s)`. Game reached the city (10,670 blits into that device) |

Regression, final build (run E): 20 of 20 launches, `--- NULLBLIT: on - 2 of 2 device vtables wrapped ...; screen
rebuild on` in every log, no episode, no access violation, all at the city by 14 s.

## Open items

- The natural trigger on the hwyscurve runs is unproven. If it recurs, the `NULLBLIT> ### episode` line in that run's
  sc3resize.log gives the init flag (0 = the create failed, 1 = released after a good create), the window and the
  display state.
- Other unchecked +0x44 reads stay stock: GZGraphicD FUN_1001552e+0x4f (seen with the SIMSPR device failing) and
  FUN_10014649+0x14 (the 10-22 CREATEFAIL case). sc3resize CREATEFAIL covers only its own resize creates.
- If the rebuild fails 3 times (the display still unavailable), the screen stays without a raster and every blit is
  skipped. The log counts skips at 100 and 10,000. No later retry after the 3 tries. Proven only on the forced
  teardown, not on a natural failure.
- The rebuild re-creates the primary and the rasters. Other holders of the old surface pointers are unknown beyond
  device+0xb0. The forced teardown run reached the city and drew it, but it covered only the loading screen, about
  1 s in, before the city view and the mods' surface caches exist.
