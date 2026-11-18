# Round 2026-11-18f: the game's UI look for every page we publish

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main 32e77f6+.

## Owner (2026-11-18)

"i want the CSS of this and the gallery showcase and every page we make in the future to have the same UI elements of
the base game". Standing rule (memory feedback-pages-game-ui-style).

## Stream sc3ui (opus / medium)

1. Study the SC3U UI from the game itself (screenshots you take in a dev tree: main menu, the right-hand toolbar,
   the bottom info bar, a dialog such as Preferences or the query dialog, the budget / graphs windows; also
   MAIN\verify\*\owner_shots pictures). Measure: panel colours and gradients (the lavender / periwinkle panels), bevel
   light and shadow edges, the dark-blue info bar and its text colours, button states (normal / pressed / disabled),
   dialog title bars, the fonts (find a free font close to the game's, Google Fonts only), corner radii, spacing.
   Write the measured palette in re/analysis/UI_STYLE.md with the screenshot each value came from.
2. docs/assets/sc3ui.css: a shared stylesheet recreating that look with CSS only (gradients, borders, shadows). No
   game bitmaps, icons or extracted UI art in the repo (public repo, publish policy). Components: page frame, panel,
   dialog with title bar, info bar / ticker, toolbar-style buttons, chips, cards, form fields (select, input,
   checkbox), progress bar, log box, lightbox, tables. Light theme is the game's look. If you keep a dark variant,
   derive it from the game's own darker UI colours. Phone width must work (16 px gutters, no sideways scroll).
3. Restyle with it, keeping every function and DOM id / class the code and tests use:
   - docs/gallery/index.html and its template MAIN\verify\showcase\site\gallery_page.html (regenerate with
     gallery_build.py so future rebuilds keep the look),
   - docs/buildings/index.html and its generator MAIN\verify\bldpack\work\make_docs.py,
   - re/tools/bldimport/classifier.html (the importer), then copy it and bldweb.js to docs/buildings/importer/ again
     and rerun re/tools/bldimport/webtest/run_all.sh (must still pass) and check_roundtrip.py.
   Pages opened from disk must keep working (stylesheet inlined or a relative path that works from file://; the
   importer inside the sample pack zip must not depend on docs/).
4. Headless Chrome screenshots of each page at desktop and true phone width (390 px iframe trick), before / after, in
   MAIN\verify\sc3ui\owner_shots\ (phone-sized JPEGs). Results MAIN\verify\sc3ui\RESULTS.md.

## Rules

Windowed game, posted input only, kill only PIDs you started, delete BMP dumps, STATUS at every milestone, no git add /
commit. Page text stays as it is (voice rules apply to anything new).
