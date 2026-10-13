# multitile: results (2026-10-13)

PRE: `verify/multitile/PRE.md` (committed f2bc17c before the first launch, addendum 1 in 1cdee76 before arms AB / B0 /
F / X). Tree `Simcity_stock_multitile` (hard links of `Simcity_stock`, stock DLLs), packages installed in overlay
mode, instance `re\harness\inst_multitile` (mods_launch -multi, sc3resize + sc3netmod from `child/multitile`). City:
copies of Roadless Paradise. Driver: `re/tools/netmod/mt_drive.py` (posted input through sc3io, live cells through
`np_drive.py cells`, cell under the cursor through `nramp_trace.py`). Logs, saves and raw frames stay in the instance
folder (`run1..run5_sc3netmod.log`, `S_after.sc3`, `shots\`). Owner images: `MAIN\verify\multitile\owner_shots\`.

| arm | outcome | verdict |
|---|---|---|
| L | log: both templates read (`rotonda4` 4 orientations cost 400, `rotonda3` cost 350, flags 3), `2 template(s), 3 of 3 slots wrapped`, window subclassed at 1.1 s | met |
| H | key T selected the On-ramp tool in template mode; hover on (120,120): 4 cells highlighted, the tool's cost label shows $400 (`h1.png`, owner shot 01) | met |
| P | log `rotonda4 rot 0 PLACED at (120,120) 2x2, 4 cell(s), cost 400, funds 24835 -> 24435`; live cells `21039.3 21039.0 / 21039.2 21039.1` (SIM identical); every other cell of x/z 117..124 unchanged | met |
| C | four Road tool drags into the four exits: template cells unchanged; (119,120) 29.0, (121,119) 29.1, (122,121) 29.0, (120,122) 29.1 as SIM; the far ends became road endings 11225.x (outside the SIM box, not predicted) | met |
| N | `rotonda3` o0 at (132,120), road (132,122)->(132,125) ending at the curve's closed side: template unchanged, (132,122) = 29.1 as SIM (the straight points into a side with no arm, the stock rules' Simple stage result) | met |
| R | `rotonda3` o0 (132,120) `21039.3 21039.0 / 21035.2 21039.1`, o1 (138,120) `21035.3 21039.0 / 21039.2 21039.1`, o2 (128,126) `21039.3 21035.0 / 21039.2 21039.1`, o3 (138,130) `21039.3 21039.0 / 21039.2 21035.1`: each equals the netpack picture | met |
| W (slope) | o2 first tried at (132,130): `REFUSED: cell (132,130) not flat`, funds unchanged (23495 before and after); tiler.py `flat()` is false on all 4 cells there too | met (slope only; water, building and protected-piece refusals not run) |
| S | save (menu 0x10009002): log `save: 20 variant tile(s) written as base`; `netvariant.py scan`: 0 raw variant tiles, section 0x4E56 with the 20 cells (ids 39 / 35 -> 21039 / 21035). Reload with DLL + pack: `load: all 20 variant tiles restored`, live grid identical. Release layout (`Simcity_stock\Apps\mods_launch.exe`, no pack, no sc3netmod): the 20 cells hold 39.x / 35.x, nothing dropped (owner shot 06) | met |
| S+ | on the reloaded city, road (134,121)->(137,121) between two templates (into one's exit, ending at the other's closed side): both templates unchanged | met (not pre-registered, extra) |
| B | Demolish (0x1000400A) on (121,121): all 4 cells of that template gone, the 4 roads re-tiled to endings 11225.x; netbridge stats `collapse ids mapped=0` (template ids kept out of the INHERIT mapping) | met |
| B0 | `nocollapse4` (protected, no Collapse group) at (126,118), Demolish on (127,119): only that cell went, the other 3 stayed | met (first named outcome); the group is what removes the whole template |
| AB | `noprotect4` (pieces not Protected) at (126,114): log PLACED, live cells `11203.3 11203.0 / 11203.2 11203.1` right after the click, as SIM; the game's retile made its own 2x2 loop (owner shot 05) | met |
| F | `tooexpensive` (cost 9,999,999): `REFUSED: funds 24435 < cost 9999999`, nothing placed | met |
| D | shared demo (addendum 2): `demo_rotonda20400/rotonda` at (120,120): log PLACED cost 400 (24835 -> 24435); cells `20400.3 20400.0 / 20400.2 20400.1`; after the 4 road drags: (119,120) 29.0, (121,119) 29.1, (122,121) 29.0, (120,122) 29.1, template unchanged; draws as a roundabout with artkit's art (owner shot 07) | met |
| X | `SC3NETMOD_TMPL=0`: log `tmpl: off (SC3NETMOD_TMPL=0)`, no subclass line, key T logged nothing, On-ramp hover gave 1 point (`trace_x.jsonl`) | met |

Not run: traffic over a template, water / building / protected-piece refusals, a `required` exit, 1024 cities, the
owner's dev install, the release layout WITH the template pack.

Functions read for this task (SIMNTWRK unless noted), all `[CONFIRMED]` at the cited address in `re/analysis/MULTITILE.md`:
FUN_10008919, FUN_10009613, FUN_1000abde (funds test 0x1000ad3e..ad4d, spend 0x1000bcd2), FUN_10009d20 (start, end),
FUN_10004754 (disassembled, ret 8), FUN_100145aa, FUN_100151f1 (entry), FUN_10013afe, FUN_1002207c, FUN_10016ccd,
FUN_10016d69, FUN_1001a7f7, FUN_10005f83, FUN_10005fad, FUN_100041e4, FUN_100106b8, FUN_1000f72c, FUN_1000f79c,
FUN_1000f9b7, FUN_1001c102 (charge site); vtables 0x1002c1b0 / 0x1002c184 / 0x1002c7bc read from the PE. The two
read-only surveys (tool path, removal path) are summarised in MULTITILE.md section 2.
