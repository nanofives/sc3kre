# STATUS smoothfont (round 2026-11-20f)

## goal
Owner: "can you make the comic sans font less pixelated?" Smooth outlines for TITLE9 ("SC3 Button") and TITLE12
("SC3 Title"), traced from the game's coverage, same metrics, one switch, nothing published.

## verdict
Done. Built, measured, switchable, not published (no change under docs/). Recommendation for the owner: switch
TITLE9 + TITLE12, keep the 1-bit fonts as pixels. Detail: `verify/smoothfont/RESULTS.md` (local).

- Layout identical: 0 of 220 advances differ, cmap / ascent / descent identical, page pictures line up.
- At 100% against the game: mean coverage error 0.064 to 0.084, ink mass 0.97 to 1.01 (pixel build 0.003, 1.00).
- 150% / 200%: no blocks, no stripes (`owner_shots/titles_buttons_150.png`, `_200.png`, `page_*.png`).
- COLR kept on smooth fonts: plain TrueType gets ClearType fringes (max |R-B| 184) in Chrome on Windows.
- 1-bit fonts trace too but only get rounded stair-step corners. Not recommended.

## built
- `sc3font.js`: `smoothContours` / `smoothLevel` / `isoLoops` (Catmull-Rom x8, mass-kept iso level, marching squares,
  Douglas-Peucker, quadratic B-spline), `writeTTF` takes curve contours and `opts.colr`, `SMOOTH` list + `opts.smooth`
  in `load()`.
- `build_fonts.mjs`: `SMOOTH` list (THE switch, `[]`), `--smooth <list|all|none>`, `--no-colr`.
- `UI_STYLE.md`: section "Smooth outlines for TITLE9 / TITLE12".

## proven game-side vs static only
Static (web fonts in headless Chrome 157 against fbf.py coverage and the sc3ui2 game grabs). No game run needed.
`build_fonts.mjs --check` with the default list: 6 of 6 identical. `sc3font_check.py`: 22 of 22.

## blocked on
Nothing. Owner pick: smooth TITLE9 + TITLE12 or keep pixels.

## to switch (after the owner picks)
`SMOOTH = ['TITLE9', 'TITLE12']` in both `build_fonts.mjs` and `sc3font.js`, `node re/tools/sc3ui/build_fonts.mjs
--game <install>`, `py -3.12 re/tools/bldimport/sync_css.py --publish`, and give `sc3font_check.py`'s two published
TITLE checks a smooth tolerance.

## files owned (worktree dev/smoothfont/wt, branch child/smoothfont)
- `re/tools/bldimport/sc3font.js`
- `re/tools/sc3ui/build_fonts.mjs`
- `re/analysis/UI_STYLE.md`
- `re/sessions/STATUS_smoothfont.md` (this file, in MAIN)

## game-harness need
None.

## asks of other sessions
None.
