# SC3U UI style, measured (sc3ui round 2026-11-18f, precision pass sc3ui2 round 2026-11-18g)

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
scales it with `--ui-scale`. Dark theme: the same noise mapped onto the dark navy (designed, the game has no dark theme).

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

## Dark variant

The game has no dark theme. The dark tokens reuse the game's own darker colours: page `#10142e` and panels `#1c2152`
(between the button shadow `#182039` and the text navy `#31347b`), lines `#4a599c` and `#636dc6`, text `#dedfff`, labels
`#adb6ff`, title bars and plates stay `#7b92ff` with navy text, ticker stays black and yellow.

## Rules for new pages

0. Lengths in game pixels: `calc(N * var(--u))`, fonts from the `--ui-type-*` tokens, so a page follows `--ui-scale`.
1. Link `docs/assets/sc3ui.css` with a relative path, or inline it between the `sc3ui.css begin/end` markers when the
   page must work outside `docs/` (the importer: `re/tools/bldimport/sync_css.py`).
2. Build with the components (`ui-window`, `ui-titlebar`, `ui-panel`, `ui-group`, `ui-btn`, `ui-plate`, `ui-chip`,
   `ui-infobar`, `ui-ticker`, `ui-field`, `ui-progress`, `ui-log`, `ui-table`, `ui-card`, `ui-lightbox`), and only the
   tokens for colours. No game bitmaps, icons or extracted UI art: everything is CSS.
3. Check phone width (390 px): 16 px gutters, no sideways scroll.
