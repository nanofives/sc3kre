# True centre: pre-registration (2026-10-07)

Owner: at the north/west edges the camera stops much earlier than at the south/east ones.
Measured live (owner's game, all four mods, window 2560x1322 physical): the city view stores 704x544, the
native visible area. Translate judges each step at w/2+dx, h/2+dy of that stored size, so the judged point sits
about 670 px left and 260 px above the real screen centre (in game pixels).

Fix: `sc3overscroll.c` `true_center` takes over Translate at the first pick (`SIMSPR 0x1001d56e`). Every step is
judged at the visible centre, visible size = stored size + (client - 800x600): the game's height-aware pick first
(mode 0, then 1), then the flat edge rule with the probes sized from the visible area. `[camera] true_center=0`
restores the old behaviour.

Fixture: all four mods, Europolis, window maximized on the primary, arrows (key-state spoof) pushed 10 s in each
screen diagonal (up-left, up-right, down-left, down-right), one grab at each limit. Measure: fraction of the
screen width along the screen's horizontal centre line that is past the map edge (non-city pixels), on the side
the camera was pushed.

| arm | prediction |
|---|---|
| A `true_center=0` | up-left and up-right limits show clearly less void than down-right and down-left (the reported asymmetry). |
| B `true_center=1` | log `TRUECENTER: view stores 704x544, visible WxH`. The four limits within 10 points of each other, each near the configured 75%. |

Fail: B still asymmetric by more than 10 points, or right-drag / arrows / edge-scroll-while-placing break.
