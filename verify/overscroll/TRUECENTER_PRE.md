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

## Results (2026-10-07)

Window maximized 2560x1351 (client 1952x1025 game px visible). Each push ran until two identical frames (the first
10 s version was too short to cross the map in B, rerun). Metric deviation: share of the city-view AREA that is void
colour (66,73,99), not the centre-line fraction pre-registered. It ranks the arms the same way.

| arm | up-left | up-right | down-left | down-right |
|---|---|---|---|---|
| A `true_center=0` | 23% | 74% | 63% | 63% |
| B `true_center=1`, surface height on every edge | 87% | 86% | 42% | 37% |
| C `true_center=1` + `front_wall=1` | **87%** | **86%** | **91%** | **85%** |

- A: the reported asymmetry, prediction met.
- B: **FAIL** against the pre-registration (spread 50 points). Top surface symmetric, but the front (south-facing)
  edges draw the terrain's cliff wall below their surface and the limit ignored it.
- C (added after B, not pre-registered): front edges, chosen per rotation, judged at altitude 0, the bottom of the
  wall. Spread 6 points. Frames look alike: a sliver of map in the far corner on all four sides.
Owner hand test pending.

## Owner session 2 crash (2026-10-07 10:47) and repro attempt

Owner launched all four mods, created a new **1024** city ("Enorme", bigcity log 41.3 s), crashed at 107.8 s:
`0xC0000005 WRITE 0x186EB000` (a page boundary) at `GZGraphicD+0xC4FB`, one of the per-format span writers that
`FUN_1000c48e` hands out, called from SIMDIRT `FUN_10013556` (`sc3_dirt_render_gouraudpoly_flat`, terrain
rasterizer). So the terrain fill wrote past the end of its target surface. Camera code is not on the stack.
Log kept: `re/harness/combo/crash_resize_1047.log`.

Repro attempt, true_center=1, all four mods, maximized 2560x1351, blank **512** fixture
(`verify/citysize_mod_test/N512_city.sc3`), 2 laps of all four diagonal limits (8 pushes, each until the camera
stopped): **no crash**, edges reached. `[UNCERTAIN]` whether the crash needs 1024, a particular zoom or terrain,
or the reach `true_center` adds. No 1024 fixture exists to rerun it.
