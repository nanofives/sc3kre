# PRE: hudclick (task hudclick, 2026-10-15)

Written and committed before the first game run of this task. Branch `child/hudclick` from `round/1012` (145f492).

## Question

menuscale's first build mapped mouse messages only at nesting depth 0 and missed clicks inside "Preferencias" at the
main menu, because that dialog runs a modal loop inside the button handler and every later click reaches the wndproc
at depth 1 (`verify/menuscale/RESULTS.md`, defect 2). HUDSCALE uses the same depth-0 rule. Does anything miss with
the enlarged city HUD while a dialog opened from the HUD is up?

## What the code does (read before any run)

sc3resize `rz_wndproc` HUDSCALE branch (`re/harness/src/sc3resize.c`, the block after MENUBG) and `rz_hs_mouse`:

1. Every mouse message `WM_MOUSEMOVE..WM_MBUTTONDBLCLK` with `g_hudscale` on and no menu frame active goes through it.
   `g_hs_depth` counts nesting of this branch only (incremented around `CallWindowProcA`).
2. A message is a mapping candidate only if `g_hs_depth == 0` and `g_hs_n > 0` (enlarged rects exist this frame).
   At depth > 0 nothing is ever mapped.
3. REPOST guard: a `WM_MOUSEMOVE` whose lParam equals the last mapped output within 500 ms is passed through unmapped.
4. `rz_hs_mouse` maps a point (inverse of `dest = C + s * (src - C)`, C = bottom-right client corner) when it lies in an
   enlarged dest rect and NOT inside a kept-native dialog rect (class `SIMUI+0xa4d64`, >= 120x80, collected per
   frame), or while `g_hs_capture` is set. A mapped press sets `g_hs_capture = 1`; only a release that reaches
   `rz_hs_mouse` (depth 0, and inside or captured) clears it. The only other place that clears it is the HUDOPT
   Preferences OK path (`ho_prefs_close`, id `0x02F95AD8`).
5. Dialogs are not enlarged: they are drawn at their native client position on top of the enlarged HUD. So a click on
   a dialog needs no conversion at any depth, unlike MENUSCALE, where the whole menu frame including its dialogs is
   scaled.

Game side (decomp, `[CONFIRMED]`):

- GZWIND `FUN_10020971` = the window manager's modal loop, vtable `0x1002db80` slot `+0xa0`: stores the dialog at
  `this+0x30`, then `PeekMessageA` / `TranslateMessage` / `DispatchMessageA` until a message registered by
  `FUN_10020b59(0xd)` arrives with `wParam` = that dialog; returns its `lParam` `[CONFIRMED @ GZWIND 0x10020971]`.
  The close is slot `+0x44` = `FUN_10020f08`, `PostMessageA(hwnd, FUN_10020b59(id), wp, lp)`
  `[CONFIRMED @ GZWIND 0x10020f08]`, called as `vt+0x44(0xd, win, result)` by every modal close site.
- While `this+0x30` is set, the mouse dispatcher `FUN_10020818` (slot `+0x64`) hands an event to that window only if
  its hit test (`vt+0xe4(x, y)`) and `vt+0x104` / `vt+0x100` pass; otherwise it only updates the hover target and drops
  the event `[CONFIRMED @ GZWIND 0x10020818]`. So in the stock game a click outside a modal dialog does nothing.
- Modal close sites (`vt+0x44(0xd, ...)`), one per function: EXE 12 (`0x0042854d 0x00428576 0x004293cd 0x004293fd
  0x0042a31a 0x0042af77 0x00433636 0x00436a63 0x0043b6c3 0x0043d8d0 0x00445022 0x0044d61e`), SIMUI 29 (`0x10005281
  0x10006838 0x10008af9 0x10008c67 0x1000fb5c 0x1001e552 0x1002ad33 0x1002ddfb 0x100307ca 0x10031909 0x10035b6d
  0x10037b1a 0x1003879a 0x100396cc 0x1003a29c 0x1003c5cc 0x1003ceca 0x1003df3d 0x1003e173 0x1003f104 0x1003f899
  0x100414f2 0x100562b1 0x1005dfcb 0x10063d0a 0x10066154 0x100685d5 0x10069f5a 0x1007b156`), GZWIND 3 (`0x10014f41
  0x10017817 0x1002250c`), SIMMISC 2 (`0x1001e836 0x10025dee`), SCENARIO 3 (`0x100017bf 0x10003398 0x10004412`).
  `0x100562b1` is the Preferences close (`OPTIONS_DIALOG.md`). Which of the others belong to which HUD dialog is
  measured at runtime below (depth of the messages while the dialog is up), not assigned from the decomp.

## Hypotheses

- H1 (the reported suspicion): clicks on a modal dialog opened from the HUD miss. **Predicted NOT to happen**: the
  dialog is native, its clicks arrive at depth >= 1 and are left unmapped, which is correct for a native dialog.
- H2: clicks on the enlarged HUD while a modal dialog is up are left unmapped. **Predicted to happen, with no visible
  effect**, because the stock dispatcher drops clicks outside a modal window whatever their coordinates. Same result
  expected with the HUD scale off.
- H3 (found while reading, not reported): stale capture. If the HUD control that opens a modal dialog acts on the
  PRESS, the press is mapped at depth 0 (capture set) and its release arrives inside the modal loop at depth 1, where
  nothing clears the capture. After the dialog closes by anything except Preferences OK, the next mouse messages at
  depth 0 are mapped as if on the HUD, wherever they are, until a release is mapped: the first press on the city after
  the dialog lands at `C + (P - C) / s` instead of P. If the opener acts on the RELEASE, the release is mapped at depth
  0 and clears the capture before the dialog opens, and H3 does not happen.

## Setup

- Stock tree `C:\Users\maria\Desktop\Proyectos\Simcity_hudclick` (Apps/Buildings/Scripts hard-linked from the live
  install, `*.cfg/*.ini/*.txt` copied, `Cities\` copied whole so a save can never write the live install,
  every `original\modules\*.dll` SHA-256-identical to the tree's, SC3U.exe = the anchor). Mod binaries built from the
  worktree into `MAIN\re\harness\inst_hudclick`, copied into the tree's `Apps\` (ship layout of `mods_launch`).
- `mods_launch.exe -multi -- <Cities\Europolis.sc3>` from the tree's Apps, `SC3RESIZE_LOG` per run,
  `SC3RESIZE_HUDSCALE_MLOG=1` (logs every mouse message the HUDSCALE branch sees with its depth). Window maximized.
  Input: `sc3io` (PostMessage only), grabs: `sc3io` desktop grab, native rects: `uiwin_dump.py`.
- Arms: **N** `SC3RESIZE_HUDSCALE=0` (control), **F** `SC3RESIZE_HUDSCALE=1` (Fit), **D** `SC3RESIZE_HUDSCALE=200`.

## Procedure, per arm, per dialog

Dialogs from the HUD: Preferencias (Options flyout), Budget and Ordinances (Review flyout), Neighbors (Review),
Reunirse (Meet Advisor button), Query (query tool on a building), Save As and Load (Options flyout), Exit (Options,
quit question, cancelled). A dialog that does not open, or needs a state the city does not have, is reported as such.

1. Open it with a click on its (enlarged in F/D) HUD control. Grab.
2. One click on one of its own controls with a visible effect (tab, radio, checkbox, list item). Grab.
3. Where it is modal: one click on an enlarged HUD button outside the dialog (the landscaping button). Grab.
4. Close with its own close box or Cancel. Grab.
5. With no HUD click in between: a move and a left press/release at a fixed city point P (query tool selected
   beforehand, so the press opens a query of the tile at P). Grab. Compare the queried tile with arm N at the same P.

Recorded per click: hit / miss (what opened or changed, seen in the grab), depth of its messages (HSMLOG), whether it
was mapped (`HUDSCALE> down/up ... -> native` lines).

## Predictions

- P1: step 2 hits in N, F and D for every dialog that opens.
- P2: step 3 changes nothing in N, F and D for every modal dialog (the step-3 button does not open its flyout).
- P3: HSMLOG shows depth >= 1 for the step-2/3/4 messages of the dialogs that run the modal loop, depth 0 for the
  others.
- P4: in F and D, if the opener's release is logged at depth >= 1, step 5 after a close by close box/Cancel is mapped
  (`down (P) -> native (P')`) and queries the tile at P' (a miss); if the opener's release is logged at depth 0, step 5
  is not mapped and queries the tile at P, as in N.
- P5: arm N logs no `HSMLOG>` and no `HUDSCALE>` lines.

## If P4 shows a miss

Fix with a switch (`SC3RESIZE_HUDSCALE_CAPFIX=0` = current behaviour), keep `SC3RESIZE_HUDSCALE=0` stock, re-run the
same arms, then the HUDSCALE checks from hudscale / hudfix / hudopt (enlarged transport button opens its flyout, first
flyout item selects roads, minimap "+" zooms, Reunirse opens and its close box closes it, the enlarged Preferencias
flyout item opens Preferences) in F and D. If nothing misses, nothing in the code changes.
