# smoothfont (round 2026-11-20f): smooth TITLE9 / TITLE12 outlines

Owner, 2026-11-20: "can you make the comic sans font less pixelated?"

**Verdict: done, not published.** Smooth outlines traced from the game's own coverage are built and switchable in one
list. They remove the blocks and stripes at 150% and 200% and keep layout identical. At 100% the pixel build is still
the exact one: smooth is softer there. Recommendation: switch TITLE9 + TITLE12, keep the 1-bit fonts as pixels. Owner
to pick.

## Pictures (`owner_shots/`, all opened and checked)

| file | what |
|---|---|
| `page_100.png`, `page_150.png`, `page_200.png` | importer top bar + two windows with buttons: today, smooth TITLE9 + TITLE12, smooth with 1-bit fonts too (headless Chrome, device scale 1 / 1.5 / 2, page `--ui-scale` 1.25) |
| `titles_buttons_100.png`, `_150`, `_200` | 4 titles + 5 button labels, today left, smooth right, device pixels 1:1 |
| `game_vs_100.png` | at 100%, every pixel x5: the game's screen grab, today, smooth, smooth without COLR. Preferencias, Indagar, Presupuesto, Sustituir, Gastos |
| `onebit_100.png`, `_150`, `_200` | MAIN9 + SYSTEM9 strings, today against traced |

## Method (`re/tools/bldimport/sc3font.js` `smoothContours`, `smoothLevel`)

1. Glyph coverage (15 levels) upsampled 8 x 8 with a Catmull-Rom kernel.
2. Cut at one iso level per font, picked so the outlines' total area equals the font's total coverage (ink mass kept):
   TITLE9 0.491, TITLE12 0.507, SERIF17 0.465, MAIN9 0.497, MAIN10 0.497, SYSTEM9 0.508.
3. Marching squares (oriented, so outer contours come out clockwise and holes counter-clockwise), specks under 1/25 px
   dropped, Douglas-Peucker at 0.07 px.
4. TrueType quadratic B-spline: vertices are off-curve points, turns sharper than 57 degrees stay on-curve corners.
5. COLR v1 layer kept (see below).

Advances, cmap, ascent and descent identical to the pixel build: 0 of 220 advances differ in each of the six fonts,
the cmap tables are byte-identical, and the page pictures show every box and line in the same place. No glyph lost its
ink (0 of 220 empty in every font).

## Numbers at 100% against the game's coverage (`compare.py`, `metrics.json`)

fbf.py's rendering = the game's draw (UI_STYLE.md: IoU 1.000 on the titles). Chrome's ink aligned to it by the best
whole-pixel shift.

| string | today: mean err / mass / IoU | smooth: mean err / mass / IoU | smooth without COLR: err / mass / colour fringe |
|---|---|---|---|
| Preferencias | 0.003 / 1.00 / 1.00 | 0.072 / 0.98 / 0.94 | 0.080 / 0.96 / 184 |
| Indagar | 0.003 / 1.00 / 1.00 | 0.064 / 0.98 / 0.94 | 0.081 / 0.96 / 192 |
| Presupuesto | 0.003 / 1.00 / 1.00 | 0.072 / 1.00 / 0.95 | 0.074 / 0.97 / 184 |
| SC3 Model Classifier | 0.003 / 1.00 / 1.00 | 0.064 / 0.99 / 0.95 | 0.080 / 0.97 / 184 |
| Sustituir | 0.003 / 1.00 / 1.00 | 0.084 / 0.97 / 0.94 | 0.093 / 0.93 / 184 |
| Gastos | 0.003 / 1.00 / 1.00 | 0.080 / 1.00 / 0.90 | 0.084 / 0.97 / 184 |
| Ingresos | 0.003 / 1.00 / 1.00 | 0.084 / 1.00 / 0.92 | 0.089 / 0.96 / 184 |
| Open folder | 0.003 / 1.00 / 1.00 | 0.078 / 1.01 / 0.92 | 0.083 / 0.96 / 184 |
| Install into the game | 0.003 / 1.00 / 1.00 | 0.078 / 0.99 / 0.93 | 0.092 / 0.94 / 184 |

Mean err = mean |coverage difference| over pixels with ink in either. Mass = ink ours / game. IoU at coverage 0.5.
Colour fringe = max |R - B| of 255 on black-on-white text.

**COLR stays on.** Plain TrueType outlines go through DirectWrite with ClearType in Chrome on Windows: colour fringes up
to 184 of 255 and 3 to 7% less ink. With the COLR v1 layer (the same trick as the pixel build) Chrome draws them
grayscale through FreeType, as the game does. So `build_fonts.mjs` keeps COLR on smooth fonts, `--no-colr` is there
for comparison only.

## 1-bit fonts (MAIN9, MAIN10, SYSTEM9)

They trace without trouble (`--smooth all`, `onebit_*.png`, third block of the `page_*.png`), but these faces are
drawn on the pixel grid: diagonals are stair steps by design. Tracing keeps the steps and only rounds their corners,
so at 200% they read as a slightly blurred pixel font, not as a smoother typeface. At 100% they lose their exactness
(mean err 0.059 to 0.085 against 0.000 today). Not recommended. A real gain there would need redrawn diagonals (a
new design, not a trace).

## The switch (one list, two files, nothing under docs/ changed)

- `re/tools/sc3ui/build_fonts.mjs`: `export const SMOOTH = [];` (published files). Pick -> `['TITLE9', 'TITLE12']`.
  `--smooth <list|all|none>` overrides it for one run. `--check` uses the list, so it stays the gate.
- `re/tools/bldimport/sc3font.js`: `const SMOOTH = [];` (the importer's run-time fallback, same list), `opts.smooth`
  overrides it.
- Then `node re/tools/sc3ui/build_fonts.mjs --game <install>` and `py -3.12 re/tools/bldimport/sync_css.py` (`--publish`
  for the importer copy). sc3ui.css does not change: same file names, same metrics, same size-adjust.
- After switching, `sc3font_check.py`'s published TITLE9 / TITLE12 checks (coverage within 0.012 of the FBF) would
  fail by design and need a smooth tolerance (mean err under 0.09, mass 0.95 to 1.05 would fit the numbers above).

Sizes (WOFF2): TITLE9 17,452 -> 21,300 bytes, TITLE12 21,956 -> 26,376. TTF: 172,656 -> 53,272 and 201,544 -> 67,040.

## Checks run

- `build_fonts.mjs --check` with the default (empty) list: all six published WOFF2 identical (the pixel path is
  untouched).
- `sc3font_check.py --game stage/release`: 22 of 22 pass.
- `compare.py`: the table above, all pictures regenerated.

Not measured: Firefox and Safari (not installed). Headed Chrome on the owner's screen: headless Chrome 157 was used,
which drew COLR glyphs the same way the published-font checks found.

## Work files (local)

`compare.html` (the test page: `?mode=page&one=1` or `?mode=strip`), `compare.py`, `shot.sh` (headless Chrome
screenshot at a device scale), `fonts_pixel/`, `fonts_smooth/` (COLR, all six traced), `fonts_smoothplain/`
(no COLR), `ttf_pixel/`, `ttf_smooth/`, `shots/`, `metrics.json`, `sc3font_check/`.
