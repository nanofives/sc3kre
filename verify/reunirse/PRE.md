# PRE: Reunirse window keeps its position when an item is opened (child `reunirse`, 2026-10-12)

Owner report: "quiero que cuando mueva una ventana en el menú 'reunirse' que al abrir un ítem la ventana se mantenga
en la misma posición".

## What is already measured (before this file, baseline build = child/hudfix 91dbc9c, 800x600, Europolis copy)

Watcher `re/tools/dlg_watch.py` (Frida, logs every SetRect vt+0xc8 on a SIMUI+0xa4d64 dialog with its caller):

1. Reunirse opens: the game sizes the dialog 383x354 and moves it to (600,284) from `SIMUI+0x6dd09`
   (`FUN_1006dcdd` MoveTo, called by the list-page builder `FUN_10004405`). sc3resize then moves it to the
   map-area centre [160 95 543 449] (not inside 800x600, so not kept as stock).
2. Title-bar drag with posted left-button moves: the game moves it to [40 175 423 529] (`SIMUI+0x6dd41`).
3. Click on the first advisor: the SAME window object is rebuilt as the detail page, 384x354, and the game moves it
   to (600,284) again (`SIMUI+0x6dd09` from `FUN_10005602`). sc3resize sees the width change 383 -> 384, resets
   its entry as a new window and centres it [160 95 544 449]. The drag is lost.

Decompilation [CONFIRMED]:
- `FUN_10004405` (list page builder) moves the dialog to (8,8) when byte 0 of the struct returned by
  `FUN_1008e998()->vt+0x5c` is 0, else to (struct+4, struct+8).
- `FUN_10005602` (detail page builder) uses (8,8) or (struct+0xc, struct+0x10).
- `FUN_10004cda` (list page close) stores the dialog's local left/top (`vt+0x98` = `FUN_1006db74` = +0x80,
  `vt+0x9c` = `FUN_1006db7b` = +0x84) into struct+4/+8 and sets byte 0 = 1.
- `FUN_10005fb4` (detail page close) stores them into struct+0xc/+0x10, struct+0x14 = this+0x10, byte 0 = 1.
- Live read after step 3: flag 1, list slot (40,175), detail slot (600,284).

So the stock game remembers ONE position PER PAGE. Opening an item moves the window to the detail page's own old
spot even without the mod. The mod adds a second jump (to the centre) at every size other than 800x600, and at
800x600 when the stored spot is not fully inside the client.

## Change under test (flag `SC3RESIZE_DLGSTAY`, default 1, `=0` restores the current behaviour)

1. Detours on `FUN_10004cda` and `FUN_10005fb4` (SIMUI, prologues `53 55 56 57 8b d9` / `53 55 56 57 8b f1`,
   checked before patching): after the original runs, copy the slot it wrote into the other page's slot.
   The game then opens the next page (and the next Reunirse) where the last page was.
2. `rz_dialogs_poll`: a dialog that becomes visible (new open, reopen, or the same object rebuilt at another size)
   exactly at the top-left where the poll last saw it, at the same client size, is kept there (clamped inside
   the client) instead of being centred or reset. After a client size change the existing rules apply.

## Arms and predictions (all windowed, Europolis copy, own -multi PID)

| Arm | Build / flags | Size | Prediction after: open, drag title to P, click an advisor |
|---|---|---|---|
| S (stock reference) | fix build, `SC3RESIZE_DIALOGS=0 SC3RESIZE_DLGSTAY=0` | 800x600 | detail page top-left = detail slot read before the click, not P (stock jumps) |
| A (control) | fix build, `SC3RESIZE_DLGSTAY=0` | 800x600 and maximized | detail page centred in the map area, or at the detail slot at 800x600 when it is fully inside. Not P |
| B (fix) | fix build, defaults | 800x600 and maximized | detail page top-left = P. Back to the list / close + reopen at the same size: still P |

Also for B: maximize then restore with the dialog open = existing rules (a dragged dialog is clamped, not centred).
Close at one size, reopen at another: re-centred (existing rule). Arm S must reproduce a jump, else the stock claim
is wrong and is reported as such.

Pass = B keeps P (exact top-left, from the watcher log and the tree dump) at both sizes, a screenshot I look at
shows the detail page where the list was, A and S jump, no `VEH FAULT` in any log.
Display caveat: the monitor was asleep at 13:36 (taskbar clock stale). If it still is, the screenshots are pending
and the verdict rests on the watcher log and tree dumps, and RESULTS says so.
