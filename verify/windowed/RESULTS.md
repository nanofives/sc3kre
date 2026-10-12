# windowed: results (2026-10-12)

Pre-registration: `PRE.md` (same folder). Branch `child/windowed` (from `child/hudfix`): 128e428, c6039e0, 0b32916.

## Verdict
On a stock install, release sc3mods-2026-10-12 comes up **windowed but not resizable**. The frame is the
stock fixed one, so the window can be neither dragged nor maximized, and none of sc3resize's scaling ever
runs. Every owner test so far ran on MAIN\Apps, where GZGraphicD carries the on-disk `resizable_frame`
recipe and the frame is resizable from creation. Fixed in sc3resize (load-time patch of the same three
bytes). The owner's camera feel (SIMSPR on-disk recipes) was also missing on stock, now in sc3overscroll.

## Measured

| run | tree / layout | binaries | style at creation | outcome |
|---|---|---|---|---|
| a1 | Simcity_stock, `Apps\mods_launch.exe` (owner path) | release 10-12 | `0x94CA0000` | windowed 800x600, no WS_THICKFRAME (0x40000), no WS_MAXIMIZEBOX (0x10000). No `FRAME>` line in 45 s |
| r1 | stock (hard-linked copy), sc3resize alone | release 10-12 | `0x94CA0000` | windowed. sc3resize alone writes the windowed byte at 824 ms and still wins on this PC |
| d1-d3 | stock copy, instance folder | 128e428 + release others | `0x94CF0000` | `EARLY` patch before GZGraphicD DllMain, `FRAME:` applied |
| d2 | same, Europolis | same | `0x94CF0000` | maximize -> client 1664x1011, resize step ran; drag (WM_SIZING path) -> 1200x800, resize step ran |
| c1-c7 | stock copy, mods in `Apps\` (owner layout) | 128e428/c6039e0 + release others | `0x94CF0000` (6 of 7) | c4: no window inside 14 s (GZGraphicD mapped at 3.3 s, machine loaded by 6 sibling games), patch applied, no fault |
| v1 | same, Europolis | 0b32916 | `0x94CF0000` | `DISPLAY>` line logged, maximize -> 1680x979, resize step ran |
| m1 | MAIN (on-disk recipes), control | 128e428 + c6039e0 | (on disk) | every block logs "already", nothing written |

Live bytes read from outside the process (stock + fix): GZGraphicD windowed byte 1, `c7 43 10 3b`, `0d 00 00 05`,
`68 00 00 cd 90`. SIMSPR steps 8.0 x5, dead zone 2.0, drag divisor -4/-4. Equal to MAIN's on-disk build.

H1 (windowed race): not reproduced. 12 of 13 stock launches showed a window and all 12 were windowed (c4 showed
no window inside its 14 s), including sc3resize alone (100 ms poll). The new load-time patch removes the race anyway: the loading thread is blocked in the callback, so
the bytes are written before `LoadLibrary` returns to the game.
H2 (fixed frame): CONFIRMED, see a1.
H3 (setter FUN_10010ef2 clobbering the flag): not needed, never observed (flag reads 1 at every later check).
H4: `escalado` may also mean HUDOPT (HUD scale in Preferencias), which the owner tested on 2026-10-11 on the
child/hudopt build. Release 10-12 does not contain it (`HUDOPT>` absent from the release DLL). It ships with
child/hudfix, which this branch is built on.

## Test-setup trap found on the way (not an owner bug)
Running mods from `Simcity_stock\re\harness\inst_*` while `Simcity_stock\Apps` also holds the release mods
crashes the game 0.2 to 3.6 s in, no window, 3 of 3 runs. SC3U loads every `*.dll` it finds and frees those
without `GZDllGetGZCOMDirector` [CONFIRMED @ 0x0040b00f, 0x0048a575 LoadLibraryA + GetProcAddress,
0x0048a675 FreeLibrary]. A copy under another path is a second module: its DllMain starts a watcher thread,
the DLL is freed, and the thread starts in freed memory (fault at `<freed base>+0x4040`, sc3bigcity's watcher
entry). The owner layout (launcher and mods in `Apps\`) is not affected: same path, so only a refcount.

## Not verified
- Visual: the display was asleep for every run (taskbar clock frozen). All checks are style reads, logs and
  memory reads. Screenshots pending.
- DPI above 100%: this PC has one 1680x1050 monitor at 96 dpi, and changing scaling with sibling games running
  crashes them. The game is DPI-unaware (awareness 0 measured), so on a 125-150% laptop panel Windows stretches
  the window bitmap. Behaviour of resize and maximize under that stretch is not measured.
- Older releases (2026-10-06, 10-11): same frame bug expected from the code path, not run.

## DPI awareness (owner call 2026-10-12: sharp, not stretched) - a535102

SC3U.exe has no manifest (no RT_MANIFEST resource, no .manifest file), so it ran DPI-unaware (awareness 0
measured). sc3resize now calls `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` in DllMain. mods_launch
injects sc3resize first while the game's main thread is still suspended, so this happens before any window
exists. Fallbacks: per-monitor v1 context, then `SetProcessDPIAware`. Opt-out: `sc3resize.ini [display]
dpiaware=0` or `SC3RESIZE_DPIAWARE=0`.

Why per-monitor v2 and not system-aware: the game draws its whole client itself, no child controls, so v2 only
adds the caption scaled for the monitor the window is on, and no bitmap stretch on a monitor whose dpi differs
from the system dpi. System-aware would still stretch there, which is what the owner rejected. WM_DPICHANGED is
not handled: on a move to another monitor the client keeps its pixel size, handled like any resize.

| run | setting | window awareness (outside read / DISPLAY>) | maximize | restore | resize_client 1200x800 | min..max track |
|---|---|---|---|---|---|---|
| dA | default | 2 / 2 (per-monitor v2) | 1680x979 [-8 -8 1688 1010] | 800x600 [432 181 1248 820] | 1200x800 [432 181 1648 1020] | 816..1680 x 639..1050 |
| dB | dpiaware=0 | 0 / 0 | 1680x979 [-8 -8 1688 1010] | 800x600 [432 181 1248 820] | 1200x800 [432 181 1648 1020] | 816..1680 x 639..1050 |
| dC | default, cold no city | 2 | - | - | - | - |

Identical at 100%, as expected: at 96 dpi all coordinate spaces coincide. The effect above 100% is NOT
measured (this PC has one monitor at 96 dpi, and changing scaling would crash the other sessions' games).

AppCompat check, HKCU layer on the test tree's exe path only, removed afterwards:

| layer (Properties > Compatibility > Change high DPI settings) | first call | awareness in effect |
|---|---|---|
| `~ DPIUNAWARE` (override: System) | error 5 (access denied) | 0, the layer wins |
| `~ GDIDPISCALING DPIUNAWARE` (System (Enhanced)) | error 5 | 0, the layer wins |
| `~ HIGHDPIAWARE` (Application) | error 5 | 2 (per-monitor v1, set by the layer) |
| none (the system shims SC3U gets by default, AcLayers loaded) | ok | 2, per-monitor v2 |

`DPI>` now says "ALREADY FIXED BEFORE THE MOD" when the first call fails with error 5.

Coordinate paths audited (all in the game's own process, so all in one coordinate space whatever the
awareness): WM_SIZE / GetClientRect (resize step, HUDSCALE fit min(cw/800, ch/600)), WM_GETMINMAXINFO
(virtual-screen metrics; the 800x600 floor now from AdjustWindowRectExForDpi), WM_NCHITTEST margin (now
GetSystemMetricsForDpi), overscroll edge scroll (GetCursorPos + ScreenToClient), game mouse (window messages).
sc3io is itself DPI-aware and posts physical coordinates: with the game aware those equal the game's client
coordinates on any scale. Before, Windows rescaled them for an unaware game.
