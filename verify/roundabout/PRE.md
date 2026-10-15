# roundabout: pre-registration (2026-10-13, written before the first game launch)

Task: ONE package for the demo junction, the 2x2 one-way mini roundabout of new piece 20400 (base road T 39, pinwheel
states 3,0 / 2,1), and an end-to-end proof in game. Package `re/tools/netmod/examples/roundabout/`:
artkit's art recipe (`recipe.json`, built at install time, `layout.json` = preview), lanekit's lanes + turn matrix
(`quarter.lanes.json`, `connects: auto`), multitile's template for 20400 (`rotonda`, rotate generate), names
`{"*": "Roundabout", "ENGLISH": "Rotonda"}` (the GOG Spanish install reads its text from `Res\Text\ENGLISH`). No rule
edits. `example_roundabout` and `example_roundabout_art` are folded into it (removed), so no package pair declares
20400 any more; `example_roundabout_lamps` (20401) and `example_template_rotonda` (21039 / 21035) stay.

Static facts already measured (worktree, before launch): `netpack.py validate`: OK, 0 ERROR, 1 WARNING (the 4
orientations of `rotonda` are identical: the pinwheel is symmetric under the quarter turn, so key R changes nothing on
the map); two `build` runs: 25 files, sha256 identical.

Trees: `C:\Users\maria\Desktop\Proyectos\Simcity_stock_roundabout` (hard links of `Simcity_stock`, stock DLLs, the
package installed in overlay mode), and `Simcity_stock_roundabout_ctl` (hard links, nothing installed; control). One
tree per running instance so sc3resize's dump trigger file in `Apps\` is never shared. Instances
`re\harness\inst_roundabout` (+ `inst_roundabout_nomod`: sc3resize only, no sc3netmod) and `inst_roundabout_ctl`;
mods_launch, sc3resize, sc3netmod built from `child/roundabout` (= round/1012 c6c0f8b code). Drivers: `mt_drive.py`
(+ `nramp_trace.py`), `np_drive.py`, `nramp_cam.py`, `lk_probe.py`. Every PID mine, stopped by PID.

Predictions marked SIM come from `netpack_templates.py place examples/roundabout <city> X,Z --template rotonda --road ...`
(tiler.py, stock rules + the package's merged rules).

## Run R: placement, roads, camera, save / load, demolish (Roadless Paradise copy)

| arm | setup | prediction (met if all hold) |
|---|---|---|
| L | launch with the package + DLL | sc3netmod log: template `roundabout/rotonda`, 4 orientations, cost 400, flags 3; `3 of 3 slots wrapped`; overlay on |
| K | key T, then key R once | log: `key T -> template 1 roundabout/rotonda`, then `key R -> ... orientation 1` |
| P | after K, hover + click with the anchor on (120,120) | log PLACED cost 400, funds - 400; cells `20400.3 20400.0 / 20400.2 20400.1` (orientation 1 = orientation 0, SIM) |
| C | Road tool drags N (121,119)->(121,116), E (122,121)->(125,121), S (120,122)->(120,125) | (121,116..119) 29.1, (122..125,121) 29.0, (120,122..125) 29.1 near the template (far ends may become road endings 11225.x, as multitile arm C); template cells unchanged (SIM) |
| N | road (116,121)->(119,121): it ends at (119,121), against the closed W side of cell (120,121) | (116..119,121) 29.0: a plain straight pointing at the closed side; template unchanged (SIM; same stock Simple-stage result as multitile arm N) |
| N2 | then the W exit road (116,120)->(119,120), beside the arm-N road | SIM: both rows become avenue, (116..119,120) 11204.2 and (116..119,121) 11204.0; template unchanged. Exploratory: no prediction on whether cars use the avenue into the W exit |
| V | `nramp_cam.py` centred on (120,120), zooms 0..4 x rotations 0..3 (20 in-process dumps) | the block draws as a roundabout in all 20 (checked by eye against artkit's offline composite, no bar on a match score: artkit showed stock pieces top out near 95 %) |
| S | Save (0x10009002) | log `save: 4 variant tile(s) written as base`; `netvariant.py scan` of the file: 0 raw 20400 tiles, section 0x4E56 lists the 4 cells |
| S0 | open that save WITHOUT the mod (`inst_roundabout_nomod`: no sc3netmod, so no overlay, no variants) | loads; the 4 cells hold `39.3 39.0 / 39.2 39.1`; every other network cell in x/z 112..129 equal to the S grid |
| S1 | reopen the same save WITH the mod | log `load: all 4 variant tiles restored`; cells 20400.x again, grid equal to S |
| B | on S1's game, Demolish (0x1000400A) one template cell (121,121) | all 4 template cells go; the exit roads stay (their ends re-tiled) |

## Run T: traffic on the ring (Berlin copy; arm and control at the same time)

Site = lanekit's arm D2 site: Berlin (25,181) .. (26,182), stock `43.0 39.0 / 39.2 39.1` with roads on all 4 exits
((24,181) 29.0, (26,180) 11203.0, (27,182) 39.3, (25,183) 29.1) and one road against a closed side ((25,180) 39.2).

| arm | setup | prediction |
|---|---|---|
| TP | arm instance: key T, click with the anchor on (25,181), over the four stock road cells | SIM: PLACED, cells `20400.3 20400.0 / 20400.2 20400.1`, (25,180) 39.2 -> 11203.2 (its arm toward the closed side dropped), the 4 exit roads unchanged. Two outcomes named in advance: placed as SIM, or REFUSED by the occupant test (then: Demolish the 4 cells, place again, record the deviation) |
| TR | both instances: camera on the site by `nramp_cam.py` (zoom 3, rotation 0), speed key 4, `lk_probe.py --watch` the ring + 8 neighbours, `--cells` the 4 site cells, about 480 s | arm: street-sim ring-to-ring moves with the ring order >= 30 and against it = 0; ring -> exit and exit -> ring both > 0. Control: against > 0. Ring order (26,181) -> (25,181) -> (25,182) -> (26,182); exit code / 8 = side x-, z-, x+, z+ (settled from lanekit's probe_D3 counts) |
| TD | same runs, SimTransit density `+0x6c` summed over the 4 site cells (rows[x][z] order) | no prediction with stock SimTransit: lanekit showed road density ignores lanes and the matrix. Reported for both. If `lanedensity`'s build exists before this run ends, TR / TD are repeated with it and both numbers reported; otherwise that is stated |
| TS | arm game after TR: save, reload with the mod | log `load: all 4 variant tiles restored` |

Not in scope: English-UK, 1024 cities, the release layout with the package installed, the owner's dev install.
