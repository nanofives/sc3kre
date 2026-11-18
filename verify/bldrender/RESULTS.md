# bldrender results (round 2026-11-18b): a 3D model grows as a zoned building

**Verdict: works in game.** Three OBJ test models, rendered by `re/tools/bldimport/` and packed as ids 38000-38002,
grew on their own in Sacramento next to the stock houses by the first autosave (2.4 game-run minutes at speed 4):
548 lots of 38000, 512 of 38001, 99 of 38002. They draw at every zoom and all four view rotations. Spec and
evidence: `re/analysis/BUILDING_ART.md`.

## What was run

| step | command | result |
|---|---|---|
| test models | `make_testmodels.py dev\bldrender\work\testmodels` | 1x1 plain cottage (54 faces, flat colours), 1x1 brick house (textured walls and roof), 2x2 three-storey block with two trees; models.json in the classifier format |
| calibration | `bldimport.py calibrate --game dev\bldrender\tree 115 3065 126 3077 3020 141 3011 176 3028 3071` | 0 differing pixels on 160 of 160 frames (lot diamond below the registration row, zooms 0-3, every slot, 1x1 to 4x4) |
| render + pack + install | `bldimport.py build dev\bldrender\work\testmodels --game dev\bldrender\tree` | 11 overlay files (BUILDFAM, OccupantAttribs_Korea, CSAttrib_Korea, 7 x SC3StringsNetpack, new B1D10001_bldimport.DAT) |
| read back | `bldimport.py check ... --game dev\bldrender\tree` | 3 of 3 ok, 20/20 frames per building equal to the rendered PNGs (5/6/5), anchors, names, family lines |
| restore | `bldimport.py restore --game dev\bldrender\tree` | all 11 files back byte for byte (sha256 = the 2026-11-18b stage), the new DAT removed; then installed again, and a second install changed nothing |
| classifier's own folder | `bldimport.py pack re\tools\bldimport\samples --out ...` + `check --root` | reads the page's models.json as written: house_a (3300) and shop_a (5100) packed, 20/20 frames each; the disabled entry skipped; `x_bldrender.palette` ignored |
| in game | `bld_lab.py --tag run1` (test slot) | see below |

Tree: `dev\bldrender\tree` (hard-linked 2026-11-18b release, no netpack ledger). The files went in with
`bldimport.py build` into its `mods\netmod\overlay`, like `bat_growables.ps1`; nothing was installed by hand.

## In game (`verify/bldrender/runs/run1/`)

`Sacramento, CA.sc3`, windowed 1600x1000, all mods of `dev\bldrender\inst`, churn `anarchy_res=5000`
(`inst\simrun.ini` for this run only, removed after), speed 4, autosave every 150 s, posted keys only, camera through
the city view's SetZoomAndRotation on the game thread (verify/showcase/cam.py), pictures by SC3RESIZE_FRAMEDUMP.
Game PID 17576, started and stopped by the lab.

| save | stock buildings | 38000 cottage | 38001 brick house | 38002 2x2 block |
|---|---|---|---|---|
| shipped Sacramento | 16,466 occupants, 0 imported | 0 | 0 | 0 |
| first autosave (2.4 min) | 11,607 | **548** | **512** | **99** |

Classes: 38000 / 38001 in 3300 (family 4, stats of Meek Cr. 115, weight 20), 38002 in 3900 (families 28 and 12,
stats of 3020, weight 20). Weight 20 against stock weights 1 to 10 is why they spread this fast; set it lower for a
normal mix.

Pictures (phone size, `owner_shots/`):

| file | what |
|---|---|
| `01_sacramento_zoom4.jpg` | the city at zoom 4: red-roof cottages and dark-roof brick houses among stock houses |
| `02_closeup_zoom4_x2.jpg` | the same, doubled: lot ground, size against stock 1x1 houses, the cottage's door and path |
| `03_four_view_rotations_zoom4.jpg` | the same lot in view rotations 0-3 |
| `04_block_2x2_zoom4_x2.jpg` | two 2x2 blocks between stock apartments |
| `05_sacramento_zoom3.jpg` | zoom 3 |
| `06_models_next_to_stock_zoom4.jpg` | offline: each model's 4 slots next to its class's stock base building |

`resize.log`: one fault line, `0xC0000096 at SC3U.exe+0x84122` at 1.0 s, before the city loads; the same line is in
four dataview runs of 2026-10/11, so it is not this change. No other fault, the game ran until the lab stopped it.

## Findings

1. **Grown lots never turn.** 16,322 of 16,450 buildings in the autosave (and 13,392 of 13,573 in shipped Berlin)
   are saved with rotation 0, whichever side their road is on (the road of 1x1 lots is on each of the four sides in
   about equal numbers, for stock and imported lots alike). So the face a player sees depends only on the view
   rotation. The tool puts the model's +Z front on the lower-right face in slot 0, the side the stock shopfronts of
   156 / 3020 show in slot 0; in `02_closeup` a cottage's door looks away from the road beside it, as stock houses
   do. [The developer code that gives state 0 was not read; the evidence is the saves.]
2. **Size**: 16 m per cell (the classifier's value) makes the test houses the size of the stock cottages. The engine
   has no metre unit to measure against, so this stays a visual match.
3. **Zoom 4** is drawn natively (own records, scale 0). It is sharper than the stock buildings around it, which
   show zoom 3 doubled.

## Not tested

Reload of a save with the buildings, and a load without them: the same containers and id handling are proven by
batconvert (verify/batconvert/RESULTS.md 3-4). Query dialog / "Copiar ID" on an imported lot. glTF / FBX,
non-square lots, ploppables / airports / seaports (later rounds).
