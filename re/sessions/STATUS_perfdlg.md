# STATUS perfdlg (2026-11-02)
## goal
Owner: opening the Sustituir dialog draws the sc3perf FPS bar much larger. Expected: normal size whatever dialog is open.
## verdict + deciding code
sc3resize.c `sc3resize_ui_scale` (sc3perf's only scale source). Since uiaudit 2d487c7 (DLGONLY) it returns the HUD factor
`g_hs_s` whenever `g_hd_n > 0` (an enlarged dialog is up), even when the HUD itself is not enlarged (`g_hs_n == 0`, where it
returns 100). So with no dialog the bar is 100%, with Sustituir open it jumps to the dialog pass factor.
## built
`SC3RESIZE_PERFDLG` (default 1): ui_scale ignores a dialog-only pass. `=0` restores the DLGONLY behaviour. sc3resize rebuilt in dev\perfdlg\inst.
Side effect: the terrain-editor-panel case DLGONLY wanted (FPS text scaled with a lone dialog) no longer scales.
## proven
Static only (code path + history). Launch OK at the menu. No in-game before/after: opening Sustituir needs a loaded city and real clicks.
## needs owner check
Load a city, open Sustituir, compare the FPS bar with and without it. Pictures: none in verify/perfdlg/owner_shots (only 00_start.png).
## files owned
re/harness/src/sc3resize.c
