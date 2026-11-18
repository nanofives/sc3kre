# SC3U UI style, measured (sc3ui, round 2026-11-18f)

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
| `--ui-lav-250` | `#d8dcf8` | S4 body (470..630, 200..370), most common colour; S5 body | clouded window body, base colour |
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
- **Window body** (S4, S5): a soft clouded texture, base `#d8dcf8`, clouds `#e0e4f8`-`#f0f4f8` and `#c8d0f8`-`#b8c0f8`.
  Recreated with layered radial gradients, no bitmap.
- **Plot area** (S4): horizontal bands alternating `#d8dcf8` / `#e0e4f8`, frame `#7b92ff`.
- **Picture frame** (S5): 1 px `#7b92ff` box round the building picture.
- **Lists**: face `#dedfff`, rows 18 px, selection solid `#0000ff` with white text, scroll bar arrows on `#7b92ff`.

## Fonts

| game | free match (Google Fonts) | why |
|---|---|---|
| Title bar text (Z1, Z2): thin hand-lettered sans, upright, `#dedfff` | **Comic Neue** 400 | same single-stroke rounded hand-lettered letter shapes, free (OFL) |
| Labels, buttons, list rows, info bar (S3, Z3): Arial-like grotesque, labels and buttons bold, about 12-13 px at 800x600 | **Arimo** 400/700 | metric-compatible with Arial, free (Apache 2.0) |

Fallback stacks: `"Comic Neue", "Comic Sans MS", "Chalkboard SE", cursive` and `Arimo, Arial, "Liberation Sans",
Helvetica, sans-serif`, so a page opened offline from disk still looks right on Windows.

## Dark variant

The game has no dark theme. The dark tokens reuse the game's own darker colours: page `#10142e` and panels `#1c2152`
(between the button shadow `#182039` and the text navy `#31347b`), lines `#4a599c` and `#636dc6`, text `#dedfff`, labels
`#adb6ff`, title bars and plates stay `#7b92ff` with navy text, ticker stays black and yellow.

## Rules for new pages

1. Link `docs/assets/sc3ui.css` with a relative path, or inline it between the `sc3ui.css begin/end` markers when the
   page must work outside `docs/` (the importer: `re/tools/bldimport/sync_css.py`).
2. Build with the components (`ui-window`, `ui-titlebar`, `ui-panel`, `ui-group`, `ui-btn`, `ui-plate`, `ui-chip`,
   `ui-infobar`, `ui-ticker`, `ui-field`, `ui-progress`, `ui-log`, `ui-table`, `ui-card`, `ui-lightbox`), and only the
   tokens for colours. No game bitmaps, icons or extracted UI art: everything is CSS.
3. Check phone width (390 px): 16 px gutters, no sideways scroll.
