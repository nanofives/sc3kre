# PRE — the 2026-10-05 maximize crash (null dest sub-surface in GZGraphicD FUN_10014894)

Written 2026-10-05, committed before the run.

## The crash

Owner maximized by hand (client 1680x979). The mod's VEH logged, right after the resize routine
finished: AV READ `0x00000000` at `GZGraphicD+0x14904`, ebx=`0x0054BC40`, ecx=0
(`verify/resize_panelshots/run_edgeon.log:467`). Disassembly: `0x100148fa mov ecx,[ebx+0x44]` then
`0x10014904 mov eax,[ecx]`. So the blit's DESTINATION raster had no DirectDraw sub-surface at `+0x44`.
The caller is not known, because the logger recorded only `[esp]`.

## Changes in this build (194,048 B)

1. `rz_repaint_rci` (RCIFIX, the present-time RCI blit) returns early if the target's or the source's
   `+0x44` is NULL. That is the exact dereference that faulted.
2. The VEH now logs `in_rci_repaint` (1 = the fault happened inside the mod's RCI blit) and up to 14
   stack words that land in a loaded module.

## Run

Same install, `SC3RESIZE_CLUSTER=1`, defaults otherwise. 30 maximize/restore cycles through sc3io,
alternating restore sizes 800x600, 1280x800 and 1600x900, 8 s settle each. The VEH log is the
instrument.

| outcome | reading |
|---|---|
| no VEH AV in 30 cycles | consistent with the guard, NOT proof. The original crash was a single event on a hand maximize, and earlier sc3io maximizes did not crash. |
| an AV with `in_rci_repaint=1` | impossible if the guard works. The guard is wrong. |
| an AV with `in_rci_repaint=0` | the game's own paint (or another mod path) hits the null target. The stack words name the caller. RCIFIX is cleared. |

The decisive check stays the owner's hand maximize on this build.
