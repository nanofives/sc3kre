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

## Five pages, not two (child `reunirse2`, 2026-10-12)

Owner after DLGSTAY: "si muevo la ventana cuando voy a otro cartel la ventana no sigue". Evidence: `verify/reunirse2/`.

The meeting manager's message dispatcher `FUN_100032ea` [CONFIRMED @ 0x100032ea] opens five page kinds. Every open
message first calls `FUN_100037f0`, which closes the pages at manager +0xc/+0x10/+0x14/+0x18. Each page has its own
stored spot in the same slot struct:

| Page | Window id | Opened by | Builder | Closer | Slot |
|---|---|---|---|---|---|
| list | 0x62be5dd2 | msg 0x724a82d0 | `FUN_10004405` | `FUN_10004cda` | +4/+8 |
| advisor | 0x62be5df0 | 0x724a82d1 (advisor portrait) | `FUN_10005602` | `FUN_10005fb4` | +0xc/+0x10 |
| topic text | 0x62be5000 | 0x724a82d2/d4/d5 (topic row on the advisor page, `FUN_100052fc`) | `FUN_10008d40` | `FUN_1000a1a2` | +0x18/+0x1c |
| petitioner | 0x62be5f00 | 0x724a82d6 (list button 0x62be5dd6, `FUN_100042f7`) | `FUN_1000690a` | `FUN_10007b8c` | +0x20/+0x24 |
| page 0x62be6000 | 0x62be6000 | 0x724a82d7 (topic page button 0x62be5009, `FUN_1000a202`) | `FUN_1000a5ec` | `FUN_1000ae3e` | +0x28/+0x2c |

The topic page's handler is `FUN_10008ceb` (0xa2bf8ace = build, 0xa2bf8acf = close). All five are 384x354 except the
list (`n*0x34+0x13` wide). Separate: the petitioner page's answer buttons 0x62be5f0c/0x62be5f0d (`FUN_10007c7a`) build
a 337x254 window with `FUN_1000823d`, which the game centres on the petitioner page's rect (`FUN_10008169` passes it
as the anchor at controller +0x14) [CONFIRMED @ 0x1000823d].

The topic page's back arrow (0x42b7c355 in `FUN_1000a202`) reaches the advisor builder BEFORE the topic page's
closer runs: measured 6 ms later in the log. `FUN_10008c67` closes a flagged (0x1000) window through the window
manager (`vt+0x44(0xd, ...)`), so the close is deferred.

A page built at the address the previous page just freed, with the same size, is not "just opened" for the dialog
poll (tracked entry still visible): it stays wherever the game put it, including half outside the client. Measured
in X1 (`SC3RESIZE_MEETALL=0`): topic page at [640 296 1024 650] in an 800x600 client, X out of reach. Round/1012
shipped with this (the C1 run got a new address and the poll centred it instead).

### MEETALL (sc3resize, `SC3RESIZE_MEETALL=0` opts out)

1. Each of the five closers copies the spot it stored into all five slots.
2. Each builder first takes the local top-left of a page that is still open (live in the tree, visible, SIMUI
   dialog class, >= 300x300) and shares it, which covers the deferred close. The closer then clears the noted page
   pointer so a freed address reused by another dialog is never read.
3. The answer popup is kept where the game centred it on its page, at the client size it was built at.
4. Unchanged: closed at one client size and reopened at another, the page is centred.
