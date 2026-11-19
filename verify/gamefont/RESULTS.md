# gamefont results (round 2026-11-19d): the game's font on every page, light theme only

## Verdict

Done. Every page (gallery, building guide, importer) draws its text with web fonts built from the game's own FBF files,
the free fonts only behind them, and the light look only.

| measure | main | gamefont |
|---|---|---|
| replica text vs the game grab (R3 Preferencias, 16 labels): ink IoU | 0.291 | **1.000** |
| replica text pixels with identical RGB | 0.123 | 0.974 (the anti-aliased title's edge pixels) |
| labels placed at 0 px from the game (top and bottom) | 5 of 16 | **16 of 16** (15 by sc3ui.css, 1 by the replica's own 17 px row rule) |
| ink mass ours / game | 0.91 to 1.14 | 1.000 (title 0.978) |
| published fonts vs the FBF rendering, Chrome 157 and Edge 157 | | 1-bit fonts 0 px differ, anti-aliased within 0.012 coverage |
| game text crisp (whole-pixel blow-up of the glyphs) at --ui-scale 1 / 1.25 / 1.5 / 2 x screens 100 / 125 / 150 / 200% and a 3x phone | 1.25 on a 100% screen: 36% of the ink solid | **20 of 20 combinations exact** |
| run_all.sh (with the SC4 steps) | | **16 of 16** |

## 1. The fonts (`docs/assets/fonts/`, `re/tools/sc3ui/build_fonts.mjs`)

`node re/tools/sc3ui/build_fonts.mjs --game <install>` runs sc3font.js's own `parseFBF` + `buildTTF` in node (one code
path with the importer's run-time builder) and writes one WOFF2 per font. The partial-pixel widths of the anti-aliased
fonts come from Chrome's measured coverage curve, kept in `re/tools/sc3ui/font_calibration.json` (`--measure` re-measures
in headless Chrome), so the build is reproducible: `--check` rebuilds and compares byte for byte (a run_all.sh step).
The FBF files are byte-identical in all seven languages, so one build serves every install. No .FBF file is in the repo.

| file | bytes | TTF bytes | line / baseline | kind | sc3ui.css family |
|---|---|---|---|---|---|
| MAIN9.woff2 | 5,692 | 39,276 | 14 / 12 | 1-bit | "SC3 Main", bold of "SC3 Text" |
| SYSTEM9.woff2 | 5,016 | 34,492 | 14 / 11 | 1-bit | "SC3 Text", "SC3 System" |
| MAIN10.woff2 | 5,784 | 40,840 | 16 / 13 | 1-bit | "SC3 Name" |
| TITLE9.woff2 | 17,452 | 172,656 | 18 / 14 | 15 levels | "SC3 Button" |
| TITLE12.woff2 | 21,956 | 201,544 | 23 / 18 | 15 levels | "SC3 Title" |
| SERIF17.woff2 | 29,712 | 355,272 | 29 / 23 | 15 levels | "SC3 Serif" (no page uses it yet) |

85,612 bytes in all (TTF: 843,080). Format: WOFF2 with the null transform on every table, compressed with node's own
brotli (no dependency). It keeps the COLR v1 / CPAL tables, which are what make the text exact:

- **Chrome 157, Edge 157** (tested): every glyph is a COLR v1 colour glyph in the text colour, drawn by Chrome's own
  FreeType path. `sc3font_check.py` published pass: 9 of 9 strings, 0 px differ on MAIN9 / MAIN10 / SYSTEM9, coverage
  within 0.012 on TITLE9 / TITLE12 / SERIF17, navy exact. Same result in Edge (`SC3_BROWSER=<msedge.exe>`).
- **Firefox** (COLR v1 since 107) and **Safari** (no COLR v1, draws the plain outlines under the colour glyphs, the same
  pixel rectangles): not installed here, not measured `[UNCERTAIN]`.

Glyph coverage: 220 characters per font (Windows-1252, the game's byte table). The pages use ASCII plus `‹ ›` (the
gallery's lightbox arrows), and every font has all of them (`verify/gamefont/coverage.py`). Nothing falls back.

## 2. sc3ui.css

- An `@font-face` per role, the game font first in every `--ui-type-*` token, Istok Web / Comic Relief behind it.
  `size-adjust` makes each token's size draw one font pixel per `--u` (12.5 px x 128% = 16 px em). The percentage
  must be rounded up: 139.1304% left 210 of 2,870 pixels 1 px off, 139.130435% none.
- Running text is SYSTEM9 (the game's regular face) with MAIN9 (its bold face) for `<b>` / `<strong>`.
- "SC3 Main" has ascent / descent overrides so a MAIN9 label sits where the game puts it in an 18 px row (1 px under the
  top). List rows, the blue strip and the dropdown got the 1 to 2 px each needed to match the grab.
- Letter-spacing tokens are 0 (the advances are the game's). `code` and the importer log use SYSTEM9. `--ui-mono` is
  left only for the importer's rules editor (JSON). Page font-size overrides of game text are gone (importer badges,
  guide download button, gallery arrows): another size draws at a fraction of a pixel.
- **Light only** (owner, 2026-11-19): the dark tokens and every `prefers-color-scheme: dark` / `data-theme` rule are
  gone from sc3ui.css and the importer, `:root` keeps `color-scheme: light`, the importer's Theme button, its handler,
  `?theme=` and the `bc-theme` storage are removed. Checked with the OS in dark mode: background `#d8d9ff`,
  `color-scheme: light` (fonts_inline.mjs).

## 3. Scale: `--u` snapped to whole device pixels

A pixel font is crisp only when a font pixel covers whole screen pixels. `--u` is now `--ui-scale` rounded to whole device
pixels (`--ui-dpr` from resolution media queries, browser zoom included; browsers without CSS `round()` keep the plain
value). The game bitmaps gain the same.

Screen px per game px (CSS px in brackets), `verify/gamefont/scale/scale_check.py`:

| --ui-scale | 100% | 125% | 150% | 200% | phone 3x | unsnapped, share of ink solid (100% / 150% / phone) |
|---|---|---|---|---|---|---|
| 1 | 1 (1) | 1 (0.8) | 2 (1.33) | 2 (1) | 3 (1) | 1.00 / 0.53 / 1.00 |
| **1.25** | **1 (1)** | **2 (1.6)** | **2 (1.33)** | **3 (1.5)** | **4 (1.33)** | 0.36 / 0.43 / 0.70 |
| 1.5 | 2 (2) | 2 (1.6) | 2 (1.33) | 3 (1.5) | 5 (1.67) | 0.53 / 0.57 / 0.81 |
| 2 | 2 (2) | 3 (2.4) | 3 (2) | 4 (2) | 6 (2) | 1.00 / 1.00 / 1.00 |

Snapped: all 20 combinations are exact whole-pixel blow-ups of the game's glyphs.

**Pick: 1.25 on every page (gallery, guide, importer). 1 for the replica and the font tests.**
- 100% desktop: 1.25 gives the game's own size, one screen pixel per game pixel. It is the only crisp step below 2x,
  and 2x doubles every length (body caps 18 px, title bars 56 px). So text on a 100% screen is 20% smaller than on main.
  Browser zoom 125% snaps it to 2x, still crisp.
- 125% and 150% laptop screens: 2 screen px (1.6 / 1.33 CSS px), close to main's sizes.
- 390 px phone (3x): 4 device px (1.33 CSS px), caps 12 CSS px. 1.5 gives 5 px (caps 15 CSS px), larger than a phone
  page needs.

## 4. Importer from disk

`sync_css.py` now inlines `fonts/*.woff2` as `data:` URIs too, so the importer (the published copy and the sample pack's
`importer\index.html`) carries the game fonts and opens from any folder. sc3font.js's run-time builder is the fallback:
`useGame()` first checks the published faces (`publishedLoaded()`) and builds from the player's game folder only when
they failed. Checked by `webtest/fonts_inline.mjs` (6 of 6): all six families load in the importer, from the page
itself (no font file fetched), body text "SC3 Text" first, the builder standing by, no Theme button, light under OS
dark mode. `sync_css.py --publish` done (`docs/buildings/importer/`, index.html identical to classifier.html).

## 5. Pictures (`owner_shots/`)

- `gallery_*`, `guide_*`, `importer_*`: `_desk_before_after.jpg` (1280 px window, main above, this branch below) and
  `_phone_before_after.jpg` (a true 390 px phone at 3x, main left, this branch right).
- `scale_desktop_1x_vs_2x.jpg` (100% screen, --ui-scale 1.25 against 1.5) and `scale_phone_4_scales.jpg` (390 px phone,
  --ui-scale 1, 1.25, 1.5, 2).
- `replica_text_x2.jpg`: the game's Preferencias, the replica with free fonts (main), the replica with the published
  fonts, x2 nearest. Local only: it holds game pixels.

Gallery and guide rebuilt from their generators (`gallery_build.py --site-only`, `make_docs.py --wt dev/gamefont/wt`,
download link kept). The sample pack's README.txt came out byte-identical.

## 6. Tests

`run_all.sh` **16 of 16** on base 764da06 + this branch (log `verify/gamefont/webtest/run_all.log`): the 14 earlier
steps, SC4 included, plus `build_fonts.mjs --check` and `fonts_inline.mjs`. `sc3font_check.py` is now 22 checks (the
run-time pass and the published pass). Run locally (`PROYECTOS_TEST_HUB=off`: the dev tree and SC4 download are local
files the notebook does not have).
