# multitile: pre-registration (2026-10-13, written before the first game launch)

Task: place multi-cell NEW intersections as netpack TEMPLATES (format + placement in game + protection + proof).
Code: `re/tools/netmod/netpack_templates.py` (format, rotation, arms check, tiler placement simulator), `netpack.py`
(wiring: Protected list + Collapse group + table lines), `re/harness/src/sc3netmod_tmpl.c` (TMPL block),
`sc3netmod_bridge.c` (template ids kept out of the INHERIT collapse mapping). Fixture package:
`re/tools/netmod/examples/example_template_rotonda` (blue variants 21039 of road T 39 and 21035 of road curve 35;
templates `rotonda4` (4 exits) and `rotonda3` (3 exits)).

Tree: `Simcity_stock_multitile` (hard links of `Simcity_stock`, stock DLLs), package installed in overlay mode.
Instance `re\harness\inst_multitile`: mods_launch (-multi), sc3resize + sc3netmod built from branch `child/multitile`.
City: Roadless Paradise copy (`rp_base.sc3`). Placement anchor (120,120) unless the cell is not flat (then the first
flat 2x2 found, recorded in RESULTS).

How the player places a template (the mechanism under test): key T selects the On-ramp tool (menu command 0x10004302)
with template mode on; hover shows the footprint highlighted (the game's own add-point FUN_10004754); click runs the
wrapped build slot (manager vt+0xac): checks, FUN_10008919 per cell, funds spent through manager+0x38 vt+0x14, then the
rectangle retile FUN_100151f1 of the footprint. Key R turns the template.

Predictions marked SIM come from `netpack_templates.py place` on the same city (tiler.py, stock rules + the package's
merged rules); the commands are in the arm.

| arm | setup | prediction (met if all hold) |
|---|---|---|
| L | launch with the package + DLL | log: `tmpl: ... template example_template_rotonda/rotonda4, 4 orientation(s), 4 cell(s), cost 400, flags 3` and the same for rotonda3 (cost 350); `2 template(s), 3 of 3 slots wrapped`; `window ... subclassed for the T / R keys`; the variant lines `21035 -> 35`, `21039 -> 39` as before |
| H | key T once, hover over (120,120) | the On-ramp tool is selected; 4 cells highlighted (selection points = the footprint); the tool's cost label shows the template cost (400) |
| P | H, then click | log `tmpl: example_template_rotonda/rotonda4 rot 0 PLACED at (X,Z) 2x2, 4 cell(s), cost 400`; live cells (np_drive cells) X..X+1, Z..Z+1 = `21039.3 21039.0 / 21039.2 21039.1` (SIM: `place ... 120,120 --template rotonda4` after the click, identical); city funds drop by exactly 400; no other cell of the 9x9 box around it changes |
| C | P's game; road tool drags (114,120)->(119,120), (121,114)->(121,119), (122,121)->(127,121), (120,122)->(120,127) | template cells unchanged (`21039.x` as in P); the road cell next to each exit has an arm into the template (SIM: 29.0 / 29.1 at (119,120), (121,119), (122,121), (120,122)) |
| N | new placement of `rotonda3` orientation 0 (keys T T), then road (120,122)->(120,127), which ends next to the curve's side with NO exit | template cells unchanged (`21039.3 21039.0 / 21035.2 21039.1`); SIM predicts (120,122) = 29.1. Exploratory: whether the game's road drag (FUN_10014a23, not modelled) gives the same end piece |
| R | keys T T (rotonda3) then R, R, R, placing each orientation on its own flat spot | each placed block equals the netpack picture of that orientation (`validate` output: o1 `21035.3 21039.0 / 21039.2 21039.1`, o2 `21039.3 21035.0 / 21039.2 21039.1`, o3 `21039.3 21039.0 / 21039.2 21035.1`) |
| AB | same as P + C with the package re-installed with `"protect": false` on both templates | the click's own retile replaces the cells: SIM `--no-protect` gives `11203.3 11203.0 / 11203.2 11203.1` right after the click, and later road retiles change them again. Shows the Protected list is what keeps a template |
| S | save P/C's city; reload with DLL + pack; then load the save in the release layout without the pack | file: the template tiles hold base ids 39 / 35 and section 0x4E56 lists them; reload with DLL: the variant ids come back on the same cells; without the pack: grey T / curve pieces on those cells, nothing dropped |
| B | P/C's game, Demolish on one template cell | all cells of that template go (one Collapse group, `example_template_rotonda`), the road cells around get re-tiled ends. Alternative outcomes recorded as they come: only the clicked cell goes, or nothing goes |
| F | money below the cost (exploratory: set funds through the budget or a nearly broke city) | log `REFUSED: funds`, nothing placed, funds unchanged |
| W | hover/click with part of the footprint on water, a slope, a building or a protected piece | log `REFUSED: cell (x,z) <reason>`, nothing placed, funds unchanged |
| X | `SC3NETMOD_TMPL=0`, package installed | log `tmpl: off`; key T does nothing (not subclassed); the On-ramp tool behaves as stock |

Not predicted (no basis yet): traffic over the template (the variants copy their bases' TrBlkAtt, so cars should use
it as T pieces; checked only if time allows), 1024 cities, the owner's dev install.
