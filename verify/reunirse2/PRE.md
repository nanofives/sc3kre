# PRE: every Reunirse page follows the dragged position (child `reunirse2`, 2026-10-12)

Owner: "antes te había pedido que mantengas la posición de la ventana en reunirse, está bien que esté todo en el
medio, pero si muevo la ventana cuando voy a otro cartel la ventana no sigue".
Base: `round/1012` (c30dc0d), which has DLGSTAY (child `reunirse`): list and advisor pages share one stored spot.

## Static inventory (SIMUI, before any run)

The meeting manager's message dispatcher is `FUN_100032ea` [CONFIRMED @ 0x100032ea]. Every page-opening message
first calls `FUN_100037f0`, which closes whatever page is open (controllers at manager +0xc, +0x10, +0x14, +0x18),
then opens one page. Five page kinds, each a separate controller and window id:

| Page | Opened by msg | Window id | Builder | Closer | Stored spot |
|---|---|---|---|---|---|
| list | 0x724a82d0 | 0x62be5dd2 | `FUN_10004405` | `FUN_10004cda` | slot +4/+8 |
| advisor | 0x724a82d1 (list click, `FUN_1000506d`) | 0x62be5df0 | `FUN_10005602` | `FUN_10005fb4` | slot +0xc/+0x10 |
| page D6 | 0x724a82d6 (list button 0x62be5dd6, `FUN_100042f7`) | 0x62be5f00 | `FUN_1000690a` (384x354) | `FUN_10007b8c` | slot +0x20/+0x24 |
| page D7 | 0x724a82d7 (button 0x62be5009, `FUN_1000a202`) | 0x62be6000 | `FUN_1000a5ec` (384x354) | `FUN_1000ae3e` | slot +0x28/+0x2c |
| topic | 0x724a82d2/d4/d5 (advisor page, `FUN_100052fc` by mode +0x10 = 1/2/3) | 0x62be5000 | `FUN_1000823d` (337x254) | `FUN_10008ae0` | NONE: centred on its parent, or on the rect at controller +0x14 when set |

`slot` = `FUN_1008e998()->vt+0x5c()` as in `re/analysis/REUNIRSE_POSITION.md`. DLGSTAY only shares list <-> advisor.

## Hypotheses (predictions for the CONTROL = round/1012 build, defaults)

- H1: drag the list, open page D6 (if the list shows such a button): D6 opens at its own slot (+0x20/+0x24) or is
  centred by the poll, NOT at the dragged spot.
- H2: drag the advisor page, click a topic: the topic page opens centred (parent or map area), NOT over the dragged spot.
- H3: drag the topic page, go back to the advisor (or to the list): that page opens at the spot stored when the
  advisor page closed, NOT where the topic page was dragged.
- H4: page D7 (from a topic page button) opens at its own slot or centred.
Which of these the owner's "otro cartel" means is not known; the fix covers all of them.

## Fix (new block, `SC3RESIZE_MEETALL=0` turns off the new parts, `SC3RESIZE_DLGSTAY=0` everything)

- F1: after ANY of the four slot closers runs, copy the spot it wrote into all four slots (one shared spot).
  Builders of D6/D7 note the page window like the list/advisor builders do.
- F2: the topic page (no slot) is moved so its centre sits on the centre of the last closed page's rect, at the same
  client size only. When it closes, the spot it was at (centre-aligned back to the 384x354 page size) becomes the
  shared spot.
- The client-size rule is unchanged: a spot noted at another client size is not used (page centred).

## Pass criteria (fix build, defaults), at 800x600 AND maximized

For each transition reached in-game (list -> advisor, advisor -> topic, topic -> advisor/back, list -> D6, D6 -> back,
topic -> D7, close + reopen), after dragging the open page to P:
- a 384x354-class page opens with top-left = P, or the clamped P when P would put it partly off the client;
- the topic page opens with its centre on the centre of the page it replaced (clamped likewise);
- from the topic page dragged to Q, the next big page opens centred on Q's centre (clamped).
Read from the live window tree (`+0x14` rect), AND one screenshot per transition looked at by eye.
Control: same steps with `SC3RESIZE_MEETALL=0` must reproduce at least one jump among H1-H4, else the report is not
explained by these and the verdict is "not reproduced".
No new `VEH FAULT` beyond the known `0xC0000096 @ SC3U.exe+0x84122` at startup.
Resize: closed at one client size, reopened at another -> centred (unchanged).
