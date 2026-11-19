# sc4web results (round 2026-11-19): SimCity 4 downloads converted inside the importer page

**Verdict: players can convert their own SC4 downloads in the importer page, and the result is byte-identical to
the Python route.** `classifier.html` opens the download as the player got it (the `.zip`, the LEX `.jar` inside it,
or the plugin folder), converts it on the PC with the new `re/tools/bldimport/sc4web.js` (a transcription of
`re/tools/sc4conv/`), fills the grid with the SC4 names, classes and lots, and installs through `bldweb.js` as
for any models folder. On the owner's BSC JMyers Homes Pack V3.1 zip: 110 buildings converted in 2.1 to 2.6 s in node
(3.5 to 4.7 s with the grid in headless Chrome), the 18 enabled ones rendered and installed by the page in 12 to
16 s. **One install made by the page grew in Sacramento: all 18 designs stood on 2 to 8 lots each at the first
autosave (2.4 game-run minutes, 84 lots), 3 to 10 each when the lab stopped (7.5 minutes, 99 lots)**, and the page's
Remove put every file under `mods` back (153 of 153 equal to the base).

Nothing from the pack is in the repository or in `docs/`: the test input stays in `MAIN\stage\st_packs\` and
`MAIN\.happy-uploads\`, the golden work folders in the session scratchpad, the pictures in `owner_shots\`
(gitignored, for the owner only).

## 1. What the player does (the guide's steps, docs/buildings/index.html#sc4)

1. Open the importer in Chrome or Edge. **Open SC4 .zip** and pick the downloaded `.zip` (or the `.jar`). Or
   **Open folder** and pick a folder with SC4 files: subfolders are read, and when the folder holds no 3D models at
   its top the page treats it as an SC4 download. The read-only fallback picker (other browsers) does the same.
2. The grid shows one card per building, grouped by design ("Abby Glen: 6 colours, 1 on"), the card's second line
   is the colour and the exemplar name, the panel's Suggested box gives the converter's class and lot with the
   reason from the SC4 data. One colour per design is on, as sc4conv.py does.
3. Game folder, Install into the game, Remove: unchanged. The colours that are off now show as one "N models are
   switched off" row instead of one row each (92 rows for this pack).
4. Where the choices are kept: opened as a folder, the page saves `models.json` and `sc3build\ids.json` into it.
   Opened from a `.zip`, Save downloads `models.json`. Picked again together with the `.zip`, the converter keeps
   every field the player changed (the `x_sc4.auto` merge of sc4conv.py). The ids come out the same without
   `ids.json`, since they are given in `models.json` order.
5. The page shows the rule next to the grid: "SimCity 4 buildings are their authors' work. Convert your own
   downloads for your own game, and never share the converted buildings without the author's permission."

## 2. Evidence

All runs inside the test slot, game tree `dev\sc4web\tree` (pristine, from the release stage).

| check | how | result |
|---|---|---|
| conversion, .zip | `sc4_golden.mjs`: the zip through `sourcesFrom` + `convert`, per building OBJ and MTL bytes and the 4 textures RGBA pixels against `sc4conv.py`'s output, then `models.json` bytes and the file list | 110 of 110 buildings, models.json (224,616 bytes, 110 models, 18 enabled), 661 of 661 files |
| conversion, folder | the unpacked download (`stage\st_packs\sc4_jmyers_homes`) through the same code | every file equal to the zip route |
| rerun merge | `models.json` edited as the page saves it (JSON.stringify layout, `1.0` written as `1`; weight, enabled, render style, name, lot, a note with an accent), converted again: against `sc4conv.py` run over the same file | byte-identical |
| render + pack | `bldweb.buildFiles` over the converted files in memory (the page's overlay folder) against `bldimport.py pack --out` of the Python output | 11 of 11 game files, `ids.json`, 360 of 360 frames (RGBA) |
| the page | `pagetest.mjs --case sc4 --sc4zip`: `classifier.html` from disk in headless Chrome, the page's own `openSc4` on the zip, grid checks, Install (`installWith`, Web Worker) | 17 of 17: 110 cards, 18 on, 18 design groups, the rule shown, every game file + ids.json byte-identical, state.json, 10 backups, worker |
| existing suites | `run_all.sh` (13 steps: the 8 of bldweb, `check_roundtrip.py`, `sync_css.py --check`, the 3 SC4 steps) | 13 of 13 (final run, pristine tree), the existing suites unchanged: golden 4 cases, install / re-install / restore, .zip route, 3 page cases, .bld reader 17 of 17, round trip 8 of 8, sc3ui.css in sync |
| renderer alone | 3 converted houses in `baked`, `baked_raw`, `baked_sharp` through `golden.mjs` | 13 of 13, 60 of 60 frames |

Python side: `sc4conv.py` 5.7 s, then `bldimport.py pack` of the 18 (the whole golden setup, two sc4conv runs and the
pack, 46 s). Page side in node: 2.1 to 2.6 s convert, 7.7 s render + pack.

## 3. How byte identity was reached

- **Numbers printed as Python prints them.** `'%.5f' % x` rounds the exact binary value half to even, keeps the
  sign of `-0.0`, and differs from JS `toFixed` on exact ties (JS rounds them up): `pyFixed` does the decimal
  expansion with BigInt. `round(x, n)` = that string parsed back, `repr` = JS's shortest digits laid out in
  Python's fixed / exponent rule, `json.dump(indent=1)` with a `PyFloat` marker so `1.0` prints as `1.0`. The
  merge reads the old `models.json` with a parser that keeps int vs float and compares with Python's `==`
  (`1 == 1.0 == True`).
- **The camera fit made portable on both sides.** `views.fit_camera` used `np.linalg.lstsq` (LAPACK) and
  `hidden_faces` a BLAS matmul, whose rounding JS cannot reproduce. Both now use plain float arithmetic in a fixed
  order (normal equations, Gaussian elimination with partial pivoting, sums in point order), the same steps in
  `sc4web.js`. The Python output did not change: all 661 files of the pack are byte-identical before and after.
- **numpy's float32 `power` is not correctly rounded.** The `baked` tone is `np.power(y, 0.75)` on float32. Over
  every luminance a texel can give (641,191 distinct float32 values, both matmul paths) numpy differs from
  `fround(Math.pow)` on 67. `bldweb.js` carries those 67 as a table (input bits, numpy result bits). Measured with
  this PC's numpy 2.5, as the OpenBLAS note of the bldweb round [another CPU's numpy not measured].
- **Python's own orders kept**: the plugin walk (files sorted, then folders, depth first), the TGI index where a
  later file wins but keeps the first position, the stable sort on the lower-case name, numpy's min / max keeping
  the later of two equal values (`0.0` / `-0.0`), `read_fsh` decoding every bitmap of a texture file.
- Textures: the Python tool writes PNG through Pillow (deflate), the page stores them uncompressed, so the PNG
  bytes differ and the pixels are compared (RGBA). The renderer reads pixels, and every frame and game file is
  byte-identical.
- atan2 / asin come from the browser's maths library. They only pick the SC4 view per SC3 slot (the nearest of
  four angles 90 degrees apart) and the camera angles rounded to 0.01 in `x_sc4`. Equal on this pack.

## 4. bldweb.js additions (bldrender's task sc4conv parts)

Texture alpha (PNG alpha band or tRNS, kept when a texel is below 128), `sc3slot<r>` groups drawn in slot r only,
depth peeling up to 4 layers (`rasterize(zmin)`), styles `baked` / `baked_raw` / `baked_sharp`. With the `sun`
light and diffuse 0 (the baked styles) the light is the ambient alone, so the page skips the shadow map
(bldrender computes it and multiplies it by 0). Models without alpha or slot groups render as before: the existing
golden, install, zip and page suites pass unchanged.

## 5. Page fixes found on the way

- **3D preview textures** (pre-existing, every OBJ model): the page's URL modifier passed every `blob:` URL
  through, and a texture named in an MTL loaded from a blob URL resolves to `blob:file:///<name>`, which is no
  blob. So textures never reached the preview or the thumbnails. It now passes through only the blob URLs it made.
- SC4 previews show the SC3 slot 3 group (SC4's front view) with the cut-out alpha, and the thumbnail waits for
  its textures.
- `check_roundtrip.py` (pre-existing flakiness): it read the page with `--dump-dom`, which fires when Chrome's
  virtual-time budget runs out, often before the self-test has written its result. Main's page failed 2 of 4 runs
  alone and every run inside the full suite. It now watches the page over the DevTools protocol until the title
  says the self-test is done (at most 180 s), as `pagetest.mjs` does, and stops the Chrome it started by PID. The
  old `--dump-dom` run stays as the fallback without node.

## 6. In game

**The install the page made grows.** The page itself (headless Chrome, `pagetest.mjs --case sc4 --sc4zip --apply`)
opened the JMyers zip, converted it and installed the 18 enabled designs into `dev\sc4web\tree` (the folder
pickers need a real click, so the driver writes what the page wrote, temp + rename). Then `bld_lab.py --tag page1`
(test slot, windowed 1600 x 1000, posted input only, mods of `dev\sc4web\inst`, churn `anarchy_res=5000`, speed
4, autosave every 150 s, Sacramento), the same recipe as the sc4conv round.

| save | game-run minutes | stock occupants | converted lots | per design |
|---|---|---|---|---|
| 1 | 2.4 | 11,882 | 84 | 2 to 8, all 18 designs |
| 3 | 5.0 | 11,640 | 117 | 2 to 10 |
| 4 (stop: every id at 3 or more) | 7.5 | 11,579 | 99 | 3 to 10 |

Save 2 read back the same numbers as save 1. Faults: only the `0xC0000096 at SC3U.exe+0x84122` line every lab run
logs at start. After the run the page's Remove (`--action remove --apply`) restored 11 files and deleted the
created `.DAT`: every file under the tree's `mods` equals the release stage again (153 of 153 hashes). Run files:
`runs/page1/` (`counts.json`, `resize.log`, `fd/*.png`, 39 dumps, `saves/`), no BMP left.

Pictures (`owner_shots/`, local only: they show the pack's houses):

- `01_sacramento_page_install_zoom4.jpg` (820 x 1284, phone-sized portrait): one Sacramento street at zoom 4, 11
  converted houses of 9 designs boxed in yellow among stock houses, a numbered legend with the SC4 names. The
  houses were found in the dump by their own frames (the game draws them pixel for pixel; finder from
  verify/sc4conv/work/find_in_dump.py, frames from the Python cache, byte-identical to the page's).
- `02_sacramento_page_install_zoom4_unmarked.jpg`: the same street without boxes.

The look matches the sc4conv round's `baked` houses (that round's section 5): they sit among the stock houses, softer
edges and roofs as seen from higher up.

## 7. Limits (also in the guide)

What the Python prototype measured (verify/sc4conv/RESULTS.md 6) holds for the page: light painted in and lit from
the screen side (the other side from the stock neighbours in view rotations 1 and 3), roofs as seen from 45 degrees,
one wall stretched in each view, no lot props or textures, the yard dropped, residential only. Other SC4 packs are
not tested [UNCERTAIN: BATs with a custom LOD mesh, props, night parts, DBPF index minor 2]. The readers stop on
what they do not know (other vertex formats, PROP / REGP entries, several meshes per view) and the page skips that
building with a log line. ZIP64 and encrypted archives are refused with a message.

## Files

`re/tools/bldimport/sc4web.js` (new), `bldweb.js`, `classifier.html`, `sync_css.py` (publishes sc4web.js too),
`webtest/sc4_golden.mjs` (new), `webtest/sc4_conv_check.mjs` (new, convert a folder or zip from the command line),
`webtest/golden_setup.py` (case sc4), `webtest/pagetest.mjs` + `pagetest.js` (SC4 case, open action),
`webtest/run_all.sh`, `check_roundtrip.py`, `re/tools/sc4conv/views.py`, `docs/buildings/index.html` (SC4 section),
`docs/buildings/importer/` (published copy). In MAIN: `verify/bldpack/work/guide_template.html` (SC4 section),
`verify/bldpack/work/make_zip.py` (ships sc4web.js in the pack's importer folder), `verify/sc4web/work/shots.py`
(owner pictures). New files under `re/tools/` need `git add -f` (`.gitignore` line 69, `/re/tools/*`).

The sample pack zip's `importer\` folder needs the orchestrator's rebuild (make_zip.py) to carry sc4web.js. The
published copy in `docs/buildings/importer/` is updated (`sync_css.py --publish`).

Whole suite: `test-slot bash re/tools/bldimport/webtest/run_all.sh <work> <pristine tree> <stage\kits> <SC4 .zip> <the same download unpacked>`.
