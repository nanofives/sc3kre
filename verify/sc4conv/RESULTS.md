# sc4conv results (round 2026-11-18h): SimCity 4 buildings into SC3U, a prototype

**Verdict: the prototype works end to end** on the owner's SC4Evermore "BSC JMyers Homes Pack V3.1": the converter
reads the pack's 19 DBPF files, writes 110 buildings (18 designs x 6 colours, Shotgun 8) as OBJ + MTL + PNG +
models.json, bldimport renders and installs them, and all 18 enabled designs (one colour each) grew in Sacramento
by the first autosave, 2.4 game-run minutes: 106 lots, 3 to 11 per design (section 5). The SC4 files hold no 3D
house, only four BAT pictures on four bounding boxes, so the rebuild re-projects the matching picture per SC3 view
(section 3). What converts well and what does not: section 6. The player-facing route (the importer page reading
`.dat` itself): section 7, about one round of work.

Input and output stay local. The pack's terms ("Feel free to modify the lots for yourself ... please don't
distribute them without asking first") allow converting for yourself. Nothing from the pack (models, textures,
renders, pictures) is in the repository or `docs/`: the output folder is `MAIN\stage\sc4conv_out\` (gitignored),
the pictures are in `owner_shots\` (gitignored, for the owner only).

## 1. Command

```
py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder or .dat> --out <folder>   [--all] [--style baked] [--no-fill]
py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder or .dat> --list
py -3.12 re/tools/bldimport/bldimport.py build <folder> --game <game>              # as for any models folder
```

On this pack: 110 buildings converted in about 7 s; bldimport renders the 18 enabled ones in about 16 s (cached
after that). `--all` enables every colour; by default one colour per design is on (the k-th design its k-th colour,
so a city shows the colours), the other 92 are written with `enabled: false` for the classifier page.

## 2. Readers (formats: `re/analysis/SC4_FORMATS.md`)

| reader | checked on the pack |
|---|---|
| DBPF 1.0 / 1.1 index + directory (`dbpf.py`) | 19 of 19 files, 7,838 entries |
| QFS / RefPack (`dbpf.qfs_decompress`) | 7,434 of 7,434 packed entries unpack to the directory's size |
| S3D `3DMD` (`s3d.py`) | 2,560 of 2,560 walk to the exact file end (chunk lengths are wrong on 5 of 8 chunk types, so the reader goes by content) |
| FSH `SHPI` (`fsh.py`) | 4,760 of 4,760: DXT1 1,117, DXT3 3,643, no mipmaps |
| exemplar / cohort, LText (`exemplar.py`, `catalog.py`) | 128 + 110 exemplars and 42 lot configurations parse to their exact length; every building's model key, name key and family resolve |

## 3. What an SC4 building is, and how it is rebuilt (decision by renders)

Measured (SC4_FORMATS.md 6): each of the 440 zoom-5 views of the 110 houses is the 7-corner bounding box (top and
the two walls facing the camera, the other faces culled) with the BAT's render of that view projected onto it
(affine fit error <= 0.50 px). One camera for all views, elevation 44.5-45.5 degrees and azimuth 22.5 degrees off
the axis; the model turns per view. So the files hold four pictures on four boxes, not a 3D house
(`owner_shots/00_sc4_view_is_a_box.jpg`).

SC3's camera is 30 degrees high and 45 degrees off the axis: each SC3 rotation slot is 22.5 degrees from one SC4
view that sees the same two walls (slot 0 E, 1 N, 2 W, 3 S). Rebuilds rendered through the SC3 camera
(`reproject.py`, `owner_shots/01_rebuild_choice_zoom4.jpg`):

| rebuild | what the renders show |
|---|---|
| walls mixed (each wall from the view that sees it most frontally) | sharper walls, but a hole between walls taken from different views: each view puts the roof outline on the box differently |
| one model for all slots | the same holes, and the roof seen from the wrong side in 3 slots |
| matching view per slot | one consistent picture; the wall SC4 saw at 67.5 degrees is stretched sideways; houses that are not box-shaped (L plans, porches) open gaps where the SC4 texel is transparent |
| **matching view + fill (chosen)** | as above, plus the box's two back walls and floor, uv from the same projection: the gaps show what the SC4 camera saw along that line. Closes most gaps (Fleetwood, Craftsman), with some repeated roof pieces |

The OBJ holds the four boxes in one model frame (metres, Y up, the SC4 S view's frontal wall = +Z = front), one
group per slot: `g sc3slot<r>`. bldrender draws a group only in its slot.

## 4. bldrender changes (task sc4conv block, `re/tools/bldimport/bldrender.py`)

1. **Texture alpha**: a texture with transparent texels keeps its alpha; a sample on a texel below 0.5 takes the
   next surface behind it (depth peeling, up to 4 layers, `rasterize(zmin=)`). Off: `SC3BLD_ALPHA=0`. An opaque
   texture renders as before.
2. **Per-slot groups**: OBJ `g` / `o` named `sc3slot<r>` is drawn only in slot r (`slot_mesh`). Off:
   `SC3BLD_SLOTGROUPS=0`. Models without such groups render as before.
3. **Styles `baked`, `baked_raw`, `baked_sharp`** for art with its light painted in: no light, no vibrance /
   contrast / grain, the stock style's lawn, front-edge band, palette and zoom 4. `baked` adds a luminance tone
   (gamma 0.75, gain 1.33) fitted on this pack; `baked_raw` has none; `baked_sharp` draws zoom 4 natively.

Regression: `bldimport.py calibrate` 0 of 160 frames differ; 4 sample-pack models (2 Kenney textured, the brick
house, the 2x2 block) x 20 frames rendered with main's bldrender and this one: 80 of 80 byte-identical.

Light (`owner_shots/02_render_style_zoom4.jpg`): the default `stock` style lights the texture again and the houses
go nearly black. Structure luminance over the 18 designs, 72 zoom-3 frames, bldlook's definitions:

| | p10 | p50 | p90 | contrast | saturation |
|---|---|---|---|---|---|
| stock SC3 buildings (bldlook, 75 buildings) | 0.201 | 0.400 | 0.688 | 1.234 | 0.225 |
| SC4 art, `baked_raw` | 0.098 | 0.203 | 0.449 | 1.732 | 0.230 |
| SC4 art, `baked` (tone 0.75 / 1.33) | 0.242 | 0.402 | 0.730 | 1.214 | 0.224 |

So the SC4 renders are about half as bright as stock SC3 art. [UNCERTAIN: whether SC4 brightens them at draw time;
not read.] `baked` matches the stock numbers; by eye it is paler than the SC4 picture itself (shot 02), `baked_raw`
looks like SC4 and darker than its SC3 neighbours. Owner call.

## 5. Classes, lots, names, and in game

**Class** (`sc4conv.class_for`): residential (purpose 1) by wealth 1 / 2 / 3 into 3100 / 3300 / 3500 (light),
3700 / 3900 / 4100 (medium), 4300 / 4500 / 4700 (dense), density from capacity (<= 60 light, <= 400 medium, else
dense: a rule of this tool, not a measured equivalence). The pack is all wealth 1, capacity 11-22: class 3100. Class
3100 has only a 1x1 stock base (batgrow.class_table: 3100 / 3300 1x1, 3500 1x1 + 2x2, 3700 2x2 + 3x3, 3900 2x2), so a
house that needs a 2x2 lot moves to the class of the same wealth that has one: the 6 Empire houses (17.0 x 19.8 m)
go to 3700.

**Lot** (`lot_for`): the smallest square with both sides <= n x 16 m. 104 buildings 1x1 (largest footprint 10.1 x
15.9 m, Destiny), 6 2x2. How SC4's lots map: SC4 1x2 and 1x3 lots are one tile (16 m) wide and 2-3 deep, the house
already fits the 16 m width, so the SC3 lot is 1x1 with the house centred and the back yard dropped; SC4's corner
lots (2x2, 2x3) hold the same houses and map to the same SC3 lot. The SC4 lots and their growth stages are kept in
`x_sc4.lots` for reference.

**Name**: the LText's first line (`214 Abbey Glen Rd`; 14 buildings, 13 of them the yellow variants, carry the pack's own
`<design> Homes by JMyers`-style title). **Weight** 1 (the 12 stock members of family 11, the one family class 3100 grows from, are all weight 1). `x_sc4` keeps the
exemplar name, design, colour, TGIs, wealth, capacity, family, SC4 lots, the view per slot and the fitted cameras.
A rerun keeps any field the player changed in the classifier page (`x_sc4.auto` = what the tool wrote last).

**In game** (`bld_lab.py`, test slot, `dev\sc4conv\tree`, windowed 1600 x 1000, posted input only, mods of
`dev\sc4conv\inst`, churn `anarchy_res=5000`, speed 4, autosave every 150 s, Sacramento). The 18 enabled designs,
alternating `baked` and `baked_raw` so both looks are in one city. By the first autosave, 2.4 game-run minutes:
**all 18 had grown**, 106 lots, stock occupants 11,917.

| id | design (colour) | style | lots | | id | design (colour) | style | lots |
|---|---|---|---|---|---|---|---|---|
| 38000 | Abby Glen (Blue) | baked | 11 | | 38057 | Fleetwood (Mauve) | baked_raw | 7 |
| 38007 | Acorn (Gray) | baked_raw | 5 | | 38064 | Four Seasons (White) | baked | 4 |
| 38014 | Allegheny (Green) | baked | 7 | | 38071 | Golden West (Yellow) | baked_raw | 5 |
| 38021 | Blue Ridge (Mauve) | baked_raw | 5 | | 38072 | Heritage (Blue) | baked | 5 |
| 38028 | BonnaVilla (White) | baked | 4 | | 38079 | Homestar (Gray) | baked_raw | 8 |
| 38035 | Commodore (Yellow) | baked_raw | 4 | | 38086 | Lavoy (Green) | baked | 4 |
| 38036 | Craftsman (Blue) | baked | 10 | | 38093 | Liberty (Mauve) | baked_raw | 4 |
| 38043 | Destiny (Gray) | baked_raw | 7 | | 38100 | Narrow Lot Colonial (White) | baked | 8 |
| 38050 | Empire (Green), 2x2, class 3700 | baked | 3 | | 38103 | Shotgun (Gray) | baked_raw | 5 |

All 106 saved with rotation 0, like the stock growables (BUILDING_ART.md 3). Faults: only the
`0xC0000096 at SC3U.exe+0x84122` line every lab run logs at start. Run files: `verify/sc4conv/runs/run1/`
(`counts.json`, `resize.log`, `fd/*.png`, `saves/`), no BMP left.

The lab's camera does not land exactly on the chosen lot (the trap of verify/bldpack step 2), and with churn at
5000 some chosen lots had been rebuilt by picture time. So the houses were found in the dumps by their own frames:
the game draws the rendered frame pixel for pixel, and `work/find_in_dump.py` slides each id's frame over a dump,
56 matches at 0.53-0.98 of the opaque pixels over the 18 zoom-4 dumps (55 at 0.6 or more, the bar the pictures use) (the rest of a frame is covered by
neighbours and cars). The owner pictures box them in yellow with a legend.

| file | what |
|---|---|
| `00_sc4_view_is_a_box.jpg` | an SC4 view model: the BAT picture with the box's 6 triangles drawn on it |
| `01_rebuild_choice_zoom4.jpg` | the rebuild candidates of section 3 against SC4's own picture |
| `02_render_style_zoom4.jpg` | `stock` (bldimport's default) vs `baked_raw` vs `baked` |
| `03_all18_next_to_stock_zoom3.jpg` | `bldimport.py preview`: the 18, four views each, next to stock 112 (141 for the 2x2) |
| `04_sc4_look_vs_converted_zoom4.jpg` | each design: SC4's picture (view S) and the converted frame of SC3 rotation 3 |
| `10`-`13_sacramento_zoom4_*.jpg` | in game, zoom 4, converted houses boxed, style in the legend |
| `11b_sacramento_zoom4_b_unmarked.jpg` | shot 11 without the boxes |
| `14`, `15_sacramento_zoom3_*.jpg` | in game, zoom 3 |

**Style, from the in-game pictures**: next to stock houses the `baked_raw` houses read as dark grey, close to the
look of a burnt-out lot (shot 11, 1 Garden Court; shot 15, numbers 3, 8, 10); the `baked` ones sit among the stock
houses (Abbey Glen, BonnaVilla, Heritage). So `baked` stays the converter's default. [Owner call: the brightness is a
taste; `--style baked_raw` keeps SC4's own darkness.]

No four-rotation in-game picture: as in bldpack, the lab's rotation shots do not keep the lot in view; the four
views are in shot 03 (offline, the same frames the game draws).

## 6. What converts well, what does not

Converts well:

- **Everything the game needs to grow a house comes from the SC4 data**: name (LText), wealth and purpose (class),
  capacity, size (footprint and height from the occupant size, equal to the model box to 0.001 m), the colour
  variants (one family per design). No hand work: 110 of 110 buildings converted, 18 of 18 enabled ones planned
  `ok` by bldimport and read back 20 / 20 frames equal.
- **Simple box-like houses** (Abby Glen, Liberty, Lavoy, Shotgun, Allegheny): the picture survives the change of
  camera with little visible distortion (`owner_shots/04_sc4_look_vs_converted_zoom4.jpg`).
- **Size against stock**: at 16 m per cell (the SC4 tile size too) the houses sit on a 1x1 lot like stock 112
  (`03_all18_next_to_stock_zoom3.jpg`). The SC4 houses are taller (10.0-12.6 m) than the stock cottages (about 8 m).
- **Detail**: SC4 zoom 5 has 7.0 px per metre, SC3 zoom 4 5.66: the source is sharper than SC3 needs. The stock-like
  zoom 4 (zoom 3 doubled) throws some of it away; `baked_sharp` keeps it.

Does not convert, or only partly:

| what | why | effect |
|---|---|---|
| camera angle | SC4 looks down at 45 degrees, SC3 at 30; SC4 is 22.5 degrees off the axis, SC3 45 | roofs look as seen from higher up, the wall SC4 saw at 67.5 degrees is stretched about 1.85 x sideways and has less detail |
| hidden parts | the files hold only what the BAT camera saw | houses that are not box-shaped show gaps; the fill closes most of them with repeated pieces (Fleetwood, Craftsman, Homestar look rougher than the box houses) |
| light direction | SC4's BAT light is fixed to the screen: the left wall is the lit one in all four views. Stock SC3 light follows the model axis | converted frames right / left luminance 0.67 / 0.63 / 0.66 / 0.64 in slots 0-3 (18 designs, zoom 3), stock 0.81 / 1.27 / 0.81 / 1.23: in view rotations 1 and 3 the converted houses are lit on the other side from their stock neighbours. Cannot be fixed without relighting a picture |
| brightness | the SC4 renders are about half as bright as stock art (section 4) | `baked` tones them to the stock numbers and they look paler than in SC4; `baked_raw` keeps the SC4 look and is darker than the neighbours. Both are in the in-game test (section 5) |
| SC4 lots (1x2, 1x3, corners 2x2 / 2x3) | SC3 growables are square and every stock base is n x n (`bldimport.lot_of`) | the SC3 lot keeps the house only, centred on a 1x1 lot (2x2 for the 17 x 19.8 m Empire); the SC4 yard, driveway and its rotation on the lot are dropped |
| lot props and lot textures | they come from the BSC Common Dependencies Pack, not in the download | plain SC3 lawn around the house |
| foundations (18 models, exemplar type 0x11) | SC3 lots are drawn flat | not converted |
| night textures (0x38xxx, 2,200) | SC3 has no night view | not used |
| SC4 zooms 1-4 | SC3 renders every zoom from one model | only SC4 zoom 5 is read; bldrender's supersampling makes SC3's small zooms |
| commercial, industrial, other purposes | the pack has residential only | `class_for` maps residential only; anything else gets class `null` and is not enabled |

## 7. The player-facing route: the importer page reading .dat in JS

Players have no Python, so the route that scales is the importer page (`classifier.html` + `bldweb.js`, which ports
bldimport byte for byte) opening the SC4 download itself. What it needs, from this prototype:

1. **Folder input**: an SC4 plugin download is a tree (`BSC\BSCProps#\...\*.dat`, `BSC\JMyers\Homes Pack#\<design>\*.dat`);
   the page lists `MODEL_EXT` files in one folder today (`classifier.html` 801). It needs a recursive listing of
   `.dat .sc4desc .sc4lot .sc4model`.
2. **Readers in JS** (sizes from the Python files): DBPF index + directory (dbpf.py, about 60 lines), exemplar +
   LText (about 60), S3D walker (about 100), DXT1 / DXT3 decoder (about 70), the catalogue (buildings, lots,
   families, about 80). QFS is there already: bldweb.js `qfsDecompress` (1172) unpacks SC3's own DAT files with the
   same RefPack, and the flag byte in the pack is 0x10 on all 7,434 packed entries. Pure ArrayBuffer work, no DOM,
   so the readers can be checked in node against the Python readers the way `bld_js_check.mjs` checks `.bld`.
3. **The conversion** (views.py, sc4conv.py, about 150 lines): the camera fit (least squares of 7 points, two 4 x 4
   normal-equation solves), the view-to-slot match, the hidden-face fill, class / lot / name rules.
4. **Renderer parity**: the three bldrender additions (section 4) ported into bldweb.js `renderFrame` /
   `rasterize`: the per-slot filter, alpha peeling with `zmin`, the `baked*` styles and the tone. bldweb.js keeps
   byte parity with Python through careful float order (`fma`, Pillow ports); the tone's `np.power` on float32 is the
   step to watch. Until this is ported, the page stops on a converted folder with "render style \"baked\": choose one
of clean, stock, stock_sharp" (bldweb.js `styleOf`, 256), and with any other style it would draw all four boxes in
every slot over one another (no slot filter) with the transparent texels opaque.
5. **No OBJ round trip needed**: the page can build the mesh and textures in memory from the `.dat`; but the cache
   key and `ids.json` are keyed by model file name, so it needs a stable key per SC4 building, for example
   `<dat file>#<exemplar TGI>`.
6. **Licence**: the conversion runs on the player's PC and nothing is uploaded, as the page works today. The page
   should say that the output is for the player's own game.

Estimate: about 600-700 lines of JS plus golden cases (Python sc4conv + bldimport against the page, as
`webtest/golden.mjs` does for OBJ). One round. [UNCERTAIN: other SC4 packs. BATs with a custom LOD mesh instead of
the box, props, animated or night parts, and DBPF 1.1 with index minor 2 were not in this pack; the readers reject
what they do not know (S3D vertex formats other than 0x80004001, PROP / REGP entries, several meshes) with a
message instead of guessing.]
