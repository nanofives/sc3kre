# sc4art results (round 2026-11-24): artifacts on converted SC4 buildings

Owner 2026-11-24: "I still see artifacts on most SC4 buildings in the post" (`verify/forumshots/owner_sc4_artifacts.jpg`:
Mayor's House, Hagia Sofia, Alamo, Small Police Station). SC4 install read in place. Pictures with SC4 art are local only
(`owner_shots\`, `fd\`, `runs\`, `verify\sc4cmp\forum\`, `dev\sc4art\work\`, all gitignored).

**Verdict.**

| artifact (owner crop) | cause, measured | change |
|---|---|---|
| Mayor's House lamp posts as tall grey slabs | the lamp prop `C1x1x8_$$$lamppost_1DFC` has 7-vertex views made of crossed billboards. `views.hidden_faces` treated any 7-vertex view as a box and added back walls and a floor whose projected uv fall outside the lamp's piece of SC4's shared prop atlas (texture 1ABE787D-1E020410), on the stair art next to it | **fixed**: `views.is_box` (7 distinct corners of the bounding box) |
| Small Police Station lamp posts as thick grey panels | `C1x1x8_$$lamppost_1DFB` is a real 1 x 1 x 9 m box view with the pole on its axis. SC3's camera sees the pole on both front walls and, through their clear texels, on the back walls: up to four poles side by side | **fixed**: `views.thin_billboard`, a box no wider than 1.5 m and at least 3 times as tall is one plane through its axis |
| Hagia Sofia: sliver in the air left of the minaret, flat wedge on the right minaret | faces of SC4's own view-N mesh that are mostly transparent proxies (skirts round the minarets 19.4 m up, 65 to 96% of their texels clear) whose every opaque texel is hidden, in SC4's own view, behind the minaret faces 10 to 21 m nearer SC4's camera. SC4's z-buffer never draws them; SC3 drew the minaret a second time on them | **fixed**: `views.proxy_hidden`, a face at least half clear loses its hidden texels (layered textures) |
| The Alamo: loose fragment on the ruined right side | the hull face x = 13.23 m of view S, seen at 67.5 degrees. View W (frontal) shows a 6 m gap between two wall blocks there with rubble on the ground; view S's oblique rays reach that rubble behind the hull and paint it at 2 to 6 m up. The same hull-in-front family as firedist's door wall | **not a converter fault**, unchanged |
| Police cars as white blobs | the baked tone (y' = 1.33 y^0.75) lifts the cars' black body panels: 25% of the car texels sampled are darker than 60, 2.7% of the output pixels | **owner call** (style). `baked_raw_sharp` keeps them black and white (`owner_shots\02`) |

Python = page byte for byte. Full suite **41 of 41**. Non-SC4 goldens **1,414 the same as main, 0 differ**.

## 1. How the pixels were traced

`dev\sc4art\work\tools\trace.py` runs bldrender's `render_frame` exactly as `bldimport.render_one` does (turned looks
included) with one hook: the final face id of every sample after peeling, per pixel, plus each face's material,
position and uv (`who.py` lists the faces under a box of pixels, `uvdraw.py` draws their uv on the texture). `occl.py`
and `ownvis.py` rebuild SC4's own z-buffer of one view in texture space (projection fitted on the faces, depth along its
null direction) and mark which opaque texels of a face lie behind a nearer face. `unfold.py` (firedist) lays a wall plane
flat as each SC4 view paints it.

- Mayor's House slot 3, the slab at frame x 72-88, y 38-88: 553 of 800 pixels on faces 893/894 (material
  `sc4p_1ABE787D_1E020410`), a vertical quad at u = 0.29 tile, 9 m tall: the back wall of the lamp's view box. Its uv
  (u 0.775-0.813, v 0.08-0.32) lies left of the lamp in the atlas, on the stair art. The lamp's own faces (886-892) are 7
  triangles over 7 vertices that are not box corners.
- Police slot 2: the columns are faces 67-86 of `sc4p_1ABE787D_1C770430`, two 0.06 x 0.06 x 0.56 tile boxes with fill.
- Hagia Sofia slot 1: the sliver is faces 162-179 of `sc4_N` (horizontal at 19.4 m along the lot edge, 4 to 33% opaque).
  Every opaque texel of them is behind faces 168/169 (the minaret), gap 8.9 to 22.8 m. The wedge is faces 116/117
  (117: 3,002 texels, 1,942 clear, 947 opaque behind faces 104/112/113/115, 113 its own: a tree crown).
- Alamo slot 3: the fragment is faces 8/61/62 of `sc4_S`, the plane u = 28.2 m (model x = 13.23 m), 0 to 13 m; no texel
  of them is hidden (0 of 1,714 / 2,270 / 132). `owner_shots\03` is the plane unfolded from the four views.

## 2. The proxy rule and why it stops at half clear

A first rule cleared every hidden texel of every face ("SC4's z-buffer owns the texel"): the shards went, and holes
opened in Hagia Sofia's roofs, because the minarets' proxy triangles also cover roof that SC4 draws on them
(`owner_shots\04`). So only proxies lose texels: a face whose centre-test texels are at least half clear.

Over the install (423 models), 58,591 faces of 365 models have hidden opaque texels. Their clear share by tenths, faces
(hidden texels): 0-0.1 49,107 (55.6 M), 0.1-0.2 2,715, 0.2-0.3 1,772, 0.3-0.4 1,152, 0.4-0.5 873, 0.5-0.6 731, 0.6-0.7
629, 0.7-0.8 512, 0.8-0.9 491, 0.9-1 609 (15,937). The count falls steadily: there is no gap at one half. The owner's
shard faces are at 0.65 to 0.96, so any threshold from 0.3 to 0.65 removes them; a solid face (under 0.1) is never
touched. Rule details: `re/analysis/SC4_FORMATS.md` section 15.

## 3. Counts (full install, `work/full_before` = main 1158ba62, `work/full_after` = this branch, `work/counts_full.json`)

| | |
|---|---|
| models whose files change | 302 of 423 (214 growable, 34 landmark, 33 reward, 21 civic) |
| proxy faces cleared | 2,972 faces in 280 models, 429,864 texels, in 1,377 new layer textures |
| house OBJ changed | 282 (280 by the proxy rule, 2 by the box test: Euro Small Shop 1 and the Lifeguard Tower, whose own views are 7-vertex non-boxes) |
| prop models with 7-vertex non-box views (fill dropped) | 8 of 366 read: Planter-Wood3, Dumpster, Dumpster lid open, lamppost 1DFC, Mike's Art Banner, 3 Taco Stand signs; 37 prop rows on 22 models |
| thin billboards | 5 prop models: lamppost 1DFB, two phone booths, drive-in audio posts, generic street sign; 109 prop rows on 35 models |
| forum set (30 models, `work/forum_cmp.json`) | the sheet slot's zoom-4 frame changes visibly (a pixel moved by more than 48 or its alpha) on 16 sheets; on the others it is byte for byte or within 1 px |

Most of a frame's differing pixels come from the 255-colour palette cut: any change re-picks the palette. The
before/after crops of the largest changes (`work/samp/dc_*.png`) show the structural change only where faces changed.

Sample looked at (zoom 4, every slot, before / after, `work/samp/`): CN Tower, Hagia Sofia, St Basil's, Schloss
Neuschwanstein, Opera House, Convention Center, Taj Mahal, Launch Pad, Empire State Building, Coit Tower, Country Club,
Deluxe Fire Station, 8 growables. Floating copies of domes, minarets and spires shrink or go; no hole was seen.

## 4. Sheets (`verify/sc4cmp/forum/`, old copies `*_pre_sc4art.jpg`)

Re-made with forumshots' `sheets.py` pointed at this branch (`work/tools/sheets.py`, police added, its four-sides
picture too) and this branch's forum conversion (`work/fo_after`). The 14 sheets whose frame did not change come out
byte for byte equal to the published ones (0 pixels moved by more than 24), so only the changed ones were replaced:
00 and 01 Small Police Station, 02 Courthouse, 03 Gazebo, 05 Independence Hall, 10 Eyler Refining, 13 Mayor's House,
14 Hagia Sofia, 16 Main Library, 19 Small Fire Station, 20 Elementary School, 22 City Museum, 25 Maxis Theatre, 26 Walton
Plaza, 28 Dao Chemicals, 29 Tsvirkunov Electronics, extra/lee_avionics. Each looked at (`work/tr/contact_sheets.jpg`).
`sheet_sc4art.json` is the new report.

In-city strips from new game frames (`dev\sc4art\tree`, windowed, posted input and Frida game calls, harness claimed and
released) where the frame changed by more than 100 pixels or the building is placed:

- Madison: Gazebo, Small Fire Station, City Museum, Elementary School, Courthouse, Mayor's House, Independence Hall, Main
  Library, Hagia Sofia (forumshots' ids 38000-38028 kept by its `ids.json`), placed with `lab.py place`, four rotations at
  1430 x 900 (`fd\city\`). Police station in a second game (id 38029). Matched at RMS 2.7 to 3.5, except Courthouse
  15.0, Independence Hall 8.2, Hagia Sofia 8.4 (the no-power bolt blinks over it), Main Library 17.2 (a pylon in front):
  looked at, the right buildings with neighbours in front.
- Dao Chemicals and Tsvirkunov Electronics: forumshots' last industry save (`runs/ind/saves/save09.sc3`) loaded with churn
  off (`grow_lab.py --from-save`, same lots as forumshots). Tsvirkunov matches at RMS 31.3 (a grown neighbour in front;
  only save09 holds it, save06-08 do not): the wrapper admits up to 32^2 (compare_sheet's limit is 30^2, every other
  entry is within it).
- Walton Plaza (12 px) and Lee Avionics (2 px) keep their old strips. Eyler Refining and Maxis Theatre have no strip.

Found on the way: compare_sheet draws its SimCity 4 column through `props.prop_views`, so the thin-prop rule changed SC4's
own picture of props (Chez Eyler, 1,405 px). `prop_views(..., billboard=False)` from compare_sheet keeps SC4's box; Chez
Eyler then reproduces byte for byte.

Game PIDs started and stopped by this session: 1452, 5008 (grow_lab), 11820, and three grow_lab runs on save06-08
(nothing to shoot). Only the start-up `0xC0000096 at SC3U.exe+0x84122` in every run. No BMP left.

## 5. Checks

- Python = page: `work/tools/parity.mjs` (firedist's, on this worktree) on Small Police Station, Alamo, Mayor's House,
  Hagia Sofia: **188 files, 0 differ** (layer textures, OBJ, MTL, models.json `x_sc4.proxy_hidden`, billboard props).
- Full suite, normal mode: `SC4INSTALL=<Steam SimCity 4 Deluxe> SC3PACK_PACKS=MAIN\stage\st_packs PROYECTOS_TEST_MEM_GB=6
  PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh dev\sc4art\suite stage\release stage\kits
  "<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes stage\st_packs\sc4`:
  **41 of 41 steps passed**, wall 1,492 s (`dev\sc4art\suite_full.log`). The install set already holds the police
  station (billboard), Mayor's House (non-box lamp) and 22 models with proxy layers (up to 4 layers).
- Non-SC4 goldens: MAIN's `golden_setup.py` into `dev\sc4art\g_main`, `verify/lotshape/work/golden_diff.py` against the
  suite's `py\`: **1,414 the same, 0 differ, 0 only in main** (`dev\sc4art\golden_diff.txt`).
- `sync_css.py --publish`: `docs/buildings/importer/sc4web.js` = `re/tools/bldimport/sc4web.js`. No guide line: no
  stated limit changes.

## 6. Pictures (`owner_shots\`, local)

| file | what |
|---|---|
| 01 | the four buildings, sheet slot, before (main) and after |
| 02 | police cars: baked_sharp (default) and baked_raw_sharp |
| 03 | Alamo: the plane x = 13.23 m unfolded from views E N W S |
| 04 | Hagia Sofia: the rejected strict rule (holes in the roof) |

## 7. Files

Code in `dev\sc4art\wt` (no commit): `re/tools/sc4conv/views.py`, `props.py`, `sc4conv.py`, `compare_sheet.py`,
`re/tools/bldimport/sc4web.js`, `docs/buildings/importer/sc4web.js`, `re/analysis/SC4_FORMATS.md` (section 15).
Records (MAIN): this file, `re/sessions/STATUS_sc4art.md`. Local: `owner_shots\`, `fd\`, `runs\`, `dev\sc4art\work\`
(tools, conversions, counts), `verify\sc4cmp\forum\` (re-made sheets).
