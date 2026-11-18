# STATUS bldpack (round 2026-11-18d)

## goal
Sample building pack (Kenney CC0 buildings + our test models) for Simtropolis players, grown in game with pictures,
zipped in `stage/sample_pack/`, the importer hosted and in the zip, and the player guide `docs/buildings/index.html`.

## verdict
**Done.** 18 buildings (16 Kenney, 2 ours), ids 38000-38017, classes 3100-8900, lots 1x1 to 3x3, weight 2.
`bldimport.py check` 18 of 18 (20/20 frames). **All 18 grew in game**: 17 with the lab's settings (Sacramento,
Berlin), the Skyscraper (6700) in Berlin with `simrun.ini [churn] anarchy_com=5000` (class 6700 changes few lots:
family 22 went 170 -> 166 lots in 10 game-run minutes). Hosted importer = main 8a206e5's page byte for byte, and its
Install path passes headless from `docs/buildings/importer/` (18 models, Web Worker, game files equal to the Python
install). Byline "nanofives". Detail: `verify/bldpack/RESULTS.md`.

## built
- `MAIN\stage\sample_pack\` (models, `Textures\`, `models.json`, `sc3build\ids.json`, CREDITS / README / Kenney licence)
- `MAIN\stage\sample_pack\dist\sc3-sample-buildings-2026-11-18.zip` (52 files, 665,296 bytes, `importer\` inside)
- guide `dev\bldpack\wt\docs\buildings\index.html` + 9 pictures in `docs\buildings\img\`
- importer `dev\bldpack\wt\docs\buildings\importer\index.html` + `bldweb.js`
- `MAIN\verify\bldpack\owner_shots\` (12 JPEG)

## proven game-side vs static only
- Game-side: growth counts per building (RESULTS steps 2 and 2b), pictures at zoom 3 and 4 next to stock.
- Static only: an install by the page from the unzipped pack folder (the same page bytes passed from docs), the
  guide's layout at phone width (headless Chrome renders wider than 390 px, the gallery shows the same cut).

## blocked on
- nothing

## files owned
Worktree `dev/bldpack/wt` (no git add / commit done):
- `docs/buildings/index.html` (new)
- `docs/buildings/importer/index.html`, `docs/buildings/importer/bldweb.js` (new, copies of main 8a206e5
  `re/tools/bldimport/classifier.html` and `bldweb.js`)
- `docs/buildings/img/pack_sheet.jpg`, `next_to_stock_z3.jpg`, `houses_z4.jpg`, `houses_z3.jpg`,
  `long_factory_z4.jpg`, `chimney_factory_z4.jpg`, `corner_shops_z4.jpg`, `berlin_glass_tower_z3.jpg`,
  `berlin_skyscraper_z3.jpg` (new)

MAIN:
- `verify/bldpack/RESULTS.md` (new)
- `re/sessions/STATUS_bldpack.md` (this file)
- gitignored, commit with `git add -f` only if wanted: `verify/bldpack/work/make_pack.py`, `make_docs.py`,
  `make_zip.py`, `pack_grid.py`, `shots.py`, `fam_counts.py`, `sky_lab.py`, `guide_template.html`, `captions.json`
- not in git: `stage/sample_pack/` (incl. `dist/`), `verify/bldpack/owner_shots/`, `verify/bldpack/runs/`

## game-harness need
None left. Every game the labs started was stopped (PIDs 12076, 19008, 2732, 11348, 784), headless Chrome runs
stopped by their driver. No BMP dumps left.

## asks of other sessions
- none. Observation for `bld_lab.py`: it writes only `anarchy_res` to `simrun.ini`, an `--anarchy-com` option (as in
  `work/sky_lab.py`) would let dense commercial ids grow in a normal run. After a 12.5-minute run `Cam([])` failed
  with "camera not captured" once.
