# STATUS sc4baseprops (round 2026-11-19l)

## goal
SimCity 4's own props from the player's install as one more dependency source for downloaded lots, Python and the page,
byte identical; measure again on JMyers; in-game check with pictures; guide text.

## verdict + deciding evidence
Done. `sc4conv.py <download> --sc4 <install>` and the page (install `.dat` files picked with the download, or the game
remembered from Open SC4 game). JMyers, 5,190 prop rows: BSC alone 486 placed (72 buildings), install alone 1,786 (110),
both 2,236 (110) with 0 rows in no source. Two rules now read the sources as one exemplar space: families pooled
(A0000038: 502 BSC + 23 install members), a prop's model from the first source holding its views (BSC
`CP_MaxisFluffyMed` -> SC4's S3D 1EDA0000). Detail: `verify/sc4baseprops/RESULTS.md`, `re/analysis/SC4_FORMATS.md` 11.

## built
No DLL changes. Converter + page + tests only.

## proven game-side vs static only
Game-side: 8 lab ids (4 designs, BSC props vs BSC + game props) grew in Sacramento by the first autosave; the SC4 Small
Police Station look picked in its list window and placed (type 13130 at (53, 75)). Static: byte identity Python = node =
page (132 + 19 + 19 checks), suite (see RESULTS section 3).

## blocked on
Nothing.

## files owned (worktree dev\sc4baseprops\wt, branch child/sc4baseprops, nothing committed)
- re/tools/sc4conv/sc4conv.py, re/tools/sc4conv/props.py
- re/tools/bldimport/sc4web.js, re/tools/bldimport/classifier.html
- re/tools/bldimport/webtest/sc4_baseprops_setup.py, re/tools/bldimport/webtest/sc4_baseprops.mjs (new, need `git add -f`)
- re/tools/bldimport/webtest/pagetest.mjs, pagetest.js, run_all.sh
- docs/buildings/importer/index.html, docs/buildings/importer/sc4web.js (sync_css --publish), docs/buildings/index.html (make_docs)
- re/analysis/SC4_FORMATS.md
- MAIN (not in the worktree): verify/sc4baseprops/RESULTS.md, re/sessions/STATUS_sc4baseprops.md, verify/bldpack/work/guide_template.html (gitignored)
- Local only, never commit: verify/sc4baseprops/owner_shots, runs; dev\sc4baseprops\work

## game-harness need
None left. Games stopped (PIDs 15028, 5480, both mine). Tree has the lab install (bldimport) and `Cities\sc4baseprops_grown.sc3`.

## asks of other sessions
sc4lottex (next stream): the install holds 1,453 FSH entries of group 0x0986135E (the lot texture group of SC4_FORMATS 9.2),
so it can be a lot-texture source the same way: `installSource` (page) / `C.Index(install)` (Python) already read its entries.
