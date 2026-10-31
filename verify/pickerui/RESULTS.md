# pickerui results (2026-10-31)

Owner feedback on the released picker (2026-10-31): no top banner, an eyedropper cursor in the game's cursor style, the
button shaded like the other minimap buttons, the picker done after the first pick, the button's tooltip drawn under
the panel (`owner_tooltip_under.png`).
Spec: `re/analysis/PICKER.md` section 6. Code: sc3resize blocks PICKER and RCIFIX (worktree `dev/pickerui/wt`).
Tree `dev/pickerui/tree`, mods from `dev/pickerui/inst` (sc3wait.py list), Berlin, windowed, posted input only (sc3io), frames
through SC3RESIZE_FRAMEDUMP. Checks: `re/tools/pickerui_check.py` (one line per step). Runs: `runs/<tag>/`
(`before` = main 7ee5ed9 build, `ui1x` = 800x600 then 1600x900, `final` = the build to merge, `offsw` = off switches).
Pictures: `owner_shots/`.

## Verdicts

| # | owner item | result |
|---|---|---|
| 1 | no top banner | **PASS.** The button starts the picker with no message (log has no `message:` line, frame `01_picker_on_no_banner_1x.png`, `01_..._1600x900_hud1.5x.png`). Kept: the 2.5 s message after a click that picks nothing ("no hay nada para copiar aqui" and the like), so a click that does nothing still says why. Say if those should go too |
| 2 | eyedropper cursor | **PASS (game side).** While the picker is on, the game's own SetCursor call with the query cursor is swapped: `cursor now 0x15AC0713 (the eyedropper), picker on`. After a pick and after Esc it is back to the game's cursor (`picker off`, another handle). Same loader as the game's cursors: both load as 64x64 on this PC (`query cursor masks 64x128, eyedropper 64x128`). The stock "?" tool keeps its "?" cursor. Picture `02_cursor_eyedropper.png` is a composite: Windows never puts the hardware cursor in a frame |
| 3 | button shading | **PASS.** The art is the minimap's zoom-out button with its bar replaced by an eyedropper, shrunk like sc3undo's arrows, so ring, bevel, face gradient and the four state frames are the game's. The button is now enabled and shows frame 1 like the zoom and rotate buttons (pixel match: frame 1 at 7.1 mean difference, the others 61..66). Hover shows frame 3. `03_button_before_after_1x.png`, `03_button_after_hud1.5x.png` |
| 4 | done after the first pick | **PASS, unchanged** (owner confirmed 2026-10-31: closing after the first pick is right). Checked with the new cursor in the final build: Molino -> Ind High `0x10003303`, `picker ended (picked)`, current tool SIMRCI+0x4C06C zone 11, then `picker off` and the normal cursor. Same at 1600x900 (Tintoreria -> Ind Med `0x10003302`). A click that picks nothing still leaves the picker on (now visible by the eyedropper cursor) |
| 5 | tooltip on top | **PASS.** Cause: RCIFIX re-blitted the whole RCI gauge at present time, after everything, over the tooltip's left 32 px. Now only the band above the bar (the part the city covers) is re-blitted. The tooltip is whole at 1x and at HUD 1.5x, and the RCI overhang band still shows the gauge (the globe button and gauge top show in both crops, `runs/rci_cmp.png`). `05_tooltip_before_after_1x.png`, `05_tooltip_after_hud1.5x.png` |
| 6 | off switches | **PASS.** `SC3RESIZE_PICKER_CURSOR=0`: `PICKER> cursor off`. `SC3RESIZE_RCIFIX_BAND=0`: `RCIFIX> ... whole` (old behaviour) |
| 7 | faults | none from these blocks. The `VEH FAULT 0xC0000096 at SC3U.exe+0x84122` at ~40 ms is in every run, including `before` |

Final build, 800x600 (`runs/final/check_1x.txt`): 7/7 steps PASS. 1600x900 HUD 1.5x (`runs/ui1x`): 7/7 PASS.

## Needs owner check

- The cursor with the real mouse, at the owner's pointer size (posted moves only here; the swap was read back from
  GetCursor in the game thread).
- The look of the 18x20 button next to the full-size zoom buttons: it went through the same shrink as sc3undo's arrows.
- Owner call: should the messages after a click that picks nothing go as well?
