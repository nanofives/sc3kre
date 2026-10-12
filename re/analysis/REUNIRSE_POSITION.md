# Reunirse window position (child `reunirse`, 2026-10-12)

Owner: "quiero que cuando mueva una ventana en el menú 'reunirse' que al abrir un ítem la ventana se mantenga en la
misma posición". Fix: sc3resize `DLGSTAY` (`SC3RESIZE_DLGSTAY=0` opts out). Evidence: `verify/reunirse/`.

## How the stock game places the two Reunirse pages

The meeting controller (SIMUI) builds the dialog as one of two pages, each a `SIMUI+0xa4d64` dialog:

| Function | Role | Position |
|---|---|---|
| `FUN_10004405` | list page builder: size `n*0x34+0x13` x `0x162` (7 advisors = 383x354) | `(8,8)` if byte 0 of the slot struct is 0, else `(s+4, s+8)` [CONFIRMED @ 0x10004405] |
| `FUN_10005602` | detail page builder: size `0x180` x `0x162` (384x354), advisor portrait + topics | `(8,8)` or `(s+0xc, s+0x10)` [CONFIRMED @ 0x10005602] |
| `FUN_10004cda` | list page close: `s+4 = vt+0x98()`, `s+8 = vt+0x9c()`, byte 0 = 1 | [CONFIRMED @ 0x10004cda] |
| `FUN_10005fb4` | detail page close: `s+0xc`, `s+0x10`, `s+0x14 = this+0x10`, byte 0 = 1 | [CONFIRMED @ 0x10005fb4] |

`s` = `FUN_1008e998()->vt+0x5c()`. `vt+0x98` = `FUN_1006db74` (returns `+0x80`), `vt+0x9c` = `FUN_1006db7b`
(returns `+0x84`): the dialog's local left/top. MoveTo is `vt+0xcc` = `FUN_1006dcdd`. Callers: `FUN_100042f7`
(list build/close), `FUN_100052fc` (detail build/close).

So stock remembers one spot per page. Opening an advisor closes the list page (its spot is saved) and builds the
detail page at the detail page's own last spot. Measured with every sc3resize dialog rule off: dragged to
[480 364], advisor page at [600 284] = the detail slot. The pages are usually NEW window objects (the list is freed,
the detail page allocated, sometimes at the same address).

The slots survive a restart in some way not traced here: the MAIN install opened at [600 284] in a fresh process,
the stock copy at [8 8]. [UNCERTAIN] where they are stored (prefs or city file). Killing the game with `taskkill /F`
did not update them.

## What sc3resize added on top (before DLGSTAY)

`rz_dialogs_poll` treats a tracked address that comes back with another size as a new window (the 1 px 383 -> 384
change counts), and a new window at any size but 800x600 (or at 800x600 when not fully inside) is centred in the map
area. So the mod turned "jump to the detail page's old spot" into "jump to the centre" at every size.

## DLGSTAY

1. Detours after `FUN_10004cda` / `FUN_10005fb4` copy the slot just written into the other page's slot: both pages
   (and the next Reunirse) open where the last page closed. They also note that spot and the client size.
2. Detours at `FUN_10004405` / `FUN_10005602` entry note the window being built (`g_meet_dlg`).
3. The poll keeps a just-opened Reunirse page that sits exactly at the noted spot at the same client size (clamped
   inside the client). Any other dialog that reappears at the top-left the poll last saw it, same client size, is
   kept too. After a client size change the old rules apply (re-centre).
4. A dragged dialog stays "dragged" through a resize (clamp only, DLGAREA no longer re-centres it), and a Reunirse
   page is never taken for the right-docked terrain panel.

Not covered: with `SC3RESIZE_HUDNATIVE=1` the SIMUI install block returns early, so parts 1-2 are not installed.
