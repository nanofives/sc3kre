# STATUS newcitydlg (child of "SC3: owner bugs 10-23"), 2026-10-26

Worktree `Simcity_wt_newcitydlg` (child/newcitydlg from main 7d3493b), test tree `Simcity_stock_newcitydlg`. State:
**fixed, checked in game** (2560x1351 and maximized 3840x1984, Europolis, in city and at the main menu). Second round
(orchestrator, same day): the table of all 16 dialog subclasses, native dialogs in front of enlarged ones, New City controls.

## Cause
1. The in-city New City options dialog is class `SIMUI+0xaa8e8`, a subclass of the dialog base (ctor `FUN_1005b6f4` runs
   `FUN_1002c688`, then writes its own vt). Every dialog test matched `0xa4d64` only, so it stayed native at [32 76].
2. Crop: DLGSCALE resamples each dialog from its native rect in the frame. Ver datos' rect held the overlapping native
   New City pixels, so they came out enlarged inside Ver datos' box, drawn on top of everything. The same happens to a
   dialog kept native (dragged partly off the client) in front of an enlarged one: it was hidden.

## Fix
Two blocks in `sc3resize.c`:
- DLGCLASS (`SC3RESIZE_DLGCLASS=0` off): `rz_is_dlg_vt()` adds New City's vt to the dialog tests in DLGSCALE, the
  placement poll (New City is now centred like other dialogs) and the two HUD-translation exclusions.
  - The other 15 subclasses are the Internet Chat client. Its only entry is the "Internet chat" cheat, which calls the
    chat manager vt `SC3U 0x4d0a70` slot +0x54 = `FUN_0041c988`, a `return 0` stub. Measured in game: the box takes the
    text and closes, and no window opens.
  - So they are left out on purpose. Table in RESULTS.
- DLGOCC (`SC3RESIZE_DLGOCC=0` off): where a dialog in front, enlarged or kept native, overlaps one behind it:
  - the enlarged one behind keeps its own last-frame pixels there;
  - a native front dialog is saved and put back right after the last enlarged dialog behind it;
  - its mouse stays native.

Checked:
- New City alone, over Ver datos (overlapping and not), dragged over it, maximized, from the main menu.
- Every New City control (name field, radios, Enorme slider to 896, the three pickers, Desastres, X, ✓ into the terrain
  editor).
- Five other dialogs over Ver datos.
- A native Ordenanzas in front of the enlarged Ver datos: drawn whole, and its ✓ works.
- An arm with DLGOCC=0 shows the ghost strip it removes.

Detail and pictures: `verify/newcitydlg/RESULTS.md`.

## Files to commit (worktree `Simcity_wt_newcitydlg`, by path)
- `re/harness/src/sc3resize.c`:
  - the DLGCLASS block (`g_dlgclass`, `g_dlg_sub[]`, `rz_is_dlg_vt`) before the DIALOGS block;
  - its 4 call sites: `rz_dialogs_poll`, the side-panel dy exclusion, the WINCAP `is_dlg` test, `rz_hs_collect`;
  - the DLGOCC comment and globals after `g_dlgscale`;
  - the z rank in `rz_hs_collect`'s KEPT NATIVE branch;
  - in `rz_hs_pre`: the two freeze loops and the native save in the DLGSCALE snapshot, and the native put-back in the
    enlarged draw loop;
  - `g_hd_nf = 0` with the `g_hd_n` reset;
  - the native test in `rz_hd_mouse`;
  - 2 env vars, 1 FLAGS line.
- `re/analysis/HUD_SCALE.md` (new last section)
- `verify/newcitydlg/RESULTS.md` (also in MAIN)
- owner shots stay local in `MAIN\verify\newcitydlg\owner_shots\` (game art). Raw frames `fd/` and `logs/` are local too.
