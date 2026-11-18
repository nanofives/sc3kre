# STATUS sc3ui (round 2026-11-18f, game UI CSS)

## goal
Measure SC3U's UI look into re/analysis/UI_STYLE.md, build docs/assets/sc3ui.css, restyle gallery, building guide
and importer with it (functions/ids/classes kept), regenerate through the generators, tests pass, before/after shots.

## verdict
Done. run_all.sh 8 of 8 PASS, check_roundtrip.py 8 of 8 PASS. One shared CSS-only stylesheet from colours measured in the game (Preferencias dialog,
city view info bar and toolbar, Graficas and Indagar windows). Gallery and guide link it (`../assets/sc3ui.css`), the
importer carries an inlined copy kept in sync by `re/tools/bldimport/sync_css.py`. Page text, ids, classes and
scripts unchanged.

## built
- docs/assets/sc3ui.css (tokens, components, dark variant)
- re/analysis/UI_STYLE.md (measured palette, bevels, fonts, rules for new pages)
- gallery, guide, importer restyled and regenerated, importer recopied to docs/buildings/importer/
- verify/sc3ui/shots.py (before/after headless shots, desktop + true 390 px phone)

## proven game-side vs static only
Colours measured off game pixels (sc3io grabs of a dev-tree game, PID 15772, started and stopped by this session).
Pages checked in headless Chrome (light, dark, phone, lightbox, importer opened outside the repo).

## blocked on
nothing

## files owned
Repo (dev/sc3ui/wt):
- docs/assets/sc3ui.css (new)
- re/analysis/UI_STYLE.md (new)
- re/tools/bldimport/sync_css.py (new, gitignored path: needs `git add -f`)
- re/tools/bldimport/classifier.html
- docs/buildings/importer/index.html
- docs/buildings/index.html
- docs/gallery/index.html
Local generators (MAIN, gitignored, edited in place):
- verify/showcase/site/gallery_page.html, verify/showcase/site/gallery_build.py (`--site-only`, CSS copy to site/assets/)
- verify/bldpack/work/guide_template.html
Results: verify/sc3ui/RESULTS.md, owner_shots/, shots.py, run_all.log, check_roundtrip.log

## game-harness need
none now (one windowed run done, game closed)

## asks of other sessions
- Rebuild the sample pack zip from docs/buildings/importer after the merge if it should carry the new look
  (verify/bldpack/work/make_zip.py still points at dev/bldpack/wt).
