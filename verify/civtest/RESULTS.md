# civtest results (round 2026-11-19k): civic looks on other bases, rewards 1x1 / 3x3 / 4x4, a 3x3 growable

Tree `dev\civtest\tree`, mods of `dev\civtest\inst` (built from main 01d6e2f+, no source change), windowed 1600x1000,
started by `dev\civtest\work\civ_launch.py` (sc3wait.launch_game, the same env as `sc3dev.ps1 run`) under test-slot.
Posted input (sc3io) and Frida game-thread calls (`re/tools/civmod_lab.py`), camera by `verify/showcase/cam.py`,
pictures by SC3RESIZE_FRAMEDUMP (BMPs deleted). City Madison, WI unless named.

Test data: `make_testmodels.py --civtest` (new) -> `bldimport.py build --game dev\civtest\tree`: 21 buildings, ids
38000-38020. One civic look for each of the 17 bases (lot = the base's: 3x3 police, jail, fire, hospital, school, college,
museum, big park; 2x2 library, playground, pond, train station; 1x1 small park, fountain, bus stop; 4x4 zoo, baseball),
rewards 1x1 (stats of stock 219), 3x3 (208) and 4x4 (8017) with population 1000, growable 3x3 class 6300 (stats of 179,
24 families, weight 20).

**Verdict.**

- **Civic looks: work on every base.** 17 of 17 buttons cycle stock, look 2, stock. Fire, school, hospital and college
  looks placed with the stock tool, powered, each one reports its own service in the query window, survive save + reload.
  Removing the fire look removes one coverage circle from the fire map.
- **Rewards 1x1, 3x3, 4x4: work.** Unlocked, listed, placed (one-shot tool ends), gone from the list, saved, reloaded,
  still gone from the list, moved with "Mover".
- **3x3 growable: grows.** In Frankfurt (commercial demand positive) ours reached 16 lots in about 11 min while
  stock 3x3 members of the same class also grew. Europolis, Europolis 1024 and Madison built no 3x3 commercial lot of any
  kind, stock or ours, so they cannot show it.
- **No bug found in sc3resize_civic.c, bldimport.py or the page.** Nothing there was changed, so byte identity and
  run_all.sh were not re-run.

## 1. Civic looks

| check | result |
|---|---|
| load | `CIVVAR> on: 17 civic button(s) with 17 variant look(s)`, one `CIVVAR> base 0x..: 0xB1D10002:0x94..` line per base |
| cycle, 17 bases x 3 presses (`civmod_lab.py command <class id>`: the GetCommand the button and hotkey make) | 51 of 51 lines as expected: `look 1 of 2, stock, key 0x207EDC0E 0x0000057E <base>`, `look 2 of 2, Test <base> look, key 0x207EDC0E 0xB1D10002 0x9470..0x9480`, `look 1 of 2, stock` |
| cost label, armed by hotkey | "Aspecto 2 de 2: Test fire look \| $500", "Aspecto 2 de 2: Test school look \| $506", "Aspecto 1 de 2: original \| $506" (owner_shots 01, 05) |
| placed (posted click, stock tool) | fire (191,204) type 13002, school (188,204) 13010, hospital (191,207) 13310, college (194,207) 13873, keys `0xB1D10002:0x9472 / 0x9474 / 0x9473 / 0x9475`, flags 0x104 (owner_shots 02). First school click was refused on a power line (red footprint), the second press of the button then armed the stock look, the third the look again: the cycle runs per press as designed |
| service (query window, owner_shots 03) | fire: Energía Sí, 4 incendios/mes, 5 llamadas/mes, efectividad Excelente, $500, $31/mes. School: 60,000 pupitres, Profesores (esta) 113, $500. Hospital: Camas (este) 1500, Médicos (este) 111, $52/mes, $500. College: Profesores (esta) 170, $3,000. There is no health or education map in the game (DATAVIEW_PLAN.md), so the query window is the check for those three |
| fire coverage | fire map with the look, then the look bulldozed, map again: 258 cyan pixels gone, 0 new, one whole circle (owner_shots 14, magenta = gone) |
| save | sc3autosave `Madison, WI (auto 5 min).sc3` copied to `civtest_saved.sc3`; occupant_layer read back: the 4 looks with their keys and types at the cells above |
| reload `civtest_saved.sc3` | all 4 stand; fire look query unchanged, Energía Sí, Excelente (owner_shots 13) |
| Mover | not offered on a civic look ("?" has Copiar ID only, owner_shots 15). Same as a stock civic building: `rl_movable` lists rewards and landmarks only. Not a change asked for |
| VEH FAULT | every run: only the start-up `0xC0000096 at SC3U.exe+0x84122` |

## 2. Rewards on 1x1, 3x3, 4x4

| check | result |
|---|---|
| rows | `NEWREWARD> on: 3 reward row(s) ... types 38017 38018 38019`, `3 reward type(s) declared by the loader`, `3 of 3 row(s) are reward items`, population 1000, year 0, petition 0, own rule 0 |
| unlock | all three `passed population and year: unlocked (SIMADV+0xa832)` 37.5 s after the city came up (population 155,486) |
| Rewards list (hotkey 0x3b) | "Test reward 1x1 / 3x3 / 4x4" with the picture and "Test reward NxN, bldimport civtest" (owner_shots 06) |
| place | OK arms a one-shot tool for `0xB1D10002:0x9481 / 0x9482 / 0x9483`. Placed 1x1 at (186,205), 3x3 at (182..184, 213..215), 4x4 at (205..208, 207..210), types 38017 / 38018 / 38019. After each the tool is gone, the next list lacks the placed one, after all three "No hay Recompensas ni Oportunidades disponibles ahora" (owner_shots 07, 08). Label price $0 / $5 / $15 = clearing only (no price row for a new type, as in civmod) |
| no-power bolt | the 3x3 and 4x4 show the stock no-power bolt (bases City Hall and Stock Exchange need power); the 1x1 (statue base) does not. Stock behaviour of the base, not art |
| save + reload | in `civtest_saved.sc3` with their types; after reload all three stand and the list is still empty (owner_shots 09, 10) |
| Mover | "?" shows Mover for each (`RELOCATE> "?" of type 38019 / 38018 / 38017: Mover button added`). 4x4 (205,207) -> (218,208) $117, 3x3 (182,213) -> (187,226) $57, 1x1 (186,205) -> (179,204) $5. `find` after each: one copy, at the new cells (owner_shots 11, 12) |

Population note: in the first reloaded game the HUD went 145,087 -> 125,340 in about 2 min. Not reproduced: the same
save loaded again held 155,407..156,066 over 5 game months (6 samples), a save with the looks only 155,249..155,616, a
save made before anything was placed 154,891..155,481. The first game had been started paused and driven a lot.

## 3. 3x3 growable (class 6300)

Stock 6300 3x3 members (BUILDFAM families of class 6300, `work\c3x3.py`): 179, 185, 4007, 4010, 4020, 4039.

| run | result |
|---|---|
| Europolis, `bld_lab.py`, 15 min, anarchy churn | 9 saves: ours 0; stock 179 16 every save; all six stock 6300 3x3 ids together 118 in every save. No 3x3 commercial lot of any kind was built in 15 min |
| Europolis 1024, `bld_lab.py`, 20 min | 1 save in 20 min (the 1024 city runs too slowly): ours 0, 179 256 |
| Madison | 0 stock 6300 3x3 lots in the city: not usable |
| Europolis, 13 stock 6300 3x3 lots bulldozed (Demolish tool, posted clicks; the zone stays), speed 4, 7 min | all 13 stay empty dense commercial zone. The C bar is about 0 there: no commercial demand (owner_shots 18) |
| RCI bars after 60 s (owner_shots 19) | C positive in Frankfurt, smaller in Berlin, Madrid, Moscow |

**Frankfurt** (39 stock 6300 3x3 lots, C demand positive): 9 of them bulldozed (13 tried, 4 clicks missed), speed 4,
autosaves read with occupant_layer:

| save (mtime) | ours 38020 | stock 6300 3x3 (179, 185, 4007, 4010, 4020, 4039) | style copies of those (400000+ / 1500000+) | the 9 bulldozed lots now hold |
|---|---|---|---|---|
| `Frankfurt, Germany.sc3` (start) | 0 | 39 | 0 | 9 stock 3x3 |
| auto 1 h (about 1 min in) | 8 | 23 | 5 | 6 smaller lots, 2 stock 3x3, 1 ours |
| auto 10 min (about 8 min) | 16 | 19 | 4 | 6 smaller, 3 stock 3x3 |
| auto 5 min (about 11 min) | 16 | 6 | 11 | 6 smaller, 2 stock 3x3, 1 ours |

So the importer's 3x3 grows wherever the game redevelops a 3x3 dense commercial lot: on bulldozed lots and in place of
stock 3x3 lots that redevelop. Stock members grow in the same run (the style copies 1500185, 1504007 and others, and 185
on a bulldozed lot). Pictures: owner_shots 16, 17 (grown plazas at zoom 4 and 3, drawn with the right footprint).
Why sc3compat-a's Maxis Plaza reached 0 lots in Sacramento: that city has no stock 6300 3x3 lot at all (count 0 in
`Sacramento, CA.sc3`) and grew none in its run, as Europolis here. Not a bldimport problem.

Weight note (not changed): at weight 20 against weight 1 for each stock member of family 0x18, ours took 16 of the 33
3x3 lots of that class within about 11 min. The page default and the owner's choice of weight decide this.

Wiring checked: overlay `BUILDFAM.IXF` family 0x18 ("Commercial High Density L-MLV", LandUse 6300, "families 24" in the
build line) has `Key: 1406,545184782,38020,20 Test plaza 3x3` next to the stock members at weight 1.

## 4. Tools changed (no game code changed)

| file | change |
|---|---|
| `re/tools/bldimport/make_testmodels.py` | `--civtest`: the 21 models above and their models.json |
| `re/tools/civmod_lab.py` | jobs `command <class id>` (the GetCommand of a button with no hotkey, released without Execute) and `empty X0 Z0 X1 Z1 N` (free N x N squares); note on hotkeys that open a modal dialog (0x3b Rewards, 0x12 Demolish arms) |

Lab scripts of this run (not for commit): `dev\civtest\work\` (civ_launch.py, go.py, place.sh, firemap.py, demol*.py,
watch*.py, c3x3.py, popwatch.sh, rci.sh).

The tree keeps the test plugin and overlay installed (`bldimport.py restore --game dev\civtest\tree` removes them) and
the saves `civtest_saved.sc3`, `civtest_looks_only.sc3`, `civtest_control_noimport.sc3` in `tree\Cities`, for civdlg.

Game PIDs, all started by this session and stopped by PID: 5880, 2400, 4180, 13368, 7552, 13748, 13600, 9116, 11000,
12360, 20156, plus bld_lab's own 20120, 2168, 1616.

## 5. Not run

- The menu button click itself (the GetCommand path the button uses was run for all 17, the hotkey for 4: fire, school, hospital, college).
- Placing the 13 bases other than police (civmod), fire, school, hospital, college: cycle keys only, as the brief says.
- Health or education coverage maps: the game has none.
