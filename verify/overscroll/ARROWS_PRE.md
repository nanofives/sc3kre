# Arrows survive a mouse move: pre-registration (2026-10-07)

Fix: `sc3overscroll.c` `patch_arrows` wraps city-view vtable slot `SIMSPR 0x100678d4` (`vt+0x40` =
`FUN_10043a38`, the edge handler). After the stock handler it re-latches any held arrow (`+0x1e1..+0x1e4`)
from the view's key-state object `+0x210` `vt+0xc(vk)`. `overscroll.ini [camera] arrows_keep=1` (0 = stock).

Control arm, already measured: owner bisect 2026-10-07, arrows stop on a real mouse move with resize, overscroll
and bigcity each loaded alone (`verify/simrun/RESULTS.md`).

Treatment (owner hand, all four mods via `re/harness/combo/mods_launch.exe`, Europolis):
- Log `### READY: ... arrows_keep=1`.
- Hold an arrow, move the mouse around the view: the camera keeps scrolling. Release the arrow: it stops.
- Edge scroll while placing (overscroll feature) and right-drag still work as before.
Fail: arrows still stop, the camera keeps scrolling after the arrow is released, or right-drag/placing breaks.
