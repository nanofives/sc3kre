# firedist results (round 2026-11-23c): the Large Fire Station's parking side, the per-face rule, two side findings

Owner 2026-11-23: "the geometry of the fire station has a weird distortion on the parking side" (sheet
`verify/sc4cmp/forum/18_large_fire_station.jpg`). First pass: cause found, no code (section 11 onwards). Owner answers
after it: "build per-face rule", a hand fix for the door wall (call (b)), investigate the Large Medical Center's floating
cars and the Soccer Field's missing pitch lines, leave the Soccer Field (call (a)). SC4 install read in place. Pictures
with SC4 art are local only (`owner_shots\`, `work\`, `sheets\`, `verify\sc4cmp\forum\`, all gitignored).

**Verdict.**

- **Per-face rule built, Python and page byte for byte.** A face the slot's own SC4 view saw at k >= 3.0 (k = SC3 view
  factor / SC4 view factor, texel stretch = k x 0.654) is drawn a second time 1 cm in front of itself, from the SC4 view
  that sees it most head-on, when that view's own mesh does not hide it. The copy is toned to SC4's right-wall light and
  cleared wherever the slot's own picture has no building, so it never draws outside the original outline. Over the 423
  models of the SimCity 4 install: **51 models, 516 faces, 92 slot frames** (35 growables, 9 landmarks, 5 rewards, 2
  civic). Of the 16 models measured in the first pass, only the Large Fire Station changes by this rule.
- **The door wall by hand.** `HAND_FACES` names the Large Fire Station (building exemplar 6534284A-07BDDF1C-030B0000 and
  model 5AD0E817-BADB57F1-030B0000, both must match), slot 0, plane +z = 15 m, from view S: 12 faces. Sheet 18 now shows
  the four arched bays and both trucks on that wall, and so does the game (section 5).
- **Large Medical Center: converter fault, fixed.** The cars at mid-wall height are a car cluster that SC4 places 17 m up,
  on the roof of a 5-storey parking garage prop. The converter dropped the garage because its S3D uses vertex format
  0x00000002, which `s3d.py` did not read. Formats 0x00000002 and 0x00140002 have the same 20-byte layout (install scan,
  section 7). Reading them places **268 more prop rows on 78 models** of the install, among them the garage and the
  shopfront props of SC4's small shops and retail stores (sheets 06 and 07 change).
- **Medical Center's "face with no texels":** 6 faces of slot 0 (view E) that view E saw at k 12.2. The rule now draws
  them from view S. With the garage in front most of that wall is hidden anyway.
- **Soccer Field: cause only (owner (a)).** The pitch lines are pale paint on grass (182 / 186 / 156) and the lawn test
  clears them with the grass. No colour or local-contrast rule keeps them without keeping specks of grass on every other
  SC4 lot (section 8). One guide line says so.
- **Checks:** Python = page on 7 buildings that switch faces or gain props (239 files, 0 differ). Full suite 41 of
  41. Non-SC4 goldens 1,284 of 1,284 the same as main (section 9).

## 1. The rule (`views.py` task firedist block, `sc4conv.write_edge`, `sc4web.js` edgeOn .. edgeMask)

Per slot, for every triangle of the slot's own view (after `clamp_ground`):

1. n = unit normal, c3 = SC3 slot camera (elevation 30 degrees, written out as constants so both sides have the same
   bits), c_v = the SC4 view's camera (`forward_model` negated).
2. Switch when n . c3 > 0, n . c_v > 0 and n . c3 >= 3.0 x n . c_v, the view w of largest n . c_w is not the slot's own and
   sees the face better (n . c_w > n . c_v), and w sees the face: at most 1 of 6 points of the face has a triangle of w's
   own mesh in front of it by more than 0.5 m at the same texture pixel (`seen_by`).
3. Plus `HAND_FACES` (section 6).
4. The copy: each face's three vertices moved 1 cm along n (never below y = 0), uv by w's fitted projection, material
   `sc4_<w>_slot<s>`, texture `<stem>_<w>_slot<s>.png` = w's picture x (0.5371, 0.5622, 0.7133) per channel, with every
   texel cleared whose centre or a corner falls on a copied face at a point the slot's own picture draws transparent.
   The own face stays behind the copy, so a cleared or transparent texel shows what the slot drew before.
5. `models.json` `x_sc4.edge_on`: per slot and substitute view the face count and the texels cleared. Absent on models
   with no switch, so their files are as before.

**Why k >= 3.0.** Over the 25,855 front-facing planes of the install's 423 models: 6,901 planes in 420 models sit at k 2.0
to 2.4 (the ordinary 67.5-degree wall of every building, theory 2.26), 79 at 2.4 to 2.8 (walls a few degrees off axis),
then a thin tail: 29 at 2.8 to 3.2, 27 at 3.2 to 3.5, 10 at 3.5 to 3.82, 18 at 3.82 to 4.5, 32 at 4.5 to 6, 86 above 6
(Columbia Seafirst Center 21 to 22, CN Tower 25, Fisk Insurance 12.8, Lincoln Memorial 6.9, the fire station's leaning
eave faces 5.55). 3.0 keeps every ordinary wall and the near-axis ones out and takes the tail. The door wall (k 2.25) is
in the ordinary cluster, so no threshold reaches it: hence the hand table.

**Why the tone constant.** SC4's light is fixed to its camera, so a wall a view sees as its frontal (left) wall is lit
brighter than the same wall seen as its 67.5-degree (right) wall, which is the light every other right-hand wall of an SC3
frame has. Measured on 1,612 vertical planes (k 2.0 to 2.4, 200 or more samples opaque in both views) of 140 models (every
third of the install): own view / most head-on view, sum of RGB per plane, median 0.5371 / 0.5622 / 0.7133, interquartile
0.441-0.726 / 0.469-0.739 / 0.631-0.843, per slot 0.51 to 0.56 red.

## 2. Seams, and what was changed for each

| seam | seen on | cause, measured | fix |
|---|---|---|---|
| copy too bright, gain at its limit | fire station slot 3 (first try) | the first try matched the tone to the own view's texels on the face. On an edge-on face those are what lies in front of it in that view (the pale eave cornice): gain 1.82 / 2.0 / 1.93 | the measured right-wall constant (section 1) |
| whole model 2.5 mm higher, every slot changed | fire station, Fisk Insurance (leaning faces, normal y -0.25 and -0.32) | the 1 cm lift moved the bottom vertices of a downward-leaning face to y = -0.0025, and bldrender sets the lowest point on the lawn | lifted vertices kept at y >= 0: the fire station's untouched slots are now byte for byte main's |
| pale panel of the tower top | Columbia Seafirst Center slots 1 and 3 | view W shows another part of the tower at those faces | occlusion test: slot 1 30 -> 4 faces, slot 3 24 -> 3 |
| slab in the air past the outline | Seafirst slot 3 | the faces lie partly outside the building in the slot's own picture (transparent there), w's picture is opaque there | mask by the own picture (step 4): 6,575 texels cleared on slot 0, 425 on slot 3 |
| 1-2 px line left at the slab's edge | Seafirst slot 3 | texels straddling a face edge with their centre outside were not masked, the renderer still samples them | footprint = centre or any corner inside |
| white strip at the tower corner, ghost chimney top | fire station door wall (first-pass mock) | the mock moved every +z face of slot 0, the tower's face too (the chimney ghost), and took the light of view S | the hand table names one plane only (no tower face), the tone constant. Left: view S's round turret lands on the flat plane as a short brick-and-stone strip at the wall's left end, and a sliver past the right corner, where the plane runs on under the eave (owner_shots 21) |
| leaning faces still streaky | fire station slot 3 (turned slot 2) | their upper part maps onto view W's eave | not fixed. Darker and in the right-wall light now, no windows (owner_shots 21, 22) |

## 3. Counts (full install, `work/full_before` = main's converter, `work/full_after` = this branch, `work/counts_full.json`)

| | |
|---|---|
| models with switched faces | 51 of 423 (35 growable, 9 landmark, 5 reward, 2 civic) |
| faces / slot frames | 516 faces in 92 slot frames (12 of the faces: the hand table) |
| texels cleared by the mask | 186,474 |
| house OBJ different from main's | exactly these 51 |
| prop rows placed | 5,010 -> 5,278 (+268 on 78 models), rows without a readable model 2,869 -> 2,601 |
| models changed by either | 122 |
| of the 16 first-pass models | Large Fire Station (rule + hand table), Large Medical Center (garage, 7 -> 8 props, 6 faces) |
| forum sheets whose frame changed | 3 of 29: 06 Small Shops (+1 prop), 07 Retail Stores (+3 props), 18 Large Fire Station |

## 4. Before and after (`owner_shots\`, zoom 4, the four slots as installed, before = main)

| picture | building | changed slots (differing px) | what to look at |
|---|---|---|---|
| 20 | Large Fire Station | turned 2, 3 (33,335, 28,529), 0 and 1 byte for byte | door wall in turned slot 3, leaning side in turned slot 2 |
| 21 | Large Fire Station, both walls at 3x (top turned slot 2, bottom turned slot 3) | | doors and trucks, turret strip, leaning side |
| 22 | Large Medical Center | all four, 55,683 to 75,800 (the garage) | the garage under the roof cars |
| 23, 23b | Columbia Seafirst Center | 0, 1, 3 (23,206, 61,160, 54,587) | the top of slot 3 (24 faces -> 3 with the occlusion test, no slab) |
| 24 | Fisk Insurance | 0, 2, 3 (61,861, 84,690, 155,689) | the leaning ground-floor skirt now shows the storefronts |
| 25 | Country Club | 0, 2 (17,632, 12,791) | the left tower in slot 0 |
| 26, 26b | Retail Stores (the sheet's variant), Small Shops | Retail 0, 1, 2 (15,208, 15,322, 8,657), Shops 0, 3 (6,056, 5,310) | the shopfront props |
| 27, 27b, 27c | The Alamo, Small Police Station, Soccer Field | none (0 px in every slot) | the controls |
| 28 | Soccer Field lot textures, lawn test off | | the pitch lines the lawn test clears |
| 29, 29b | in game, Madison, zoom 4, turned slots 3 and 2 | | door wall and leaning side in the city |
| 30, 30b, 30c | sheets 18, 06, 07 as re-made | | |

## 5. Sheets and game

- Re-made: `verify/sc4cmp/forum/06_small_shops.jpg`, `07_retail_stores.jpg`, `18_large_fire_station.jpg` (old ones kept as
  `*_pre_firedist.jpg`), with forumshots' `sheets.py` on this branch's `compare_sheet.py` (unchanged) and the forum set
  converted with this branch (`work/conv_forum`, ids identical to forumshots').
- In-city strips from new game frames (`dev\firedist\tree`, windowed, posted input and Frida game calls, harness claimed):
  - Large Fire Station: Madison, placed with `lab.py place` at (192, 207) (key 207EDC0E-B1D10002-947C, $500), zoom 4, four
    view rotations at 1430 x 900 (`fd\id38012b_z4_v*.png`). Matched at RMS 2.8 in slot 3, as forumshots' frame. A first copy
    at (197, 210) stood under a power line and was not used.
  - Small Shops and Retail Stores: forumshots' Berlin save (`runs\com\saves\save03.sc3`) loaded in this tree with churn
    off and the same 7 ids, `grow_lab.py --from-save` (`runs\shops2\`). Same lots and camera as forumshots: matched at RMS
    19.9 (was 19.8) and 16.5 (was 5.2: the lot in front of the retail store is a construction site this time). A first run
    with 2 ids shot the shop's lot while it was still being built and was not used.
- Game PIDs started and stopped by this session: 15444, 21304, 25060. Only the start-up `0xC0000096 at SC3U.exe+0x84122`
  in every run. No BMPs left.

## 6. The hand table: the Large Fire Station's door wall

SimCity 4's Large Fire Station has its four engine-bay doors under the roof, about 3.9 m behind the plane z = 15 m that
SC4's view meshes put at the eave line (0 to 10.9 m high). The yellow apron paint on that plane stops at 4.25 m in view S and
at 9.75 to 10.25 m in view E: the ground is 3.9 m and 3.8 to 3.95 m behind the plane. So view E, which SC3 slot 0 (the
sheet's turned slot 3) is built from, paints the covered apron floor, the truck and the flags over 9.75 of the plane's
10.9 m, while view S shows the doors (first pass, section 12, `work/unfold.py`, owner_shots 03). The plane is at k 2.25 in
slot 0: the ordinary cluster (section 1). A picture-agreement test does not single it out either: ordinary walls score -0.07
to 0.1 (correlation of luminance on the plane between the two views), this one 0.23.

`views.HAND_FACES` / `sc4web.js HAND_FACES`: (building tgi, model key) -> [(slot 0, normal (0, 0, 1), plane 15.0 m, view
S)]. A face of that slot within 0.01 of the normal and 0.05 m of the plane takes view S, drawn as the rule draws its copies
(1 cm in front, tone, mask). Only a building whose exemplar tgi and model key both match can be touched.

## 7. Large Medical Center

- `work/dump_rows.py` (the lot rows as `props.plan` sees them): row 19 `C16x7x3_$3LotCarCluster-01011_1E4E` at x -29.10,
  z -11.95, **y 17.00**, on row 12 `C14x30x18_$$$5StoryPG_CE030000` (x -32.95, z -8.95, state ok), outside the house (x -24
  to 24). `work/dump_why.py`: the garage row ends `unreadable`, why `vertex format 0x00000002 not read`.
- `work/probe_s3d.py`: its views' vertex groups of format 0x00000002 hold 20-byte vertices, 3 f32 position + 2 f32 uv: first
  vertices (-15.25, 0, 7.25 | 0.655, 0) and (15.25, 18.60, 7.25 | 0.522, 0.773), the 30.5 x 18.6 x 14.5 m garage.
- `work/scan_vfmt.py` / `scan_vfmt2.py` over every S3D of the install: format 0x80004001 165,193 vertex groups, 0x00000002
  1,526, 0x00140002 286, 0x80004101 2. With 20 bytes per vertex every S3D lands on its INDX tag except the 2 of 0x80004101
  (stay unread). uv outside 0..1: 7.3%, 1.2% and 14% of the vertices of the three read formats (tiling uv, as the
  standard format has).
- Fix: `s3d.VERTEX_FORMATS = (0x80004001, 0x00000002, 0x00140002)`, the same three in `sc4web.js`. The garage now stands
  under its roof cars in all four slots (owner_shots 22).

## 8. Soccer Field (left, owner (a))

- Its 27 lot texture rows are drawn (16 pitch textures 25C7..25D6). `work/soc_nograss.py` composites them with the lawn
  test off (owner_shots 28): the whole pitch with its lines. With the test on, 95.9% of the lot is cleared as SC4 grass.
- The lines are paint on grass: line texels median 182 / 186 / 156. Against the pitch grass: saturation median 0.35 against
  0.41, luminance 135 against 133, overlapping. No threshold on saturation separates them (`work/lawn_lines.py`).
- A local test (lighter than the 5 x 5 around it, `lawn_lines2.py`) keeps 1.7 to 3.3% of the pitch's lawn texels (the
  lines) and at the same time 1.0 to 4.8% of the lawn texels of every other SC4 lot texture (192 textures), which would
  speckle every converted lot with SC4 grass.
- Guide: one sentence added to the lawn bullet of the lot textures section.

## 9. Checks

- Python = page: `work/parity.mjs` (sc4web.js convert of the install against a sc4conv.py folder): fire station, Medical
  Center, Seafirst, Country Club: 148 files, 0 differ. Fisk Insurance, Retail Stores, Small Shops (growables): 91 files, 0
  differ.
- Suite set: `webtest/sc4_install_set.json` + the Large Fire Station (hand table, edge rule) and the Large Medical Center
  (format 0x00000002, edge rule), expect 30 cards, 25 on.
- Full suite, normal mode (`SC4INSTALL=<Steam SimCity 4 Deluxe> SC3PACK_PACKS=MAIN\stage\st_packs PROYECTOS_TEST_MEM_GB=6
  PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh deviredist\work stageelease stage\kits
  "<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes stage\st_packs\sc4`):
  **41 of 41 steps passed**, wall 1,270 s (log `deviredist\suite_full.log`), with the install set of 30.
- Non-SC4 goldens against main: MAIN's `golden_setup.py` (main 28f2eb1) into `deviredist\g_main`, compared with
  `verify/lotshape/work/golden_diff.py` against this run's `py\`: **1,284 files the same, 0 differ, 0 only in main** (all 10
  non-SC4 cases). The 2,273 files only in the branch are the `sc4` case, which main's setup did not run (no `--sc4`).
- Importer copy published (`sync_css.py --publish`, `--check` in sync before): of the five copied files only
  `docs/buildings/importer/sc4web.js` changed, now byte for byte `re/tools/bldimport/sc4web.js`.

## 10. Files

Code in `dev\firedist\wt` (no commit): `re/tools/sc4conv/views.py`, `re/tools/sc4conv/sc4conv.py`,
`re/tools/sc4conv/s3d.py`, `re/tools/bldimport/sc4web.js`, `re/tools/bldimport/webtest/sc4_install_set.json`,
`docs/buildings/index.html` (+ `docs/buildings/importer/sc4web.js` after publish). MAIN (local, not in git):
`verify/bldpack/work/guide_template.html` (old copy `.pre_firedist`). Tracked here: this file. Scripts in `work\`.

---

# First pass (2026-11-23, before the owner's answers): the cause, no code

Owner 2026-11-23: "the geometry of the fire station has a weird distortion on the parking side" (sheet
`verify/sc4cmp/forum/18_large_fire_station.jpg`, SC3 side and in-city strip). SC4 install read in place. Pictures with
SC4 art are local only (`owner_shots\`, `work\`, both gitignored). No code changed, no game run, no BMP written.

**Verdict.**

- **Not the civlot turn.** The turned look (2x3, as installed) and the same model on its unturned 3x2 lot give the same
  frames with the slot numbers moved by one: turned slot t = unturned slot t + 1, alpha equal on all 8 frames of zooms 3
  and 4 (1 pixel of 64,000 differs at z4 t3). The colour differences that remain (10,700 to 15,800 pixels at zoom 4) are
  the lot rim, which is lit by world axis, and the 255-colour palette cut. The installed frames are byte for byte this
  session's turned render. No mirror and no wrong rotation sign: in every slot the two walls are the walls of the SC4
  view the slot is built from (owner_shots 01, 02).
- **Cause: SC4's own view mesh puts the bay-door wall at the eave line, about 4 m in front of the doors, and view E
  paints the covered apron floor onto it.** The sheet's SC3 frame is turned slot 3 = unturned slot 0, built from SC4 view
  E (the sheet's SC4 picture). In that view the bay-door wall is the plane z = 15 m, 0 to 10.9 m high, seen at 67.5
  degrees. The doors stand under the roof behind that plane: the yellow apron paint on the plane stops at 4.25 m in view S
  (the ray reaches the ground 3.9 m behind the plane) and at 9.75 to 10.25 m in view E (3.8 to 3.95 m behind). Two views,
  one depth: a covered apron about 3.8 to 3.9 m deep. So in view E 9.75 of the plane's 10.9 m show apron floor, the truck
  and the flags, and the doors do not show. SC3 draws that picture on a vertical plane under the eave: the apron
  continues up the wall to the roof (owner_shots 03, view E panel against view S).
- **A second band on the next side, same family.** Turned slot 2 = unturned slot 3, from view S. SC4's mesh for that view
  closes the +x side with faces that lean out from the wall foot (x = 15 m) to the eave edge (x = 17.85 m at 10.89 m),
  normal (0.97, -0.25, 0). View S sees them at 85 degrees from their normal (n.c = 0.086), SC3 at 62 degrees (n.c =
  0.469): **3.5 to 3.9 SC3 zoom-4 pixels per SC4 texel**, 5,173 pixels (14.4% of the frame's building faces) drawn from
  about 1,100 texels. Every other face of the 16 civic, reward and landmark models measured here is at most 2.1, mostly
  0.6 or 1.5 (owner_shots 04, view S panel).
- **The 1.48 stretch every converted building has.** In each SC3 slot one wall comes from a view that saw it at 67.5
  degrees: measured 1.42 to 1.59 SC3 pixels per texel on the fire station, 1.73 on its -x wall, against 0.62 on the other
  wall (theory: (cos 45 x 5.66) / (cos 67.5 x 7.0) x (cos 30 x 5.66) / (cos 45 x 7.0) = 1.48). That is the known limit of
  the `match` rebuild (SC4_FORMATS 7). On its own it blurs, it does not move things. Here it lands on a wall that is not
  where the SC4 picture has it, so the error shows.
- **Other looks: no such band.** Small Police Station, Large Medical Center, Ranger Station, Soccer Field (the other 4
  turned looks) and Elementary School (not turned) rendered both ways; Small Fire Station, Medical Clinic, City Museum,
  Local Branch Library, Faneuil Hall, Alamo, Independence Hall, Mayor's House, Main Library, Courthouse, City Hall
  measured from round forumshots' conversion. Pixels from faces at 2.5 or more pixels per texel: 0 to 57 per slot on all
  of them, except Large Medical Center slot 0 (3,370, 2.0%, one face with no texels, not looked into). Turned against
  unturned: equal silhouettes on all five turned looks.

## 11. Four ways, zoom 3 and 4

`work/renderall.py`: the six buildings converted with this worktree's `sc4conv.py --growables --all --only ...`
(baked_sharp default; the fire station's OBJ and four view textures are byte for byte round forumshots'), rendered by
`bldimport.render_one` on the unturned lot and, for w > d, through `turned_model`. Each picture: row 1 SC4 views E N W S,
row 2 unturned slots 0 1 2 3, row 3 turned slots 3 0 1 2, so every column is one SC4 view and the two SC3 frames built
from it.

| SC4 view | unturned slot | turned slot | left wall in SC3 | right wall in SC3 | which one is bad |
|---|---|---|---|---|---|
| E | 0 | 3 (the sheet) | -x (tower, windows), view E sees it at 22.5 | +z (bay doors), view E at 67.5 | right: apron floor on the door plane |
| N | 1 | 0 | -z (back, windows) | -x | none |
| W | 2 | 1 | +x (side windows) | -z | none |
| S | 3 | 2 | +z (bay doors), view S at 22.5 | +x, view S at 85 (leaning faces) | right: 3.5-3.9 px per texel smear |

## 12. Numbers

`work/faces.py` (every face: normal, extent, SC4 texels, SC3 pixels), `work/stretch_summary.py` (per model and slot),
`work/unfold.py` (a wall plane laid flat, sampled from each view through its fitted projection, fit 0.45 to 0.56 px),
`work/recess.py` (apron paint per height on the door plane).

Fire station, unturned, largest faces of the two bad slots:

| slot (view) | face | normal | y (m) | x (m) | SC4 texels | SC3 z4 px | px per texel |
|---|---|---|---|---|---|---|---|
| 0 (E) | f49 | +z | 0.74-10.90 | -16.16-4.70 | 1,407 | 2,080 | 1.48 |
| 0 (E) | f5 | +z | 0-10.89 | 4.70-17.85 | 774 | 1,101 | 1.42 |
| 3 (S) | f42 | (0.97, -0.25, 0) | 1.67-10.89 | 15.44-17.85 | 241 | 937 | 3.89 |
| 3 (S) | f50 | (0.97, -0.25, 0) | 0-10.89 | 15.00-17.85 | 255 | 902 | 3.54 |
| 3 (S) | f49 | (0.97, -0.25, 0) | 0-10.89 | 15.00-17.85 | 165 | 647 | 3.93 |

Apron paint on the plane z = 15 (x -11 to 4.5 m, the four bays): view S 36% at 0.75 m, 8% at 3.75 m, 0% from 4.75 m;
view E 30-32% up to 2.25 m, 6-12% up to 9.25 m, 2% at 10.25 m. SC3's own camera (slot 0, elevation 30) looking into a
3.9 m recess would show the floor on the lowest 3.2 m of the plane (a ray drops 1 m per 1.22 m of depth: 3.9 / 1.22).

## 13. Proposal (not built)

**Per face, take the texels from the view that sees that face at 22.5 degrees when the slot's own view saw it nearly
edge-on.** A rule such as: a front face whose SC3 pixels per SC4 texel is above 2.0 (or whose plane is the 67.5-degree
wall and carries ground paint above the bottom quarter) is re-textured from the view that sees it frontally, uv by that
view's fitted projection (both meshes share the model frame). Mock, offline only (`work/mock_frontal.py`, 28 faces of the
fire station moved: the +z door plane of slot 0 to view S, the leaning +x faces of slot 3 to view W), owner_shots 05:

- slot 3 of the sheet: the four arched bays and both trucks show on the door wall instead of apron floor.
- slot 2: a brick wall with two rows of windows instead of the dark smear.
- costs seen in the mock: a white seam strip at the tower corner and a ghost of the chimney top where view S's outline
  meets view E's, the wall still stands at the eave line (no apron under the roof, which SC3 would see over the lowest
  3.2 m), and the doors carry view S's light. This is the `frontal` rebuild's known seam problem (SC4_FORMATS 7), here
  on 2 faces' worth instead of the whole building.

Other routes, cheaper and weaker: (a) leave it and drop the fire station from the forum set (the measurement says no
other converted civic look has it); (b) only for the leaning faces, a vertical stand-in at x = 15 m textured from view W.
A blend of two views was not tried: on the door plane the two views disagree on content (doors against floor), so a blend
would show both.

## 14. Checks

- No code changed in `dev\firedist\wt` (git status clean), so no suite run was needed. The work scripts read the
  worktree's `bldimport.py` / `bldrender.py` / `sc4conv.py` unchanged.
- No game run: the frames the game draws are bldimport's frames, and the installed ones were compared byte for byte.
- Seen in passing, not looked into: Large Medical Center slots 0 and 1 show parked cars at mid-wall height; the Soccer
  Field shows no pitch markings (SC4 view of the goal posts only, lot paint not visible at this scale).

## 15. Pictures (`owner_shots\`, local)

| file | what |
|---|---|
| 01 | Large Fire Station zoom 4: SC4 views E N W S over unturned slots 0-3 over turned slots 3 0 1 2 |
| 02 | the same at zoom 3 |
| 03 | the door plane z = 15 laid flat, as each SC4 view paints it (S frontal: doors; E: apron floor to the eave) |
| 04 | the side plane x = 15 laid flat (W frontal: windows; S: the smear) |
| 05 | mock: as installed against the frontal source, turned slots 3 (the sheet) and 2 |
| 06_* | the other four turned looks and the Elementary School, same layout as 01 |

