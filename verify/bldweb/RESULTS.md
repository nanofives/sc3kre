# bldweb: the building importer runs inside classifier.html (2026-11-18d)

Players have no Python. `re/tools/bldimport/classifier.html` now renders, packs, installs and removes buildings itself
(Chrome / Edge, opened from disk), through `re/tools/bldimport/bldweb.js`, a transcription of `bldimport.py`,
`bldrender.py`, `bldfile.py` and the batgrow packing. It writes the same files, ids (`<models>\sc3build\ids.json`),
backups and `state.json` as the Python tool: **byte-identical on every check below**, in node and in the page itself
in headless Chrome. One install made by the page grew in Sacramento: the 3 Kenney buildings stood on 760 / 32 / 40 lots at the first
autosave (2.6 game-run minutes), and the page's Remove put the tree's files back.

## What a player does (the page's own steps, for the guide)

1. Open `classifier.html` in Chrome or Edge (from disk, no server; the 3D preview loads three.js from the internet,
   as before). **Open folder**: the models folder (OBJ + MTL + textures, `.bld` files, an existing `models.json` is
   read back). Classify as before.
2. **Game folder**: the SimCity 3000 Unlimited folder (the one with `Apps`, `Cities`, `Buildings`). The page checks
   for `Apps\Sys\SYS.PAK` and the road mod (`mods\netmod\overlay\...\OccupantAttribs_Korea.IXF`) and remembers the
   folder for the next visit.
3. **Look** (optional): `stock` (default), `stock, sharp zoom 4`, `clean`: the style for OBJ models whose entry names
   none (what `SC3BLD_STYLE` does for the Python tool). `x_bldrender.style` in `models.json` still wins per model.
4. Close the game. **Install into the game**: the page saves `models.json` if it changed, renders each enabled model
   (progress per model and per picture, 20 pictures each, in a Web Worker so the page stays usable), shows each
   building in its 4 views, and writes the files. Re-running it replaces the last install (same ids).
5. **Remove from the game**: every file put back as it was before the first install, the created `.DAT` deleted.
6. No folder access (Firefox, Safari, or a game folder the browser refuses to open for writing): under
   "No folder access", **Make the install .zip** reads the game folder through the browser's folder upload picker
   and downloads `sc3-buildings-install.zip` (unpack it into the game folder, replace files); a models folder the
   page could not write to also gets `ids.json` as a download (into the models folder's `sc3build` folder).
   **Make the removal .zip** downloads the files to put back plus `DELETE_THESE_FILES.txt` (the `.DAT` the install
   created).

## Evidence

Golden data: `webtest/golden_setup.py` makes the model folders and runs `bldimport.py pack --out` on each;
the JS side runs on copies of the same folders against the same game tree (`dev\bldweb\tree` before the install,
`stage\release` after; their `mods` trees hash equal, 153 files). All runs inside the test slot.

| check | how | result |
|---|---|---|
| pack, 4 cases | `node webtest/golden.mjs --frames`: the 11 game files, `ids.json`, every frame vs the Python tool's cache PNG | 52 of 52 |
| install / re-install / restore | `node webtest/install_golden.mjs --case kenney`: two hard-linked game copies, `bldimport.py build` vs `BLDWEB.install`, then the same `models.json` edit (weight 7, one model off) and again, then `restore`; every file under `mods\netmod` | 8 of 8, incl. "overlay = the tree's own after restore" and "hard-link source untouched" |
| .zip route | `node webtest/zip_golden.mjs`: game read as a browser file list, install .zip, removal .zip from the folder with the install unpacked | 6 of 6 |
| the page itself | `node webtest/pagetest.mjs --case <c>`: `classifier.html?bldtest=...` from disk in headless Chrome 157, the page's Install path (`installWith`, blob-URL Web Worker), folders as File System Access stand-ins over `fetch` | 60 of 60 (4 cases x 15) |
| existing page tests | `check_roundtrip.py` (models.json round trip), `bld_js_check.mjs` (.bld reader, 17 shipped files) | 8 of 8, 17 of 17 |
| in game | page install (`pagetest.mjs --apply`) into `dev\bldweb\tree`, `bld_lab.py --tag page1`, Sacramento, speed 4, churn `anarchy_res=5000`, autosave 150 s, posted input only | grown, table below; page Remove afterwards: every file under `mods` equal to before the install (153 of 153 hashes), plus the backups and an empty `state.json` the Python tool also leaves |

| save | stock | 38000 Kenney house A (3300, 1x1) | 38001 Kenney shop A (5100, 1x1) | 38002 Kenney works A (8700, 2x2) |
|---|---|---|---|---|
| 1 (2.6 min) | 11,625 | 760 | 32 | 40 |

Weight 20 each (to see growth quickly, as the bldfile round did; the default is 1). The lab stopped at the first save
because every id had 3 lots or more. Faults: only the `0xC0000096 at SC3U.exe+0x84122` line every run logs at start.
The page install: `pagetest.mjs --apply` runs the page (headless Chrome, worker renderer) over the real tree read
through `fetch` and writes what the page wrote into the tree (temp + rename) and `ids.json` into the models folder.
The folder pickers need a real click, so this is the one step not done by the page itself; the bytes are the page's.

Cases: **testmodels** (`make_testmodels.py`: plain, textured, 2x2), **bld** (6 shipped `.bld`: Dupont House and The
Joneses with BAT.DAT art, Garvey Plaza and Tutorial House preview art in the BA look, North Shore Cannery preview
`stock`, Hotel Splash preview `stock_sharp`), **kenney** (CC0 Kenney suburban house A, commercial building A,
industrial building A, PNG colormap textures in a `Textures` subfolder), **styles** (`clean` screen-sun light,
`stock_sharp` native zoom 4, rotations 45 / 90 / 180, `shadow: false`, `ground: "none"`, `cell_m: 15`, a model larger
than its lot, a missing file and a wrong extension skipped as the Python tool skips them).

Speed: the three first cases took 3.8 + 0.9 + 5.2 s in node against 39 s for the three Python runs; the page took
6.8 s for the Kenney case in headless Chrome.

## How byte identity was reached

Every numpy expression of `bldrender.render_frame` is evaluated in numpy's order and precision (float32 where numpy
keeps float32, NEP 50: a Python float meeting a float32 array is cast to float32 first). Measured on the Python
tool's own numpy 2.5 / OpenBLAS 0.3.34 (Haswell kernel), bit for bit against exact rational arithmetic on random
operands (2D: N = 1 to 40, 63 to 65, 127, 129, 1000 to 1003; 3D: 1 to 19, 100, 101, 333):

- float64 `(N,3) @ (3,)` (the shadow map, the shadow lookups, the back-face test) is `fma(x2, v2, fma(x0, v0, x1*v1))`,
  for 2D and 3D operands of every size. JS has no fused multiply-add, so `bldweb.js` emulates it exactly (exact
  product, TwoSum, round to odd).
- float32 `(N,3) @ (3,)` (luminance) is sequential float32 for N >= 2 and accumulated in double for N = 1.
- 1-D `dot`, `norm(axis=1)`, `.sum(1)`, `prod(axis=1)` over 3 values, and the ss x ss box filter are sequential.
- The grass texture's `default_rng(7)` is numpy's PCG64 from the same state (fixed seed), checked against numpy.

The palette cut is Pillow 12.3.0's median cut transcribed from `Quant.c`, `QuantHash.c`, `QuantHeap.c` (the hash
table's bucket order decides the list order before the merge sorts, and colours whose `PIXEL_HASH` collides merge);
`.bld` previews use Pillow's `Resample.c` LANCZOS / BICUBIC with its RGBa premultiplication. Textures go through
a PNG decoder that gives what `Image.open(p).convert("RGB")` gives. The pixel records use the transcribed
GZResourceD QFS compressor (`qfs_encode.compress`, quick 1).

## Known differences from the Python tool

- The page writes no render cache (`sc3build\<model>\*.png`, `anchors.json`, `meta.json`, `sheet.png`): it renders
  on every install. It writes `ids.json`, which is what keeps the ids.
- The browser cannot see running processes: the page tells the player to close the game, it does not check
  (`bldimport.py` refuses while `SC3U.exe` runs from that folder). Writing while the game holds the files open was
  not tested. A run stopped midway leaves the same state a stopped Python run leaves, and the next Install starts
  from the files on disk with the same code (`sources`, `upsert`, the family-line strip of ids 38000-38999).
- A texture outside the models folder (`../x.png`, an absolute path) is not readable by the page; the Python tool
  reads it.
- JPEG textures are decoded by the browser, not checked against Pillow (the tests use PNG, as the Kenney kits do).
- `models.json` numbers: JSON cannot tell `1` from `1.0` in a browser, so a lot, weight or class written as `1.0`
  is accepted by the page and refused by the Python tool. A `models.json` with a UTF-8 BOM is read by the page,
  refused by Python's `json.load`.
- Writes remove the old file, then write the new one (never through a hard link). A failure between the two leaves
  that file missing until the next Install or Remove; the backup of its original is already on disk.
- Byte identity was measured against this PC's numpy and OpenBLAS. OpenBLAS picks its kernel per CPU (DYNAMIC_ARCH),
  so the Python tool on another CPU may round the fused matmul differently [not measured]. The page uses IEEE
  arithmetic only, apart from `Math.pow` (lawn rim), `Math.sin` / `Math.cos` (rotation, `.bld` resize filters), whose
  last bit belongs to the browser's maths library [Chrome only measured].

## Files

`re/tools/bldimport/bldweb.js` (new), `classifier.html` (Game panel, install / remove / .zip, test hook),
`webtest/golden_setup.py`, `golden.mjs`, `install_golden.mjs`, `zip_golden.mjs`, `pagetest.mjs`, `pagetest.js`,
`nodefs.mjs`, `run_all.sh` (new). No change to the Python tools. Whole suite:
`test-slot bash re/tools/bldimport/webtest/run_all.sh <work dir> <pristine game tree> <stage\kits>` (8 steps).

## Pictures (`owner_shots/`)

- `01_page_after_install.jpg`: the page after the install (headless Chrome, 1280 px): Game panel, progress, each
  building in its 4 views (zoom 2), the log.
- `02_kenney_house_38000_zoom4.jpg`: Kenney house A (white walls, green roof) on many lots among stock houses.
- `03_kenney_shop_38001_zoom4.jpg`: Kenney shop A (dark four-storey blocks, blue windows) along the main street.
- `04_kenney_works_38002_zoom4.jpg`: Kenney works A (white 2x2 blocks, solar panels on the roof) in the industry.
- `05_kenney_houses_zoom3.jpg`: the houses at zoom 3.
- `06_kenney_house_4_views_zoom4.jpg`: the house lot in the 4 view rotations.
Raw dumps, counts, saves: `runs/page1/`. Models used: `work/models/` (CC0, Kenney, www.kenney.nl).
