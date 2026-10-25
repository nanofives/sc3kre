# STATUS uiaudit (child of "SC3: owner bugs 10-23", 2026-10-25)

Milestone 1 (audit): DONE. Milestone 2 (fixes #1 #2 #4 #6, owner pick): DONE, checked in game at 2560x1351 and 3840x1984.

- Worktree `Simcity_wt_uiaudit` (child/uiaudit, main 54bf548). Blocks in sc3resize.c: TIPDLG, MINIVIS, DLGONLY, MSOPEN
  (off: SC3RESIZE_TIPDLG=0, SC3RESIZE_MINIVIS=0, SC3RESIZE_DLGONLY=0, SC3RESIZE_MENUSCALE_OPEN=0). FLAGS line `### FLAGS> uiaudit:`.
- No edits near CITYZOOM / ZOOMCENTER (zoomcrash owns those).
- Evidence: `MAIN\verify\uiaudit\RESULTS.md` (audit + fixes), `owner_shots\fix*_before_after.png`, A/B frames in `fix_A\`, `fix_B\`.
- No game running.

## Files to commit (from the worktree)
- re/harness/src/sc3resize.c
- re/analysis/HUD_SCALE.md
