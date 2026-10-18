# PRE: hudfix A/B (task hudfix, 2026-10-11)

Written before the A/B runs. Build: `child/hudfix` at the commit that adds this file. Instance `re/harness/inst_hudfix`,
Europolis copy, `-multi`, windowed, client 1200x900 virtual (window on the 125% monitor, grabs 1500x1125 physical),
`sc3resize.ini [hud] scale=150` with no `smooth` key (so the default applies).

## What is already measured (runs r1 to r3, before this file)

- Defect 1: ini with `scale=150` and no smooth key -> log `HUDOPT> on: scale 150 smooth 1` (r1, new default).
- Per frame the game Blts the city layer into its composite with a client-sized dest, then each HUD window into the
  composite, then the composite into the primary (HSSEQ dump, r2). No full present was skipped by the enlarge pass
  (HSDIAG census, r1 and r2: skipped 0 in every 1-s window).
- r2 scroll, HUDFIX not yet built: frame-to-frame specks of city inside the enlarged side panel (button outlines), the
  RCI columns and around the minimap buttons, plus a 1-px line along the outer edge of the enlarged bar and panel
  (`r2_scroll_on/heat_hud.png`).
- Minimap: the in-process dump (r3) shows the bilinear pass reaches the map picture (88 interpolated colours in a
  40x40 block), and that the native picture itself is pixel data with hard stair steps (`dump3/mini_before_x3.png`).

## Arms

- **A (control):** `SC3RESIZE_HUDFIX=0`. Must reproduce the specks, or the run says nothing.
- **B:** default (HUDFIX on, MINISMOOTH on).

Same procedure in each arm, fresh launch each: load, `dismiss_tips`, resize to 1500x1125 physical, wait 3 s, then
`re/tools/hudfix_scrollgrab.py --dir right,down --taps 8 --hold 0.2 --frames 150` (reference frame first, then frames
during the spoofed scroll).

## Metrics (physical pixels of the grab, rects inside the enlarged HUD, 2 px in from its outer edges)

- P = side panel `[1324 0 1500 812]`, R = RCI + bar right `[1124 977 1198 1123]`, L = bar lower row left of the pause
  button `[0 1064 900 1123]`.
- For each rect: U = number of pixels that differ (sum |dRGB| > 24) from the reference in at least one frame.

## Predictions

1. A reproduces: U(P) >= 50 or U(R) >= 50. Otherwise the run is void (control failed).
2. B: U(P) <= 5 and U(R) <= 5 and U(L) <= 5.
3. The camera moved in both arms: >= 30 frames whose city region changed > 30% against the previous frame.
4. B cost: the logged pre-present ms per frame in B is at most A + 3 ms.
5. Minimap (smooth on): in a B frame dump the map picture's diagonal edges are smoother than in an A dump of the same
   view (by eye, x3 crops side by side), and the frame/buttons look the same in both.
6. Regressions, B build: HUDOPT log shows `smooth 1` with no ini; Preferencias shows Suavizado checked with no ini;
   OK applies (log `HUDOPT> OK`), Esc keeps (log `kept`); `SC3RESIZE_HUDOPT=0` gives 0 HUDOPT lines.
