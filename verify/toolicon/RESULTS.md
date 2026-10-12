# RESULTS.md, toolicon (2026-10-12)

Pre-registration: `PRE.md` (written before any run, addendum before the fix's first run). Analysis:
`re/analysis/TOOLTIP_CURSOR.md`. Instance `MAIN\re\harness\inst_toolicon` (owner round binaries + my sc3resize),
city = copy of `Cities\Europolis.sc3`, road tool, this PC (dpi 120, pointer size 4 = CursorBaseSize 80).

A desktop grab never contains the hardware cursor. Composites (`re/tools/ptr_composite.py`, copy in this folder) draw the pointer measured with
`re/harness/src/ptrshape.c` (DXGI `GetFramePointerShape`, `ptr_road_80.bmp`, 80x80, hotspot 0,0) at the cursor point.

## Before (owner round build, no fix)

| Arm | Measurement | Result |
|---|---|---|
| M1 stock-equivalent | instance with sc3simrun (+sc3perf) only | not usable: garbled 16-bit main menu, city never loads (no MENUBG fix). Replaced by M3 and the code reading. |
| M2 DPI-aware, 800x600 | label rect vs cursor (uiwin_dump + grab) | label `[412 346 432 362]` for cursor (400,300): top +46, centred on +22. Anchor `+0xc4..+0xd0` = `[x y x+44 y+44]` |
| M2 maximized 2560x1351 | 24-point hover sweep (`label_sweep.py`) | same +12/+46 everywhere, root extent 2560x1351, no clamp involved |
| M2 | Frida on SetCursor | road cursor HCURSOR 32x32 mono, hotspot 0,0, SM_CXCURSOR 32 at dpi 120 |
| M2 | `ptrshape.exe`, real mouse over the game window | drawn **80x80**, hotspot 0,0, opaque rows 2..77 |
| M2 | `m2/BEFORE_aware_800_composite.png` | the "§9" label completely hidden under the road icon |
| M3 `SC3RESIZE_DPIAWARE=0`, maximized | anchor (hook on SC3U 0x4430f3) + ptrshape | anchor in logical px `[214 117 258 161]`; pointer still drawn 80x80 physical. Label 57.5 physical px below, still inside the icon |

Verdict: stock behaviour at a large pointer size (P1 refuted for this PC, P2 refuted: DPI awareness is not the
cause, P3 refuted: the cursor is not drawn into the frame). HUDSCALE floating-window path not involved (owner log).

## After (TIPCURSOR, commit on child/toolicon)

| Prediction | Measured | Evidence |
|---|---|---|
| P5 aware: box 92, anchor `[mx my mx+92 my+92]`, label below the icon | log `pointer 80 px (CursorBaseSize 80), monitor dpi 120, window dpi 120 -> anchor box 92`; anchor `[300 300 392 392]` | `m4_fix/AFTER_aware_800_composite.png`, maximized with the real pointer `m4_fix/AFTER_max_realcursor.png` |
| P6 unaware: box 76 | log `window dpi 96 -> anchor box 76`; anchor `[320 320 396 396]` for physical (400,400); held drag shows "§36" below the icon | `m5_fix_dpi0/AFTER_dpi0_drag.png` |
| P7 `SC3RESIZE_TIPCURSOR=0` | log `disabled`; anchors `[300 300 344 344]`, `[650 300 694 344]` (shipped) | `resize_off.log` |
| P8 `SC3RESIZE_TIPCURSOR_PX=32` | log `anchor box 44 game px (shipped)`; anchors identical to P7 | `resize_px32.log` |
| P9 flip near the view edge | right `[558 264 650 280]`, bottom `[208 464 300 480]`: label above-left, readable | `m4_fix/AFTER_flips.png` |

## Side observation, not attributed

Once, after a maximized session with drags and posted moves (fix on), `restore` left the side panel ~160 px lower and
the bottom bar blank (`m4_fix/restored.png`, persisted 3 s). Not reproduced in 3 later tries (fix off, fix on with
PX=32, restore with the flyout open). The TIPCURSOR stubs only write the tooltip anchor fields `+0x148..+0x154`.
