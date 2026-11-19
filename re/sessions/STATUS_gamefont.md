# STATUS gamefont (round 2026-11-19d: the game's font on every page, light theme only)

## goal
Web fonts built once from the game's FBF files (sc3font.js builder), in docs/assets/fonts/, used by sc3ui.css on every
page with the free fonts as fallback. Pick --ui-scale for crisp pixel text. Importer keeps working from disk. Extra
owner instruction (via orchestrator): light theme only, dark variant and Theme button removed everywhere.

## verdict
Done. Results: verify/gamefont/RESULTS.md. run_all.sh 16 of 16 (log verify/gamefont/webtest/run_all.log).
- 6 WOFF2 files, 85,612 bytes, built by re/tools/sc3ui/build_fonts.mjs (same parseFBF/buildTTF as sc3font.js, Chrome
  coverage curve kept in font_calibration.json, --check reproduces byte for byte).
- Chrome 157 + Edge 157: published fonts 0 px differ on the 1-bit fonts, within 0.012 coverage on the anti-aliased ones.
  Firefox / Safari not installed here, not measured.
- Replica vs the game grab: text ink IoU 0.291 -> 1.000, all 16 labels at 0 px.
- --u snapped to whole device pixels: 20 of 20 (scale x screen) combinations exact. Pick 1.25 everywhere (100% screen =
  the game's own size, 125/150% = 2 px, phone 3x = 4 px), 1 for replica/tests.
- Importer: fonts inlined as data: URIs by sync_css.py, run-time builder only as fallback. Published.
- Light only: dark tokens/rules, data-theme, ?theme=, Theme button + handler gone, color-scheme light, checked under OS
  dark mode.

## built
docs/assets/fonts/*.woff2, sc3ui.css (@font-face, tokens, snapped --u, light only, list/strip/dropdown text offsets),
build_fonts.mjs, font_calib.html, font_calibration.json, sync_css.py (fonts inline), sc3font.js (sideFrom,
publishedLoaded, fallback), sc3font_test.html (?published=1), sc3font_check.py (published pass, SC3_BROWSER),
webtest/fonts_inline.mjs (new), run_all.sh (2 new steps), classifier.html (Theme removed, badges/log font, gameFonts
note), replica_prefs.html (17 px rows), UI_STYLE.md ("Game fonts and scale", dark section removed, rules).
Gallery and guide rebuilt, sync_css.py --publish done.

## proven game-side vs static only
No game run (the sc3ui2 grab R3 reused). Browser-side only: replica diff, sc3font_check, scale_check, page shots.

## blocked on
nothing

## files owned
In dev/gamefont/wt (git add; the ones marked -f are hidden by the deny-by-default .gitignore):
- docs/assets/sc3ui.css
- docs/assets/fonts/MAIN9.woff2, MAIN10.woff2, SYSTEM9.woff2, TITLE9.woff2, TITLE12.woff2, SERIF17.woff2 (new)
- docs/buildings/index.html, docs/buildings/importer/index.html, docs/buildings/importer/sc3font.js
- docs/gallery/index.html
- re/analysis/UI_STYLE.md
- re/tools/bldimport/classifier.html, sc3font.js, sc3font_test.html, sync_css.py
- re/tools/bldimport/webtest/run_all.sh, sc3font_check.py
- re/tools/bldimport/webtest/fonts_inline.mjs (new, -f)
- re/tools/sc3ui/replica_prefs.html
- re/tools/sc3ui/build_fonts.mjs, font_calib.html, font_calibration.json (new, -f)
MAIN in place (gitignored verify/): verify/showcase/site/gallery_page.html, gallery_build.py (copies assets/fonts too),
verify/bldpack/work/guide_template.html (backups in verify/gamefont/backup/). verify/gamefont/ (results, scripts, shots).
re/sessions/STATUS_gamefont.md.

## game-harness need
none

## asks of other sessions
none
