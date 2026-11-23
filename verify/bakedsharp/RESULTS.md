# bakedsharp results (round 2026-11-23): `baked_sharp`, SC4 thin details at zoom 4

Worktree `dev\bakedsharp\wt` (branch child/bakedsharp, from main 8b091cf), nothing committed. SC4 install read in place.
Pictures with SC4 art stay local (`owner_shots\`, gitignored).

**Verdict.**

- **The style already existed.** `baked_sharp` (`dict(STYLES["baked"], zoom4="native")`) has been in `bldrender.py`
  and `bldweb.js` since sc4conv / sc4web. It works per entry (`"x_bldrender": {"style": "baked_sharp"}`) and with
  `sc4conv.py --style baked_sharp`. Nothing in the standing suite rendered it through the importer, and the guide did not
  mention it.
- **Added:** `baked_raw_sharp` (one line each side), golden case `sharp` (Python = page), one guide line, the published
  importer's `bldweb.js` re-copied. `baked` stays the default. The page has no style control for `baked_raw` (its picker is
  stock / stock_sharp / clean), so no control was added.
- **The Alamo, baked vs baked_sharp:** zooms 0 to 3 are byte identical (16 of 16 frames). At zoom 4:

  | rotation | baked (zoom 3 doubled) | baked_sharp (native) |
  |---|---|---|
  | 0 | flag hidden behind the building | same |
  | 1 | pole drawn 2 px wide and pale, flag blocky | pole 1 px, flag and the sign's lettering sharper |
  | 2 | **only a 2 px stub on the wall, flag floating above** | **whole curved pole from wall to flag** |
  | 3 | pole 2 px | pole 1 px |

  The same in game (Madison, both placed side by side, `owner_shots/03`, `04`).
- **Other changes at zoom 4:** edges are 1 px steps instead of 2 px blocks. The neighbour-pixel luminance step goes from
  7.4 to 11.3, because doubled frames repeat each pixel, so this is detail, not added noise. The frames are 1 px taller or
  shorter in 3 rotations (crop). About 10 to 11 pixels per 1,000 of the frame turn transparent (thinner antialiased silhouette),
  mean luminance +0.6 to +1.4 levels, colour count within 7. **File size: the Alamo's `bldimport.dat` alone is 164,591
  bytes with baked and 263,960 with baked_sharp (+60%).** Doubled frames compress better.

## Checks

- Golden case `sharp` (house_tex baked, block_2x2 baked_sharp rotated 90, obelisk_2x2 baked_sharp with its 0.6 m lamp
  posts, house_plain baked_raw_sharp rotated 45): 13 of 13, 80 frames Python = page (`golden.mjs`).
- Full suite, `SC4INSTALL=<Steam SimCity 4 Deluxe> SC3PACK_PACKS=MAIN\stage\st_packs PROYECTOS_TEST_MEM_GB=6
  PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh dev\bakedsharp\work\runall stage\release
  stage\kits ".happy-uploads\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes\jar
  stage\st_packs\sc4`: **41 of 41 steps**, wall 1,401 s (log `dev\bakedsharp\work\runall.log`).
- Existing goldens against main: main's `golden_setup.py` for the 9 existing cases (`dev\bakedsharp\work\g_main`) vs this
  run: **1,090 files, 39 differ, all `sc3build/<stem>/meta.json`, only the `key` field.** That field hashes
  `bldrender.py`, which changed. Frames, anchors and every game file are byte identical.
- `sync_css.py --check`: in sync. `--publish` copied classifier.html + scripts to `docs/buildings/importer/`, and only
  `bldweb.js` changed there.
- In game: `dev\bakedsharp\tree`, Madison, windowed, posted input and Frida game calls (lotshape's `lab.py` / `shots.py`,
  copies in `work\`). Alamo baked = 38000 at (181,204), baked_sharp = 38001 at (181,208), both 2x3. Zoom 4, four
  rotations. PID 3500 started by `sc3dev run`, stopped by PID. The only VEH line is the startup `0xC0000096 at
  SC3U.exe+0x84122`. No BMPs left. The yellow wedge over both is the game's no-power bolt.

## Pictures (`owner_shots\`, local only)

| file | what |
|---|---|
| `01_alamo_z4_baked_vs_sharp.png` | renderer frames, zoom 4, rotations 0-3 top to bottom, baked left, baked_sharp right |
| `02_alamo_flagpole_x4_baked_vs_sharp.png` | the pole at 4x, rotations 1, 2, 3 |
| `03_ingame_z4_4rot_baked_vs_sharp.png` | in game, zoom 4, four rotations, both Alamos |
| `04_ingame_r2_flag_x4_sharp_left_baked_right.png` | in game, rotation 2 at 4x: whole pole (sharp) vs stub + floating flag (baked) |
| `05_ingame_r1_flag_x4.png` | in game, rotation 1 at 4x (baked left, sharp right) |

## Owner call (optional)

Whether `sc4conv` / the page should default SC4 landmarks (or all SC4 buildings) to `baked_sharp`. Cost: +60% file size.
Gain: thin parts survive at zoom 4 and the picture is sharper, but it no longer matches the stock buildings' doubled zoom-4 look.
