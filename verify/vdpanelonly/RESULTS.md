# vdpanelonly: "Mapa de vecinos" grey with VERDATOS (owner report 2026-10-27)

Owner report: "mapa de vecinos looks off on craterville, there's no terrain visible on the map". Their screenshot: the
region diamond flat grey, terrain colour only inside the city-name label boxes.

## Cause

VERDATOS (sc3resize, `verify/verdatos/RESULTS.md`) redraws a map view that sits in an enlarged dialog as a twin at the
dialog's factor and pastes it over the enlarged dialog. It was written for Ver datos but took every map view
(vt `SIMUI 0x100a7e68`) in an enlarged dialog. The neighbours map is one, and its twin (a Clone of the view) drew flat
grey. The paste skips pixels that are not the view's own, which is why the label boxes kept the game's terrain.

Reproduced in `dev/autosave/tree`, Craterville, client 2560x1351, HUD 2.252x, posted clicks only (side panel views
category, then the neighbours icon): log `VERDATOS> twin ... of map view ...`, 16,205 px/frame pasted, grey diamond.
Same run with `SC3RESIZE_VERDATOS_NATIVE=0`: the region terrain shows (the game's 256 picture enlarged).

## Fix (sc3resize.c, VERDATOS `vd_after`, `SC3RESIZE_VDPANELONLY=0` turns it off)

Only a map view inside a panel of its dialog is taken. Window chains measured (SIMUI vtable offsets):

| dialog | chain | dialog found |
|---|---|---|
| Ver datos | map view `A7E68` < panel `A4D64` < dialog `A4D64` | 2 levels up |
| Mapa de vecinos | map view `A7E68` < dialog `A4D64` | 1 level up |

The panels share the dialog class, so the class alone cannot tell them apart; the depth does.

## Check (same tree, city and size)

| run | result |
|---|---|
| Mapa de vecinos, fix | log `VERDATOS> map view ... sits directly in its dialog (not a Ver datos panel) - not taken`, region terrain visible |
| Ver datos (aura), fix | `VERDATOS> first twin draw ... twin 851x851 texture 512 (native 256)`: still the sharp map |

Not checked: other dialogs that might hold a map view (none known). The neighbours map is now the game's 256 picture
enlarged, not drawn sharp.
