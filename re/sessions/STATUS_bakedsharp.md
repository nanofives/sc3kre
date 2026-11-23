# STATUS bakedsharp (round 2026-11-23, baked_sharp)

Worktree `dev\bakedsharp\wt` (branch child/bakedsharp, from main 8b091cf), nothing committed. Results:
`verify/bakedsharp/RESULTS.md`.

## goal

A render style that is `baked` except zoom 4 drawn natively, so thin SC4 details (the Alamo's flagpole) survive.

## verdict + deciding evidence

- `baked_sharp` already existed in `bldrender.py` and `bldweb.js` since sc4conv / sc4web (`dict(STYLES["baked"],
  zoom4="native")`), selectable per entry (`x_bldrender.style`) and by `sc4conv.py --style`. What was missing: no suite
  coverage through the importer, no guide line. Added `baked_raw_sharp` (one line each side, free).
- Alamo, converted from the Steam SC4 install: zoom 0-3 frames byte identical between baked and baked_sharp. At zoom 4,
  rotation 2 shows the whole curved pole in baked_sharp and only a stub with the flag floating in baked. That holds offline and in game.
  At rotations 1 and 3 both show the pole (baked 2 px wide, baked_sharp 1 px). At rotation 0 the building hides the flag.
- Cost: the game file is 60% bigger (Alamo alone 164,591 -> 263,960 bytes).

## built

- `bldrender.py`, `bldweb.js`: `baked_raw_sharp`.
- `webtest/golden_setup.py`: case `sharp` (baked, baked_sharp, baked_raw_sharp on test models, obelisk lamp posts).
  `webtest/suite.py`: case in golden.mjs, setup label 10 cases.
- `docs/buildings/index.html`: one line next to `baked_raw`. `docs/buildings/importer/bldweb.js` republished.

## proven game-side vs static only

- Game-side: dev\bakedsharp\tree, Madison, both Alamos placed (38000 baked at 181,204, 38001 sharp at 181,208), zoom 4
  four rotations, frame dumps. PID 3500 started and stopped. Only fault line: the startup 0xC0000096 at SC3U.exe+0x84122.
- Static: golden case sharp 13 of 13 (80 frames Python = page). Full suite (six args + SC3PACK_PACKS + SC4INSTALL): 41 of 41. Existing goldens vs main: 1,090 files, only 39 meta.json cache keys differ (hash of bldrender.py).

## blocked on

Nothing.

## files owned

- re/tools/bldimport/bldrender.py
- re/tools/bldimport/bldweb.js
- re/tools/bldimport/webtest/golden_setup.py
- re/tools/bldimport/webtest/suite.py
- docs/buildings/index.html
- docs/buildings/importer/bldweb.js
- re/sessions/STATUS_bakedsharp.md
- verify/bakedsharp/RESULTS.md
- (local, gitignored) verify/bakedsharp/owner_shots/*, verify/bakedsharp/work/*

## game-harness need

None: claim released, no game running.

## asks of other sessions

None.
