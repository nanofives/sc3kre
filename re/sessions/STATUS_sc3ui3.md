# STATUS sc3ui3 (round 2026-11-19b: game bitmaps for small UI pieces + runtime game font)

## goal
Owner 2026-11-19: replica play/stop, X, slider, dropdown arrow and dropdown text are wrong, wants the game font. Second
list (same day): list scroll bar, OK button, check boxes, radio buttons. Publish the game's bitmaps (docs/assets/sc3ui/),
runtime FBF font loader for the importer only (sc3font.js), prove per element with replica_diff, regenerate gallery +
guide + importer copy. Results: verify/sc3ui3/RESULTS.md.

## verdict
DONE (2026-11-19), on main cf2b01b (sc4diag merged, fast-forward) + uncommitted branch work.
- Bitmaps found by matching every UI record against a native grab, states observed with posted input, every frame
  0 px different: close X SYS 453ba1f4, play 82fab6d2, stop 22fab6de, dropdown arrow 62b99d31, slider c2b99e09,
  volume steps OtherCtrls 22dec92d:1, check box c2d6e93a, radio 0000000a (magenta key), OK a2defd9a, scroll bar e2b99e01.
  Button strips: 0 disabled, 1 normal, 2 pressed, 3 hover. Check box / radio: 0 on, 1 off, 2/3 hover, 4/5 pressed, 6/7
  disabled (6 observed). Scroll bar: 12 frames, both directions.
- Replica identical px, main -> sc3ui3: X 1.9 -> 89.4%, play 10.2 -> 100%, stop 10.0 -> 100%, sliders 60.2 -> 100%,
  arrow 0.4 -> 100%, volume 46.0 -> 100%, check boxes 49.7/65.7/8.9 -> 100%, radios 33.3/43.1 -> 100%, scroll up /
  thumb / down 10.2/4.7/2.0 -> 100%, track 93.8 -> 98.9% (Chrome's minimum thumb is 17 px, the game's 16), OK 26.4 -> 100%.
  Edges 30/30 within 1 px (main 29/30).
- sc3font.js: 1-bit fonts 0 px differ, AA fonts coverage within 0.012, colour exact (sc3font_check.py 12/12).
  COLRv1 foreground glyphs make Chrome rasterise with FreeType instead of DirectWrite's filter; full-height bars for
  partial coverage, calibrated in a canvas at run time.
- Replica with the game fonts (?gamefont=1&game=): every text sample aligned IoU 1.000, ink ratio 1.00, within 1 px.
- Dropdown text: SYSTEM9, navy. Istok Web stays the best free family (kept 11.5 px).
- run_all.sh 14/14 on cf2b01b + branch (log verify/sc3ui3/webtest/run_all_final.log). sync_css.py --publish done.
  Guide rebuilt from the shared template: byte-identical to main's. Gallery rebuilt: byte-identical.
- classifier.html SC4 note: "One colour of each straight design is on" (orchestrator).

## built
- docs/assets/sc3ui/*.png (25 files) via re/tools/sc3ui/uiart.py (--check: all identical).
- sc3ui.css: bitmap buttons (.ui-close/.ui-play/.ui-stop/.ui-ok), select with outside arrow, slider from bitmaps,
  .ui-volume, every check box / radio, ::-webkit-scrollbar on every scrolling box (scrollbar-color fallback),
  list row check box placement.
- sc3font.js + sc3font_test.html + webtest/sc3font_check.py (run_all.sh step 11); classifier.html hook (gameFonts).
- sync_css.py inlines sc3ui/*.png as data: URIs (31 in the importer), publishes sc3font.js too.
- gallery_build.py (MAIN\verify\showcase\site, in place) copies assets/sc3ui/ next to the local site.

## proven game-side vs static only
- Game-side: bitmap identity and frame order (two sessions, PIDs 14844 and 9600, both started and stopped by me,
  windowed, posted input only, dialog restored to its opening pixels each time, no setting changed).
- Browser-side: replica diff, sc3font_check, page shots. Not checked: non-Chrome browsers (Firefox gets the
  scrollbar-color fallback; exact game text needs COLRv1 support).

## blocked on
- Nothing.

## files owned
Worktree dev\sc3ui3\wt. `git add -f` needed for the four marked *:
- docs/assets/sc3ui.css
- docs/assets/sc3ui/ (25 PNGs: checkbox, close, combo_arrow + _disabled/_hover/_pressed, ok, play, radio, scroll_down
  + _pressed, scroll_hthumb, scroll_htrack, scroll_left + _pressed, scroll_right + _pressed, scroll_thumb, scroll_track,
  scroll_up + _pressed, slider_knob, slider_track, stop, volume) - game bitmaps, owner calls 2026-11-19
- docs/buildings/importer/index.html, docs/buildings/importer/sc3font.js (new)
- re/analysis/UI_STYLE.md
- re/tools/bldimport/classifier.html, re/tools/bldimport/sync_css.py, re/tools/bldimport/webtest/run_all.sh
- re/tools/bldimport/sc3font.js *, re/tools/bldimport/sc3font_test.html *, re/tools/bldimport/webtest/sc3font_check.py *
- re/tools/sc3ui/uiart.py *, re/tools/sc3ui/fontscore.py, re/tools/sc3ui/replica_diff.py, re/tools/sc3ui/replica_prefs.html
MAIN in place: verify/showcase/site/gallery_build.py (backup verify/sc3ui3/gallery_build.before.py).
MAIN records: re/sessions/STATUS_sc3ui3.md, verify/sc3ui3/RESULTS.md (verify/ is local).
Not changed by me: docs/buildings/index.html, docs/gallery/index.html (rebuilt byte-identical).

## game-harness need
None. The game is closed.

## asks of other sessions
- None.
