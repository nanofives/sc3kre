# STATUS bldweb (round 2026-11-18d): the building importer inside classifier.html

## goal

Players have no Python, so `re/tools/bldimport/classifier.html` itself renders, packs, installs and removes buildings in
the game folder, producing the same files, ids (`sc3build\ids.json`) and backups as `bldimport.py`. Proof: byte-identical
output against the Python tool for the 3 test models, the bldfile .bld samples and 3 Kenney buildings (golden test,
headless), Web Worker rendering with progress per model, page usable from disk, one page install growing in Sacramento.

## verdict

DONE (2026-11-18). Results: `verify/bldweb/RESULTS.md`, pictures `verify/bldweb/owner_shots/01..06`.

- Byte-identical to `bldimport.py` on every check: pack 52 of 52 (testmodels, 6 .bld, 3 Kenney, a styles case),
  install / re-install / restore 8 of 8 (every file under mods\netmod incl. state.json and backups, hard-link safe),
  .zip route 6 of 6, the page itself in headless Chrome (file://, blob-URL Web Worker) 60 of 60, existing page tests
  8 of 8 + 17 of 17. Whole suite: `webtest/run_all.sh`, 8 of 8 steps on the final code.
- In game: a page install of the 3 Kenney buildings into `dev\bldweb\tree` grew in Sacramento, 760 / 32 / 40 lots at
  the first autosave (2.6 min, weight 20); the page's Remove then put every mods file back (153 of 153 hashes).
- Deciding facts (no RVA work this round): numpy 2.5 / OpenBLAS 0.3.34 evaluates float64 `(N,3) @ (3,)` as
  `fma(x2,v2,fma(x0,v0,x1*v1))` (emulated exactly in JS); Pillow's median cut depends on its hash bucket order
  (ported literally from Pillow 12.3.0 Quant.c / QuantHash.c / QuantHeap.c).

## built

- `bldweb.js`: renderer (numpy order and precision, NEP 50), Pillow median cut + LANCZOS/BICUBIC, PNG decoder,
  QFS compressor, IXF / TKB1 packer, class table from SYS.PAK, .bld art (BAT.DAT and preview), install / restore over
  the File System Access API, a read-only file-list view + .zip writer for browsers without folder writing, Web Worker
  built from the library's own source (falls back to rendering on the page if a worker cannot start). Pillow notice
  included (its licence asks for it; the repo is public).
- `classifier.html`: Game panel (Game folder, remembered in IndexedDB; Look = default style; Install into the game;
  Remove from the game; per-model progress and 4-view previews; log), "No folder access" .zip route, `?bldtest=` hook.
- `webtest/`: golden_setup.py, golden.mjs, install_golden.mjs, zip_golden.mjs, pagetest.mjs (+ pagetest.js, CDP
  driver, `--apply` writes the page's output to a real tree), nodefs.mjs, run_all.sh.

## proven game-side vs static only

- game-side: page-made install grows (Sacramento, 3 of 3 ids), page Remove restores.
- static: everything else is byte identity with the Python tool, whose output is game-proven by bldrender / bldfile.
- not tested: the real folder pickers (need a real click; the page's code ran with stand-in handles); writing while
  the game holds the files open; JPEG textures; browsers other than Chrome 157.

## blocked on

- nothing

## files owned (worktree `dev/bldweb/wt`, no git add / commit)

The new files sit under the deny-by-default `/re/tools/*` rule, like the existing bldimport files: add with `git add -f`.

- `re/tools/bldimport/classifier.html` (modified)
- `re/tools/bldimport/bldweb.js` (new)
- `re/tools/bldimport/webtest/golden_setup.py`, `golden.mjs`, `install_golden.mjs`, `zip_golden.mjs`, `pagetest.mjs`,
  `pagetest.js`, `nodefs.mjs`, `run_all.sh` (new)
- MAIN (not in the worktree): `verify/bldweb/RESULTS.md`, `verify/bldweb/owner_shots/*.jpg`, `verify/bldweb/runs/page1/`
  and `verify/bldweb/work/` (lab dumps, saves, the CC0 models used, hash lists: not for git).

## game-harness need

- done: one windowed run of `dev\bldweb\tree` (bld_lab.py, posted input only, test slot, stopped by its PID). The
  harness check reported BUSY only because bldpack's game ran from its own tree; nothing was built in `re\harness`.
- `dev\bldweb\tree` is back to its pre-install files (plus `mods\netmod\bldimport\` backups and an empty state.json).

## asks of other sessions

- bldpack / orchestrator (guide): the player steps are in RESULTS.md "What a player does" with the page's exact button
  labels (Open folder, Game folder, Look, Install into the game, Remove from the game, Make the install .zip, Make the
  removal .zip).
- Whoever changes `bldrender.py` / `bldimport.py` output later: port the change to `bldweb.js` and re-run
  `webtest/run_all.sh` (the Python tool stays the reference).
