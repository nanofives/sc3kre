# Round 2026-11-19b: game bitmaps for small UI pieces + the game font at runtime in the importer

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main.
Previous: ROUND_2026-11-18g_sc3ui_precision.md, verify/sc3ui2/RESULTS.md (replica_prefs.html, replica_diff.py,
fbf.py, UI art = compressed 16-bit images inside Apps\Res\UI\Shared\*.IXF, cloud tile in SYS.IXF).

## Owner (2026-11-19)

On the replica: "the play and stop buttons should bring their texture, font is different (can you pull the font from
the game?), slider texture is different, background is fine, X button is also different, text of dropdown is also
different, dropdown arrow is wrong". Calls: font = runtime in the importer only (never published); play / stop
buttons, X, slider, dropdown arrow = publish the game's bitmaps (risk accepted, memory publish policy).

## Stream sc3ui3 (opus / high)

1. Extract from the player-side game files (Apps\Res\UI\Shared\*.IXF, SYS.IXF or wherever they live; find them by
   matching the Preferences grab) the bitmaps of: the music play and stop buttons (every state the game has:
   normal / pressed / disabled if present), the window close X, the slider knob and track (and the volume bar steps
   if they are one bitmap), the dropdown arrow button. Only these. Lossless PNG, original pixels and transparency
   (magenta or the IXF's own key), in docs/assets/sc3ui/. Document ids and offsets in UI_STYLE.md.
2. sc3ui.css uses them (background-image, image-rendering: pixelated, sized by --ui-scale). The importer keeps
   working opened from disk: inline them as data URIs in its inlined CSS (sync_css.py handles it).
3. Dropdown text: which FBF the game uses there (SYSTEM9 per the precision pass) and the best free match for that role
   on the public pages, if it differs from what is used now.
4. Runtime font (importer only): a standalone re/tools/bldimport/sc3font.js that, given the game folder handle the
   importer already has, reads the FBF files of the game's language folder, builds web fonts in memory (glyph pixels
   to outlines, or another way that gives crisp exact text) and registers them with the FontFace API, then switches
   the page's font variables to them; falls back to the free fonts when no game folder is chosen. Test it with a
   standalone test page and headless Chrome (game folder given by a test hook). DO NOT edit classifier.html or
   bldweb.js until the orchestrator says so (child sc4web is changing them now); then add one hook.
5. Proof: replica_prefs.html with the new pieces, diffed against the game grab as before, per element (play, stop,
   X, slider, dropdown arrow, dropdown text): zoomed side-by-sides and the numbers. Also the replica rendered WITH
   the runtime game font (test hook) to show exact text.
6. Regenerate the gallery and the guide, run sync_css.py --publish, before / after shots (desktop + 390 px).
Results MAIN\verify\sc3ui3\RESULTS.md, STATUS MAIN\re\sessions\STATUS_sc3ui3.md.

## Rules

Windowed game, posted input only, kill only PIDs you started, no git add / commit. EA files in the repo: ONLY the
bitmaps listed in step 1. Never the FBF files or a font made from them.
