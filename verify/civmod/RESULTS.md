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
