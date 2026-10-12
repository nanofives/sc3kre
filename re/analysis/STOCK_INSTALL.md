# Stock install vs the dev PC (2026-10-12, child windowed)

The owner's hand tests all ran on MAIN\Apps, which is NOT stock. A player's install is. What differs, and
where the mods now cover it. Evidence: `verify/windowed/RESULTS.md`.

| on-disk recipe on the dev PC | module | what it gives | stock + mods (branch child/windowed) |
|---|---|---|---|
| `resizable_frame` | GZGraphicD | WS_THICKFRAME + WS_MAXIMIZEBOX from window creation | sc3resize WINDOWED-EARLY + FRAME, same 3 bytes at load (`SC3RESIZE_EARLY=0`, `SC3RESIZE_THICKFRAME=0`) |
| `close_button_quit` | GZGraphicD | X quits | sibling task `closex` |
| `scroll_speed=8`, `drag_divisor=4`, `drag_deadzone=2` | SIMSPR | owner's camera feel (ruling 2026-08-26) | sc3overscroll CAMFEEL, same bytes when SIMSPR maps (`overscroll.ini [camera]`, `SC3OVERSCROLL_CAMFEEL=0`) |
| `resize_rectfix` | SIMSPR | present rect after the iso Init | not needed: inert without Init, sc3resize step 9 pushes the rect itself |

Before 128e428 a stock install with any release so far showed a fixed 800x600 window (style `0x94CA0000`): no
drag border, no maximize button, so the resize/scaling code never ran. MAIN shows `0x94CF0000`.

## The game loads every DLL in Apps

SC3U scans for `*.dll`, `LoadLibraryA`s each, asks for `GZDllGetGZCOMDirector` and `FreeLibrary`s the ones
without it [CONFIRMED @ 0x0040b00f, 0x0048a575, 0x0048a675]. So every mod DLL sitting in `Apps\` gets its
DllMain called by the game itself.
- Owner layout (launcher + mods in `Apps\`, injected from there): same path, the scan only bumps and drops a
  refcount. Harmless.
- A second copy of a mod under another path (an instance folder while `Apps\` also has the mods) is a second
  module. Its DllMain starts the watcher thread, the scan frees the DLL, the thread starts in freed memory and
  the game dies before its window shows (measured 3 of 3, fault at `<freed base>+0x4040`, the sc3bigcity
  watcher entry). Test trees must have mods in exactly one place.
- Consequence for mod design: a mod DLL must survive being loaded and freed by the scan. Today's watchers do
  not (the thread outlives the module). Only matters if a player keeps two copies.

## Windowed timing

GZGraphicD Init (`FUN_100114b8`) reads the windowed byte `DAT_1006cdac` [CONFIRMED @ 0x100114b8]. The only
writer in the module is the setter `FUN_10010ef2` (vtable slots at 0x1001edc4 and 0x1001efa0). sc3bigcity and
sc3overscroll poll every 1 ms, sc3resize every 100 ms after SIMSPR also maps. All won on this PC (12 of 12
windows seen were windowed, sc3resize alone patched at 824 ms). sc3resize now patches from a loader
notification (`LdrRegisterDllNotification`), before GZGraphicD's DllMain and before `LoadLibrary` returns to
the game, so load order no longer decides it.

## DPI
SC3U has no manifest and ran DPI-unaware: on a >100% screen Windows stretched the window bitmap. Owner call
2026-10-12: sharp instead. sc3resize sets per-monitor v2 awareness in DllMain, before the game's window exists
(a535102, opt-out `[display] dpiaware=0`). An exe-level "override high DPI scaling: System / System (Enhanced)"
compat layer wins over it (measured, logged in `DPI>`). Details and A/B: `verify/windowed/RESULTS.md`.
