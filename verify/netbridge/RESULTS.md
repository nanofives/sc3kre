# netbridge results (2026-10-13)

Pre-registration: `PRE.md` (commit `fefa46d`, before any code). Branch `child/netbridge`. Test tree
`Simcity_stock_netbridge` (hard links to `Simcity_stock`, stock DLLs), packs installed in overlay mode, instances
`inst_netbridge` (sc3netmod.dll from this branch + sc3resize for frame dumps) and `inst_netbridge_ctl` (no
sc3netmod.dll: the game is exactly stock there). City: copies of `Roadless Paradise` (free flat land and water) and
`Berlin, Germany`. Raw cell reads (`*.jsonl`, `nb_drive.py cells`) and frames sit beside this file and are not committed
(frames are game art).

Placement without the mouse: `re/tools/netmod/nb_drive.py build` calls manager vt+0xf0 (`FUN_10014a23`) on the game
thread. Two things the UI does first had to be reproduced, both measured: the cells must be marked in SIMSPR's
drag-highlight grid (`FUN_1004adcd` answers the tool code 0x23 only for cells whose low nibble is 1), and the bridge
builders ask manager vt+0x140 (`FUN_10006018`, the "bridge costs $N" dialog), which the tool answers Yes. Highway cells
go in pairs, the second lane at -1 on the other axis, as two UI highway drags sent them (34 cells each, captured).
Removal: manager vt+0xb4 (`FUN_1001d6ef`) with the argument shapes of the game's own bulldozer call
(SIMGEOM+0x142cf, watched during a UI demolish).

## Build sequence (same in every Roadless Paradise arm)

1. road (19,31)-(30,31): crosses 4 water cells
2. highway x=122, z=5..19 (two lanes, x=121/122)
3. road (116,12)-(128,12) across the highway; 4. rail (116,16)-(128,16) across the highway
5. road (126,7)-(134,7); 6. rail (130,5)-(130,10) across that road
7. road (13,10)-(30,10): crosses 10 water cells
8. remove (25,31) (a span tile of the first bridge)

## Arms

| arm | setup | result | verdict |
|---|---|---|---|
| G0 (control) | no DLL, stock | bridge 18051.2 / 87 88 87 88 / 18051.0; L=10 bridge 18051 / 11268 11269 83 82 81 x2 / 18051; highway lanes 73.2 / 73.0, ends 11237 / 11235; road x highway 11258.2 / 11258.0; rail x highway 16006.2 / 16006.0; road x rail 69.0; removing 87 at (25,31) removes the whole bridge (22..27) | reference |
| B1 | G1: 4 packs + DLL | bridge 28051.2 / 20087 20088 20087 20088 / 28051.0: the pack's record, same layout as control | **met** |
| B2 | G1 | L=10: the stock layered bridge, identical to control (18 of 18 cells) | **met** |
| H1 (built) | G1 | highway lanes 20073.2 / 20073.0 on all 22 cells where control has 73, ends 11237 / 11235 as control | **met** |
| H2 | G1 | road x 20073 = 11258.2 / 11258.0, as control | **met** |
| H3 | G1 | rail x 20073 = 16006.2 / 16006.0, as control | **met** |
| X1 | G1 | rail x 20029 = **20069.0** (blue crossing, XCROSS log `variant crossings=1`); frame shows the blue base under the rail | **met** |
| B3 | G1 | removing 20087 at (25,31) removes the whole bridge (22..27), as control | **met** |
| G1 vs G0, all reads | | 102 cells: 58 equal, 44 "variant of the same piece" (base in G0, its variant in G1, same state), **0 other differences** | **met** |
| H4 / B4 / X2 save | G1, Save | log `save: 44 variant tile(s) written as base, section 0x4E56 written`; `netvariant.py scan` lists the 44 | |
| G2 | the G1 save loaded with NO DLL (stock) | every tile present, as its base: identical to G0 on all 96 cells (0 differences) | **met** |
| G3 | the G1 save loaded with the DLL | log `load: all 44 variant tiles restored`; identical to G1 before the save on the 78 cells read (0 differences) | **met** |
| H1 (retile) | Berlin copy, 4 packs + DLL, GZ retile `0x637c0dab` mask 1, rect 110,25-150,60 | `netrules preview --rect` on the merged rules predicted 74 changes (4 highway 73 -> 20073, 70 road 29 -> 20029); the game changed exactly those 74 cells, none else (1,031 unchanged in the read box) | **met** |
| H5 traffic | Berlin TCh (stock tiles) vs TMh (all 194 tiles 73 set to 20073 offline), 120 s at speed 3 each, saved | `surf_live` on the 194 highway cells: 0 in the stock file, 0 in TCh, 0 in TMh. Highway tiles hold 0 in both density grids in all 15 shipped saves (about 2,700 tiles of 73), so this oracle cannot see highway traffic. Whole-city `surf_live`: TCh 1,117,637, TMh 1,104,735 (one run each, spread not measured, not a finding). No crash, the date advanced in both | **not measured** |
| AB0 | G1 setup, `SC3NETMOD_XCROSS=0 SC3NETMOD_INHERIT=0`, before Collapse.txt inheritance existed | rail x 20029 = 69.0 (stock crossing art, the opt-out works); removing 20087 removed nothing, not even that tile | opt-outs work; shows the DLL mapping was what made B3 pass then |
| AB1 | packs re-merged with Collapse.txt inheritance, `SC3NETMOD_INHERIT=0` | removing 20087 removes the whole bridge (22..27): the data layer alone is enough | **met** (not pre-registered) |
| FIN | final install (Collapse data) + DLL fully on | identical to G1 on all four reads (0 differences) | **met** |

Frames (in-process dumps, display awake): `G1_bridge.png` (red bridge at the centre, stock layered bridge of the L=10
crossing top left), `G1_hway.png` (yellow highway, stock grey crossing tiles where the blue road and the rail cross it),
`G1_xcross.png` (the blue crossing under the rail).

## What was not run

- Highway diagonals and onramps (`FUN_10009d20`, `FUN_1000abde`): the INHERIT thunks are in place (29 of 29 sites
  patched) but no arm built a diagonal highway: `highway id reads mapped=0` in every log. Static only.
- A HWAY bridge style in game (format, lane-pair warning and limits are checked offline only).
- Removing a variant crossing (20069) again; the owner's dev install (MAIN\Apps); the release layout; 1024 cities.
- Direct-mode install (no DLL) was not run in game; AB1 shows the Collapse data works without the DLL mapping, and
  `NEW_PIECE.md` 4 lists what direct mode loses (crossings, stock-safe saves).
