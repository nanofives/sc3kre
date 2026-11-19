# Round 2026-11-19: SC4 conversion inside the importer page

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main ac0d4f3+.
Previous: ROUND_2026-11-18h_sc4_convert.md, verify/sc4conv/RESULTS.md, re/analysis/SC4_FORMATS.md,
ROUND_2026-11-18d (bldweb: the page renders / packs / installs byte-identical to the Python tool).

## Owner (2026-11-19)

"SC4 conversion: Yes, add it to the importer page". Default light for converted SC4 buildings: `baked` (brighter).

## Stream sc4web (opus / high)

1. Port to the page (bldweb.js or a new sc4web.js loaded by classifier.html): the SC4 readers (DBPF 1.0 / 1.1, QFS
   already there, S3D, FSH, exemplar, LText), the view reprojection and export of re/tools/sc4conv/, and bldrender's
   new parts (texture alpha, `sc3slot<r>` groups, styles baked / baked_raw / baked_sharp). `baked` is the default
   style for every SC4 entry.
2. Input as players get it: a folder picked in the page (recursive listing: .dat, .SC4Model, .SC4Desc, .SC4Lot) AND
   the downloaded .zip / .jar itself (LEX installers are jars), read in the browser (DecompressionStream
   'deflate-raw', no new library unless needed, pinned CDN if so). The classifier grid shows the SC4 buildings with
   names, class and lot filled from the SC4 data, colour variants grouped (one enabled per design, as sc4conv does).
3. Byte identity with the Python route (sc4conv.py then bldimport.py build) for the JMyers pack: every converted
   model, models.json, and the installed files, golden tests headless in re/tools/bldimport/webtest (extend
   run_all.sh). The existing suites must still pass (run_all.sh, check_roundtrip.py, sync_css.py --check, and the
   sc3ui look: keep sc3ui.css inlined and in sync).
4. One install made by the page from the JMyers zip grows in Sacramento (picture, phone-sized, local only).
5. Guide: add an "SC4 buildings" section to docs/buildings (template MAIN\verify\bldpack\work\guide_template.html +
   make_docs.py): what converts and the limits (light painted in, roofs from higher up, no lot props, look softer
   than 3D models), how to do it in the page, and the rule: SC4 content is the authors' work, convert your own
   downloads for your own game and never share the converted buildings without the author's permission. English,
   voice rules (no em-dashes, semicolons, emoji, ellipsis, intensifiers, invented numbers). No pictures of the JMyers
   houses in docs/ (the pack's terms).
6. Publish copy: sync_css.py --publish (docs/buildings/importer), note that the sample pack zip importer needs the
   orchestrator's rebuild.
Results MAIN\verify\sc4web\RESULTS.md, STATUS MAIN\re\sessions\STATUS_sc4web.md.

## Rules

Windowed game, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, no git add /
commit. Nothing from SC4 packs goes into the repo or docs/.
