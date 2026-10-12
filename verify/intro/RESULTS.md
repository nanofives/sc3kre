# RESULTS: intro movie shown whole (task intro, 2026-10-12)

Pre-registration: `PRE.md` (written before the first INTRO run). Mechanism: `re/analysis/INTRO_MOVIE.md`.

## Verdict

Cause found and fixed. On a 32bpp desktop the intro codec (UV.DLL, direct-to-primary mode) writes the 320x480 movie
one pixel per source pixel, at half the screen x the game intended. The game halves x because on a 16bpp screen the
same writer emits two pixels per source pixel. Result in an 800x600 window centred on screen: a 320-wide picture that
starts 180 px left of the client, so only its right 140 columns show at the window's left edge. The INTRO block in
sc3resize decodes into a private buffer and scales the picture into the client: 640x480 centred in the 800x600 window
(as stock fullscreen), 1280x960 when maximized on a 1680x1050 screen, black bars. Opt-out `SC3RESIZE_INTRO=0`,
fit-to-window at any scale `SC3RESIZE_INTRO=2`.

## Evidence

Pictures, logs and tracer scripts are local only (gitignored, game-derived): `verify/intro/` in MAIN and in the
`child/intro` worktree.

All pictures are the game's client region read from the locked primary at the codec's own Unlock call
(Frida at UV `0x10005ffa`, `uvwitness.py`). The display was asleep for the whole session (taskbar clock frozen at
13:04), so no on-screen grab was possible. The magenta in the control pictures is what the locked primary buffer
held outside the codec's write, not a claim about what the screen shows there.

| Run | Tree | Arm | Client | Result | File |
|---|---|---|---|---|---|
| 1 | MAIN | SC3RESIZE_INTRO=0 | 800x600 at 440,212 | 140 px strip at the left edge, rest not movie | `main_intro0_client_f60.png` |
| 2 | MAIN | default (1) | 800x600 at 440,212 | whole picture 640x480 at client 80,60, black bars | `main_intro1_client_f60.png` |
| 3 | MAIN | default (1), maximized at ~1 s | 1680x979 at 0,23 | 1280x960 at client 200,9, black bars | `main_intro1_maximized_f300_half.png` (half size) |
| 4 | MAIN | SC3RESIZE_INTRO=2, maximized | 1680x979 at 0,23 | 1305x979 at client 187,0 | `main_intro2_maximized_f200_half.png` (half size) |
| 5 | stock | SC3RESIZE_INTRO=0 | 800x600 at 440,212 | same strip as run 1 | `stock_intro0_client_f60.png` |
| 6 | stock | default (1) | 800x600 at 440,212 | same as run 2 | `stock_intro1_client_f60.png` |

Before any fix (no INTRO code): `codec_frame_32bpp_dump.png` is the codec's own output read at its destination,
720 px wide from x=260: the movie is 320 wide, colours correct. `trace_uv_frame.log`: primary 1680x1050 pitch 6720
32bpp, codec dest x,y 260,272, ctx flags 0x038114C3, movie 320x480.

Log lines (sc3resize.log), MAIN default:
```
--- INTRO: armed (mode 1) - UV.DLL base 0x10000000, writer calls at +0x5ef9/+0x5e2a re-targeted
INTRO> primary 1680x1050 pitch 6720 bpp 32
INTRO> FUN_10006900 frame 1: codec x,y 260,272 (stock dest), client 800x600 at 440,212 on the primary, movie 320x480 shown 640x480 at 520,272
INTRO> FUN_10006900 frame 2: codec x,y 260,272 (stock dest), client 1680x979 at 0,23 on the primary, movie 320x480 shown 1280x960 at 200,32
```
Stock tree, default: the same `armed`, `primary 1680x1050 pitch 6720 bpp 32` and `frame 1 ... shown 640x480 at 520,272` lines.

After the movie (MAIN default, 120 s run): the codec wrote 1051 frames in ~70 s, then stopped, and sc3perf logged the
game presenting at 6-60 fps from t=72 s, so the game moves on to the menu as before. Not checked: what the menu looks
like after the intro (display asleep).

## Predictions vs outcome

1. armed + bpp 32: **held**. 2. 640x480 at 520,272: **held**. 3. whole picture in the lock, black bars: **held**.
4. maximized 2x centred: **held** (1280x960 at 200,32). 5. INTRO=0 back to 260,272 and the strip: **held**.
6. on-screen grab: **not run, display asleep**. 7. stock install same: **held** (in-lock witness, log).

## Test setup notes

- Stock runs used `Simcity_stock_intro\` (hard links of `Simcity_stock`, mod files removed from its `Apps\`), instance
  `re\harness\inst_intro`. Running a second copy of the mods from `Simcity_stock\re\harness\inst_*` while
  `Simcity_stock\Apps` holds the release DLLs kills the game at 0.2-3.6 s (sc3overscroll.dll+0x4040 thread after the
  game frees the copy; found by child `windowed`, reproduced here 3/3 with my build and 1/1 with the release sc3resize).
- Owner laptop: not measured. If its desktop runs at 16bpp, or Windows applies the DWM 16-bit mitigation layer to
  SC3U.exe, the codec doubles natively and INTRO stays out (logs `stock path (bpp 16 ...)`). If the laptop uses display
  scaling above 100%, the client-to-primary mapping uses surface/screen ratios that were not tested here.

## Owner decision (2026-10-12, via orchestrator)

Default stays integer scaling: 1x in the 800x600 window, 2x when it fits. `SC3RESIZE_INTRO=2` (fill the window at any
scale) stays available as an option. `SC3RESIZE_INTRO=0` = stock.
