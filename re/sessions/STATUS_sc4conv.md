# STATUS sc4conv (round 2026-11-18h): SimCity 4 building converter prototype

## goal
SC4 -> SC3U building converter prototype: DBPF / QFS / S3D / FSH / exemplar / LText readers, S3D geometry space and
per-view culling decided by renders, OBJ + MTL + PNG + models.json export, render with bldimport, grow 6+ designs in
Sacramento, pictures, report. Brief: re/sessions/ROUND_2026-11-18h_sc4_convert.md. Results: verify/sc4conv/RESULTS.md.

## verdict + deciding evidence
**Done (2026-11-18).** The prototype converts the owner's JMyers Homes Pack end to end: 110 buildings out, the 18
enabled designs (one colour each) all grew in Sacramento by the first autosave (2.4 game-run minutes, 106 lots,
3-11 per design, the 2x2 Empire included). The page route (bldweb.js reading .dat) is sized in RESULTS 7.

- Readers checked on the whole pack: DBPF 19 of 19 files, QFS 7,434 of 7,434 entries, S3D 2,560 of 2,560 (to the
  exact file end), FSH 4,760 of 4,760 (DXT1 / DXT3), every exemplar and lot. Formats: re/analysis/SC4_FORMATS.md.
- Geometry: each zoom-5 view is the 7-corner bounding box with the BAT render projected on it (440 of 440, affine
  fit error <= 0.50 px). One camera for all views (elevation 44.5-45.5, azimuth 22.5 off the axis), the model turns
  per view. There is no 3D house in the files.
- Decided by renders (owner_shots 01): SC3 slot r draws the SC4 view 22.5 degrees from it (0 E, 1 N, 2 W, 3 S) plus
  the box's back walls + floor as a fill. Mixing views per wall leaves holes.
- Light: SC4 renders are about half as bright as stock art (structure luminance p50 0.203 vs 0.400). Style `baked`
  (unlit + tone 0.75 / 1.33) measures 0.242 / 0.402 / 0.730 vs stock 0.201 / 0.400 / 0.688. In game `baked_raw`
  reads as burnt-out next to stock houses, `baked` fits: `baked` is the converter's default.
- Not convertible: the SC4 light is fixed to the screen (converted frames lit on the left in all 4 slots, right/left
  0.63-0.67, stock 0.81 / 1.27 / 0.81 / 1.23), the 45-degree camera, hidden parts of non-box houses, lot props
  (BSC dependencies), foundations, night textures. RESULTS 6.

## built
- `re/tools/sc4conv/`: dbpf.py, exemplar.py, s3d.py, fsh.py, catalog.py, views.py, reproject.py, sc4conv.py.
  `py -3.12 re/tools/sc4conv/sc4conv.py <SC4 folder> --out <folder>` then `bldimport.py build <folder> --game <g>`.
- bldrender.py, task sc4conv block: texture alpha with depth peeling (`SC3BLD_ALPHA=0` off), OBJ groups
  `sc3slot<r>` drawn only in slot r (`SC3BLD_SLOTGROUPS=0` off), styles `baked`, `baked_raw`, `baked_sharp`.
  Inert for existing models: calibrate 0 of 160 frames differ; 80 of 80 sample-pack frames byte-identical to main's
  renderer; web golden (webtest golden_setup + golden.mjs, all 4 cases, frames): 52 of 52 PASS.

## proven game-side vs static only
- Game-side: 18 of 18 designs grow (verify/sc4conv/runs/run1, counts.json); bldimport check 18 of 18, 20/20 frames;
  in-game pictures found by template match of the rendered frames (56 matches). Only the usual start-up
  `0xC0000096 at SC3U.exe+0x84122` fault line.
- Static only: the readers' DXT5 / packed-pixel FSH formats and DBPF index minor 2 (not in the pack; DXT5 / DXT3
  checked on synthetic blocks), other SC4 packs (custom LOD meshes, props, commercial / industrial), the class rule
  for medium / dense / wealthier SC4 buildings.

## blocked on
nothing

## files owned
- dev\sc4conv\wt\re\tools\sc4conv\ (new): dbpf.py, exemplar.py, s3d.py, fsh.py, catalog.py, views.py, reproject.py,
  sc4conv.py. **Under the deny-by-default rule `/re/tools/*` (.gitignore 69): needs `git add -f`, as
  re/tools/bldimport/ has, or an allowlist entry.**
- dev\sc4conv\wt\re\tools\bldimport\bldrender.py (modified)
- dev\sc4conv\wt\re\analysis\SC4_FORMATS.md (new)
- MAIN\re\sessions\STATUS_sc4conv.md, MAIN\verify\sc4conv\RESULTS.md
- NOT for git (local, pack-derived, licence forbids redistribution): MAIN\stage\sc4conv_out\ (110 converted
  buildings), MAIN\verify\sc4conv\owner_shots\ (13 JPEG), verify\sc4conv\runs\, verify\sc4conv\work\ (scripts:
  decide.py, cmp_styles.py, lum.py, shots_offline.py, shots_game.py, find_in_dump.py). All gitignored.

## game-harness need
dev\sc4conv\tree only. The tree still has the 18 converted buildings installed (`bldimport.py restore --game
dev\sc4conv\tree` takes them out); prune the child as usual.

## asks of other sessions
- bldweb.js owner (page route, RESULTS 7): port the three bldrender additions (slot groups, alpha peel, `baked*`
  styles + tone) and the SC4 readers; until then the page stops on a converted folder with "render style baked".
- Owner calls: `baked` vs `baked_raw` brightness (shots 02, 11, 15); whether converted SC4 houses lit on the other
  side in view rotations 1 and 3 is acceptable.
