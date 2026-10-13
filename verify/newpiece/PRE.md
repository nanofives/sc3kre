# newpiece: pre-registration (written and committed before any game run, 2026-10-12)

Question: can SC3U use a network piece id that does not exist in stock, with its own art, placed by the tiling
rules, and keep it across save/load?

## Setup

- Tree: `C:\Users\maria\Desktop\Proyectos\Simcity_stock_newpiece\`, hard links of `Simcity_stock` made by
  `re/tools/netmod/link_tree.py` (stock GOG DLLs, Spanish text, no release mods in Apps). Instance
  `...\re\harness\inst_newpiece\` with `mods_launch.exe -multi` and `sc3resize.dll` built from `child/newpiece`
  (base `round/1012`, which holds QUERYID "Copiar ID"). No other mod.
- Mod files: `re/tools/netmod/newpiece.py build --stock Simcity_stock --id 20029 --src 29 --tint blue` ->
  `verify/newpiece/mod_blue/` (manifest with sha256). Installed with `newpiece.py install` (delete + copy), removed with
  `uninstall` (relink to stock). Contents:
  - NEW `Res\Occupant\OccupantAttribs_Korea.IXF`: exemplar `{0xE223741F, 0xA317745F, 20029}` = byte copy of piece
    29's, prop 0x67 rewritten to `{0x6300, 0x55908ADB, 20029}`.
  - NEW `Res\Sprites\CSAttrib_Korea.IXF`: frame table `{0x6300, 0x55908ADB, 20029}` = copy of CSATTRIB 0x1D, frames
    pointed at group `0x4E3D0001`, instances `0x4E3D0000..13`.
  - NEW `Res\Sprites\4E3D0001_NewPiece20029.DAT`: piece 29's 20 anchor records verbatim + 20 pixel records tinted blue
    (`verify/newpiece/frames_stock_vs_new.png`).
  - `Res\SSimData\<7 langs>\TrBlkAtt.IXF`: + records `0x4E3D00`, `0x4E3D01` (copies of `0x1D00`, `0x1D01`).
  - `ROAD_GRND_Set.txt`: + `20029`. `ROAD_GRND_SimpleRules.txt`: the two bare straight RESULT lines (77, 105)
    `7425 -> 5127425`, `7424 -> 5127424` (the T2 lever).
- City: copy of `Cities\Roadless Paradise.sc3` in the instance folder (has rail and power lines, no road).
- Oracle 1 (file): `network_layer.py --diff` between the loaded copy and the saved copy, per tile piece / state / props.
- Oracle 2 (pixels): sc3io grabs, looked at.
- Oracle 3 (live): "Copiar ID" block on the drawn tile.

## Arms and predictions

**C (control, mod uninstalled).** Draw one straight road along each axis on flat empty land, save (fire 0x10009002).
Predict: middle (straight-mask 5/10) tiles = piece 29, state 0 on one axis and 1 on the other (word0 bits 30-31),
props 0x3000; ends = 11225. This run is also the in-game rotation diff for Step A.

**M (mod installed).** Same drawing. Predict, if the hello world works:
1. the game starts and loads the city (no crash from the new containers);
2. straight middles = piece 20029, same state as C on the same axis, props 0x3000; ends unchanged (11225);
3. the drawn middles render blue at the default zoom; Copiar ID prints `network.piece_id: 20029`, `network.sets: ROAD`,
   `object.key: 0xE223741F 0xA317745F 0x00004E3D`, `network.trblkatt_key: ... 0x004E3D0x`;
4. save, quit, relaunch, load the saved copy: the tiles read back 20029 in the file and render blue again;
5. blue at all 5 zooms and 4 rotations.
If 1 fails: bisect by rebuilding with `--no-trblk`, then without the Korea files, and record the deciding file.
If 2 fails with 29: the Set/rule edit did not take (check the files in the tree). If 2 gives 20029 but 3 is not blue
or is invisible: the exemplar or art chain is the break, and its link is named from the Copiar ID block.

**X (crossings, exploratory, mod installed).** Drag rail across a 20029 tile and across a stock 29 tile (the stock
tile is made by drawing a road short enough not to be a bare straight, or in the control tree).
Static prediction from SIMNTWRK `0x100167d4`: a crossing forms only over 0x1d, 0x2c, 0x49, 0x0e, 0x0f, 0x5c, 0x2bc4,
0x3acb, so rail over 20029 does NOT form a level crossing (the call returns without placing); over 29 it does (69).

**R (exploratory).** Load M's saved city in the tree with the mod uninstalled. No prediction: record what happens to
tiles whose id has no exemplar (crash, invisible, dropped on load, or kept).

**T (traffic, exploratory, only if time allows).** Unpause with a road joining zones; compare `transit_layer.py`
surface sums with and without the mod. T3 of the tiling ladder was VOID, so a null here is not evidence either way.

## Not claimed by this test
Highway, rail, bridges, slopes, ComplexRules contexts, other topologies. Only the bare straight selector is retargeted.
