# rewardlook: a look picker for reward buildings (2026-11-25)

Simtropolis asked for "an easy texture swap screen" so rewards such as Historic Statue, Lighthouse, Mayor's House,
County Courthouse and City Hall can be built in the North American, European or Asian look whatever the city's building
set. Owner approved. **Verdict: built and checked in game.** Picking a reward in "Recompensas y oportunidades" now opens
the civic look window ("Elegir aspecto") for the rewards the game's sets re-skin: the original first, labelled with the
city's set, then the other sets. The pick is placed by the stock tool, so price, TAB rotation, Move and Undo work, the
City Planner counts it as the reward ("already built"), saves reload, and the stock game loads each look as the game's
own reward of the same type.

Child `rewardlook`, branch `child/rewardlook`, tree `dev\rewardlook\tree` (LAN base 2026-11-25 + the style_mix 1.4.0
overlay below). Windowed 800x600, posted input only (sc3io), Frida game calls on the game thread for the camera,
occupant reads and the unlock, pictures by `SC3RESIZE_FRAMEDUMP` (stock runs: `sc3io.grab_to`, gate clean). Every game
PID was started by `sc3dev.ps1 run rewardlook` and stopped by PID.

## Which rewards have a set look (offline read, 2026-11-25)

Every row of `Advisor-CityPlanner.ini` `[REWARD_BUILDINGS]` and `[BUSINESS_DEAL_BUILDINGS]`, its exemplars in
`Apps/Res/Occupant` (type prop 0x65), checked against both set archives (`BuildingSets/e523f3fb`, `6523f3d5`):

| reward (type) | exemplar the catalog uses | European | Asian |
|---|---|---|---|
| Mayor's House (10110) | 243 | no | yes |
| City Hall (10120) | 208 | yes | yes |
| County Courthouse (13005) | 8013 | yes | yes |
| Historic Statue (14150) | 219 | no | yes |
| Lighthouse (14550) | 8019 | yes | yes |
| Performing Arts Center (14170) | 8011 | no | yes |
| Stadium (14600) | 8020 (16333 is a second type-14600 exemplar, no set art; the catalog item is 8020, measured) | yes | yes |
| Stock Exchange (1002) | 8017 | yes | yes |
| GigaMall (business deal 19002) | 8085 | yes | yes |
| the other 15 (National Park, Golf, Military Base, Medical, R&D, University, Theme Park, Defense Contractor, Spaceport, Haunted House, Skating Rink, Casino, Prison, Toxic Factory, Castle) | | no | no |

Every set exemplar keeps the base's type id and footprint (`_civic_check` at install). The three 4-piece rewards
(Military Base, University, Theme Park) have no set art, so nothing is excluded for being 4-piece.

## What was built

| piece | what it does |
|---|---|
| style_mix 1.4.0 (`netpack_stylesets.py`, manifest key `"rewards": true`, `REWARD_BASES`) | copies the set exemplars of the 9 rewards above verbatim at base + 400000 (European, 6) / + 1500000 (Asian, 9) with frame tables and pixels, and the stock exemplar of each re-skinned reward at + 2600000 (9, North American look in a European or Asian city). No family line. Same writer and checks as the civic copies. `stylemix_build.py` now writes 1.4.0 (it was still at 1.2.0 without the 1.3.0 `lot_colour` keys; its output equals the manifest). |
| sc3resize REWARDLOOK (`sc3resize_civic.c`) | the SIMUI catalog's GetSelected slot (iface vtable `0x100ab4f4` + 0x1c, `0x1006959c`) points at `rwl_getsel`. Only for the call from the catalog command's Execute (`0x10011919`, return address `0x10011a59`) in the Rewards mode `0x62e92553` (or deals `0xe2e92527`), and only when the picked exemplar is one of the 9 with a copy in the attrib cache: the Rewards window is hidden, the civic look window opens with the civic look list (`cv_looks`), and the picked look's attrib replaces the stock one before `0x10011a8f` building layer +0x50(attrib, one-shot 1, 0). Esc / close = no tool. |
| switch | `SC3RESIZE_REWARDLOOK=0` / `sc3resize.ini [buildings] rewardlooks=0` (own switch, default on). It needs CIVSTYLE: the existing mods page row is extended rather than a new row, now "Cívicos y premios: estilos" / "Civic + rewards: game styles" (`SC3RESIZE_CIVSTYLE` turns both off). Off = the vtable slot is not touched. |
| strings | `resize.rl_desc_look`, `resize.rl_desc_stock` (reward wording of the description) and the relabelled `resize.mt_civstyle`, all 7 tables, `sc3lang.py check` clean (378 keys). fr / de / it / nl / sv are mine, for review. |
| lab | `re/tools/civmod_lab.py unlock [TYPE ...]` (sets "unlocked" on City Planner items, advisor found by its vtable SIMADV `0x1003056c`); `verify/rewardlook/work/lab.py` (copy of stcompat's) and `pick.sh` (one reward through the real Rewards button, list, look window, camera, posted click). |

## Evidence (pictures in `MAIN\verify\rewardlook\owner_shots\`, numbers below)

Data:

- style_mix 1.4.0 compiled against the stage base: reward looks 208, 8013, 8019, 8020, 8017, 8085 + 400000;
  243, 208, 8013, 219, 8019, 8011, 8020, 8017, 8085 + 1500000; the same 9 + 2600000.
- The 1.3.0 manifest compiled with the new code: all 6 output files byte-identical to the old code's.
- Re-merge of all 25 packages in a hard-linked copy of `stage/src` (uninstall + install, 12 min 37 s, exit 0): only the
  4 overlay files style_mix writes changed (`OccupantAttribs_Korea.IXF`, `CSAttrib_Korea.IXF`, `5432D60E_netpack_set.DAT`,
  `547B7DF5_netpack_set.DAT`) plus the ledger and the package manifest. Those 4 were copied into the test tree.

North American city (Roadless Paradise, skin 0), rewards unlocked by `civmod_lab.py unlock`, opened by the real
civic flyout button "Premios y oportunidades":

1. Start: `REWARDLOOK> on: a Rewards pick with set looks opens the look list (SIMUI catalog GetSelected +0xab510, 9 reward exemplars)`.
2. Rewards list (`01`); Mayor's House picked: "Elegir aspecto" with "Norteamérica: Casa del Alcalde" (original, "La
   recompensa original del juego, en el estilo de esta ciudad (Norteamericano)") and "Asia: Casa del Alcalde" (`02`, `03`).
   Log: `CIVDLG> entry 1: key 0x0000057E 0x0016E453 type 10110 lot 2x2 price 0 style Asiático`, then
   `REWARDLOOK> reward 0xF3: look 2 of 2, Asiático, key 0x207EDC0E 0x0000057E 0x0016E453 -> building layer +0x50`.
3. The tool is the stock building tool (SIMGEOM+0x29504) with the look's key; cost label "Aspecto 2 de 2: Asiático | §0"
   and "Giro 0 grados (TAB)" (`04`); one TAB, placed: occupant 1500243, type 10110, 2x2, rotation 1 (`05`, `06`).
4. Placed in the same way: City Hall European 400208 (type 10120), County Courthouse Asian 1508013 (13005, `07`),
   Historic Statue Asian 1500219 (14150), Lighthouse European 408019 (14550), Performing Arts Asian 1508011 (14170),
   Stock Exchange European 408017 (1002) (`08`, `09`). Stadium Asian armed with its look ("Aspecto 3 de 3: Asiático |
   §75,000") and refused by the stock funds check: the city had §19,669 (`19`). The price is the type's, as for the original.
5. "Already built": the City Planner's items read back `placed 1` for all seven types after placing the looks (Stadium
   `placed 0`). They left the Rewards list.
6. Move: the "?" dialog of the Asian Courthouse shows "Mover" (`10`); moved: `RELOCATE> MOVE placement (kind 0) at (130,
   139): placed`, occupant still 1508013, one copy.
7. Save + reload with mods (autosave copied to `tree\Cities\rl_na.sc3`): the save holds the 7 look keys; reloaded, the
   same 7 occupants, drawn the same (`11`), City Planner `placed 1` for all seven.
8. Mods off (`sc3dev run -Stock`, sc3winonly only): the city loads, each look is the game's own reward at the same cells:
   208, 8013, 243, 219, 8019, 8011, 8017 with types 10120, 13005, 10110, 14150, 14550, 14170, 1002, drawn North American
   (`12`). Process alive.

Asian city (Roadless Paradise after SetCityScheme 6523F3D5, the stock City Properties call; skin read back 6523f3d5):

9. City Hall's window: "Asia: Ayuntamiento" first (the base key, drawn Asian here), "Norteamérica: Ayuntamiento"
   (+2600000), "Europa: Ayuntamiento" (`13`).
10. Placed: Mayor's House North American 2600243, City Hall North American 2600208, County Courthouse European 408013,
    Historic Statue North American 2600219, Lighthouse North American 2608019, plus Performing Arts original (Asian, 8011)
    for contrast (`14`). Picking the original logs `REWARDLOOK> reward 0x1F4B: the original (stock attrib)`.
11. Undo (paused, sc3undo's rule): Stock Exchange North American placed, `APPLY> building: 1 inserted ... entry 1 of 1`,
    undo button: `UNDO> entry 1 (building): 19 op(s), 0 failed, $17 refunded`; no occupant left, City Planner `placed 0`
    for 1002 (offered again) (`17`, `18`).
12. Save + reload with mods (`rl_as.sc3`): skin still 6523f3d5, the 6 occupants at their keys, drawn the same (`15`).
13. Mods off: 8011, 8019, 243, 8013, 219, 208 at the same cells and types, drawn in the city's Asian set as the stock game
    draws every reward there (`16`). Process alive.

Switch:

14. `SC3RESIZE_REWARDLOOK=0`: `REWARDLOOK> off (...)`; Mayor's House from the Rewards list arms the stock tool with key
    0xF3, no look window (`20`).
15. A reward without set art (Defense Contractor, Madison, before the overlay was installed):
    `REWARDLOOK> reward key 0x0000057E 0x00001F57: no set look (stock tool)`, stock tool armed.

No VEH fault in any run except the start-up `0xC0000096 at SC3U.exe+0x84122` every run logs.

## Lab traps (cost runs)

- `civmod_lab.py hotkey 0x3b` (Rewards and Opportunities through DefOnHotKey inside a Frida DispatchMessageA hook) never
  returned its result here, and stopping that helper while still attached took the game down (no VEH line). Use the
  real button: civic flyout (765,160), then "Premios y oportunidades" (717,216). The flyout button toggles, so check the
  list opened (pixel test in `pick.sh`) and retry.
- A camera recentre needs a zoom change (the showcase trap): `cam x z 2` then `cam x z 3`.
- sc3undo records only while the sim is paused (P before the pick and the click; Frida jobs refuse a paused game).
- The stock control starts paused and its pause key is not sc3resize's P: click the HUD play button (521,566).

## Release

style_mix must be reinstalled in the stage source, as the 1.3.0 round did (`verify/mods_release_1124/RESULTS.md`):
`netpack.py uninstall style_mix` then `netpack.py install re/tools/netmod/examples/style_mix --tree stage/src
--allow-tree` (12 to 15 min, all 25 packages re-merged), then the normal `stage_lan_release.py` + publish. Expected
changes against the 1.3.0 stage: the same 4 overlay files (`OccupantAttribs_Korea.IXF` 958,758 -> 969,532 B,
`CSAttrib_Korea.IXF` 851,808 -> 861,856, `5432D60E_netpack_set.DAT` 11,155,014 -> 12,243,915,
`547B7DF5_netpack_set.DAT` 20,454,214 -> 24,457,932), `2627D60E` unchanged. Plus sc3resize.dll and the 7 sc3lang
tables. Without the reinstall the code is inert (no copies in the cache: the Rewards list stays stock).
The README's civic section should gain the rewards (text proposal in `re/tools/netmod/examples/style_mix/README.md`).

## Not checked / open (owner checks)

- GigaMall (business deal): data and hook cover it (deal items are listed in the Rewards window once a deal is
  accepted), not opened in game.
- European city: same code path as the Asian city (the civic looks were checked in Berlin), not run for rewards.
- Lighthouse on a coast and Stadium with enough money: both placed / armed through the same tool, not placed in game
  (Stadium refused for funds, Lighthouse placed inland like the stock one allows).
- 6 other languages not seen in game (tables checked). At 800x600 "Norteamérica: Casa del Alcalde" clips its last
  letters in the list, as the civic rows did (`02`); the region word stays visible.
- The mods page with the relabelled row was not opened in game; the Spanish and English labels have the same length as
  before, German was shortened to 27 characters.

## Files

- Commit (branch `child/rewardlook`): `re/harness/src/sc3resize_civic.c`, `re/harness/src/sc3resize.c`,
  `re/harness/lang/{de,en,es,fr,it,nl,sv}.txt`, `re/tools/netmod/netpack_stylesets.py`, `re/tools/netmod/netpack.py`
  (report line), `re/tools/netmod/netpack.schema.json`, `re/tools/netmod/stylemix_build.py`,
  `re/tools/netmod/examples/style_mix/{manifest.json,README.md}`, `re/tools/civmod_lab.py`, `re/analysis/CIVIC_REWARD.md`
  (section 9), `verify/rewardlook/RESULTS.md`, `verify/rewardlook/work/{lab.py,pick.sh}`.
- MAIN: `re/sessions/STATUS_rewardlook.md`. Not committed: `verify/rewardlook/owner_shots/*.png` (game art), test saves
  `dev/rewardlook/tree/Cities/rl_na.sc3`, `rl_as.sc3`.
