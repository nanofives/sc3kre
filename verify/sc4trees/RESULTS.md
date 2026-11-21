# sc4trees: black patches on SC4 tree props (2026-11-20)

Owner: "Fix the black patches on tree props: yes" (verify/lotshape/RESULTS.md section 5, owner_shots/04).
Worktree `dev\sc4trees\wt` (branch child/sc4trees, from main 0a4b357). No git add / commit.

## 1. Verdict

The cause is in the frame renderer, not in the FSH reader, the alpha handling or resampling. bldrender.py and
bldweb.js peel through transparent texels **at most 4 times** (`PEEL_LAYERS = 4`). A converted SC4 lot stacks more
see-through surfaces than that. A sample still on a clear texel after the 4th peel was drawn with that texel's colour,
and in SC4 prop textures that colour is (0, 0, 0). Fix: peel until no sample is left on a clear texel (cap 256), in
Python and in the page, with the same arithmetic, so byte identity holds.

## 2. Evidence

**The textures are decoded right and their alpha is 1-bit.**

- Hagia Sofia's 48 prop textures are all FSH code 0x60 (DXT1), read from the install (`fshfmt` probe). Alpha values
  are {0, 255}, and every clear texel decodes to (0, 0, 0, 0). In DXT1, when c0 <= c1, index 3 is transparent black
  (`fsh._dxt_colour_block`), so black under alpha 0 is what the format holds, not a decoder fault.
- Every prop PNG the converter wrote: install, 113 buildings, 415 textures, all alpha 0/255 with RGB 0 under alpha 0.
  JMyers + BSC + install props, 135 textures, all alpha 0/255; 31 of them keep a non-zero colour under alpha 0.
- bldrender samples the nearest texel and tests alpha < 0.5. So premultiplied vs straight alpha, the threshold and
  colour bleeding under resampling cannot produce these pixels.

**Peel depth decides it.** Hagia Sofia, `sc4conv.py <install> --only Lm76x60_HagiaSofia_04C9` (61 files, the same
lot lotshape converted), bldrender, zoom 3. Near-black pixels = opaque with max(R, G, B) < 24:

| peels | slot 0 | slot 1 | slot 2 | slot 3 |
|---|---|---|---|---|
| 4 (main) | 977 | 406 | 221 | 724 |
| 16 | 0 | 0 | 0 | 0 |
| until none open (fix) | 0 | 0 | 0 | 0 |

Rasterize passes the frames need (first pass + one per peel): zoom 0: 16, 17, 14, 19; zoom 3: 19, 18, 15, 19; zoom 4:
20, 18, 15, 19. Each prop is a view box whose front faces, two back walls and floor (views.hidden_faces) are clear
around the tree. A line of sight through a few overlapping trees and the house box crosses a dozen or more clear
surfaces before it reaches a texel or the lawn. The installed frames of the 4-peel copy: zoom 0: 0, zoom 1: 22 / 13 /
8 / 15, zoom 2: 201 / 76 / 38 / 148, zoom 3 as above, zoom 4: 3,908 / 1,624 / 884 / 2,896 near-black pixels. The fixed copy: 0 in all 20 frames.

**How widespread it is (zoom 3, the four slots).** Survey of every converted model: samples still on a clear texel
after the 4th peel, as pixels of the opaque frame:

| set | buildings | with such pixels | frames | pixels | most passes needed |
|---|---|---|---|---|---|
| SC4 install (civic, parks, rewards, landmarks) | 113 | 76 (67 of them on) | 274 of 452 | 85,335 | 18 |
| JMyers + BSC + install props | 110 | 110 (74 on) | 412 of 440 | 32,698 | 16 |

The worst on the install: Cemetery (2,287-2,819 per frame), the second Cemetery, Jefferson Memorial, Columbia Seafirst
Center, American Museum of Natural History, Hagia Sofia (321-1,931). The pixel count includes pixels where only some
of the 16 samples are affected, so it is larger than the near-black count. JMyers houses: 413-676 per frame
(their own view box with back walls and floor + props).

## 3. The fix

| file | change |
|---|---|
| `re/tools/bldimport/bldrender.py` | `PEEL_LAYERS` 4 -> 256 (guard only; `SC3BLD_PEEL=4` gives the old frames). `rasterize(box, open_)`: a peel draws only inside the box of the open samples and skips a triangle whose box holds none (summed-area table). The peel loop re-tests only the samples the last peel refilled. Every sample is computed with the same expressions, so the frames equal an unclipped loop |
| `re/tools/bldimport/bldweb.js` | the same three steps (`PEEL_LAYERS = 256`, `rasterize(..., box, open)`, `chk`) |
| `docs/buildings/importer/bldweb.js` | `sync_css.py --publish` copy |
| `re/analysis/SC4_FORMATS.md` | section 9.5 |

Checks of the speed-ups:

- Hagia Sofia zoom 3, new loop vs a plain unclipped rasterize on every peel: 4 of 4 frames byte-identical.
- The re-test-only-refilled step: 4 of 4 frames byte-identical to the version without it.
- With `SC3BLD_PEEL=4`, the new code reproduces the 1,000 frames of `verify/sc4cmp/work/conv` (50 buildings x 5 zooms
  x 4 slots, rendered with main's code), 1,000 of 1,000 identical.

Time, Hagia Sofia's 4 zoom-3 frames: 8.5 s before, 12.4 s after. Before the speed-ups, a full loop took 32 s.

## 4. Python = page, and the goldens

`run_all.sh` with all six arguments, `SC3PACK_PACKS=MAIN\stage\st_packs`, `SC4INSTALL=<SimCity 4 Deluxe>`,
`PROYECTOS_TEST_HUB=off`, `PROYECTOS_TEST_MEM_GB=6`, test slot (`dev\sc4trees\work\suite.sh`, logs `dev\sc4trees\work\new.log`,
`base.log`):

- Branch: **41 of 42**. The failure is step 36 (`pagetest.mjs sc4install --sc4grow`, opening only, no frames): it
  printed nothing for 10,010 s, while my survey, the forum renders and the game ran on the same PC. I stopped that node
  and its Chrome by PID. **Re-run alone on the branch: 5 of 5 passed in 238 s.** No cause found for the hang
  `[UNCERTAIN: not reproduced]`.
- Main's code (MAIN checkout), same inputs, right after: **42 of 42**.
- Every SC4 frame check that renders props passed on the branch, Python = page, byte for byte: `sc4_golden`,
  `sc4_packs`, `sc4_props` (31 frames changed), `sc4_install` (60), `sc4_baseprops` (410), `sc4_lottex` (20).

Every Python output of the two runs compared file by file (`verify/sc4trees/work/golden_diff.py`, output
`golden_diff.txt`): **39,793 files the same, 661 differ, none missing on either side.** The 661:

| files | why |
|---|---|
| 98 `sc3build/<stem>/meta.json` (every case, SC4 or not) | only `key`: the render cache key hashes `bldrender.py`. The rest of each meta.json is equal (checked) |
| 521 SC4 frames (`sc4baseprops` 410, `sc4install/sub` 60, `sc4props` 31, `sc4lottex` 20) + 33 `sheet.png` | the fix |
| 4 `B1D10001_bldimport.DAT` (sc4baseprops x2, sc4props, sc4lottex) + `sc4install/sub` `bldimport.dat`, `bldimport_rewards.dat` | the game files that hold those frames |
| `sc4baseprops/counts.json`, `sc3pack_pagetest.json`, `sc3pack_classifier.png` | the work folder's path (base vs new) and timings |

**No frame or game file of a non-SC4 case changed** (testmodels, bld, kenney, styles, ports, landmarks, civic,
lotshape, landmarkdesc, sc3pack: only meta.json keys). The JMyers case without props (`py/sc4`) and the tower
(`sc4packs/goc`) kept their frames.

Step times, branch vs main: the frame-heavy SC4 steps took about the same time when the PC was quiet
(`sc4_install.mjs` 523 / 502 s, `sc4_baseprops.mjs` 69 / 71 s, `sc4_lottex.mjs` 59 / 63 s). The early steps ran slower
on the branch while the survey ran next to them (the font checks too, 14 / 8 s, and those draw nothing).

## 5. In game

Tree `dev\sc4trees\tree`, Madison, windowed, posted input and Frida game calls (`verify/sc4trees/work/lab.py`, lotshape's
lab pointed at sc4trees). One models folder (`dev\sc4trees\work\lab`) with Hagia Sofia twice: `HagiaOld` frames
rendered with `SC3BLD_PEEL=4` (main's frames), `HagiaNew` with the fix. Installed with `bldimport.py build --game
tree` as landmarks 38000 / 38001. Placed with the building layer vt+0x38: 38000 at (185, 203), 38001 at (191, 203),
both `placed: 1`. Game PID 10564, started by `sc3dev.ps1 run sc4trees`, stopped by PID. The only VEH FAULT line is
the game's own startup `0xC0000096 at SC3U.exe+0x84122`.

| check | result | picture |
|---|---|---|
| zoom 3, 4 rotations | the 4-peel copy shows black patches under its trees in every rotation, the fixed copy none | `01` |
| zoom 4, 4 rotations | the same, larger | `02` |
| offline frames, zoom 3 and 4, slots 0-3 | before / fixed, row by row | `00` |

Pictures: MAIN `verify/sc4trees/owner_shots/` 00-02 (SC4 art, local only).

## 6. Forum pictures (verify/sc4cmp, section 6 recipe)

The SC3 column comes from bldrender frames, so it changes with the fix. The SC4 column is painted back to front with no
peel limit, so it does not. Re-rendered a copy of `verify/sc4cmp/work/conv` (`dev\sc4trees\work\cmpconv`): 41 of
the 50 buildings' zoom-4 frames change. Rebuilt `verify/sc4cmp/forum` with `compare_sheet.py` from that copy (the old
set is kept as `verify/sc4cmp/forum_before_sc4trees`).

The published set is not reproducible on main's code even with the old frames: built from the 4-peel frames into a
scratch folder, 9 of its 17 pictures differ from the published files, and `sheet.json` changes Ferrara's
`scale_vs_zoom4` from 1.353 to 1.29. That comes from converter or compare_sheet changes since sc4cmp (sc4ground,
lotshape), not from this fix `[cause of that drift not traced]`. Against that old-frames build on main's code, the fix
changes **11 of 17 pictures**: 00 and 01 small police station, 02 courthouse, 03 gazebo, 07 retail stores, 08 LAM
banking, 10 Eyler refining, 12 Pumpkin Acres, extra lee_avionics, extra small_fire_station. `sheet.json` is the same.

## 7. Files

Code (worktree, to commit by path): `re/tools/bldimport/bldrender.py`, `re/tools/bldimport/bldweb.js`,
`docs/buildings/importer/bldweb.js`, `re/analysis/SC4_FORMATS.md`. Records (MAIN): `re/sessions/STATUS_sc4trees.md`,
`verify/sc4trees/RESULTS.md`. Local only: `verify/sc4trees/owner_shots/`, `verify/sc4trees/work/` (lab.py, shots.py,
golden_diff.py, golden_diff.txt, resize.log, fd/), `verify/sc4cmp/forum` (rebuilt) and `forum_before_sc4trees`.
