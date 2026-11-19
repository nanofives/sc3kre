# Round 2026-11-19d: the game's font on every page

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main 499a8f1+.
Previous: ROUND_2026-11-19b (sc3ui3: bitmaps, sc3font.js builds the game fonts in memory from FBF files at runtime).

## Owner (2026-11-19)

"can you keep the game font?" -> "Use it on every page": publish web fonts built from the game's FBF files in docs/
(risk accepted, memory publish policy). The raw .FBF files never go in the repo.

## Stream gamefont (opus / medium)

1. Build the fonts once from the game's FBF files with sc3font.js's builder (node, same code path), one file per
   game font the pages use (TITLE12, TITLE9, MAIN9, MAIN10, SYSTEM9, SERIF17 as mapped in UI_STYLE.md), into
   docs/assets/fonts/ (smallest format that keeps the crisp colour-glyph rendering in Chrome / Edge and works in
   Firefox; say what each browser does). Script: re/tools/sc3ui/build_fonts.mjs. Glyph coverage: what the FBF has
   (report which characters the pages use that a font lacks).
2. sc3ui.css: @font-face for each, the element mapping from the precision pass, free fonts only as fallback. Pixel
   fonts blur at fractional scales: test --ui-scale 1, 1.25, 1.5 and 2 for crispness and readability on a desktop and
   at 390 px, and pick per page context (explain). The importer keeps working from disk: fonts inlined as data URIs
   or loaded from its own folder (sync_css.py), and its runtime builder becomes the fallback when the files are
   missing.
3. Proof: the replica with the published fonts diffed against the game grab (text pixels), and before / after shots of
   the gallery, the guide and the importer at desktop and 390 px.
4. Regenerate gallery and guide, sync_css.py --publish, run_all.sh must pass every step.
Results MAIN\verify\gamefont\RESULTS.md, STATUS MAIN\re\sessions\STATUS_gamefont.md.

## Rules

No game runs needed unless for a new grab (windowed, posted input only). No git add / commit. Only built web fonts
from the FBF, never the .FBF files.
