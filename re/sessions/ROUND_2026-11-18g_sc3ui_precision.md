# Round 2026-11-18g: sc3ui precision pass (font, spacing, background)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main f08d4f4+.
Previous: ROUND_2026-11-18f_game_ui_css.md, re/analysis/UI_STYLE.md, verify/sc3ui/RESULTS.md (docs/assets/sc3ui.css).

## Owner (2026-11-18)

"let's first tweak the UI, font, spacing and background is still not quite there yet, be more precise".

## What is known

- The game's UI text is drawn with its own bitmap fonts: Apps\Res\Text\<lang>\MAIN9.FBF, MAIN10.FBF, SYSTEM9.FBF,
  SERIF17.FBF (and any other .FBF the UI loads). UI bitmaps (clouds, frames) are in Apps\Res\UI\Shared (*.bmp).
- Pass 1 picked fonts by eye (Comic Neue, Arimo) and drew the clouds with radial gradients.
- EA files never go into the repo: no FBF, no bitmap, no font converted from them. Measurements, statistics and our
  own generated textures are fine.

## Stream sc3ui2 (opus / high): measured match, proven by a replica diff

1. References at NATIVE size (800x600 window, no UI scale, no zoom): the Preferences dialog, the query dialog, the
   budget window, the main menu, the info bar. PNG crops, no resampling.
2. Fonts: decode the FBF format (header, glyph table, bitmaps; document it in re/analysis/UI_STYLE.md) and map which
   UI element uses which FBF (titles, body, buttons, info bar, ticker) from the references. For each, rank free Google
   Fonts candidates by rendering the same strings at the same pixel size and scoring glyph overlap (IoU) and advance
   width error against the game's own glyphs. Pick per element: family, size, weight, letter-spacing, and whether text
   rendering should be crisp. Report the scores.
3. Background: from the real cloud bitmap(s), measure colour histogram, mean / spread, dominant cloud size (power
   spectrum) and tile size. Generate our own texture (SVG feTurbulence + colour matrix as a data URI, or a small
   generated PNG we own) tuned to match those numbers, with the numbers side by side.
4. Spacing: measure every metric in the references (title bar height, frame bands, padding, gaps, control heights,
   button size and corner shape, group box insets, line height, list row height) and express sc3ui.css on one
   --ui-scale (1 = native px; choose the web default, e.g. 1.5, and say why).
5. Proof: re/tools/sc3ui/replica_prefs.html rebuilds the Preferences dialog with sc3ui.css at --ui-scale 1; render it
   headless at the dialog's exact size and diff against the game crop: per-region colour error (Delta E 2000) for
   frame, title bar, group boxes, buttons, body; edge positions in px; text overlay. Targets: frame / panels mean
   Delta E <= 3, edges within 1 px, title and body text visibly the same size and weight. Iterate until met or explain
   what cannot be matched with free fonts. Side-by-side + diff images, phone-sized, in MAIN\verify\sc3ui2\owner_shots\.
6. Re-apply to the gallery, the building guide and the importer (and their generators), recopy the importer to
   docs/buildings/importer (sync_css.py --publish), rerun webtest/run_all.sh and check_roundtrip.py (must pass),
   before / after screenshots at desktop and true 390 px phone width.
Results MAIN\verify\sc3ui2\RESULTS.md, STATUS MAIN\re\sessions\STATUS_sc3ui2.md.

## Rules

Windowed game, posted input only, kill only PIDs you started, delete BMP dumps, no git add / commit. Page text unchanged.
