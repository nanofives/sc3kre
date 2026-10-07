# Camera past the map edge, edge sliding, and edge scroll while placing (`sc3overscroll`)

Status: owner-tested 2026-10-06, alone and together with `sc3resize` and `sc3bigcity` (the combined
launcher `mods_launch.exe`). Source `re/harness/src/sc3overscroll.c`, build
`re/harness/build_overscroll.ps1`, launcher `overscroll_launch.exe`. Run record:
`verify/overscroll/RESULTS.md`. Everything is patched in memory, every installer checks the shipped
bytes first. No game file is modified.

## The stock scroll limit is one check

`SIMSPR FUN_1001d503` (`cISC3CityViewIso::Translate(float dx, float dy, bool)`, vtable `0x10063390`
slot `+0x78`) moves the camera only if `FUN_1000902f` finds a map tile under the NEW screen centre,
first with mode 0, then mode 1. If both miss, the whole step is thrown away (`0x1001d594 je
0x1001d5bc`). There is no other clamp. Arrow keys, game edge scrolling and right-drag all go
through Translate, and so does the minimap's centre-on-tile.

So the centre can never leave the map, and at most about half the screen can be empty.

## What the mod changes

**1. Overscroll.** The 9 bytes at `0x1001d58d` (mode-1 pick call, `test al,al`, `je refuse`) jump to
a hook. It repeats the stock call, and when that misses it checks the new centre and 8 points
`(overscroll - 50)%` of the view away (left, right, up, down, diagonals). If any is over the map
the step is accepted. With the default 75 the camera stops when about 75% of the screen is past a
straight edge. At a corner the diagonal points let it go further. The camera's stored centre tile
(`+0xb0/+0xb4`) becomes the centre tile clamped onto the map.

The check is FLAT, not the game's height-aware pick. That took three versions:

| version | limit test | result |
|---|---|---|
| v1 | the game's pick at each probe | outline followed every hill, the camera caught on slopes near the edge (owner) |
| v2 | flat at altitude 0 | on Europolis the limit sat ~20 tiles off the drawn edge, no step past the edge was ever accepted (`run8.log`) |
| v3 | flat at ONE height, the median of all edge cells | 1024 map: the north and west edges were far above the median (41), the camera stopped early there (owner) |
| v4 | flat at the height of the NEAREST edge, box-averaged over +-24 cells along it | owner: right |

The flat projection is the game's own arithmetic re-done in C: `FUN_100090b7` (view -> world, +origin
`+0x54/+0x58`), `FUN_1000a33a` (world -> raw u,v, by tileW `+0x30`, tileH `+0x38`, zoom `+0x28`) and
`FUN_1000a5c6` (rotation `+0x2c`, W/H `+0x14/+0x18`), with the altitude added back as
`alt << cellmap+0x44` (the term `FUN_100090ef` subtracts). Altitude = cell record byte `+0xb`.
The edge height is found in three rounds: project, read the nearest edge's height there,
re-project.

**2. Edge sliding.** When a push is refused, the hook tries the push turned by 15, 30, 45, 60 and
75 degrees, the side that worked last time first. The first allowed one wins, at the push's speed
times the cosine of the turn. Translate reads the step back from `[ebp-0xc]`/`[ebp-4]` after the
hook, so the hook rewrites those.

| version | sliding | result |
|---|---|---|
| v1 | the axis parts of the push, then the two 2:1 edge directions | stuck in the corners of the allowed area, never slid (`run3.log`) |
| v2 | turn up to 90 degrees at FULL speed | "sloppy": pushing almost straight into an edge sent the camera sideways at full speed (owner) |
| v3 | turn up to 75 degrees at speed x cos, last side first | owner: right |

**3. Edge scroll while placing.** The resize mod turns the game's edge scrolling off in windowed mode.
While a drag that started on the city view is held (zones, roads, pipes, bulldozer) and the cursor is
outside the window, the camera moves toward it at `gain` px/s per pixel outside (default 8, capped at
1600 px/s), time-based. The move goes through the right-drag call, outer view `vt+0x34` =
`FUN_1004327d(dx, dy, 1)` (Translate + view update), so overscroll and sliding apply. A
`WM_MOUSEMOVE` at the cursor is posted at most every 60 ms so the drag preview follows.

It runs from the city view's tick `FUN_10042a95`, detoured at entry. That function is called with
ecx = the view's cIGZWin sub-object (vtable `SIMSPR+0x676ac`), the outer view (vtable `+0x67894`)
is ecx - 4 (`run13.log`). The first version ran from the GZGraphicD blit heartbeat and posted a
mouse move every step: the UI flickered while the camera moved (owner).

**4. True centre and the front wall (2026-10-07).** The view stores its size at `+0x20/+0x24` as the native
visible area, **704x544** (800x600 minus the side panel and bar), and the resize mod never changes it (read live
in a 2560x1322 window). Translate judges each step at `w/2+dx, h/2+dy` of that size, so at a large window the
judged point sat far up-left of the real centre: north/west limits came early, south/east late (owner). The mod
now takes over at the FIRST pick (`SIMSPR 0x1001d56e`) and judges every step at the visible centre, visible size
= stored size + (client - 800x600). The game's height-aware pick runs first at that point, then the flat rule.
Front edges (stepping off them moves down the screen, chosen per rotation) draw a cliff wall below their surface,
so they are judged at altitude 0, the bottom of the wall. Measured void share at the four diagonal limits: old
23/74/63/63%, true centre alone 87/86/42/37%, with the wall rule 87/86/91/85% (`verify/overscroll/TRUECENTER_PRE.md`).

## Config (`overscroll.ini` beside the DLL)

```ini
[camera]
overscroll=75   ; percent of the screen allowed past the edge, 50 = stock, max 95
slide=1
arrows_keep=1   ; a held arrow survives a mouse move
true_center=1   ; judge steps at the real visible centre
front_wall=1    ; front edges judged at the bottom of the cliff wall
[edge]
enabled=1
gain=8          ; px/s per pixel the cursor is outside the window
max=1600        ; px/s
[display]
windowed=1
```

## Running it with the other mods

`re/harness/src/mods_launch.c` injects every one of `sc3resize.dll`, `sc3bigcity.dll`,
`sc3overscroll.dll` found beside it. Each mod checks the bytes it patches and logs a refusal rather
than half-patching. Measured with all three: every installer of each mod went in. The windowed and
16-bit patches exist in all three, the first one to load applies them and the others log a pattern
mismatch and skip, which is expected. `bigcity` and `resize` share the GZGraphicD tick, the
detours chain. A `0xC0000096` at `SC3U.exe+0x84122` in resize's VEH log at startup is in every
earlier resize hand-test log too, it is not from the combination.

## Still open
- Click-to-place tools (buildings) do not hold the button, so edge scroll while placing does not
  trigger for them.
- The overscroll limit is computed from the view size, measured only at the sizes the owner used.

## Arrow scrolling stops when the mouse moves (stock, traced 2026-10-07)

Owner report: holding an arrow key scrolls, moving the mouse stops it. Bisect: happens with resize, overscroll
and bigcity each loaded alone (`verify/simrun/RESULTS.md`), so it is not a mod.

The arrow keys and the mouse edge scroll **share four latch bytes** on the city view (outer object, vtable
`SIMSPR 0x10067894`): up `+0x1e1`, down `+0x1e2`, right `+0x1e3`, left `+0x1e4`. `+0x177` enables scrolling,
`+0x1e6` is the right-drag mode.

- Arrows set them only from key events: KeyDown `vt+0x68` = `FUN_1004985a` and KeyUp `vt+0x64` =
  `FUN_1004979a` re-read all four arrows through the key-state object `+0x210` (`vt+0xc(vk)`), and the scroll step
  `FUN_10043daf` re-reads them only when all four are 0. `[CONFIRMED @ 0x1004985a, 0x1004979a, 0x10043daf]`
- The mouse edge handler `vt+0x40` = `FUN_10043a38(x, y)` writes the same bytes. Cursor inside the view's inner
  rect (`+0x178..+0x184`): **all four cleared**. Outside it: each set from its edge band rect (`+0x188..`,
  `+0x198..`, `+0x1a8..`, `+0x1b8..`). `[CONFIRMED @ 0x10043a38]` With the resize mod the bands are emptied
  (`rz_edge_off`), so outside the inner rect they also come out 0.
- Once all four are 0 the view tick stops calling the scroll step, so nothing re-reads the keys until the next
  key event. `[UNCERTAIN]` whether typematic repeat KeyDowns reach `vt+0x68`; the owner sees the scroll stay
  stopped, which suggests they do not.
- `[UNCERTAIN]` why a posted `WM_MOUSEMOVE` did not reproduce it. GZWIND has a `GetCursorPos` + `ScreenToClient`
  accessor (`FUN_10020260`, vtable slot at `0x1002dc04`), so the edge handler is probably fed the real cursor
  position (unchanged by a posted message) rather than the message's lParam. Caller not traced.

Fix candidate (not built): after `FUN_10043a38` runs, OR the four latches with the live arrow-key state from
`+0x210` `vt+0xc`, so a held arrow survives a mouse move and edge scroll still works.
