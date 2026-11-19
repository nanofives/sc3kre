# STATUS sc3ui2 (round 2026-11-18g, sc3ui precision pass)

## goal
Measured match of font, spacing and background for docs/assets/sc3ui.css, proven by replica_prefs.html diffed
against the game's Preferencias dialog at native size, then re-applied to gallery, building guide, importer.

## verdict
Done, all targets met. Results: verify/sc3ui2/RESULTS.md, tables: re/analysis/UI_STYLE.md "Precision pass".
- FBF format decoded (re/tools/sc3ui/fbf.py). Font map by exact glyph match: titles TITLE12, labels / lists / info bar /
  ticker MAIN9, buttons TITLE9, budget rows + combo SYSTEM9, query name MAIN10, main menu SERIF17.
- Fonts by score against those glyphs (91 free families): Comic Relief (titles 400 16 px, buttons 700 11 px), Istok Web
  (labels 700 12.5 px, rows 400 11.5 px, name 700 13.5 px). Replaces Comic Neue + Arimo.
- Cloud: real tile = SYS.IXF {0x82b9b75b, 0xe2b14588} 256x256. Ours: 500-byte feTurbulence SVG, same mean/spread/colour
  axis, octave shares 0.914/0.054/0.024 vs 0.912/0.047/0.026, mean-colour dE 0.01.
- Replica at --ui-scale 1: frame/panels mean dE max 0.69 (target 3), edges 29/30 within 1 px (30th = game-only cut),
  15/16 labels within 1 px top and bottom, ink 0.91..0.98.
- Pages on --ui-scale 1.25, regenerated through their generators. Text/scripts/ids/classes/markup unchanged.
  run_all.sh 8/8 PASS, check_roundtrip.py 8/8 PASS.

## built
- re/tools/sc3ui/fbf.py, fontscore.py, texstats.py, cloudgen.py, replica_prefs.html, replica_diff.py
- docs/assets/sc3ui.css rewritten on --ui-scale (1 = native px, pages 1.25), type tokens, cloud SVG
- page styles of gallery, guide, importer moved onto the tokens

## proven game-side vs static only
References grabbed from a stock windowed game in dev/sc3ui2/tree (-Stock = sc3winonly only: no UI scale). PIDs 1264 and
19824, started and stopped by this session. The replica proof is headless Chrome against those grabs.

## blocked on
nothing

## files owned
Repo (dev/sc3ui2/wt):
- docs/assets/sc3ui.css
- docs/gallery/index.html (regenerated)
- docs/buildings/index.html (regenerated)
- docs/buildings/importer/index.html (sync_css.py --publish)
- re/tools/bldimport/classifier.html
- re/analysis/UI_STYLE.md
- re/tools/sc3ui/fbf.py, fontscore.py, texstats.py, cloudgen.py, replica_prefs.html, replica_diff.py (new, under the
  ignored /re/tools/*: need `git add -f`)
Local generators (MAIN, gitignored, edited in place; before copies in verify/sc3ui2/*.before.html):
- verify/showcase/site/gallery_page.html
- verify/bldpack/work/guide_template.html
Results (MAIN): verify/sc3ui2/RESULTS.md (tracked), owner_shots/, logs, local scripts (shots.py, replica_shots.py,
textcheck.py, fontmap.py, textpos.py, scan.py, rects.py, fs_viz.py)

## game-harness need
none now (game closed)

## asks of other sessions
- Rebuild the sample pack zip from docs/buildings/importer after the merge if it should carry the new look (pending since sc3ui).
