# STATUS sc4lottex (round 2026-11-19l)

## goal
SC4 lot textures (driveways, paths, paving, the lot's base) drawn on the ground under the building in the SC3 pictures,
from the download, the dependency packs and the SC4 install, Python and the page byte identical; measure on JMyers and SC4
civic lots; in-game check with pictures; per building switch; guide text.

## verdict + deciding evidence
Done. Texture rows (lot object kind 2, FSH group 0x0986135E, id + 4 = 128 px over 16 m) composited on the props' SC3 lot
window, SC4 grass cleared to SC3's lawn, drawn by a quad in the new OBJ group `sc3ground` that bldrender / bldweb.js shade
as their lawn. Orientation, mirror bit and layering decided by the cars test (parked cars on paving): install 197 of 239,
JMyers 20 of 29 for the chosen mapping, lot order 182 / 11. JMyers + BSC + install: 622 of 634 rows drawn on 110 of 110
buildings. SC4 install: 2,143 of 3,675 on 111 of 112. Detail: `verify/sc4lottex/RESULTS.md`, `re/analysis/SC4_FORMATS.md` 12.

## built
No DLL changes. Converter, bldrender (`sc3ground` group, off switch `SC3BLD_GROUNDGROUP=0`), page, tests, docs.

## proven game-side vs static only
Game-side: 8 lab ids (4 designs, textures on / off) grew in Sacramento by the first autosave; the SC4 Small Police Station
look with textures picked in the Police list window and placed (type 13130 at (232..234, 218..220)), its frame found pixel
for pixel in all four view rotations. Static: Python = node = page (sc4_lottex 24/24, sc4_baseprops 132/132), suite 40/40.

## blocked on
Nothing.

## files owned (worktree dev\sc4lottex\wt, branch child/sc4lottex, nothing committed)
- re/tools/sc4conv/lottex.py (new, needs `git add -f`), re/tools/sc4conv/sc4conv.py, re/tools/sc4conv/catalog.py
- re/tools/bldimport/bldrender.py, bldweb.js, sc4web.js, classifier.html
- re/tools/bldimport/webtest/sc4_lottex_setup.py, sc4_lottex.mjs (new, need `git add -f`)
- re/tools/bldimport/webtest/run_all.sh, sc4_props.mjs, sc4_baseprops.mjs, sc4_golden.mjs, sc4_packs.mjs
- docs/buildings/importer/index.html, bldweb.js, sc4web.js (sync_css --publish), docs/buildings/index.html (make_docs)
- re/analysis/SC4_FORMATS.md
- MAIN (not in the worktree): verify/sc4lottex/RESULTS.md, verify/sc4lottex/lawn_numbers.json, re/sessions/STATUS_sc4lottex.md,
  verify/bldpack/work/guide_template.html (gitignored, backup .bak_sc4lottex)
- Local only, never commit: verify/sc4lottex/owner_shots, verify/sc4lottex/runs, dev\sc4lottex\work

## game-harness need
None left. Games stopped (PIDs 17252, 12748, both mine). The tree has the lab install (bldimport) and
`Cities\sc4lottex_grown.sc3`.

## asks of other sessions
None. Owner call: lot textures on by default (as now) or off.
