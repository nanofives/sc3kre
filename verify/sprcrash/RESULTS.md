# sprcrash: SIMSPR+0xDF01 crash during `rb_lab.py cam` (2026-10-24)

**Verdict: the Frida camera tool causes it, not ordinary play. The tool is fixed. No mod change.**

## 1. The crash

Game PID 14180 (avflow, all mods of main ef8b8c8), logs `verify/sprcrash/crash_14180/` (MAIN). `sc3resize.log` line 2094:
`VEH FAULT 0xC0000005 at 0x00002B7C`, `[esp]` = SIMSPR+0xDF01, then a follow-on fault at SC3U+0x143A.

- SIMSPR 0x1000defe `call [edx+0x40]` with ecx = 0x13F6DCD4 (the occupant), edx = 0x1290C740 (its "vtable", a heap
  address), so the slot read 0x2B7C. That is the second draw loop of UpdateAllDirtyRects 0x1000dc17 (display list
  iso+0x500, entry types 0 / 2). The occupant was freed and its memory reused [CONFIRMED @ 0x1000dee5..0x1000defe].
- Caller: CityViewIso Plot 0x1001cab9, call at 0x1001cbdd. Plot brackets that call with City LockGraphics / UnlockGraphics
  (city vt+0x240 / +0x244) [CONFIRMED @ 0x1001cbdd, 0x1001cbe3]. It was reached from the city view tick 0x10042a95.
- The avflow session had just pressed `1` (unpause), then ran `rb_lab.py cam 157,206 1 0` (transcript 5114b7b5 line 1024).
  The capture click logged `ZOOMCENTER> #1` at 305358 ms. The queued rotate + zoom jobs ran about 1 s later, and the
  fault came at 306955 ms.

## 2. Cause

`nramp_cam.JS` (used by `rb_lab cam`, `hwcars_uicam.py`, `rb_outline.py`) called iso SetZoom 0x10006752 and SetRotate
0x10006a55 through Frida `NativeFunction` with the default `exceptions: 'steal'`.

1. A zoom or rotation change makes a mod write a log line. `OutputDebugStringA` raises 0x40010006 (DBG_PRINTEXCEPTION_C),
   and KERNELBASE normally handles it itself. With 'steal', Frida takes that exception and unwinds out of the game call
   halfway. The job comes back `Error: system error`, and the camera rebuild is left unfinished (sprite caches, display
   lists, the background lock iso+0x46c that SetZoom / SetRotate take when iso+0x3c9 is set).
   - Measured (PID 8236, excprobe.py): 3 of 3 zoom changes with 'steal' returned `system error` (0->2, 2->1, and one
     through the view method). A logging-only `Process.setExceptionHandler` showed 0x40010006 raised from
     sc3resize.dll+0x9a3b (`logf`, `OutputDebugStringA` at sc3resize.c:127). The same zoom job with
     `exceptions: 'propagate'` completed (0->3, `ok`).
   - A call with an unchanged zoom early-outs before any log line. This is why the 2026-10-20 note found only
     zoom-changing calls failing (memory `project-rblab-cam-zoom-deadlock`).
2. The tool also skipped what every game zoom / rotate method does around the camera call: view message 0xa36cf3d1,
   City LockGraphics, the camera call, UnlockGraphics, message 0x835ee78b (view 0x1001d2d6 zoom in, 0x1001d3f3 rotate,
   SetZoomAndRotation 0x1001d1d9) [CONFIRMED @ those addresses]. Arm D shows this alone did not fail in 60 jobs.
   Factor 1 is what breaks the game.

Ordinary play: no mod calls SetZoom / SetRotate directly. The only one is sc3resize `SC3RESIZE_MINZOOM`, a 2026-08-28
crash-hunt flag that is off by default. The game's buttons and keys go through the view methods above.

## 3. Measurements (seoulbv2, all 8 mods of abfd044, speed 4, windowed 800x600, `re/tools/sprcrash/cam_soak.py`)

Each cam job = a rotate call + a zoom call to a random zoom 0..4, rotation 0..3 and tile. The yearly budget dialog was
closed by the soak (frame dump + budget_closer patches). Hang = no answer to WM_NULL for 60 s.

| arm | path | games | steps | crash | hang | aborted calls |
|---|---|---|---|---|---|---|
| A | game: minimap zoom in / out / rotate buttons, numpad + / -, minimap clicks, a Road drag every 10 steps | 2 | 159 (59 + 100) | 0 | 0 | - |
| B | fixed tool: view SetZoomAndRotation 0x1001d1d9, 'propagate' | 1 | 145 jobs (53 + 32 + 60) | 0 | 0 | 0 |
| D | `SC3_CAM_RAW=2`: bare iso calls, 'propagate' | 1 | 60 jobs | 0 | 0 | 0 |
| C | `SC3_CAM_RAW=1`: the old tool (bare calls, 'steal') | 2 | 1 job each | 0 | **2 of 2** | - |

- Arm C hung on the first job that changed the camera on both games (rotate 0->3 on PID 23568, zoom 0->1 on PID 29676).
  The main thread is blocked in both: STRTSIM car move -> SC3U -> SIMSPR+0x19EA9 -> SIMCITY+0xD31D -> wait in ntdll,
  while the sim thread keeps moving the date (`data/armC_hang_stacks_23568.txt`, `armC2_hang_stacks_29676.txt`).
  That is the deadlock memory `project-frida-paused-attach-deadlock` recorded on 2026-10-19 (same chain). That memory
  blamed attaching while paused. These hangs happened on a running sim, so the camera job is the trigger there too.
  The 14180 crash is the other outcome of the same unfinished rebuild. Its paint ran on a display list built from
  half-updated caches.
- Arm B had two early "no result" steps (B step 54, B2 step 33) with no error. The jobs were held behind a slow frame or
  the budget dialog, before the soak polled for results. They are not failures. Arm B3 polled and ran 60 of 60.
- Arm A run 1 ended at step 59 when the harness killed the launcher's shell (30 min limit) and the game with it. No
  fault was logged. Later games were started detached (Start-Process).
- The PC ran other sessions' games and Python jobs at 100% CPU throughout, which gave 3..30 fps.
- Not run: Seoul and Europolis 1024. The cause is in the tool call, not in the city.

## 4. Fix (tools only)

- `re/tools/netmod/nramp_cam.py`: jobs go through the city view's own SetZoomAndRotation 0x1001d1d9 (view captured from
  the same click through 0x1d2d6 / 0x1d365 / 0x1d3f3 / 0x1d47b / 0x1d1d9, checked by view+0x158 == the camera), with the
  target tile written to view +0xb0 / +0xb4. All its NativeFunctions use `exceptions: 'propagate'`.
  `SC3_CAM_RAW=1` = the old path (control arm only), `SC3_CAM_RAW=2` = bare calls with 'propagate'.
- `re/tools/netmod/np_drive.py`: `post()` (menu commands, message posts) uses 'propagate'. The probing calls in
  `cells()` keep 'steal', because they rely on try/catch around objects that may be bad.
- `re/tools/sprcrash/`: `cam_soak.py` (the arms above), `excprobe.py` (steal vs propagate on one zoom job, with an
  exception logger), `stacks.py` (thread stacks of a live or hung game from outside, no debugger).

## 5. Open

26 other files under `re/tools` create NativeFunctions with the default 'steal' (55 sites, `grep -rn "new NativeFunction"
re/tools | grep -v propagate`). Any of them that calls game code which may write a mod log line can abort that call
halfway in the same way. Calls that perform game actions should move to 'propagate'. Calls that probe possibly-bad
objects should keep 'steal'. The 55 sites were not sorted into those two groups here.
