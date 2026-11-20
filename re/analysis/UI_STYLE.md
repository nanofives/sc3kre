# SC3U UI style, measured (sc3ui round 2026-11-18f, precision pass sc3ui2 round 2026-11-18g, game bitmaps + fonts sc3ui3 round 2026-11-19b)

Owner, 2026-11-18: every page we publish (gallery, building guide, importer, future pages) uses the UI elements of the
base game. This file is the measured palette behind `docs/assets/sc3ui.css`. Every value below was read off a pixel of a
screenshot of the running game, not picked by eye.

## Screenshots the values come from

All are local only (gitignored `verify/`), game pixels are never published.

| id | file | what | how |
|---|---|---|---|
| S1 | `verify/sc3ui/g1_city.png` | Berlin, city view: right-hand toolbar, info bar, minimap panel | `sc3dev run sc3ui -City "Berlin, Germany.sc3"`, `sc3io --grab`, 800x600 client |
| S2 | `verify/sc3ui/g2_flyout.png` | S1 with the options flyout open | posted click on the options button |
| S3 | `verify/sc3ui/g3_dialog.png` | Preferencias dialog: title bar, group boxes, radio buttons, check boxes, list with selection, sliders, pill buttons | posted click on the flyout's preferences button |
| S4 | `verify/graphaxis/owner_shots/1_un_grafico_1600x900.png` | Graficas window: clouded body, left icon strip, plot bands | earlier round, game pixels |
| S5 | `verify/batconvert/owner_shots/t2_query_the_joneses.png` | Indagar (query) dialog: picture frame, label/value text | earlier round, game pixels |
| Z1-Z3 | `verify/sc3ui/zoom_title_prefs.png`, `zoom_title_graficas.png`, `zoom_button.png` | nearest-neighbour x3 crops of the title font and a pill button | PIL crop of S3/S4 |

The game draws its UI in 16-bit colour, so the same colour reads `#7b92ff` in S3 (565 expanded) and `#7890f8` in S4
(an older capture path). The tokens use the S3 values.

## Palette

| token | value | where measured | used for in the game |
|---|---|---|---|
| `--ui-blue` | `#7b92ff` | S3 (300,75) title bar; (560,170) sound box; (480,388) "Escuchar eleccion" bar; S4 (40,30) title | dialog title bars, blue plates behind buttons, inset blue areas, window icon strip |
| `--ui-blue-line` | `#7b8aff` | S3 (166,300), (372,300), (300,106) | 1 px groove shadow line round group boxes and under the title bar |
| `--ui-blue-dark` | `#7382ff` | S1 toolbar edge (715,420) | darker band of the toolbar's rounded frame |
| `--ui-blue-deep` | `#636dc6` | S1/S3 info bar bevel (250,549) | last bevel line above the ticker |
| `--ui-navy-line` | `#4a599c` | S3 (240,528) button drop shadow | mid tone of a button's drop shadow |
| `--ui-shadow` | `#182039` | S3 (240,526) | darkest line of a button's drop shadow |
| `--ui-outline` | `#313863` | S3 close button (608..630, 72..92) | button outline |
| `--ui-lav-50` | `#e7e7ff` | S3 (300,65..67) and (300,99..105) | frame highlight band round the title bar, button top highlight |
| `--ui-lav-100` | `#dedfff` | S3 (250,260), (500,320) | group box face, list background, title text |
| `--ui-lav-150` | `#dedbff` | S3 (330,514) | pill button face |
| `--ui-lav-200` | `#d6dbff` | S3 (366..371,300) | separator band between group boxes, toolbar face (S1 760,200) |
| `--ui-lav-250` | `#d8d9ff` | mean of the body tile SYS.IXF e2b14588 (sc3ui2; pass 1 read `#d8dcf8` off S4, an older capture path) | clouded window body, base colour |
| `--ui-cloud-hi` | `#f0f4f8` / `#e0e4f8` | S4 body | light clouds in the body texture |
| `--ui-cloud-lo` | `#c8d0f8` / `#b8c0f8` | S4 (620,180), S5 (330,180) | dark clouds in the body texture |
| `--ui-lav-300` | `#c6c7ff` | S3 (161..165,300) | dialog outer frame band |
| `--ui-lav-400` | `#bdc3ff` | S3 info bar fields (250,572..587) | info bar value fields (city, population, funds, date) |
| `--ui-lav-500` | `#adb6ff` | S3 (300,68), (300,98) | bevel mid tone next to the title bar, info bar bevel |
| `--ui-hi` | `#ffffff` | S3 (300,64), (160,300), (250,544) | 1 px outer highlight of every window and bar |
| `--ui-grey-edge` | `#848284` / `#6b696b` | S3 (158..159,300) | grey outline outside a window |
| `--ui-text` | `#31347b` | S3 radio labels (190..265,152..166), list items, button labels, text on blue plates | all body text |
| `--ui-label` | `#7b7db5` | S3 "Efectos sonido", "Trafico visible", "Sonido" | group headings and sub-labels |
| `--ui-info-text` | `#18288c` | S3 info bar (150..260,572..588) | info bar value text |
| `--ui-title-text` | `#dedfff` | S3 title (166..270,74..94) | title bar text |
| `--ui-select` | `#0000ff` | S3 list selection (560,255), text `#ffffff` | selected list row |
| `--ui-ticker-bg` | `#000000` | S3 (250,550..566) | news ticker strip |
| `--ui-ticker` | `#fffb00` | S3 (250,555..560) | ticker text |
| `--ui-check-box` | `#ffffff` with `#31347b` mark | S3 (383..396,133..146) | check box and radio button face |

## Bevels and shapes

- **Window frame** (S3 scan x=156..175 at y=300): grey edge `#848284`, 1 px `#ffffff`, 5 px `#c6c7ff`, 1 px
  `#7b8aff`, then the face `#dedfff`. Corners are square.
- **Title bar** (S3 scan y=62..107 at x=300): 1 px `#ffffff`, 3 px `#e7e7ff`, 1 px `#adb6ff`, 29 px flat `#7b92ff`
  (no gradient), 1 px `#adb6ff`, 7 px `#e7e7ff`, 1 px `#7b8aff`. Close box at the right end: a small square button with
  a navy X.
- **Group box** (S3 x=360..383 at y=300): face `#dedfff`, 1 px `#fff3ff` highlight, 6 px `#d6dbff` gap, 1 px `#7b8aff`
  shadow line. A heading in `#7b7db5` sits inside the box at the top left.
- **Pill button** (S3 y=494..533 at x=240, Z3): sits on a `#7b92ff` plate. Outline `#848294`/`#313863`, face
  `#dedbff` with a `#e7e7ff` highlight along the top, height about 24 px, ends fully rounded. Below it a 7 px drop shadow
  `#737184 #636573 #393c4a #182039 #313863 #4a599c #6371ce` that fades into the plate (offset down and right).
  Label `#31347b`, bold sans, about 13 px. The OK button is the same shape with a navy tick.
- **Info bar** (S3 y=540..599 at x=250): grey `#6b696b`, 1 px `#a5aeb5`, 1 px `#ffffff`, `#cecfff #adb6ff #8c92ff
  #8496ff #636dc6` bevel, 17 px black ticker with yellow text, then `#8c96ff #7b82ff #8c92ff #949eff` and the
  `#bdc3ff` value fields separated by `#7b86ff` lines. Text `#18288c`, bold, centred.
- **Toolbar** (S1 x=700..800): a rounded lavender frame (`#a5aaff` edge, `#7382ff` band, face `#d6dbff` to `#e7e7ff`)
  holding rounded square icon buttons with a dark outline. Icons are game art and are not reproduced.
- **Window body** (S4, S5): a soft clouded texture. Pass 1 recreated it with radial gradients from S4's older capture
  colours. Since sc3ui2 it is our own SVG noise tile matched to the game's tile, mean `#d8d9ff` (Precision pass, Window body clouds).
- **Plot area** (S4): horizontal bands alternating `#d8dcf8` / `#e0e4f8`, frame `#7b92ff`.
- **Picture frame** (S5): 1 px `#7b92ff` box round the building picture.
- **Lists**: face `#dedfff`, rows 18 px, selection solid `#0000ff` with white text, scroll bar arrows on `#7b92ff`.

## Fonts

Pass 1 (2026-11-18f) picked Comic Neue and Arimo by eye. Replaced by the measured picks in "Precision pass" below:
Comic Relief (title bars, buttons) and Istok Web (everything else).

## Precision pass (sc3ui2, round 2026-11-18g)

Owner, 2026-11-18: "font, spacing and background is still not quite there yet, be more precise". Everything in this
section was measured at the game's native size: a stock game (`sc3dev run <name> -Stock`, only `sc3winonly.dll`, so no
UI scale and no mod text rendering) in an 800x600 window, grabbed with `sc3io`, no resampling.

| id | file (local only, `verify/sc3ui2/`) | what |
|---|---|---|
| R1 | `r1_city.png` | Berlin, city view: info bar, ticker, toolbar |
| R3 | `r3_prefs.png`, crop `ref_prefs.png` (x 160..639, y 64..535) | Preferencias dialog, 480x472 |
| R4 | `r4_query.png` | Indagar (query) dialog, clouded body, "Sustituir" pill button |
| R5 | `r5_budget.png` | Presupuesto window, "Gastos" / "Ingresos" pill buttons, table rows |
| R7 | `r7_menu.png` | main menu |

Dialog coordinates below are relative to the dialog's top-left pixel (R3 at screen 160,64).

### FBF bitmap fonts (`Apps\Res\Text\<lang>\*.FBF`)

All 8 files parse to EOF with this layout (`re/tools/sc3ui/fbf.py`). ENGLISH and English-UK copies are byte-identical.

| offset | type | field |
|---|---|---|
| +0x00 | u32 | 1 in every file `[UNCERTAIN]` version or kind |
| +0x04 | u32 | sheet width, 640 in every file |
| +0x08 | u32 | sheet height |
| +0x0c | u32 | 1 in every file `[UNCERTAIN]` |
| +0x10 | u8[w*h] | 8-bit sheet, top row first. 16 = key (transparent, read from pixel (0,0) by GZServiceD `FUN_10007ce5`), 1..15 = coverage, 1 = full ink (SetColor ramps palette 1..15 from the text colour to entry 16, `FUN_100070aa`) |
| +0x10+w*h | u16[256] | RGB565 palette (entries 1..16 are replaced at draw time) |
| then | 256 x 5 u32 | glyph table per byte value: left, top, right, bottom (right/bottom exclusive), advance px. The same 0x14-byte cells GZServiceD `FUN_10006e54` reads |

| file | sheet | line px | coverage | cap / x-height / descender px | game slot (`cSC3App::ctrlmgr_setup` 0x0040efd8) |
|---|---|---|---|---|---|
| MAIN9 | 640x42 | 14 | 1-bit | 9 / 7 / 2, stem 2 px (bold) | 0xf |
| MAIN10 | 640x48 | 16 | 1-bit | 10 / 7 / 3, bold | 1, 2, 0xe |
| SYSTEM9 | 640x28 | 14 | 1-bit | 9 / 6 / 2, stem 1 px (regular) | 0, 0xb |
| TITLE9 | 640x54 | 18 | 15 levels | 9 / 6 / 3 | 3, 0xc |
| TITLE12 | 640x92 | 23 | 15 levels | 12 / 9 / 4 | 0xd |
| SERIF17 | 640x145 | 29 | 15 levels | serif | 0x10 |
| systemloadsave | 640x51 | 17 | full palette (not coverage) | | 0x11 |

### Which font draws what (exact glyph match, `verify/sc3ui2/fontmap.py`, local: it reads game grabs)

Each font's rendering of the known string, slid over the grab's ink (by text colour). IoU 1.000 = every pixel identical.

| element | where | font | IoU |
|---|---|---|---|
| title bars | R3 "Preferencias", R4 "Indagar", R5 "Presupuesto" | TITLE12 | 1.000 |
| group headings, sub-labels, radio / check labels, list rows | R3 | MAIN9 | 1.000 |
| info bar fields, ticker | R3 bottom bar | MAIN9 | 1.000 |
| query dialog labels | R4 "Elevacion:" | MAIN9 | 1.000 |
| query dialog building name | R4 "Camiones O'Plenty" | MAIN10 | 1.000 |
| pill buttons | R4 "Sustituir", R5 "Gastos" | TITLE9 | 0.75 / 0.79 (anti-aliased, threshold 0.5) |
| budget table rows, combo box text | R5 "Ordenanzas", R3 "800x600 NVIDIA" | SYSTEM9 | 1.000 |
| main menu labels | R7 "Nueva Ciudad", gold `#f2ce73` | SERIF17 | 0.86 (anti-aliased over art) |

### Free font picked per element (`re/tools/sc3ui/fontscore.py`)

Every candidate (family x weight x half-pixel size) renders the same game string as DOM text in headless Chrome, the
way the pages render it. Letter-spacing is fitted so the total advance equals the game's. Score = 0.5 x glyph IoU (each
glyph aligned on its own: shape and size) + 0.5 x blurred string IoU (shape and spacing, forgiving sub-pixel placement).
Ink = candidate ink / game ink (weight). 47 sans, 30 hand-lettered and 21 serif families (7 of them local Windows faces, for reference), 98 to 2,585 configurations
per element. Scores are relative: a 1-bit game glyph against an anti-aliased one never reaches 1.0 (Comic Sans MS,
which TITLE12 was evidently drawn from, scores 0.662).

| element (FBF) | top 3 | pick | why |
|---|---|---|---|
| title bars (TITLE12) | Comic Relief 400 16 px 0.677, Comic Sans MS (local) 0.662, Andika 0.646 | **Comic Relief 400, 16 px, +0.43 px** | best overall, ink 1.01. Comic Neue (pass 1) scores 0.608 |
| pill buttons (TITLE9) | Comic Sans MS (local) 0.731, Delius 700 0.710, Comic Relief 700 11 px 0.706 | **Comic Relief 700, 11 px, +0.83 px** | 0.004 under the best free face, and one hand-lettered family for titles and buttons |
| labels, headings, info bar (MAIN9) | Atkinson Hyperlegible 0.757, Arial (local) 0.749, Tahoma (local) 0.747, Istok Web 0.739 | **Istok Web 700, 12.5 px, 0** | see below |
| digits (MAIN9, "Pob: 794,278 2/9/2067 800x600 0123456789") | Istok Web 0.724, Arimo 0.682, Atkinson Hyperlegible Next 0.677, Atkinson Hyperlegible 0.669 | Istok Web | plain zero like the game. Atkinson draws a slashed zero |
| table rows, combo (SYSTEM9) | Verdana (local) 0.705, Istok Web 400 11.5 px 0.705, Segoe UI (local) 0.704 | **Istok Web 400, 11.5 px, -0.34 px** | best free face |
| building name (MAIN10) | Istok Web 0.794, Arial (local) 0.787, Tahoma (local) 0.772 | **Istok Web 700, 13.5 px, -0.45 px** | best overall |
| main menu (SERIF17) | Times New Roman (local) 0.670, Gelasio 400 23.5 px 0.666, Lora 0.649 | Gelasio (not used by the pages) | best free face |

One sans family for the four sans elements: Istok Web totals 2.962, Atkinson Hyperlegible 2.851, Atkinson Hyperlegible
Next 2.837, Arimo 2.825. Istok Web has 400 and 700 only, so "600" in the score tables renders as 700. In the replica its
labels carry 0.91 to 0.98 of the game's ink (Atkinson 1.06 to 1.17). Istok Web and Comic Relief are OFL, from Google Fonts.

Crisp text: Chrome on Windows always anti-aliases DOM text (`-webkit-font-smoothing` works on macOS only), so 1-bit
rendering cannot be asked for. Body text is the game's bold face (MAIN9 is bold, so every UI label is 700). Running
text (paragraphs, which the game does not have) uses the same family and size at 400 (`--ui-type-prose`).

Type tokens in sc3ui.css (native px x `--ui-scale`): `--ui-type-ui` MAIN9, `--ui-type-prose`, `--ui-type-row` SYSTEM9,
`--ui-type-name` MAIN10, `--ui-type-title` TITLE12, `--ui-type-btn` TITLE9, each with its `--ui-ls-*` letter-spacing.

### Window body clouds

The body is one 256x256 tile, `SYS.IXF {group 0x82b9b75b, instance 0xe2b14588}`, type 0x62b9da24, QFS-compressed RGB565.
It repeats from the window's top-left corner: two 12x12 patches of R4 matched the tile at the same offset (40, 40), mean
error 0.6/255 (565 rounding). Measured with `re/tools/sc3ui/texstats.py`; ours generated by `re/tools/sc3ui/cloudgen.py`
(feTurbulence fractalNoise, baseFrequency 0.00586 = 1.5 periods per tile, numOctaves 5, seed 29, stitchTiles, a colour
matrix onto the game's colour axis; chosen from 1,000 rendered candidates by octave shares and histogram shape).

| statistic | game tile | ours (as Chrome draws it) |
|---|---|---|
| mean RGB | 215.5, 216.7, 255.0 (`#d8d9ff`) | 215.5, 216.7, 255.0 (`#d8d9ff`) |
| standard deviation RGB | 12.33, 10.86, 0.0 | 12.34, 10.87, 0.0 |
| colour axis (R, G, B), share of variance | 0.752, 0.660, 0.0, 98.6% | 0.751, 0.661, 0.0, 100% |
| luminance percentiles 1/10/50/90/99 | 200.2 / 204.8 / 219.6 / 231.8 / 239.2 | 196.4 / 204.3 / 219.5 / 233.9 / 241.5 |
| variance per wavelength octave, 256-128 / 128-64 / 64-32 / 32-16 / 16-8 px | 0.912 / 0.047 / 0.026 / 0.007 / 0.003 | 0.914 / 0.054 / 0.024 / 0.006 / 0.001 |
| tile size, seam | 256 px, seamless (seam step 0.79 x interior step) | 256 px, stitched (1.24 x) |
| CIEDE2000 of the mean colours | | 0.01 |

Blue is constant: the clouds vary only along red + green, one or two large blobs per tile (91% of the variance at
wavelengths of 128 to 256 px). Pass 1's radial gradients were far smaller. The SVG is 500 bytes inline; `--ui-cloud-size`
scales it with `--ui-scale`. (The dark theme's navy copy went with the dark theme in gamefont, 2026-11-19d.)

### Spacing, native px (R3 unless noted)

| metric | value |
|---|---|
| window edge | 1 px `#ffffff` top/left, 1 px `#000000` right/bottom, clouds inside |
| title plate | 3 px inside the edge line. 1 px `#adb6ff` border, flat `#7b92ff`, 31 px tall (1 + 29 + 1), 472 px wide in a 480 px window |
| title text | TITLE12 `#dedfff`, ink 4 px in from the plate's edge, baseline 21 px below its top, no shadow |
| close box | 17x16 at (451, 9), 1 px outline, inner 1 px navy square, 2 px X, drop shadow to (472, 30) |
| title to content | 7 px of clouds |
| window side margin | 5 px (edge line excluded) |
| group box | 1 px groove: `#7b8aff` top/left, `#fff3ff` bottom/right, flat `#dedfff`. Left (6,42) 200x300, right (212,42) 262x300, bottom (6,346) 468x76 |
| gaps between groups | 6 px side by side, 4 px stacked |
| group content | 7 px inside the groove (heading ink 8 px from the line), heading baseline 17 px below the groove |
| line pitch | 18 px (radio rows, list rows), heading after rows 22 px (4 px extra), check rows beside sliders 24 px, bottom group 17 px |
| radio | 12 px footprint: outer ring `#6b71bd` / `#b5b6e7`, inner ring `#31347b` / `#7b82bd`, 8 px white face, 4 px navy dot; label 3 px after |
| check box | 13 px footprint, same rings, 9 px white face, 2 px navy tick; label 3 px after |
| combo | 20 px tall (18 + 2 groove), white face, SYSTEM9 navy text 3 px in, arrow button outside the box |
| list | groove, `#dedfff` face, 18 px rows, 16 px scroll bar on `#7b92ff` |
| blue panel | 1 px `#7b8aff` border, `#7b92ff` fill (sound sliders 96x110) |
| blue strip | 28 px, same border, MAIN9 navy text 6 px in (R3 "Eschuchar eleccion", the game's spelling) |
| slider | 3 px track (2 rows `#080c18`, 1 row white), round grey knob about 20 px |
| pill button (R4, R5) | 21 px tall, ends fully round, 8 px side padding, outline `#848294` / `#5a5d6b`, `#dedbff` face with a 2-row `#e7e7ff` highlight, drop shadow 1..5 px down-right `#393c4a #182039 #313863 #4a599c #6371ce`, TITLE9 text, on a `#7b92ff` plate |
| ticker | 17 px black strip, MAIN9 `#fffb00` (R1) |

### Scale

Superseded by "Game fonts and scale" below (gamefont, 2026-11-19d): `--u` is now snapped to whole device pixels.


sc3ui.css writes every length as `calc(N * var(--u))` with N in game pixels and `--u: calc(var(--ui-scale) * 1px)`.
`--ui-scale: 1` reproduces the game's pixels (the replica). Pages use **1.25**: the game's body text is 12.5 px, and
1.25 brings it to 15.6 px, the size the pages' body text already had (15 px) and close to the browser default (16 px),
so running text reads at a normal size while every proportion stays the game's. At 1.5 the body would be 18.75 px and
title bars 24 px, larger than pages need on a desktop or a phone. Borders stay 1 px at any scale (Chrome rounds 1.25 px
borders to whole device pixels), like the game's 1 px lines.

### Proof: replica_prefs.html against R3 (`re/tools/sc3ui/replica_diff.py`)

`re/tools/sc3ui/replica_prefs.html` rebuilds the dialog with sc3ui.css at `--ui-scale: 1`. The group boxes are placed by
hand from the rectangles above; everything inside them (bevels, fonts, row pitch, padding, control sizes) comes from
the stylesheet. Rendered in headless Chrome at 480x472 and compared pixel for pixel.

| measure | result | target |
|---|---|---|
| CIEDE2000 of region mean colours, frame and panels (title bar, clouds, 3 group faces, sound panel, list, strip, combo) | max 0.69 (title bar 0.09, frame clouds 0.43, groups 0.19..0.47, list 0.69) | <= 3 |
| CIEDE2000 per pixel, flat regions, text excluded | max 1.59 | |
| CIEDE2000 per pixel, frame clouds | 4.87 (two patches of the game's own tile differ by 4.1 to 6.1) | |
| 1 px lines (grooves, plates, title bar), found and within 1 px | 30 found, 29 within 1 px. The 30th is the strip's bottom line, which the game cuts at its two buttons | within 1 px |
| label ink boxes (16 labels), top and bottom within 1 px | 15 of 16 ("Ver consejos" bottom +2: Istok's j descender), left 0..+2 px | same size |
| label ink mass, ours / game | MAIN9 labels 0.91..0.98, title 1.14, combo 1.50 (SYSTEM9 is a 1 px regular face) | same weight |
| close box, OK button (game bitmaps, drawn in CSS here) | 3.03, 2.00 | |

## Game bitmaps (sc3ui3, round 2026-11-19b)

Owner, 2026-11-19: "the play and stop buttons should bring their texture, slider texture is different, X button is also
different, dropdown arrow is wrong". His call: these pieces are the game's own bitmaps, published in
`docs/assets/sc3ui/` (risk accepted, memory `project-sc3kre-publish-policy`). Nothing else from the game is published.

Found by decoding every UI record of `Apps\Res\UI\Shared\*.IXF` (710 images, type `0x62b9da24`) and matching each
against a native 800x600 grab of Preferencias (`verify/sc3ui3/g3_prefs.png`, identical to R3: 0 pixels differ).
Written by `re/tools/sc3ui/uiart.py --game <install> --out docs/assets/sc3ui` (byte-stable PNGs, `--check` compares).
565 is expanded by bit replication (`r<<3|r>>2`, `g<<2|g>>4`), the colours the game's screen shows (`#7b92ff`).

| piece | file | record (group:instance) | size | where in R3 (dialog px) | match against the grab |
|---|---|---|---|---|---|
| close X | `close.png` | SYS.IXF `82b9b75b:453ba1f4` | 92x23, 4 frames of 23x23 | rows 2..22 of a frame at (449, 9) | 432 of 483 px identical, the other 51 (drop shadow) within 4/255 |
| play | `play.png` | SYS.IXF `82b9b75b:82fab6d2` | 96x25, 4 frames of 24x25 | (414, 313) | 0 px differ |
| stop | `stop.png` | SYS.IXF `82b9b75b:22fab6de` | 96x25, 4 frames of 24x25 | (438, 313) | 0 px differ |
| dropdown arrow | `combo_arrow.png` (normal), `_disabled`, `_pressed`, `_hover` | SYS.IXF `82b9b75b:62b99d31` | 64x16, 4 frames of 16x16, one file each | (178, 316), 1 px right of the box | 0 px differ |
| slider track | `slider_track.png` | SYS.IXF `82b9b75b:c2b99e09` columns 0..59 | 60x20 | left cap at (378, 67), track to 443 | 0 px differ |
| slider knob | `slider_knob.png` | the same record, columns 60..79 | 20x20 | (444, 67), (444, 91), (444, 115) at 100% | 0 px differ |
| volume steps | `volume.png` | `22DEC92D_OtherCtrls.ixf` `22dec92d:00000001` | 68x10 | (386, 50) | 0 px differ |
| check box | `checkbox.png` | SYS.IXF `82b9b75b:c2d6e93a` | 104x13, 8 frames of 13x13 | (222, 70) "Musica" on, (222, 142) off, (223, 182) list | 0 px differ |
| radio button | `radio.png` (RGBA: the magenta key is transparent) | SYS.IXF `82b9b75b:0000000a` | 96x12, 8 frames of 12x12 | (17, 89) on, (17, 107) off | 0 px differ outside the key |
| OK button | `ok.png` | SYS.IXF `82b9b75b:a2defd9a` | 168x32, 4 frames of 42x32 | (432, 434) | 0 px differ |
| scroll bar | `scroll_up.png`, `_up_pressed`, `scroll_thumb.png`, `scroll_track.png`, `scroll_down.png`, `_down_pressed`, and the horizontal `scroll_left`, `_right`, `_hthumb`, `_htrack` (+ pressed) | SYS.IXF `82b9b75b:e2b99e01` | 192x16, 12 frames of 16x16, one file each | up (453, 178), thumb (453, 194), track 210..291, down (453, 292) | 0 px differ |

**Frame order** of a 4-frame button strip, observed in the running game with posted input (`verify/sc3ui3/states.py`,
`disabled.py`, every frame 0 px different from the grab): **0 disabled** (Musica unticked greys play and stop),
**1 normal**, **2 pressed** (mouse down), **3 hover**. The dropdown arrow keeps frame 1 under the mouse (no hover
change in the game) and shows frame 2 while pressed. The CodeView enum `cIGZWinBtn::tImageIdx` names 10 image slots
(`kUpOnNormal` .. `kDownOffHilite`, `cvdump_sc3u.txt` type 0x2f96). How ImageSetup maps a 4-frame strip onto them was
not read `[UNCERTAIN]`: the order above is the observed one.

**Check box and radio frames** (second owner list, 2026-11-19, observed the same way, 0 px differ each): 0 on, 1 off,
2 on + hover, 3 off + hover, 4 on + pressed, 5 off + pressed, 6 on + disabled (the music list's ticks with Musica
unticked), 7 off + disabled (by the pairing, not seen in Preferencias). The radio's 6 and 7 are by the same layout
`[UNCERTAIN]`: no disabled radio was found. **Scroll bar frames:** 0/1 left arrow normal/pressed, 2 horizontal thumb,
3 horizontal track, 4/5 right arrow, 6/7 up arrow, 8 vertical thumb, 9 vertical track (16 identical rows, tiled),
10/11 down arrow. The arrows show no hover change, and a held arrow scrolls the list (posted press). **OK:** 1 normal,
2 pressed, 3 hover observed, 0 disabled by the 4-frame order.

The slider is one bitmap: a left cap (column 0), 58 identical track columns, a right cap (column 59), then the knob.
The game draws the cap at the control's left, the track across, the knob at the value. The volume steps are one
bitmap too. The bitmaps carry no key colour: their background is the blue panel they sit on.

How sc3ui.css uses them: every `input[type=checkbox]` and `input[type=radio]` on every page is the game's strip
(`:checked`, `:hover`, `:active`, `:disabled` pick the frame, same 13 / 12 px footprint as before). Every scrolling box
gets the game's scroll bar through `::-webkit-scrollbar` (one arrow at each end, pressed frame while held, track tiled,
thumb exact at 16 px and with both ends kept when longer). Chrome draws a thumb at least 17 px long, one row more than
the game's 16. Browsers without `::-webkit-scrollbar` get `scrollbar-color` in the game's colours. An element with its
own `scrollbar-width` (the gallery and guide's thin tab strip) keeps the browser's bar. `button.ui-ok` is the OK button.
`button.ui-close`, `button.ui-play`, `button.ui-stop`, `button.ui-ok` show one frame of the strip
(`:disabled` 0, normal 1, `:active` 2, `:hover` 3). `select` draws its groove with background layers so the arrow sits
outside the box, as in the game. `input[type=range]` paints the track with `border-image` (1 px caps, middle stretched)
and the knob as the thumb. `.ui-volume` is the steps. `image-rendering: pixelated`: exact at `--ui-scale` 1, at 1.25
every fourth game pixel is drawn twice. The importer carries them inline as data: URIs (`sync_css.py`).

Replica (`replica_diff.py`, ELEMENTS), share of pixels identical to the game, main -> sc3ui3: close X 1.9% -> 89.4%,
play 10.2% -> 100%, stop 10.0% -> 100%, sliders 60.2% -> 100%, dropdown arrow 0.4% -> 100%, volume steps 46.0% -> 100%.
Second list: check box 49.7% / 65.7% / 8.9% (on / off / list) -> 100%, radio 33.3% / 43.1% -> 100%, scroll up 10.2% ->
100%, thumb 4.7% -> 100%, track 93.8% -> 98.9% (Chrome's 17 px thumb covers one track row), down 2.0% -> 100%,
OK 26.4% -> 100%.

## Dropdown text (sc3ui3)

The dropdown draws SYSTEM9 (`ctrlmgr_setup` slot 0 / 0xb, fontmap IoU 1.000), navy `#31347b`, ink from 3 px inside the
box. In the old replica the arrow sat inside the box and cut the text ("RTX" lost). Now it sits outside.
Free face for that role, scored on the dropdown's own strings (`fontscore.py --el combo`, 2,112 configurations):
Istok Web stays the best free family. 13.0 px with -1.06 px spacing scores 0.693, the current 11.5 px with -0.34 px
0.673. The gain comes from the digit-heavy strings and costs 1 px of spacing per letter, so `--ui-type-row` keeps
11.5 px (the budget rows chose it). With the game folder chosen, the importer draws it with SYSTEM9 itself (below).

## Game fonts at run time (importer only, sc3ui3)

Since gamefont (2026-11-19d) this is the fallback: the published fonts below come first, and `useGame()` builds from the
player's folder only when they did not load.

Owner call: the game's font, but never published. `re/tools/bldimport/sc3font.js` reads the FBF files of the player's
own game folder (`Apps\Res\Text\<lang>\`, all 7 language folders hold byte-identical fonts, file name case varies)
when the importer is given that folder, builds TrueType fonts in memory and switches the `--ui-type-*` tokens to them.
Without a game folder the page keeps the free fonts. Nothing is stored.

- One font pixel = 64 units at 1024 per em, so 16 px draws one font pixel per CSS px. Ink pixels become rectangles,
  partial coverage (TITLE9, TITLE12, SERIF17) a centred full-height bar whose width is the coverage in 1/64 steps.
  Baseline = the row under 'H' (MAIN9 12, MAIN10 13, SYSTEM9 11, TITLE9 15, TITLE12 19, SERIF17 23 px from the cell top).
- Chrome on Windows draws ordinary web fonts with DirectWrite, which spreads every pixel into its neighbours (measured:
  ink 0.882, 0.098 into each neighbour, also with a gasp table that asks for no anti-aliasing). So every glyph is also a
  COLR v1 glyph painted in the text colour (palette index 0xFFFF): Chrome then draws it through its own FreeType
  rasteriser, whose coverage of a pixel-aligned shape is exact, and CSS `color` still applies.
- Squares of area c do not draw coverage c on that path (a curve with gaps: 0.36, then 0.56, then 0.78). Bars do,
  linearly (width k/64 -> coverage k/64). `calibrate()` measures this in a canvas at run time and picks the width per
  level, so a browser with another curve is corrected too.
- The font pixel snaps to whole device pixels (`--ui-gpx`): at `--ui-scale` 1.25 on a 100% screen the text is the
  game's own size, at 200% two device pixels per font pixel. Crisp also needs the text origin on a whole pixel.

`webtest/sc3font_check.py` (a step of `run_all.sh`): 12 of 12. MAIN9, MAIN10, SYSTEM9: 0 pixels differ from fbf.py's
rendering of the same strings (max coverage error 0.000). TITLE9, TITLE12, SERIF17: coverage within 0.012 on every
pixel. Navy text: every ink pixel exactly `#31347b`. The replica with the game fonts
(`replica_prefs.html?gamefont=1&game=<install URL>`): title, labels, radio labels, list rows and dropdown text carry the
game's ink pixel for pixel (aligned IoU 1.000, ink ratio 1.00), placed within 1 px by the stylesheet's line flow.

## Game fonts and scale (gamefont, round 2026-11-19d)

Owner, 2026-11-19: "Use it on every page": web fonts built from the game's FBF files are published in `docs/` (risk
accepted). The .FBF files themselves never enter the repo. Also from the owner the same day: light theme only. The dark
variant, its tokens, `data-theme` / `?theme=` and the importer's Theme button are gone, and `:root` keeps
`color-scheme: light`.

### The files (`docs/assets/fonts/`, `re/tools/sc3ui/build_fonts.mjs`)

`node re/tools/sc3ui/build_fonts.mjs --game <install>` runs sc3font.js's own `parseFBF` + `buildTTF` in node (the same
code path as the importer's run-time builder) and writes one WOFF2 per font. The partial-pixel bar widths of the
anti-aliased fonts come from Chrome's measured coverage curve, `re/tools/sc3ui/font_calibration.json` (`--measure`
re-measures it in headless Chrome with `font_calib.html`, Chrome 157). `--check` rebuilds and compares (a `run_all.sh`
step). All seven languages carry byte-identical FBF files, so one build serves every install.

| file | bytes (TTF) | glyphs | line / baseline px | kind | family in sc3ui.css | token |
|---|---|---|---|---|---|---|
| MAIN9.woff2 | 5,692 (39,276) | 220 | 14 / 12 | 1-bit | "SC3 Main", "SC3 Text" bold | `--ui-type-ui`, `<b>` in prose |
| SYSTEM9.woff2 | 5,016 (34,492) | 220 | 14 / 11 | 1-bit | "SC3 Text" regular, "SC3 System" | `--ui-type-prose`, `--ui-type-row`, `code` |
| MAIN10.woff2 | 5,784 (40,840) | 220 | 16 / 13 | 1-bit | "SC3 Name" | `--ui-type-name` |
| TITLE9.woff2 | 17,452 (172,656) | 220 | 18 / 14 | 15 levels | "SC3 Button" | `--ui-type-btn` |
| TITLE12.woff2 | 21,956 (201,544) | 220 | 23 / 18 | 15 levels | "SC3 Title" | `--ui-type-title` |
| SERIF17.woff2 | 29,712 (355,272) | 220 | 29 / 23 | 15 levels | "SC3 Serif" | none yet (main menu) |

85,612 bytes for all six, against 843,080 as TTF. A page downloads only the faces it draws. Format: WOFF2 with the null
transform on every table (glyf and loca as built, one brotli stream from node's own zlib, no dependency). It carries the
COLR v1 / CPAL tables unchanged, and those make Chrome draw the glyphs exactly.

Browsers: **Chrome 157 and Edge 157** (both tested): every glyph is a COLR v1 colour glyph in the text colour,
rasterised by Chrome's own FreeType path, so 1-bit fonts are pixel-exact and anti-aliased ones within 0.012 coverage
(`sc3font_check.py`, published pass, 9 of 9 strings in each browser). **Firefox** (COLR v1 since version 107) and
**Safari** (no COLR v1: it draws the plain outlines under the colour glyphs, the same rectangles) are not installed on
this PC, so they are not measured `[UNCERTAIN]`. A browser that cannot load the files falls back to the free fonts.

Glyph coverage: 220 code points per font, Windows-1252 (the game's own byte table). Every character the three pages use
is in all six fonts (`verify/gamefont/coverage.py`: the page sources are ASCII plus `‹ ›`, the gallery's lightbox arrows,
which every font has). A character outside Windows-1252 would draw in the free font of the same token.

### How sc3ui.css uses them

- One font pixel = 64 units of a 1024-unit em. Each `@font-face` has a `size-adjust` so that the token's measured free
  font size (12.5 / 11.5 / 13.5 / 16 / 11 game px) draws exactly one font pixel per `--u`: 128%, 139.130435%,
  118.518519%, 100%, 145.454546%. **Round the percentage up**: 139.1304% gives 15.99999 px, the baseline lands 1 px
  higher and 210 of 2,870 pixels change (measured). Weights are declared as the full range, so nothing is synthesised.
- "SC3 Text" is SYSTEM9 (the game's regular face, 1 px stems) at weights 1..549 and MAIN9 (its bold face, the same 9 px
  caps) at 550..1000: running text reads in the regular face and `<b>` / `<strong>` in the bold one.
- "SC3 Main" adds `ascent-override: 75%; descent-override: 25%` (12 + 4 font px): in an 18 px row the game draws a
  MAIN9 cell 1 px under the row top, and with these metrics the page does too. List rows (2 px in the game) get
  `padding-top: 2u; line-height: 16u`, the blue strip text sits 7 px in and 2 px down, the dropdown has
  `line-height: 18u`.
- Letter-spacing tokens are 0: the game's advances are in the fonts. The free fonts keep their fitted sizes but not their
  fitted spacing (they are a fallback only).
- `code` / `kbd` / `samp` and `.ui-log` use SYSTEM9 (the game has no monospace face). `--ui-mono` stays only for the
  importer's rules editor (JSON). Page-level `font-size` overrides of game text were removed (importer badges 10.5, guide
  download button 13, gallery arrows 14): a game font at any size other than its token's draws at a fraction of a pixel.

### Scale: `--u` snapped to whole device pixels

A pixel font is crisp only when one font pixel covers a whole number of screen pixels. `--ui-scale` is the wanted size
of a game pixel in CSS px, and `--u = max(1, round(--ui-scale x dpr)) / dpr` px, with `--ui-dpr` set by
`min-resolution` media queries at the common ratios (0.5 to 4, browser zoom included, the nearest one in between).
Browsers without CSS `round()` keep the unsnapped size. The bitmaps (`image-rendering: pixelated`) gain the same: at
1.25 on a 100% screen they used to draw every fourth game pixel twice, now none.

Measured (`verify/gamefont/scale/scale_check.py`: game strings at each `--ui-scale` and device scale, compared with the
FBF rendering blown up by whole pixels. "Full ink" = share of ink pixels drawn at full strength). Screen px per game px,
CSS px in brackets:

| --ui-scale | 100% screen | 125% | 150% | 200% | phone (3x) | unsnapped full ink, 100% / 150% / phone |
|---|---|---|---|---|---|---|
| 1 | 1 (1) | 1 (0.8) | 2 (1.33) | 2 (1) | 3 (1) | 1.00 / 0.53 / 1.00 |
| **1.25** | **1 (1)** | **2 (1.6)** | **2 (1.33)** | **3 (1.5)** | **4 (1.33)** | 0.36 / 0.43 / 0.70 |
| 1.5 | 2 (2) | 2 (1.6) | 2 (1.33) | 3 (1.5) | 5 (1.67) | 0.53 / 0.57 / 0.81 |
| 2 | 2 (2) | 3 (2.4) | 3 (2) | 4 (2) | 6 (2) | 1.00 / 1.00 / 1.00 |

Snapped, all 20 combinations are exact whole-pixel blow-ups of the game's glyphs (3 of 3 strings each, full ink 1.00).
Unsnapped, the fractional ones blur: at 1.25 on a 100% screen only 36% of the ink stays solid.

**Pick: `--ui-scale` 1.25 on every page. The replica and the font tests use 1.** On a 100% desktop 1.25 is the game's
own size, one screen pixel per game pixel: crisp, and the only crisp step below 2x. 2x on a 100% screen doubles
every length (body caps 18 px, title bars 56 px), so a 1280 px window shows a quarter of the area of text it shows at
1x. On 125% and 150% laptop screens 1.25 lands on 2 screen px (1.6 and 1.33 CSS
px), close to the old sizes, and on a 390 px phone on 4 device px (1.33 CSS px): caps 12 CSS px. 1.5 on a phone (5 px)
gives caps 15 CSS px, larger than the page text a phone shows elsewhere.
A reader who wants larger text on a 100% screen uses browser zoom: at 125% zoom the page snaps to 2 screen px per game
pixel and stays crisp (`verify/gamefont/owner_shots/scale_desktop_1x_vs_2x.jpg`, `scale_phone_4_scales.jpg`).

### Smooth outlines for TITLE9 / TITLE12 (smoothfont, round 2026-11-20f, built, not published)

Owner, 2026-11-20: "can you make the comic sans font less pixelated?". At 150% and 200% screens every game pixel of the
pixel build shows as a block (2 and 3 device px), and the partial-coverage bars show as thin stripes.
`sc3font.js` `smoothContours` traces each glyph instead: coverage upsampled 8 x 8 with a Catmull-Rom kernel, cut at one
iso level per font (picked so the outlines' area equals the font's total coverage: TITLE9 0.491, TITLE12 0.507),
Douglas-Peucker at 0.07 px, drawn as a TrueType quadratic B-spline (vertices off-curve, turns past 57 degrees kept as
on-curve corners). Advances, cmap, ascent and descent are identical to the pixel build (0 of 220 advances differ in all
six fonts), so layout does not move. Each glyph keeps its COLR v1 layer: without it Chrome draws the outlines with
ClearType colour fringes (max |R-B| 184 of 255, measured), with it grayscale like the game.

At 100% against the game's coverage (fbf.py, the game's draw): mean coverage error 0.064 to 0.084, ink mass 0.97 to
1.01, IoU at 0.5 0.90 to 0.95 (the pixel build: 0.003, 1.00, 1.00). So the pixel build stays the exact one at 100%,
the smooth one wins at 150% and up. 1-bit fonts (MAIN9, MAIN10, SYSTEM9) trace too, but they are drawn on the pixel
grid (stair-step diagonals), so tracing only rounds the corners: not recommended.

**The switch:** `SMOOTH` in `re/tools/sc3ui/build_fonts.mjs` (published files) and `SMOOTH` in `sc3font.js` (run-time
fallback), both `[]` today. Owner pick -> `['TITLE9', 'TITLE12']` in both, re-run `build_fonts.mjs --game <install>`,
then `sync_css.py` (+ `--publish`). sc3ui.css does not change (same file names and metrics). `sc3font_check.py`'s two
published TITLE checks (coverage within 0.012) then need a smooth tolerance. WOFF2 sizes: TITLE9 17,452 -> 21,300,
TITLE12 21,956 -> 26,376 bytes. Pictures and numbers: `verify/smoothfont/RESULTS.md` (local).

### Proof: the replica with the published fonts against R3

`replica_diff.py` + `verify/gamefont/text_pixels.py`, the 16 labels of Preferencias, the replica at `--ui-scale` 1:

| | main (free fonts) | gamefont |
|---|---|---|
| text ink IoU, all labels | 0.291 | **1.000** |
| text pixels with identical RGB | 0.123 | 0.974 (the anti-aliased title's edge pixels) |
| labels with top and bottom within 1 px | 15 of 16 (5 at 0 px) | 16 of 16, all at 0 px (one by the replica's own rule for its 17 px bottom rows) |
| ink mass ours / game | 0.91 to 1.14 | 1.000 (title 0.978) |
| element "dropdown box", identical pixels | 87.8% | 99.8% |
| 1 px lines within 1 px | 30 of 30 | 30 of 30 |

## Rules for new pages

0. Lengths in game pixels: `calc(N * var(--u))`, fonts from the `--ui-type-*` tokens, so a page follows `--ui-scale`.
1. Link `docs/assets/sc3ui.css` with a relative path, or inline it between the `sc3ui.css begin/end` markers when the
   page must work outside `docs/` (the importer: `re/tools/bldimport/sync_css.py`).
2. Build with the components (`ui-window`, `ui-titlebar`, `ui-panel`, `ui-group`, `ui-btn`, `ui-plate`, `ui-chip`,
   `ui-infobar`, `ui-ticker`, `ui-field`, `ui-progress`, `ui-log`, `ui-table`, `ui-card`, `ui-lightbox`, `ui-close`,
   `ui-play`, `ui-stop`, `ui-volume`), and only the tokens for colours. The only game bitmaps are the ones in
   `docs/assets/sc3ui/` (Game bitmaps above) and the game fonts the ones in `docs/assets/fonts/` (Game fonts and
   scale above). No other game icons or UI art, never a raw .FBF file.
2b. Text only through the `--ui-type-*` tokens, without `font-size` overrides: a game font at another size draws at a
   fraction of a pixel and blurs. Light theme only: no dark rules, no theme switch.
3. Check phone width (390 px): 16 px gutters, no sideways scroll.
