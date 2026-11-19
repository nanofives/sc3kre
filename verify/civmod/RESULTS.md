# civmod results (round 2026-11-19j): civic looks, new rewards, Mover for imported landmarks

Built in sc3resize (no new DLL): `re/harness/src/sc3resize_civic.c`, a line in `sc3resize_placehints.c` (cost label),
`rl_movable` and two "Activar mods" rows in `sc3resize.c`. Data from `bldimport.py` kinds `civic` and `reward`.
Static evidence and the two corrections to last round's proposal: `re/analysis/CIVIC_REWARD.md` section 5.

**Verdict.**

- **Civic looks: work.** Each press of the stock Police button builds the next look (stock, ours, stock). Our look is
  a police station to the game: type 13130, $500, its own coverage circle on the criminality map. The cost label names
  the look. Saved and reloaded. Without the plugin it comes back as the stock station.
- **New rewards: work, with one open risk.** Our rows are read by the game's own ini class from a loose file (no SYS.PAK
  edit). A reward unlocks at its population, is listed, placed, leaves the list, survives save and reload, and moves.
  The new type has to be declared like a CitySim.ini type, or the game faults placing it and exits loading a city that
  holds it. sc3resize declares it at run time. **The stock game (mods off) with the plugin installed still exits
  loading such a city**: owner's call between two fixes (below).
- **Mover for imported landmarks: works.** Type 18000 gets "Mover"; so do the new rewards. The picker refuses both as
  one per city.

## 1. Checks run

Tree `dev\civmod\tree`, mods of `dev\civmod\inst`, windowed 800x600, `sc3dev.ps1 run civmod` only. Posted input (sc3io)
and Frida game-thread calls (`re/tools/civmod_lab.py`: the city view's own `DefOnHotKey` 0x18 = the Police button's
command path), camera by `netmod/nramp_cam.py`, pictures by SC3RESIZE_FRAMEDUMP (BMPs deleted). Test data:
`make_testmodels.py --civmod` -> `bldimport.py build`; `check`: 0 of 4 failed, 20/20 frames equal each.

| check | result |
|---|---|
| civic hook at the proposed `0x1000b19d` | **failed**: Police press built the stock key `0x57E:0xD2`, no hook call. 16 of the 17 cases `jmp 0x1000b1a2`. Hook moved to the call at `0x1000b1a3` |
| Police button, presses 1, 2, 3 | keys `0x57E:0xD2`, `0xB1D10002:0x9470`, `0x57E:0xD2` (log `CIVVAR> button of base 0xD2: look 1/2/1 of 2`, and `civmod_lab tool`) |
| cost label | "Aspecto 2 de 2: Test police look \| $505" and "Aspecto 1 de 2: original" (owner_shots 01, 02) |
| place our look and a stock station | (178, 209) price $505 and (178, 213) $522 (police $500 + clearing); both type 13130, flags 0x104 |
| coverage | stock station already powered at the river; our look placed beside it at (148, 176), no power bolt. Criminality map: 150 new cyan pixels in one region, none gone, a second circle with its own centre next to the stock one (owner_shots 04, 05). Unpowered stations (both kinds) draw no circle |
| reward rows | `EnumEntries true: 2 of 2 row(s) are reward items`, population 1000 / 100,000,000, year 0, petition 0, own rule 0 |
| unlock | `type 38001 passed population and year: unlocked` ~36 s after unpausing (city 151,282); 38002 never; Rewards dialog lists only "Test reward obelisk" with our description (owner_shots 06) |
| place the reward, first build | **fault** `0xC0000005 at SIMADV+0xB392`, read of 0: building inserted, commit aborted, tool still armed (owner_shots 16). Cause: type 38001 not declared (CIVIC_REWARD.md 5.2) |
| place the reward, after the declaration fix | `declared [AgentTypes] 38001=...` / `[AgentTypeHierarchy] 38001=10001` at 67-71 ms; placed at (177, 219), $21, no fault, one-shot tool ended |
| Rewards list after placing / after save + reload | "No hay Recompensas ni Oportunidades disponibles ahora" both times (owner_shots 08, 09) |
| landmark (type 18000) | placed from the stock landmark dialog at (184, 215), $68 |
| save + reload | sc3autosave wrote `Madison, WI (auto 5 min).sc3` (temp + rename, link-safe), copied to `civmod_saved.sc3`; reloaded: our look (178,209) 13130, stock police (178,213), reward (177,219) 38001, landmark (184,215) 18000 |
| Mover, reward | "?" shows Mover (`"?" of type 38001: Mover button added`); first spot over the rail refused (red); moved to (174, 211), $32 (bulldoze 20 + levelling 12), original gone (owner_shots 10, 12) |
| Mover, landmark 18000 | Mover in the "?" (owner_shots 11); moved (184,215) -> (174,216), $76; original gone |
| picker | landmark and reward: "Cuentagotas: solo uno por ciudad"; our look: tool for key `0xB1D10002:0x9470` |
| ini files removed (civic + rewards ini out, types file + plugin kept), load `civmod_saved.sc3` | no fault; `CIVVAR> ... not installed` / `NEWREWARD> ... not installed`; Police presses give `0x57E:0xD2` twice; Rewards list as stock; buildings stay (owner_shots 13) |
| first version of that run (declarations inside the rewards ini) | **game exited** on load, fault at `SIMADV+0xB392`. Fixed: declarations moved to `bldimport_types.ini`, made with the switch on or off |
| both switches off (`SC3RESIZE_CIVVAR=0`, `SC3RESIZE_NEWREWARD=0`), all files in | no fault; types still declared; Police presses stock |
| `bldimport.py restore` (plugin gone), load `civmod_saved.sc3` | no fault; reward and landmark lots empty orange ground; our look came back as a stock police station `0x57E:0xD2` (owner_shots 14) |
| stock game (`-Stock`, sc3winonly only) + plugin, `civmod_saved.sc3` | **exited within 10 s** (PID 17576). Control, same setup on the original `Madison, WI.sc3`: ran 90 s |
| "Activar mods" page | two rows "Cívicos: varios aspectos", "Premios nuevos" under "Simulación y edificios"; notes and the city row where they were (owner_shots 15). Unchecking "Premios nuevos" wrote `[env] SC3RESIZE_NEWREWARD=0` (`MODTOGGLE> -SC3RESIZE_NEWREWARD off`). Turning it back on from the page was not run (the second open of Preferences missed) |
| VEH FAULT lines | every run: only the known startup `0xC0000096 at SC3U.exe+0x84122`; the `SIMADV+0xB392` lines above are the two pre-fix runs |
| bldimport, old cases | `pack --out` of `--landmarks` and `--ports` with the old and new bldimport.py: outputs byte-identical. Only the refusal text of a civic entry with no base changed |
| translations | `sc3lang.py extract` + `check`: 352 keys in all 7 tables, 0 missing, 0 unknown |

Game PIDs, all started by `sc3dev.ps1 run civmod` and stopped by PID: 8888, 17912, 3656, 2932, 9280, 728, 12336, 19616,
9808, 17576, 10200, 8516.

## 2. What stays open

- **Stock game + plugin + a placed new reward = exit on load.** Two fixes, owner's call: (a) declare the types in an
  overlay SYS.PAK `CitySim.ini` (netpack `ini[]`, ties rewards to sc3netmod, still not stock); (b) use for rewards the
  building types CitySim.ini declares but no stock exemplar uses (24 found, about eight of them plain buildings:
  1001 Arcology, 12260 Parking, 12510 Dam, 13008 PostOffice, 13120 SmallPoliceStation, 13320 FreeClinic, 14160
  HistoricBuilding, 14910 Church), stock-safe but limited, and each type's stock meaning has to be read first. Until
  then: keep sc3resize installed while the plugin holds rewards; `bldimport.py restore` is a safe uninstall.
- The reward keeps its base's query fields (the Mayor's House "Número de huevos lanzados") and the base's land value
  family (parent 10001).
- Not run: the menu button click (only the hotkey path, the same GetCommand), a second civic base, a 1x1 / 3x3 / 4x4
  reward, year-gated rewards, the picker on an unplaced reward, sc3undo of a look placement.
- The page side (classifier.html / bldweb.js kinds civic and reward) waits for plop2's merge.

## 3. Files

| file | change |
|---|---|
| `re/harness/src/sc3resize_civic.c` (new, needs `git add -f`) | CIVVAR (SIMGEOM `0x1000b1a3`), NEWREWARD rows (SIMADV `0x10006f80`), unlock (`0x1000a7fa`), type declarations (SC3U `0x0040bc80` / `0x0040bccb`) |
| `re/harness/src/sc3resize.c` | include, `rl_movable`, switches (`[buildings] civicvariants=` / `newrewards=`, env `SC3RESIZE_CIVVAR` / `SC3RESIZE_NEWREWARD`), `at_install` in DllMain, install thread, page C rows ('-' rows, mods rows 17 px) |
| `re/harness/src/sc3resize_placehints.c` | `ph_label`: the look prefix, always shown |
| `re/harness/lang/*.txt` | 5 new keys, `resize.mt_sim` -> `resize.mt_simbld` |
| `re/tools/bldimport/bldimport.py` | kinds civic / reward, `bldimport_civic.ini`, `bldimport_rewards.ini`, `bldimport_types.ini`, check of the plugin kinds, help |
| `re/tools/bldimport/make_testmodels.py` | `--civmod` |
| `re/tools/civmod_lab.py` (new) | the lab |

# Round 2 (2026-11-19, after the merge 289d3ce): "Loader declares", rewards plugin, page side, guide

Owner calls: reward safety = the loader declares the reward types; then the page side of kinds civic and reward.

## 4. The loader declares the reward types

| change | where |
|---|---|
| the `[AgentTypes]` / `[AgentTypeHierarchy]` hooks (SC3U `0x0040bc80` / `0x0040bccb`) and the row feed moved from sc3resize to the loader | `re/harness/src/sc3mods.c` "REWARD TYPES", run from DllMain whenever the patched exe maps it as a static import, mods on or off |
| sc3resize no longer declares | `sc3resize_civic.c`: asks the new export `sc3mods_reward_types(out, cap)` at the first city load and unlocks only those types (`NEWREWARD> 2 reward type(s) declared by the loader 38001 38002`) |
| rewards are their own plugin | `Apps\PlugIn\bldimport_rewards\` = `bldimport_rewards.pin`, `.dat`, `bldimport_rewards.ini`, `bldimport_types.ini`. Civic looks and landmarks stay in `Apps\PlugIn\bldimport\` |
| `sc3mods_patch.ps1 -Restore`, `sc3mods_patch.sh --restore` | move `PlugIn\bldimport_rewards` to `Apps\sc3mods_off\PlugIn\`. A patch run moves it back. The rewards are split, so only they leave (civic looks and landmarks use stock types and stay) |
| the importer's Remove | removes every file the install wrote, both plugins included (`bldimport.py restore` and the page's Remove both put back state.json's list) |
| loader size / VERSIONINFO | sc3mods.dll 123,392 -> 126,976 bytes. VERSIONINFO kept: "sc3mods for SimCity 3000 Unlimited", "SimCity 3000 Unlimited mod: mod loader", 2026.11.19 |

Removed-data table, city `civmod_saved.sc3` (police look, stock police, landmark 18000, placed reward 38001), each run
started by `sc3dev.ps1 run civmod`, watched 60 s after the city came up (or after start when sc3resize was not there):

| run | setup | result |
|---|---|---|
| 0 | all mods on (sc3mods.dll + sc3resize.dll of this round) | loads, alive. Loader log: types 38001 and 38002 declared before app init. sc3resize: `2 reward type(s) declared by the loader`, both rows read from the new plugin, reward 38001 found at (177, 219). VEH FAULT: only the startup `0xC0000096 at SC3U.exe+0x84122` |
| A | every row on the mods page off: `sc3mods.ini` `[mods]` 10 DLLs = 0 and `[env]` 21 feature switches = 0 (CIVVAR and NEWREWARD included) | loads, alive 60 s. `1 mod(s) loaded, some turned off`, both types declared, `CIVVAR> off`, `NEWREWARD> off` |
| B | sc3resize not loaded (`-Stock`: the loader + the test DLL sc3winonly only) | alive 60 s and more, the city on screen with the reward standing (window grab `work\fd\80_B_sc3resize_off.png`). Round 1 with the same setup and no loader declaration: exited within 10 s |
| C | `sc3mods_patch.ps1 -Restore`: SC3U.exe back to `49DD55E1...` (stock 2.0.0.3), `PlugIn\bldimport_rewards` moved to `sc3mods_off\PlugIn` | to run it windowed the exe was patched again with `sc3mods_patch.sh` (same hash `e5b6330c...` as the .ps1), the moved folder held aside, and the loader started with `SC3MODS_DECLARE=0` (test switch: no declaration), so the game saw what the bare stock exe sees: no reward exemplar, no declared type. Loads, alive 60 s, reward lot empty orange-brown ground, police look and landmark stand (`work\fd\81_C_restored.png`). The bare stock exe itself was not started (it runs fullscreen) |
| C2 | `sc3mods_patch.ps1` (no -Restore), then `.sh --restore`, then `.sh` | the folder went back into PlugIn, out again, back again. Exe hashes `49DD55E1` stock / `e5b6330c` patched each time |

## 5. Page side (classifier.html + bldweb.js)

- bldweb.js: `CIVIC`, `REWARD`, `civicTable`, `rewardTable`, `agentTypeRows`, `civicIni`, the reward plugin, kinds civic
  and reward in `plan` and `buildFiles`, ported line by line from bldimport.py.
- classifier.html: kinds `civic` and `reward` in the Kind list. Base (17 buttons, it sets the lot), Population and Year
  rows shown only for those kinds, the Description row for landmark, civic and reward. Suggest: the civic words pick
  `civic` and the button. Warnings mirror bldimport.py's refusals. `models.json` gets `base` / `population` / `year`
  only on those kinds. The install hint names both plugin folders.
- Golden case `civic` (make_testmodels.py `--civmod`): golden.mjs 9 of 9 (7 files byte-identical: both .dat, both .pin,
  the three ini files, plus ids.json and 80 frames), pagetest.mjs civic 11 of 11 (the page in headless Chrome installs
  the same 7 files).
- Stock reward per lot (bldimport `reward_table`, stage\release): 1x1 Historic Statue (219, type 14150), 2x2 Mayor's House
  (243, 10110), 3x3 City Hall (208, 10120), 4x4 Stock Exchange (8017, 1002). Civic lots per button: police, jail, fire,
  hospital, school, college, museum, big park 3x3; library, playground, pond, train station 2x2; small park, fountain,
  bus stop 1x1; zoo, baseball 4x4.
- Test case `landmarks`: its refused entry `civic_1x1.obj` was kind civic (meaning "not imported"). Now kind
  `ploppable`, still refused, same file and id, so its outputs are unchanged. pagetest's "Description hidden" check now
  picks a card of a kind without a Description (landmark, civic and reward have one).

## 6. Suite, guide, build

- `SC3PACK_PACKS=stage\st_packs test-slot bash re/tools/bldimport/webtest/run_all.sh dev\civmod\work\runall2 stage\release
  stage\kits "<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes
  stage\st_packs\sc4`: **31 of 31 steps passed** (30 -> 31: the new step `pagetest.mjs civic`; golden_setup 8 cases).
  First run 29 of 31: `pagetest.mjs kenney` failed on EBUSY reading Chrome's DevToolsActivePort at start (passed on the
  rerun with no change), `pagetest.mjs landmarkdesc` failed its "Description hidden" check (fixed, section 5).
- `sync_css.py --check`: in sync. `--publish`: classifier.html, bldweb.js, sc4web.js, sc3font.js, sc3pack.js to
  docs/buildings/importer/.
- Guide: `verify/bldpack/work/guide_template.html` (MAIN) + `make_docs.py --wt dev\civmod\wt --tree dev\civmod\tree --zip
  <the 2026-11-18 sample pack URL>`: new sections "Civic buildings" and "Rewards" (nav entries), the "What it does not
  do" line replaced, the Kind / Description / Base / Population / Year fields in Classifying. Published link kept.
  `stage\sample_pack\README.txt` rewritten byte-identical (sha256 `bdda1dee...`). Numbers from sections 1 to 5 only.
  Voice check over the new text: 0 dashes, semicolons, ellipses, emoji, intensifiers.
- Build: `sc3dev.ps1 build civmod -Mods sc3mods,sc3resize`: sc3mods.dll 126,976 bytes (tree\Apps), sc3resize.dll
  748,544 bytes (inst), no errors. Run 0 above is the start + load with all mods on: no new VEH FAULT.
