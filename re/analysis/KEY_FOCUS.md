# Keyboard focus: how the engine routes keys, and how to tell a text field has focus

2026-10-11, session `keys`. Used by sc3resize KEYFOCUS (P and 1-4 skip while a text field is focused).

## Route of a key

1. GZGraphicD WndProc `0x10017e2f` turns WM_KEYDOWN / WM_KEYUP / WM_CHAR (and WM_SYSKEY*) into a 16-byte GZ event
   (`FUN_100178a6`: type 5 = keydown, 6 = keyup, 4 = char, +4 = wParam) and calls `(*(this+0x30))->vt+0x68(&event)`.
   [CONFIRMED @ GZGraphicD 0x10017e2f, 0x100178a6]
2. `this` is the object at `GZGraphicD+0x6cdb8` (vtable GZGraphicD+0x1f740). Its `+0x30` is the window manager,
   vtable `GZWIND+0x2db80` (measured live). Manager `+0x38` = root window, `+0x3c` = back pointer to the GZGraphicD object.
3. Manager vt+0x68 = GZWIND `0x10020947`: if `+0x2c` (the in-game focus window) is set and its vt+0x104 returns
   true, it calls the focus window's vt+0xc with the event. [CONFIRMED @ GZWIND 0x10020947]
4. In the framework window class, vt+0xc dispatches on the event type: 4 -> vt+0x1a8 (char), 5 -> vt+0x1ac
   (keydown), 6 -> vt+0x1b0 (keyup); if the handler returns 0 the event goes to vt+0x118. [CONFIRMED @ SIMINIT 0x100181a1]

## Which focus window is a text field

The base class's vt+0x1a8 is `return 0` (SIMINIT `0x10018393`, 5 bytes). Text fields override it with a handler that
inserts the character, gated on byte `+0x111`. A PE scan of every vtable in every game DLL for a vt+0x1a8 whose
prologue tests `[reg+0x111]`, plus the GZWIND multi-line text area, gives exactly five classes:

| module | vtable | char handler (vt+0x1a8) | kind |
|---|---|---|---|
| GZWIND.DLL | 0x1002a8cc | 0x100053a9 | single-line edit (framework original) |
| GZWIND.DLL | 0x1002bf10 | 0x1000fb3b | multi-line text area (vt+0x144 = 0x10010a19 paint lines, vt+0x1ac = 0x1000fec5 edit commands) |
| SIMINIT.DLL | 0x10030890 | 0x1001d706 | single-line edit (copy) |
| SIMUI.DLL | 0x100a5f7c | 0x1007cb69 | single-line edit (copy) |
| SIMUI.DLL | 0x100adca0 | 0x1007cb69 | single-line edit (copy, second class) |

Measured live (save dialog, "Guardar ciudad"): the file name, mayor name and city name fields each put a
SIMINIT+0x30890 object at manager `+0x2c` with `+0x111` = 1. The dialog's file list: SIMINIT+0x3050c. The city view:
SIMSPR+0x676ac. No RTTI in these DLLs (vtable[-1] does not point at a locator), so classes are told apart by vtable.

Only the SIMINIT class was seen live. The two SIMUI classes and the two GZWIND classes are static only: the in-game
dialogs that use them were not opened.

## Test (sc3resize KEYFOCUS)

Europolis copy, 2026-10-11, posted keys (sc3io), pause = city+0x140, speed = clock(city+0x130)+0x50:
- Old build, city name focused, keys P 1 2 3 4: text "p1234" arrived AND pause 1 -> 0, speed 43200 -> 10080 ->
  43200 -> 129600 -> 525600.
- Fixed build, same field, keys P 1 2 3 4 numpad-1: text "p12341" arrived, pause stayed 1, speed stayed 43200,
  no PAUSEKEY/SPEEDKEYS lines in the log.
- Fixed build, city view focused (before opening the dialog and after closing it): P toggles, 1 / 3 / 4 / numpad 2 set
  the speed.
