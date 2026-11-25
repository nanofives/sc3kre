# stcompat: two Simtropolis reports with our mods + thronevintagetech's SC3KU package (2026-11-25)

Child `stcompat`, branch `child/stcompat`, tree `dev\stcompat\tree` (LAN release 2026-11-25). Windowed 800x600, posted
input only, game calls by Frida on the game thread (`work/lab.py`, copied from rotplace's lab), pictures by
`SC3RESIZE_FRAMEDUMP`. Every game PID was started by `sc3dev.ps1 run stcompat` and stopped by PID. Third-party material:
`dev\_ext_sc3ku_1109\` (Standalone + Source zips of SC3KU Enhancement Package v2026.11.09, each extracted to its own
folder; `Installer.ps1` read, not run: its terrain component is 4 plain file copies, which were copied by hand into the
tree after deleting the hard links, and put back to stock afterwards).

| report | cause | ours? | fix |
|---|---|---|---|
| 1. land drawn red/magenta speckle on dark blue | the land's water-surface table sits above its ground, so the cells are coloured as seabed; Natural World's water palette makes that look red | the look: no (palette values). The trigger: unknown, needs the player's save | none in code; player steps below; a tip for the palette author |
| 2. five rewards stay Western in an Asian city | our STYLEPICK gave every New City the North American skin; the Asian set has art for all five | yes | SPNEWSKIN in sc3netmod (built, measured) |

## 1. Terrain speckle

### What the picture is (measured)

- The player's land pixels are Natural World PALWATER colours: most common (8,32,107), (8,32,99), (16,40,115), which are
  PALWATER rows 30..48 as 16-bit, plus (255,20,99) / (255,20,90): the same colours with red wrapped to 255. Red share
  of the land area: 22.5%.
- Their Natural World files are byte-identical in colour to our `sc3natworld.bin` (all 8 palettes 100.0% equal, same
  sizes 32x512 x5, 1x256, 1x512 x2). So a palette mismatch between their files and our NATWORLD redirect is ruled out.
  With their files installed, NATWORLD off and on: normal terrain (Seoul, no speckle).
- SIMDIRT draws a cell's corner colours with one of three functions, all caching a 16-bit colour per vertex in
  `DAT_10025bac+0x2c`: land `0x1001309e` (land palette, row = water - ground + 256), shore `0x100144ff` (edge palette)
  and water `0x10013fab` (palette 6 = PALWATER, row = water - ground, the depth) `[CONFIRMED @ those addresses]`.
  `+0x18` is the ground table, `+0x20` the water-surface table, `+0x1c` the shade.
- Reproduction: `lab.py seabed 90 50 110 70 40 clear` (Roadless Paradise) raises the water table to ground + 40 on a
  21x21 box. Before a reload, only some cells switch to the water function; after an autosave and a reload the whole box
  draws as the player's picture: red share 20.7% against the player's 22.5%, the same blues, land outside the box and the
  minimap unchanged (player's minimap is normal too). `owner_shots/1_player_vs_repro.png`.
- Same state with stock palettes: plain dark blue, no red (`owner_shots/2_seabed_nw_vs_stock.png`). Stock PALWATER keeps
  red at 20 or more down to row 128; Natural World's rows from about 30 down have red 16 or less (4 at the deepest), and
  the land texture noise (up to about 16 per channel) wraps the byte.

So: the player's city has land whose water table is above the ground. Natural World only makes it visible as red.
With stock palettes the same land would be dark blue.

### What raised the water table: open

- None of our mods writes the water-surface table. sc3undo hooks `SetWaterTable` (DirtBag `+0x88`) and `BlockCell`
  (`+0x15c`) to journal the game's own writes and replays per vertex; SALTFIX, TERRPANEL and NATWORLD only read the dirt
  object. A fresh 512 New City with Natural World palettes showed no speckle.
- Their weather, snow and forest DLLs are cheat-driven and do not write the table (source read). Their hydro dam
  (`Standalone/Source/Hydro/dam_lifecycle.c`) swaps the DirtBag vtable for a copy and blocks cells, and refuses to start
  when slot 87 (`+0x15c`) is not stock; our sc3undo patches that slot, so with our mods their dam stays off (static read,
  not run).
- Modern Camera, Agricultural Zone and Ambient Sound Fix: not available here, untested.
- The player's `.sc3` settles it in one load: `lab.py seabed x0 z0 x1 z1 0` prints ground and water at the speckled
  cells, and the save's history shows whether a terrain tool, a water tool, an Undo or a dam touched that land.

### What the player can do now

1. Send the save (`.sc3`) of that city, and say which tools were used on that land before it turned red (terrain
   raise/lower/level, place water, Undo, a dam, Modern Camera).
2. To get normal colours back meanwhile, remove the Terrain component of the SC3KU package (its `Remove.cmd`, or restore
   the 4 backed-up files in `Apps\Res\Dirt\Palette`). The land will then show dark blue instead of red: same cells, the
   water table is still above them.
3. Our own Natural World switch (terrain panel, "Natural World") gives the same colours without replacing game files, so
   with the package's Terrain component removed the player can keep the look in other cities.

For the palette author: keeping every PALWATER / PALEDGEL / PALEDGED channel at 16 or more would stop the wrap.

## 2. Rewards stay Western in an Asian city

### Cause (measured)

- Stock: the Asian set archive `BuildingSets/6523f3d5/MBE_0015.dat` holds exemplars for all five rewards: City Hall 208,
  Historic Statue 219, Mayor's House 243, County Courthouse 8013, Lighthouse 8019 (keys `{0x207EDC0E, 0x57E, id}`). The
  European set has 208, 8013, 8019. A city whose skin is the Asian set draws them Asian.
- Ours: sc3netmod STYLEPICK (released 2026-11-21) gave every New City skin 0 (`pass = 0` in `sp_scs`, logged as
  `SetCityScheme from New City ... asked set 6523F3D5, skin 00000000 -> 00000000`, verify/stylepick item 7). The Asian
  pick then only filters growables, and civic buttons have the CIVSTYLE look list. Everything else the set re-skins
  stays North American for the life of the city: 20 Asian-set exemplars that are neither a family member nor a civic
  base (the five above plus Performing Arts 8011, Stock Exchange 8017, Stadium 8020, GigaMall 8085, Lumber Mill 8054,
  Grain Silos 190, three parks, ...), 12 for the European set.
- Their package: its `BuildingReplacementRows.json` only adds `[replaceablebuildings]` rows for its own 19 buildings
  (`old: null`), and `[BuildingSets]` / the stock rows are unchanged in our overlay `SYS.PAK`. Not involved.
- In game (Roadless Paradise, skin 0): 3 statues, 2 Mayor's Houses, 2 City Halls, 2 Courthouses, 3 Lighthouses placed
  by `lab.py place`, all North American. `lab.py scheme 6523F3D5 0` (SetCityScheme, the call City Properties makes in
  stock): the same 12 buildings redraw with the Asian set's art. `owner_shots/3_rewards_skin_na_vs_asian.png`.

### Fix: SPNEWSKIN (sc3netmod, `re/harness/src/sc3netmod_stylepick.c`)

A New City passes the picked set to SetCityScheme, as stock does. Nothing stands on a new map, so the skin re-Inits
nothing. The style filter works the same on either skin (North American copies +2600000 exist for European and Asian
skins, style_mix 1.1.0). City Properties still never re-skins and a load still keeps the saved set.
`SC3NETMOD_SPNEWSKIN=0` = the old rule. Start log: `stylepick: SPNEWSKIN on (a New City takes the picked set as its skin)`.

Measured (built into `dev\stcompat\inst`): main menu > Nueva Ciudad > Edificios Asian > OK logged
`SetCityScheme from New City (ret 0x03A71D24): asked set 6523F3D5, skin 00000000 -> 6523F3D5, style Asian + mix`; the
scheme read back `set 0x6523f3d5`; Accept; the five rewards placed in that city draw Asian
(`owner_shots/4_spnewskin_newcity_asian_rewards.png`). No fault in that run.

This changes behaviour the owner approved on 2026-11-21 ("a New City keeps set 0"), for New Cities only. Owner call:
keep SPNEWSKIN on (stock behaviour for new maps), or ship it off.

### What the player can do now (existing city, any build)

1. Open "Activar mods" and untick "Style picks new buildings" (`SC3NETMOD_STYLEPICK`), OK, restart the game.
2. Load the city, Options > City Properties, Buildings: Asian, OK. The stock re-skin turns every building the Asian set
   covers Asian, rewards included (verify/stylepick item 6: with the row off, the picker re-skins). Save.
3. Optional: tick the row again and restart. The city keeps its Asian skin (saved set). The style becomes Asian with
   "Mix" on; untick Mix in City Properties if only Asian buildings should grow.

New cities need nothing once SPNEWSKIN ships.

### Look-swap screen for rewards: can CIVSTYLE cover it?

Partly, and not as a small change, so it is not built:

- Data, small: `CIVIC_BASES` in `re/tools/netmod/netpack_stylesets.py` drives the style_mix civic copies. Adding the
  reward ids makes the European / Asian / North American copies (same type id and footprint, checked by
  `_civic_check`). Cost: a style_mix version bump and the netpack re-merge (about 45 min per install).
- Code, medium: `cv_looks` / `cv_pick` are reached only from the civic command hook (SIMGEOM `0x1000b1a3`) and the
  Marina call (`0x1000afc0`). Rewards are placed from the City Planner catalog: SIMUI `FUN_10011919:60-68` calls the
  building layer `+0x50(attrib, 1, 0)` (CIVIC_REWARD.md 2.3). That call needs its own hook, plus a way to choose (the
  catalog dialog is already the list, so either extra rows per look or the cycle). The City Planner marks a reward
  placed by type id, and copies keep the type id, so unlocks and "already built" keep working (same as civic copies).
- With SPNEWSKIN, an Asian city gets the Asian rewards by default, which is what the player asked first.

## Other findings on the way

- Their Roads component overwrites `TilingRules\ROAD/RAIL/HWAY_GRND_Set.txt` and `*_Bridges.txt`, `CSATTRIB.IXF` and
  `00000005_Roads.DAT`; sc3netmod serves its own copy of the `_Set.txt` files from `mods\netmod\overlay` and merges player
  edits through `overlay_base.txt` (OVMERGE). Not run together here.
- `iso vt+0x14c` (full repaint, the rotplace lab's `bench`) killed the game in this tree twice with no VEH line. The lab
  forces a redraw with a camera zoom change instead.
- Their README: "Use one edition per installation. Combined already includes NanoFives." Their Combined source carries a
  copy of our sc3bigcity with the same 12 SIMDIRT sites and stride 1025, so a double install does not desync the vertex
  cache.

## Files

- `re/harness/src/sc3netmod_stylepick.c` (SPNEWSKIN), `re/analysis/BUILDING_PICK.md`, `re/analysis/COMMUNITY_MODS.md`
- `verify/stcompat/RESULTS.md`, `verify/stcompat/work/lab.py` (jobs `seabed`, `skin`, `scheme` added)
- Pictures (not committed): `MAIN\verify\stcompat\owner_shots\` 1..4
