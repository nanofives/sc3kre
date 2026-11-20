# sc4ground results (round 2026-11-20c): converted SimCity 4 buildings standing above the lawn, the Alamo flag

Input: SimCity 4 Deluxe (Steam) on this PC, read in place; the JMyers Homes pack and the Global Office Center from
`stage\st_packs`. EA and community pictures stay local (`verify\`, gitignored). Worktree `dev\sc4ground\wt`, nothing
committed.

**Verdict.**

- **Cause: SC4 lot props carry a height and the converter dropped it.** Lot object word 4 is the object's height above
  the lot (s32 / 65536 m). 2,431 prop rows on 815 of the install's 1,908 lots are not 0 (0.25 to 324 m, none below 0):
  the wall and roof signs of SC4's shops and offices. The converter put them at 0, so the Small Shop's sign
  (`CSign1x2x6_$$$sign_1D63`, row height 8.75 m, model y -3.00 to 3.01 m) hung 3 m under the ground and bldrender, which
  sets a model's lowest point on the lawn, lifted the whole lot 3 m. That is 23 of the 24 lifted models sc4cmp found
  (every Small Shops and Retail Stores variant, Ferrrara Inc.). The 24th, Smith Tower, is its own view box reaching
  -0.41 m (transparent there).
- **Fix, in the converter only** (`catalog`, `props`, `views`, `sc4conv`, `compare_sheet`, and `sc4web.js` with the same
  steps): the prop's height is added to its y; every vertex below y = 0 is raised to 0 (house views and back walls keep
  their texel through the view's own projection, props keep their uv); the lot quad sits at 0.01 m and the window
  triangle at 0; every OBJ gets one zero-area triangle at y = 0 (`sc4base`), so y = 0, SC4's ground, is the lowest point
  and lands on the SC3 lawn. bldrender, bldimport and bldweb.js are untouched.
- **Result:** of the 194 OBJs of the 50 sc4cmp models, 78 had their lowest point below 0 (down to -5.49 m) and 10 above
  it; now all 194 have it at exactly 0. In the pictures and in game the shops and Ferrrara stand on the lawn with their
  signs on the wall and the billboard on the roof, on both the SC4 and the SC3 side (section 3).
- **Python = page:** `sc4_install.mjs` 21 of 21 (its growables subset holds the Small Shop, a Retail Stores and
  Ferrrara: OBJ / MTL / models.json byte for byte, PNG pixel for pixel). Full suite 40 of 41, the one failure a
  Chrome start-up race that passed on rerun; non-SC4 goldens 975 files, 0 differ from main (section 6).
- **The Alamo flag: not a converter fault.** The converted model draws the pole (zoom 4 rendered natively: a grey
  1-pixel pole down to its base). The `baked` style draws zoom 4 as the zoom-3 frame doubled (bldrender `zoom4 =
  "double"`, the stock look), and at zoom 3 (2.83 px/m) the 0.14 m pole is 0.4 px wide and drops out under the alpha
  test; only its base knob stays. Not changed (renderer style, shared). `baked_sharp` (native zoom 4) would keep it.
- **Extras:** none of the four has a cause fixed here. City Hall's grey hook above the dome is the same pixels before and
  after. Small Fire Station, Mayor's House (lot size) and Lee Avionics (washed out) are as sc4cmp described.

## 1. Measured: what reaches below SC4's ground

Script `verify/sc4ground/work/measure_below.py` (data `m_inst.json`, `m_jm.json`, `m_goc.json`; lot heights
`lot_y.py`; masks `show_below.py`; the cut / raise A/B `clamp_ab.py`; Alamo `alamo_exp.py`): for each model with a model state `ok`, the four
zoom-5 views (`views.load_views`), lowest and highest vertex, and how many opaque texels of each view's picture land on
the view mesh below y = 0 and on no face above it.

| source | models | lowest point below 0 | above 0 |
|---|---|---|---|
| SC4 install (civic, park, reward, landmark + C / I growables) | 423 | 39 (-3.91 to -0.01 m) | 31 (0.01 to 0.82 m) |
| JMyers Homes (download) | 110 | 32 (-0.10 to -0.01 m) | 0 |
| Global Office Center | 1 | 0 | 0 |

The deepest install models: Lincoln Center -3.91 m, Smoke Stacks -1.00, Furnace -0.56, MPR Metals -0.50, Smith Tower
-0.41, Paull Inc. -0.39, Television Studio -0.33, Zeno's Truck Parts -0.28, Graber Corporate Suites -0.25. Opaque texels
below 0, most of one view: 0 on 21 of the 39, 3 to 105 on 13, Mixer 392, Television Studio 509, Smoke Stacks 3,493 (the
sides of a 1 m base slab), Wong Insurance 5,766 (its paved forecourt, on a mesh face 0.13 m under 0), Lincoln Center
15,666 (a 3.9 m skirt under its plaza). JMyers: at most 1.

**Why these numbers did not explain sc4cmp's 24:** none of Retail Stores, Small Shops or Ferrrara Inc. is in the 39. In
sc4cmp's OBJs the lowest vertices were prop materials (`sc4p_1ABE787D_0520..`, `05F7..`, `0519..`, all -2.55, -3.00,
-4.00, -5.49 m), and the lot rows of those props hold a height in word 4 (`CS$4_1x1`: sign at 8.75 m; `CS$$6_2x2`:
`CSign2x4x11_$sign_1D68`; `CO$$$6_3x2`: billboard `CBill12x2x8_$$sign2_2A21`).

Lot object word 4 over the inputs:

| source | lot objects | word 4 not 0 |
|---|---|---|
| install | 73,832 | 2,431 (all kind 1 props, 815 lots, 0.25 to 324 m) |
| JMyers | 2,634 | 0 |
| Global Office Center | 147 | 0 |

## 2. Fix, and why a raise and not a cut

First built as a cut at y = 0 (each triangle clipped). Tested against no cut on Wong Insurance (W view, zoom 4 native):
the cut took away the paved forecourt between the wings, which SC4's own picture shows. The view mesh there is a face
0.13 m under 0 carrying texels of paving at ground level, so the meshes do not always enclose the model. Replaced by a
raise (`views.clamp_ground` / `clampGround`): a vertex below 0 goes to 0; for house views and back walls its uv moves by
the view's projection (`uv + A[1] * d / texture size`, A from `views.fit_camera`), so it keeps the texel the SC4 camera
saw at its new place; a prop keeps its uv (props reach at most a few cm under 0 once their height is added). Results:

| building | before | cut at 0 | raise to 0 (shipped) |
|---|---|---|---|
| Wong Insurance | 0.13 m up | forecourt gone, lawn shows | forecourt drawn at ground level |
| Smoke Stacks | 1 m up on its slab, slab sides showing | | slab top flush with the lawn, sides gone |

A face that lies wholly under the ground collapses to nothing. [UNCERTAIN] whether SimCity 4 itself hides parts under
its terrain: not checked against an SC4 screenshot.

Other details: a box's hidden floor sits 0.05 m above the ground instead of above the box bottom; the lot quad
(`sc3ground`) at 0.01 m instead of 1 cm above the lowest vertex; the `sc4lot` window triangle at 0. Models whose lowest
point was above 0 (31 install models, up to the Radio Station's 0.82 m) now stand that far up, as their coordinates say.

The SC4 side of the pictures (`compare_sheet.py`) also dropped word 4 (signs drawn at ground level): fixed the same way,
lot ground at y = 0; its pixel check against SC4's picture still uses the unchanged view.

## 3. Pictures

`verify/sc4cmp/forum/` rebuilt (12 + four sides + 4 extras, every one looked at), `sheet.json` with them. Before: copy in
`verify/sc4ground/forum_before/`. Owner shots in `verify/sc4ground/owner_shots/`:

- `forum_06_small_shops_before_top_after_bottom.jpg`, `forum_07_...`, `forum_09_...`: before, the SC3 side stands on a
  green block with a second lawn edge and the sign at its foot; after, on the lawn, sign on the wall (06), planters at
  the door (07), billboard on the roof on both sides (09).
- `ingame_small_shops_before_after.jpg`, `ingame_ferrrara_before_after.jpg`: the same city and camera (sc4ci's save),
  left sc4ci's build, right this one.

The in-city strips of 06 and 09 now come from this round's game frames (`verify/sc4ground/runs/shotCom/fd`, matched by
`verify/sc4ground/work/match_ingame.py`, a copy of sc4cmp's matcher pointed at the new conversion and frames): the Small
Shop matches 14 px lower in the frame than before (y 398 -> 412), the 3 m lift at zoom 4. The other strips (police,
industry, farm) are sc4lottex / sc4ci frames as before; those buildings were not lifted (the police lot 1.8 cm, its
props: frame mean difference 1.58 levels).

## 4. In game

Tree `dev\sc4ground\tree`, mods `dev\sc4ground\inst`, windowed 1600 x 1000, posted input and Frida camera calls only,
test slot, harness claimed and released. `sc4conv.py <install> --growables --all --only <Ferrrara, Lam Banking, Retail
Stores CS$$12x28_1HouMediumStore1_05C5, Small Shops CS$14x14_1ChiSmallShop1_05CD>` + `bldimport.py build --game
dev\sc4ground\tree`: ids 38000-38003, the same ids, classes and lots as sc4ci's build. `verify/sc4ground/work/ground_lab.py`
(sc4ci's `ci_lab.py` with this worktree's paths) `--from-save verify/sc4ci/runs/comA/saves/save01.sc3`: the city where
sc4ci grew them, loaded with churn off, 27 frame dumps (PNG; no BMP left). Faults: only the start-up `0xC0000096 at
SC3U.exe+0x84122` every run logs. Game PIDs started and stopped by this session: 8856 (cut build), 8440 (shipped
build). Small Shops and Ferrrara Inc. stand on their lots with signs and billboard in place. The Retail Stores spot of
that save shows a construction site in both sc4ci's shot and this one.

## 5. Alamo flag (details)

The Alamo's zoom-5 view S is 2 meshes: the building (59 vertices) and a pole piece (10 vertices, x 12.6-13.2, y 0-13,
z -14.2 to -12.7 m, its texture a 4 x 73 px strip). The flag and pole visible in SC4's picture are texels of the main
piece; the pole piece projects to the other side of the canvas. Slot 3 at zoom 4 without its 8 triangles: both frames
show the same pole; 305 pixels differ by more than 16 levels, spread over the whole frame (x 19 to 243, mean 1.14
levels: the frame's centring and palette), none of them the pole. bldrender at zoom 4 (native) draws the pole; at zoom
3 it is gone, and `baked` makes zoom 4 from zoom 3.

## 6. Checks

- Python = page, focused before the suite: `sc4_install_setup.py` + `sc4_install.mjs --frames`: 21 of 21.
- Full suite, `SC4INSTALL=<SimCity 4 Deluxe> SC3PACK_PACKS=MAIN\stage\st_packs PROYECTOS_TEST_MEM_GB=6
  PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh dev\sc4ground\work\runall stage\release
  stage\kits ".happy-uploads\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes\jar
  stage\st_packs\sc4` (paths under MAIN), log `dev\sc4ground\work\runall2.log`: **40 of 41** on the run. The one failure, `pagetest.mjs landmarks`, was Chrome
  start-up in the harness (`EBUSY` reading `DevToolsActivePort`, before the page loaded); that step rerun alone: 6 of 6
  (`dev\sc4ground\work\rerun_landmarks.log`). Every SC4 step (23-41) passed: Python = page byte for byte on every SC4
  route.
- Non-SC4 goldens byte identical: main's own `golden_setup.py` (its `re/tools` unchanged since this worktree's base
  497191d) for the 8 cases testmodels, bld, kenney, styles, ports, landmarks, landmarkdesc, civic, against this run's:
  **975 files, 0 differ**. No module outside the SC4 routes imports the changed files (bldrender and bldweb.js mention
  sc4conv in comments only). The sample-pack steps (19-22) passed.
- The page did not change (`sc4web.js` only): `sync_css.py --check` runs in the suite; no guide statement changed (the
  guide's "the lowest vertex touches the ground" is bldrender's rule, unchanged).

## 7. Rebuild

```
set SC4="C:\Program Files (x86)\Steam\steamapps\common\SimCity 4 Deluxe"
py -3.12 re/tools/sc4conv/sc4conv.py %SC4% --growables --all --only "<verify/sc4cmp/work/only.txt>" --out verify/sc4ground/work/conv
py -3.12 re/tools/bldimport/bldimport.py render verify/sc4ground/work/conv
py -3.12 verify/sc4ground/work/match_ingame.py
py -3.12 re/tools/sc4conv/compare_sheet.py %SC4% verify/sc4ground/work/conv verify/sc4cmp/forum ^
    --ingame verify/sc4ground/work/ingame.json --game-root <MAIN>
```
