# netramp: pre-registration (2026-10-13)

Task: ramps, interchanges and slope pieces as moddable tables (netmod step 4b). Analysis: `re/analysis/NET_RAMPS.md`.
Code: `re/tools/netmod/netramp.py` (registry + manifest section `ramps` + `mirror_base`), `netpack.py` (wiring),
`re/harness/src/sc3netmod.c` NETRAMP block (applies `ramp` lines, classifier mapping). Fixture package:
`re/tools/netmod/examples/example_ramp_variant` (variants 25131/25135/25139 of on-ramp pieces 15131/15135/15139, green,
`mirror_base`, `ramps`: those three ids in the `onramp` table, both states = slots 12, 13, 14, 21, 22, 23).

Tree: `Simcity_stock_netramp` (hard links of `Simcity_stock`, stock DLLs). Instance `re\harness\inst_netramp`:
mods_launch (-multi), sc3resize (frame DUMP only), sc3netmod from this branch. City: Roadless Paradise copy.
Build sequence (same in every arm, all through the game's own tools, cmd ids from MenuItem.INI):
Highway (0x10004301) drag (95,145)->(108,145); Road (0x10004001) drag (101,139)->(101,151); On-ramp (0x10004302) click on
cell (103,143). Before the click the road tool is hovered once (resets the stock point cap DAT_100322a4, see below).

Already measured on stock data with a NETRAMP-less DLL (arm S0, 2026-10-13 13:0x, fixture `fx_onramp_stock.sc3`):
strip (102,143) 15139.0, (103,143) 15135.0, (104,143) 15131.0; road cell (101,143) 15046.2; highway lane
(104,144) 15120.0, (105,144) 15116.0, (106,144) 15147.2; FUN_1000abde returned 1 with 3 points.

| arm | setup | prediction (met if all hold) |
|---|---|---|
| A0 | new DLL, pack NOT installed | the S0 cells exactly; log `ramp: 0 slot(s) changed` |
| A1 | pack installed (overlay), new DLL | log: 6 `ramp: onramp slot N` lines, `3 variant id(s) classified as their base`; strip (102,143) 25139.0, (103,143) 25135.0, (104,143) 25131.0; every other cell of x 96..108, z 139..150 equal to A0/S0; live class of 25139 = SIMNTWRK+0x2a020 (kind 14, as 15139), of 25131/25135 = SIMNTWRK+0x29e74 (kind 15) |
| A2 | A1's game, then the On-ramp tool on the other side, cell (103,146) | strip (102..104,146) = stock 15138.0/15134.0/15130.0 (slots 15-17 not in the pack), road (101,146) 15045, lane z=145 merge pieces as stock rules give |
| R | A1's game | frame dumps of the strip at zooms 1..5 x 4 rotations: the A1 strip draws green, the A2 strip grey; no missing tile |
| S | A1's game, Save | file: the three cells hold 15139/15135/15131 (base) and section 0x4E56 lists 3 entries; stock instance (no DLL, data uninstalled) loads it with the base pieces; with DLL + pack the 3 variants come back |
| B | A1's game | Bulldozer on (103,143): all three variant tiles go (Collapse group 7 holds the variants), as the stock strip does in A0 |
| T | Berlin, pack + DLL, On-ramp tool at an x-strip whose slots are 12-14 or 21-23 (candidate (231,145)) | after >= 60 s of sim, traffic density on the variant strip cells > 0, comparable to a stock strip built the same way (exploratory) |
| X | `SC3NETMOD_RAMPS=0`, pack installed | the strip is stock (15139/15135/15131): the table lines are the only path a variant gets in |

Stock quirk found while setting up (not an arm): the On-ramp tool's hover adds selection points through FUN_10004754,
which stops at the global cap DAT_100322a4 < 0x200; only FUN_1000488d (drag path) resets it. After ~500 hover points
the tool selects nothing until a road/rail drag tool is used.
