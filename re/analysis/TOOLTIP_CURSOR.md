# TOOLTIP_CURSOR.md: the cost label under the tool icon (task toolicon, 2026-10-12)

Owner report: "el ícono de la herramienta seleccionada está renderizando sobre el valor de lo que estoy construyendo".
Round build `inst_round1012b`, this PC (125% / dpi 120), often maximized 2560x1351. Evidence: `verify/toolicon/`
(PRE.md, RESULTS.md, grabs and composites).

## Verdict

Stock behaviour at a large Windows pointer size, not a mod regression. This PC has the accessibility pointer size
at 4 (`HKCU\Control Panel\Cursors\CursorBaseSize = 80`, `HKCU\Software\Microsoft\Accessibility\CursorSize = 4`).
Windows draws the game's 32x32 tool cursors at 80x80. The game leaves room for a 32 px cursor only.

## The chain

1. The cost value next to the cursor is the game's tooltip window, SC3U class `0x004d3bcc`, a root child
   (`re/tools/uiwin_dump.py` while hovering with the road tool: `[412 346 432 362]` for a cursor at (400,300)).
2. The city view builds the tooltip anchor box from the mouse point (view `+0x204/+0x208`):
   `[mx, my, mx+0x2c, my+0x2c]`, or `[mx-0x2c, my-0x20, mx, my]` when the box leaves the view rect `+0xd8..+0xe4`,
   then posts message `0x22c010d0` with it [CONFIRMED @ SIMSPR 0x1004a3d7, immediates at 0x1004a47b, 0x1004a486,
   0x1004a4d5, 0x1004a4e0].
3. The tooltip manager dispatches it [CONFIRMED @ SC3U 0x00443952 -> 0x00443aba] to `FUN_004430f3`, which copies the
   anchor to label `+0xc4..+0xd0` and, with no placement bits set, mode `0x8000000` [CONFIRMED @ SC3U 0x004430f3].
4. `FUN_00443331` places mode `0x8000000` centred under the anchor, top = anchor bottom + 2, then clamps into the root
   [CONFIRMED @ SC3U 0x00443331]. So the label top is my + 46, centred on mx + 22.
5. Tool cursors are hardware cursors: 32x32 monochrome `.cur` files with the hotspot at (0,0)
   (`Apps\Res\UI\Shared\Cursors\ROAD.CUR`), loaded with `LoadCursorFromFileA` and set with `SetCursor`
   [CONFIRMED @ SC3U 0x0047cf0f, 0x0047d159]. Frida in the game: the HCURSOR bitmap is 32x32, `SM_CXCURSOR` = 32 at dpi
   120. A desktop BitBlt never contains it, which is why no grab ever showed the icon.
6. DXGI desktop duplication (`re/harness/src/ptrshape.c`, `GetFramePointerShape`) with the real mouse over the game
   window and the road tool active: monochrome **80x80**, hotspot (0,0), opaque rows 2..77. Same 80x80 with
   `SC3RESIZE_DPIAWARE=0`. The label at +46 (DPI-aware) or +57.5 physical (unaware, 46 x 1.25) is inside the icon.

DPI awareness is not the cause. It only puts the label 11 physical px closer (46 instead of 57.5). HUDSCALE is not the
cause either: the owner's log has HUDSCALE floating entries only for side-panel tooltips, and the owner was back at
scale 0 (Normal) before building.

## Fix: TIPCURSOR (sc3resize, `SC3RESIZE_TIPCURSOR=0` opt-out)

Two detours replace the anchor block (SIMSPR 0x1004a475..0x1004a494) and the flip (0x1004a4d5..0x1004a4ee):
- box B = drawn pointer / (physical px per game px) + 12, the shipped 44 = 32 + 12 rule with the real pointer size;
- flipped (box leaves the view): `[mx-B, my-36, mx, my-20]`, the label above-left of the cursor;
- B <= 44 (default pointer size) keeps both shipped boxes exactly.
Drawn pointer = max(`CursorBaseSize`, `GetSystemMetricsForDpi(SM_CYCURSOR, monitor dpi)`), re-read once a second.
Physical px per game px = monitor dpi / window dpi (1.0 DPI-aware, 1.25 unaware here). The monitor dpi is read with the
thread switched to per-monitor v2 for the call, since an unaware thread reads 96. `SC3RESIZE_TIPCURSOR_PX=<n>` sets the
pointer size by hand. Only one pointer-size/dpi pair is measured: `U-084`.

Both patch sites are byte-identical in the stock and the dev-PC SIMSPR.DLL (the camera recipes do not touch them).
