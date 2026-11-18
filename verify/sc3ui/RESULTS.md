# sc3ui results (round 2026-11-18f): the game's UI look for every page

## Verdict

Done. The gallery, the building guide and the importer now use one shared stylesheet, `docs/assets/sc3ui.css`, built
from colours measured off the running game (`re/analysis/UI_STYLE.md`). CSS only, no game bitmaps, icons or art in the
repo. Page text, every DOM id and class, and every script are unchanged (checked by diffing the visible text, the
`<script>` blocks, the id list and the class list against main: the only addition is `id="sc3ui"` on the importer's
inlined style block, plus `ui-*` classes on static markup). Importer tests: run_all.sh 8 of 8 steps PASS, check_roundtrip.py
8 of 8 PASS.

## What the game looks like (measured, S3 = Preferencias dialog in a dev-tree game)

- Title bars: flat `#7b92ff`, text `#dedfff` in a thin hand-lettered face (free match: Comic Neue).
- Window frame: grey edge, 1 px white, 5 px `#c6c7ff`, 1 px `#7b8aff`, face `#dedfff`. Square corners.
- Group boxes `#dedfff` with a `#7b8aff` line, headings `#7b7db5` bold. Body text `#31347b` (Arial-like, free match Arimo).
- Pill buttons: `#dedbff` face, white top highlight, dark navy outline, a dark drop shadow down and right, on a blue plate.
- Clouded window body `#d8dcf8` with lighter and darker clouds (layered radial gradients here).
- Info bar: bevel, black ticker with `#fffb00` text, `#bdc3ff` fields with `#18288c` text.
- List selection solid `#0000ff` with white text.

Full table with the pixel each value was read from: `re/analysis/UI_STYLE.md`.

## How each page uses it

| page | how it loads the CSS | generator |
|---|---|---|
| `docs/gallery/index.html` | `<link href="../assets/sc3ui.css">` (works from file:// inside docs/) | `verify/showcase/site/gallery_page.html` + `gallery_build.py` (new `--site-only` flag: page only, leaves the Simtropolis post files alone; copies the CSS to `site/assets/` so `gallery_site/index.html` opens from disk too) |
| `docs/buildings/index.html` | `<link href="../assets/sc3ui.css">` | `verify/bldpack/work/guide_template.html` + `make_docs.py` (unchanged script; README.txt it rewrites came out byte-identical) |
| `re/tools/bldimport/classifier.html` and `docs/buildings/importer/index.html` | inlined between `sc3ui.css begin/end` markers, so the copy in the sample pack zip needs nothing from docs/ | `re/tools/bldimport/sync_css.py` (new): refreshes the copy, `--check` exits 1 when out of sync, `--publish` also copies classifier.html + bldweb.js to docs/buildings/importer/ |

Fonts load from Google Fonts through an `@import` at the top of sc3ui.css. Offline, the stacks fall back to Comic Sans MS
and Arial, which are the closest local faces on Windows. The importer's 3D view still reads `--canvas` and `--accent`
as plain colours (now `#d8dcf8` / `#0000ff`, dark `#1c2152` / `#7b92ff`). The theme button and `?theme=` still work.

Components in sc3ui.css: page frame (`ui-wrap`), window (`ui-window`, `ui-titlebar`, `ui-close`), panel / group box /
blue strip, pill buttons (normal, hover, pressed, disabled, primary), toolbar-style chips, info bar + ticker + fields,
cards, form fields (text, number, select with a blue arrow box, check box and radio drawn in CSS), progress bar, log box
(ticker colours), tables (blue header plate, lavender rows, blue row hover), lightbox, note. Dark variant built from the
game's darker colours (UI_STYLE.md, Dark variant).

Two small layout fixes came with the restyle: the importer's progress row now hides while idle (`#prog[hidden]`; the old
`display:flex` overrode `hidden`, so an empty bar showed), and the guide's picture pairs no longer stretch a short card
to the height of a tall one (`.pair { align-items: start }`).

## Tests

- `test-slot bash re/tools/bldimport/webtest/run_all.sh verify/sc3ui/webtest_work dev/sc3ui/tree stage/kits`:
  8 of 8 steps PASS. Log: `verify/sc3ui/run_all.log`.
- `check_roundtrip.py`: 8 of 8 PASS (log `verify/sc3ui/check_roundtrip.log`).
- `sync_css.py --check`: in sync. The docs/ importer copy is byte-identical to classifier.html.
- The importer opened from a folder outside the repo (index.html + bldweb.js only, as in the zip): styled, no missing
  files.

## Pictures (`owner_shots/`)

Headless Chrome, light scheme unless the name says dark. Desktop = 1280 px window scaled to 640 wide. Phone = the page
in a true 390 px iframe.

- `before_*` / `after_*` for `gallery`, `guide`, `importer`, `gallery_dark`, `importer_dark`, each `_desk.jpg` and
  `_phone.jpg`.
- `after_gallery_lightbox_light_desk.jpg`, `after_gallery_lightbox_dark_desk.jpg`: the picture viewer open.
- Game reference grabs used for the measurements (local only): `verify/sc3ui/g1_city.png`, `g2_flyout.png`,
  `g3_dialog.png`, zoom crops `zoom_*.png`. Script for the page shots: `verify/sc3ui/shots.py before|after [page]`.

## Notes for the orchestrator

- `re/tools/bldimport/sync_css.py` is hidden by the deny-by-default `.gitignore` (`/re/tools/*`): it needs `git add -f`.
- `verify/bldpack/work/make_zip.py` still reads the importer from `dev/bldpack/wt/docs/buildings/importer`. The released
  sample pack zip carries the old look until it is rebuilt from `docs/buildings/importer` after this merge.
- Before copies of the two local generators and templates: `verify/sc3ui/*.before.*`.
