# FIELDBG pre-registration (2026-10-07): bottom-bar field erase at large windows

Fix in `sc3resize.c` `patch_fieldbg`: SIMUI `0x10026a5c` reads the bar ART origin (`+0x120/+0x124`) instead of
the bar origin (`+0x24/+0x28`) when computing the background patch that erases a field (`FUN_10026a09`).

Fixture: all four mods, Europolis, sim at speed 3, window maximized on the 2560x1440 primary (client 2560x1351),
`run_while_scrolling=1`. Driver `datebig.py` (10 still grabs, 20 s arrows, 6 still grabs), date field cropped.

| arm | env | prediction |
|---|---|---|
| A control | `SC3RESIZE_FIELDBG=0` | log `FIELDBG: off`. Date smears (overprinted digits) by the 3rd still grab, as in the 2026-10-07 runs. |
| B fix | default | log `FIELDBG: ... reads the ART origin`. Every date crop legible, one date per crop, through all phases. |

Plus a default-size (1000x750) B run: date legible (the fix must be stock-equivalent at native size).
Fail: any smeared crop in B, or a crash. Void: A not smearing.
