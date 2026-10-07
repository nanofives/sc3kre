# FIELDBG results (2026-10-07): PASS

Pre-registration `FIELDBG_PRE.md` (`1cfff0f`). Deviation: the maximized window came out **1680x979**, not
2560x1351 (the primary display had changed). Same size in both arms, and the control arm smears at that size,
so the A/B holds.

| arm | log | date crops (23 per arm) |
|---|---|---|
| A `SC3RESIZE_FIELDBG=0` | `FIELDBG: off` | smeared from the 3rd grab on (prediction met, not void) |
| B default | `FIELDBG: ... reads the ART origin` | **23/23 legible, one date each**, advancing 22, 25, 29, 3, 7, 12, 16, ... through still, arrows and still phases |
| B at default 800-wide window | same | 21/21 legible: no change at native size |

Full bar in B: city, population, money and date all clean. No crash in any run.
Fix: `sc3resize.c` `patch_fieldbg`, SIMUI `0x10026a5c` (`FUN_10026a09` field erase) reads the art origin
`+0x120/+0x124` instead of the bar origin `+0x24/+0x28`. Staged in `re/harness/combo/`.
