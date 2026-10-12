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
