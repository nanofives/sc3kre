# Round 2026-11-20f: smooth the game's title and button font on the pages

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main fd06ca7+.
Owner (2026-11-20): "can you make the comic sans font less pixelated?" The comic-style face is the game's own TITLE12
(titles, "SC3 Title") and TITLE9 (buttons, "SC3 Button"), 15-level anti-aliased FBF bitmap fonts. Today
re/tools/sc3ui/build_fonts.mjs (same code as re/tools/bldimport/sc3font.js buildTTF) turns every pixel into a square or
a partial bar plus a COLR v1 glyph, so the web font is pixel-exact at --ui-scale 1 but at 150% / 200% (high-DPI screens,
the owner's) every game pixel shows as a block. Read re/analysis/UI_STYLE.md "Fonts", "Game fonts at run time" and
"Game fonts and scale" first, and memory feedback-pages-game-ui-style (light theme only, game fonts on every page,
.FBF files never in the repo).

## Stream smoothfont (opus / medium)

1. Smooth outlines traced from the game's own glyphs: the 15 coverage levels give sub-pixel edge positions (for example
   upsample the coverage, take the 50% contour, simplify, fit quadratic curves, keep stems and counters). Same advance
   widths, line height and baseline as today, so layout does not move. Plain TrueType outlines (no COLR needed).
2. TITLE9 and TITLE12 first. Report whether the 1-bit fonts (MAIN9, MAIN10, SYSTEM9) can be smoothed acceptably too,
   with a picture, but do not switch them without the owner.
3. Pictures for the owner: the same strings (a page title, button labels, the importer's top bar) today against smooth,
   at 100%, 150% and 200% (headless Chrome with device scale factor, re-use the CDP pattern in
   re/tools/bldimport/webtest/pagetest.mjs), and next to the game's own pixels at 100%. Local in verify/smoothfont/.
4. Wire it so it can be switched in one place (build_fonts.mjs option or new files, sc3ui.css @font-face), but do not
   publish: no change under docs/ until the owner picks. The importer's run-time builder (sc3font.js) the same way if
   it is cheap, else say what it needs.
5. Results verify/smoothfont/RESULTS.md, STATUS re/sessions/STATUS_smoothfont.md.

## Rules

The game install is read in place (the FBF files never enter the repo, only built fonts). No git add / commit.
