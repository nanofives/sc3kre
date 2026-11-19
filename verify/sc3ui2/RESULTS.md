# sc3ui2 results (round 2026-11-18g): measured font, spacing and background

## Verdict

Done. Every target in the brief is met, measured against a native 800x600 stock game:

| target | result |
|---|---|
| frame / panels mean CIEDE2000 <= 3 | max 0.69 (title bar 0.09, frame clouds 0.43, group faces 0.19 to 0.47, list 0.69, strip 0.20, sound panel 0.13, combo 0.36) |
| edges within 1 px | 30 of 30 lines found, 29 within 1 px. The 30th is the strip's bottom line, which the game cuts where its two buttons sit |
| title and body text the same size and weight | 15 of 16 labels match the game's ink top and bottom within 1 px (the 16th is 2 px lower at a `j` descender). MAIN9 labels carry 0.91 to 0.98 of the game's ink |
| importer tests | `run_all.sh` 8 of 8 steps PASS, `check_roundtrip.py` 8 of 8 PASS |
| page text unchanged | text, scripts, ids, classes and markup identical to main on all 4 pages. Only `<style>` changed (`textcheck.py`) |

What changed for the owner's three points:

- **Font.** The game draws its UI with its own bitmap fonts. I decoded the FBF format and matched every UI element to
  its font pixel for pixel. Then I scored 91 free Google Fonts families (plus 7 local Windows faces for reference) against those glyphs. Titles and buttons are now
  **Comic Relief** (pass 1 used Comic Neue, which scores 0.608 against Comic Relief's 0.677). Everything else is now
  **Istok Web** (pass 1 used Arimo), bold like the game's labels, with the game's plain zero.
- **Spacing.** Every length in sc3ui.css is now a game pixel count multiplied by one knob, `--ui-scale`. At 1 the
  stylesheet reproduces the Preferencias dialog (the replica above). Pages use 1.25.
- **Background.** The real cloud bitmap is one 256x256 tile in `SYS.IXF`. Ours is a 500-byte SVG noise tile with the
  same colour, spread and cloud size. The mean colours differ by CIEDE2000 0.01. The clouds are now 128 to 256 px
  blobs like the game's, against the small gradients of pass 1.

Full tables (FBF format, font map, scores, cloud statistics, spacing, scale, proof): `re/analysis/UI_STYLE.md`,
section "Precision pass".

## 1. References (native, no scale)

`pwsh re/scripts/sc3dev.ps1 run sc3ui2 -Stock [-City "Berlin, Germany.sc3"]`: only `sc3winonly.dll` loads, so the game
runs stock in an 800x600 window with no UI scale and no mod text rendering. Grabs with `sc3io` (physical 800x600, no
resampling), posted clicks only. PIDs 1264 and 19824, both started and stopped by this session.

`r1_city.png` (city view, info bar, ticker), `r3_prefs.png` + crop `ref_prefs.png` (Preferencias, 480x472 at 160,64),
`r4_query.png` (Indagar), `r5_budget.png` (Presupuesto), `r7_menu.png` (main menu). All local, game pixels.

Correction to the brief: the UI bitmaps are not loose `.bmp` files. They are records of type `0x62b9da24` inside
`Apps\Res\UI\Shared\*.IXF`: a 0x18-byte header (`2, size, width, height, 7, size`), then a QFS stream that decodes to
RGB565 (710 of 711 records decode this way with `re/tools/qfs.py`).

## 2. Fonts

FBF layout: 16-byte header (`1, 640, height, 1`), an 8-bit coverage sheet (16 = key, 1 = full ink, up to 15 levels),
a 256-entry RGB565 palette, then 256 glyph cells of 5 u32 (left, top, right, bottom, advance). All 8 files parse to EOF.
Reader: `re/tools/sc3ui/fbf.py`.

Which font draws what (exact match, IoU 1.000 unless noted): title bars TITLE12, labels, headings, lists, info bar and
ticker MAIN9, the query dialog's building name MAIN10, pill buttons TITLE9 (0.75 to 0.79, anti-aliased), budget rows
and the combo box SYSTEM9, main menu labels SERIF17 (0.86).

Scores (`re/tools/sc3ui/fontscore.py`, headless Chrome renders each candidate as DOM text, letter-spacing fitted to the
game's advances; score = half glyph IoU, half blurred string IoU):

| element | pick | score | best overall |
|---|---|---|---|
| title bars (TITLE12) | Comic Relief 400, 16 px, +0.43 px | 0.677 | itself (Comic Sans MS, local only, 0.662) |
| buttons (TITLE9) | Comic Relief 700, 11 px, +0.83 px | 0.706 | Comic Sans MS 0.731 (local), Delius 0.710 |
| labels (MAIN9) | Istok Web 700, 12.5 px, 0 | 0.739 | Atkinson Hyperlegible 0.757 |
| digits (MAIN9) | Istok Web | 0.724 | itself. Atkinson 0.669: it draws a slashed zero |
| table rows, combo (SYSTEM9) | Istok Web 400, 11.5 px, -0.34 px | 0.705 | Verdana 0.705 (local) |
| building name (MAIN10) | Istok Web 700, 13.5 px, -0.45 px | 0.794 | itself |
| main menu (SERIF17) | Gelasio 400, 23.5 px (not used by the pages) | 0.666 | Times New Roman 0.670 (local) |

I picked one sans family for the four sans elements. Istok Web totals 2.962, Atkinson Hyperlegible 2.851 and Arimo
2.825. In the replica, Atkinson labels carried 1.06 to 1.17 of the game's ink, and Istok Web carries 0.91 to 0.98.

Crisp text cannot be had: Chrome on Windows always anti-aliases DOM text. Paragraphs (the game has none) use the same
face and size at 400.

## 3. Background

| | game tile `SYS.IXF {0x82b9b75b, 0xe2b14588}` | ours (`re/tools/sc3ui/cloudgen.py`) |
|---|---|---|
| mean RGB | 215.5, 216.7, 255.0 | 215.5, 216.7, 255.0 |
| spread RGB | 12.33, 10.86, 0 | 12.34, 10.87, 0 |
| variance per octave 256-128 / 128-64 / 64-32 / 32-16 px | 0.912 / 0.047 / 0.026 / 0.007 | 0.914 / 0.054 / 0.024 / 0.006 |
| luminance percentiles 1/50/99 | 200.2 / 219.6 / 239.2 | 196.4 / 219.5 / 241.5 |
| tile | 256 px, seamless | 256 px, stitched |

The window body repeats the tile from the window's top-left corner. Two patches of the query dialog matched it at the
same offset, with 0.6/255 mean error. Ours is feTurbulence fractalNoise (baseFrequency 0.00586, 5 octaves, seed 29),
picked from 1,000 rendered candidates, then mapped onto the game's colour axis. Pixel for pixel, ours differs from the
game by CIEDE2000 5.11. Two patches of the game's own tile differ by 4.1 to 6.1, so the difference is only the pattern.

## 4. Spacing and scale

Measured table: UI_STYLE.md "Spacing, native px". Key values: window edge 1 px white/black. Title plate 31 px, 3 px
inside the edge. 7 px under the title. Group grooves 1 px, 6 px apart side by side and 4 px stacked. Content 7 px
inside, rows every 18 px, 22 px after a heading. Radio 12 px, check box 13 px, combo 20 px, strip 28 px. Pill button 21 px
with a 5-step drop shadow.

The scale is `--ui-scale`, with 1 = the game's own pixels. Pages use 1.25: it brings the game's 12.5 px body text to
15.6 px, the size the pages already used (15 px) and close to the browser default. At 1.5 the body would be 18.75 px
and title bars 24 px.

## 5. Proof

`re/tools/sc3ui/replica_prefs.html` is the dialog rebuilt with sc3ui.css at `--ui-scale: 1`. I placed the group boxes by
hand from the measured rectangles. Everything inside them comes from the stylesheet. `re/tools/sc3ui/replica_diff.py`
renders it at 480x472 and compares it with `ref_prefs.png`. Results are in the verdict table. Log:
`verify/sc3ui2/replica/diff.log`, numbers: `replica/report.json`.

Not matched: the close box and OK button are game bitmaps with soft shading, which I drew in CSS (mean ΔE 3.03 and 2.00).
The combo arrow sits inside the box (the game's is a separate button beside it). The scroll bar arrows and the volume
bars are approximations.

## 6. Pages

- `docs/assets/sc3ui.css`: rewritten on `--ui-scale`, with type tokens (`--ui-type-ui`, `-prose`, `-row`, `-name`, `-title`,
  `-btn`), the cloud SVG tile (light and dark), a measured window, title bar, close box, group box, list, strip, plate,
  pill button, check box, radio, combo, slider, info bar and ticker.
- Gallery: `verify/showcase/site/gallery_page.html` page styles on the tokens, rebuilt with `gallery_build.py --site-only`.
  The unchanged template rebuilt byte-identical first. Output copied to `docs/gallery/index.html`.
- Building guide: `verify/bldpack/work/guide_template.html` the same way, rebuilt with `make_docs.py --wt dev/sc3ui2/wt
  --tree dev/sc3ui2/tree --zip <release url>`. The unchanged template rebuilt byte-identical first, and the sample pack
  README.txt it rewrites came out byte-identical.
- Importer: the page styles in `re/tools/bldimport/classifier.html` on the tokens (42 rules), CSS copy synced, published to
  `docs/buildings/importer/` (`sync_css.py --publish`, `--check` in sync).

Tests: `test-slot bash re/tools/bldimport/webtest/run_all.sh <work> dev/sc3ui2/tree stage/kits`: 8 of 8 PASS
(`run_all.log`). `check_roundtrip.py`: 8 of 8 PASS (`check_roundtrip.log`).

## Pictures (`owner_shots/`, local: the replica ones hold game pixels)

- `replica_side_by_side.jpg` (game | ours, 1080 wide), `replica_stacked_2x.jpg` (game above ours, 2x nearest, phone
  portrait), `replica_zoom3x_q1..q4.jpg` (quadrants at 3x), `replica_diff_dE.jpg` (heat map 0 to 10),
  `replica_text_overlay.jpg` (red = game ink, blue = ours, purple = both).
- `cloud_tile_game_vs_ours.jpg`: the game tile and ours, each repeated 2x2.
- `before_*` / `after_*` for gallery, guide, importer, gallery dark and importer dark, `_desk.jpg` (1280 px window at
  640) and `_phone.jpg` (true 390 px). Before = main, after = this worktree.

## Notes for the orchestrator

- `re/tools/sc3ui/*` sits under the deny-by-default `/re/tools/*`: it needs `git add -f`.
- `fbf.py` and `cloudgen.py` read the game install at run time. No FBF, bitmap or font made from them is in the repo:
  the tools write only to gitignored `verify/`.
- `verify/bldpack/work/make_zip.py` still reads the importer from `dev/bldpack/wt` (noted by sc3ui). The released sample
  pack zip keeps the old look until it is rebuilt from `docs/buildings/importer`.
