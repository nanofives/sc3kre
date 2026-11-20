# lotshape results (round 2026-11-20e): landmarks and rewards on non-square lots, and 5x5

**Verdict.** Done. Landmarks and rewards take `"lot": [w, d]` with w and d from 1 to 5 each (bldimport.py, the page,
the frames and anchors), and 5x5. The SC4 converter keeps SimCity 4's own lot for landmarks and rewards when it fits
5x5. Growables, ports and civic looks stay square. Python and the page are byte identical on every case. The full suite
passes 42 of 42 steps. In game, SimCity 4's Alamo (2x3 landmark), Mayor's House (2x3 reward) and Hagia Sofia (5x5
landmark) were placed, drawn whole in all four view rotations, saved with footprints 2x3 / 2x3 / 5x5 and reloaded the
same. Static detail: `re/analysis/LOT_SHAPES.md` section 9.

## 1. What changed

| part | change |
|---|---|
| `bldimport.py` | `lot_of(m, rect)`: kinds `landmark` / `reward` (`RECT_KINDS`) accept `[w, d]`, 1..5 each, and 5x5; prop 0x66 = (w, the base's height, d) (`tkb1_set_footprint`); stats of the stock base of the longer side; LANDMARK / REWARD sizes 1..5; rewards skip a base under type 11000 Military (below) |
| `bldrender.py` | `place`, `render_frame`, `_rot_slot`, `ground_mesh` take (w, d): slot extents (w, d), (d, w), (w, d), (d, w); frame width (e_u + e_v) x W / 2, B = e_v x W / 4 + 1, anchor (0, T) at the lot's left vertex in every slot. Square n and (n, n) give the same bytes (checked) |
| `bldweb.js` | the same steps (`placeRect`, `rotPts` on [e_u, e_v], `renderFrame`, `lotOf`, `rewardTable`, `tkb1SetFootprint`) |
| `classifier.html` | Lot choices: 1x1 to 4x4 for every kind, plus 5x5 and every w x d (1..5) when the selected cards are all landmarks or rewards; a landmark's suggestion takes each side from the footprint; warnings: "needs the mods page row Non-square buildings on, off it draws as one square over bare ground" on a non-square landmark or reward, a skip warning on a non-square growable / port / civic look; the hint under Install says the same |
| `sc4conv.py`, `sc4web.js` | `real_lot`: a landmark or reward takes its SC4 lot (the props' lot, turned into the model frame) when both sides are 1..5 and the footprint fits it, else the smallest square, now up to 5x5. A note names the SC4 lot when it differs from the square |
| `props.py`, `lottex.py` (+ `sc4web.js`) | props window and lot-texture canvas w x d (columns along model x, rows along z) |
| tests | `make_testmodels.py --lotshape` (2x3, 3x2 landmarks, 1x4 and 5x5 rewards, 5x4 landmark, an overhanging 2x3, four refused entries); golden case `lotshape` in `golden_setup.py`, `golden.mjs` and `pagetest.mjs` (`run_all.sh`, 22 -> 23 base steps); case landmarks' `landmark_5x5.obj` is now accepted; the install's expected count 113 cards, 82 on (was 73) |
| guide | `docs/buildings/index.html` from MAIN `verify/bldpack/work/guide_template.html` (`make_docs.py`, the published sample-pack link kept): new section "Lots that are not square", Lot / stats rows of Landmarks and Rewards, the Lot field, the footprint row, the SC4 section and the install count |

Base choice for 5x5: the first stock 5x5 landmark by id is 9500 (San Francisco City Hall, type 18044). The first 5x5
reward by id is 8023 Defense Contractor, type 11001, whose CitySim.ini [AgentTypeHierarchy] parent is 11000
"Military". A new reward's type takes its base's parent (`agent_type_rows`), so rewards skip that parent: 5x5 rewards
take 8046 Country Club (type 14370 under 14300). The 5x5 rewards before it by id (8009, 8018, 8020) have 0x6301 frame
tables. The bases of 1x1 to 4x4 have parents 14100, 10001, 10001 and 1000, so they keep their bases.

## 2. Frames against the lotdraw probe

`bldrender` 2x3 box at zoom 0: frames 20 px wide, T = 8 / 10 / 8 / 10 in slots 0-3, L = 0. `verify/lotdraw/work/make_lotrect.py`
(the art LOTRECT was tested with): 2x3 at zoom 0 also 20 px wide, T 8 / 10 / 8 / 10, L 0; 3x2 10 / 8 / 10 / 8. The test
halls 2x3 and 3x2 (`owner_shots/00`): the long red -x wall and the tall +z tower turn with the slots as on the square
test models.

## 3. Python = page, and the goldens

`run_all.sh` with all six arguments, `SC3PACK_PACKS=MAIN\stage\st_packs`, `SC4INSTALL=<SimCity 4 Deluxe>`,
`PROYECTOS_TEST_HUB=off`, test slot: **42 of 42 steps** (`work/new.log`). Main's code on the same inputs, before any
change: 41 of 41 (`work/base.log`). New: case lotshape, 8 files + 120 frames equal Python vs page (`golden.mjs` lines
81-88), and the page installing it (`pagetest.mjs lotshape`).

Every Python output of the two runs compared file by file (`work/golden_diff.py`, `work/golden_diff.txt`): 39,433
files the same. What differs, and why:

| files | why |
|---|---|
| 89 `sc3build/<stem>/meta.json` | only the `key` field: the render cache key hashes `bldrender.py`, which changed. The frames, anchors and the rest of meta.json are the same |
| cases landmarks, landmarkdesc: `models.json`, `bldimport.dat`, `bldimport.pin`, 23 frame files of `landmark_5x5` | a lot really changed: the 5x5 entry was refused, now it is imported (stats of 9500). The .dat gains its 44 records (id 38002), none of the other 132 records changed |
| SC4 install (`sc4install/conv`, `rerun`, `sub`): 33 entries change lot, 7 more come on | a lot really changed: list below |
| 23 install entries with the same lot: `notes`, `x_sc4.auto` | the "1x1 to 4x4" in their notes is now "1x1 to 5x5", and 7 of them (5x5) are now on |
| 3 dependency caches, `counts.json`, `sc3pack_pagetest.json`, a page screenshot | the work folder's path (base vs new) and timings |

SC4 install, entries whose lot changed (main -> branch, the on / off state after): Bank of America 5x5 -> 5x3 (on, was
off), Lincoln Memorial 5x5 -> 5x4 (on, was off), The Alamo 2x2 -> 2x3, Mayor's House 1x1 -> 2x3, The Sphinx 4x4 -> 4x2,
Tourist Trap 3x3 -> 3x2, Stock Exchange 4x4 -> 3x4, Opera House 4x4 -> 3x4, Main Library 3x3 -> 3x4, City Hall (3)
3x3 / 3x3 / 4x4 -> 3x4, Private School (3) 2x2 -> 4x2 / 2x4 / 3x4, Cruise Ship Port 3x3 -> 5x4, Statue of Liberty 2x2 ->
4x4, Missile Range 2x2 -> 4x4, Resort Hotel 3x3 -> 4x4, Toxic Waste Dump 3x3 -> 4x4, House of Worship (4) 2x2 -> 3x3,
Lighthouse 1x1 -> 3x3, Farmer's Market 1x1 -> 3x3, Colossal Mayor's Statue (2) 1x1 -> 3x3, Magnificent Mayor's Statue
(2) 1x1 -> 2x2, Cemetery (3) 1x1 -> 5x5. Now on with the same lot (5x5 allowed): Columbia Seafirst Center, The White
House, Palacio Real, Hagia Sofia, The Guggenheim Museum, Convention Center, Space Port. Result: 113 cards, 82 on (73 on
main). 12 of the 82 are not square.

`sync_css.py --check`: in sync. `sync_css.py --publish`: classifier.html + the four scripts copied to
`docs/buildings/importer/`.

## 4. In game (dev\lotshape\tree, Madison, windowed, posted input and Frida game calls)

Converted with `sc4conv.py` from the Steam SimCity 4 Deluxe (`--only` the three), installed with `bldimport.py build`:
38000 The Alamo (landmark [2, 3], stats of 9528), 38001 Hagia Sofia (landmark [5, 5], stats of 9500), 38002 Mayor's
House (reward [2, 3], stats of 208, type 38002). Load: `LOTRECT> 29 SIMSPR sites patched`, `save footprint: 9 of 9`.
Game PIDs 5412 and 18280, started by `sc3dev.ps1 run lotshape`, stopped by PID.

| check | result | picture |
|---|---|---|
| place (building layer vt+0x38, as lotdraw's lab) | all three placed. Occupants: Alamo rect [181, 204, 182, 206], SizeInCellsX 2, Z 3, 6 cells; Mayor's House [181, 208, 182, 210], 2 x 3, type 38002; Hagia Sofia [185, 203, 189, 207], 5 x 5, 25 cells; rotation 0 | |
| draw, zoom 3, 4 rotations | all three whole, no cut strip, the rail line and trees around drawn in order | `01` |
| draw, zoom 4, 4 rotations | Alamo and Mayor's House whole, lot textures (paths) and props on the 2x3 lot | `02` |
| save (autosave #2, after the placement) | `38000 at (181,204) size 2x3`, `38002 at (181,208) size 2x3`, `38001 at (185,203) size 5x5` (occupant_layer.py) | |
| reload of that save (`lotshape test.sc3`) | same three occupants and rects; Alamo sprite cells (181..182, 204..206), one sprite, size byte 2, registration (182, 204), flag 0x400 on all 6; the same pictures in all 4 rotations | `03` |
| faults | none: the only VEH FAULT line in either run is the game's own startup `0xC0000096 at SC3U.exe+0x84122` | |

## 5. Open / not done

- Hagia Sofia's frames have 184 to 813 near-black pixels per zoom-3 frame on the edges of SC4 tree props near the lot
  corner (`owner_shots/04`, marked magenta). Main's converter writes the same 61 files for it byte for byte (it is 5x5
  on main too, then off), so this comes from the existing prop conversion, not from this change `[cause not traced]`.
- Mover and bulldoze of a converted non-square building were not run here (lotdraw ran them on its probe landmarks).
- The SC4 lot is taken when it fits 5x5, so some small buildings now stand on a larger lot with their SC4 yard: the
  Cemetery's 9 x 11 m building on 5x5, the Lighthouse on 3x3. That is SimCity 4's own lot. An owner call if a "smallest
  square" option is wanted for them.
- With "Non-square buildings" off, a non-square landmark or reward draws as one square over bare ground (lotdraw
  measured it on its 1x3); the page and the guide say so.

## Files

Code and pages: see `re/sessions/STATUS_lotshape.md`. Tools (`verify/lotshape/work`): `lab.py`, `shots.py` (lotdraw's,
pointed at dev\lotshape), `golden_diff.py`; logs `new.log`, `base.log`, `golden_diff.txt`. Pictures: MAIN
`verify/lotshape/owner_shots/` 00-04 (SC4 art, local only). The test city is `dev\lotshape\tree\Cities\lotshape test.sc3`.
