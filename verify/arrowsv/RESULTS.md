# arrowsv RESULTS (2026-11-03): Vida util footer arrows centred on the buttons. PASS

Owner: "center vertically the forward and backward button on restaurar menu".
Cause: `ya = yb + (QI_BH - 25) / 2` centred the 24x25 frame's box, but the art sits 2 px high in it. Measured on
uipolish `01_list_p1_800x600` (dark-pixel extent, rows 413..437 for "Restaurar todos" / "Volver", arrows 415..431, centre 423 vs 425).
Fix: `ya += g_rs_arrow_dy` (default 2, `SC3RESIZE_RSARROW_DY=<n>`, 0 = the old placement), sc3resize_restore.c rm_open.

After (same measure): arrows 417..433 on page 1 and on a later page (800x600), Volver / Restaurar todos 413..437:
both centres 425. Large window (3840x1984, dialog scaled): arrows and pills line up in the zoom crop (3_).
Pictures: `owner_shots/1_..3_`. Files to commit: `re/harness/src/sc3resize_restore.c` only.
