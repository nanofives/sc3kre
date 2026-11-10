# batslots: players add their own BAT buildings to zoned growth, through the stock Building Replacement path (2026-11-10)

Verdict: **works, data only, no code.** The package `bat_slots` adds 16 new growable "slot" buildings (ids 36100 to
36121). Each one is a copy of a stock building at a new id, sits at weight 1 in the family of its zone class, and is
listed in `SC3CityScheme.ini [ReplaceableBuildings]`. In game, every slot grew in Moscow next to the stock buildings.
A slot house queried in the city shows the stock "Sustituir" (Replace) button. The stock replace dialog put the
Building Architect building The Joneses on slot 36100 and took it off again: game state, save and picture all agree.
The replacement survives save and reload. Loading the save without the package does not crash. The slot buildings
are dropped and their lots regrow with stock buildings.

Question from a Simtropolis player. Static RE: `re/analysis/BUILDING_PICK.md` sections 5 and 6 (C), updated.

## Design decisions

### (1) How the replacement windows build their lists, and the footprint rule

Two stock windows commit a replacement. Both end in the scheme manager's `MakeBATReplacement`.

| Window | Opened from | Stock list | Commit |
|---|---|---|---|
| Building Replacement Manager (`cSC3WinProcBuildingReplacementMgr` [LINUX-HINT]) | City Scheme dialog of the New City flow, button `0x2552485a` (SIMUI `0x1005e3a1` -> command `0x75942963` -> `0x1001b3fa`) | every attrib in the occupant attrib cache whose key is in `[ReplaceableBuildings]` | OK: `FUN_1001b38d`, scheme vt+0xa4 per changed entry |
| Replace dialog (`cSC3WinProcReplaceBuildingDialog` [LINUX-HINT]) | query dialog of a building in the city, button "Sustituir" (control 4, SIMUI `0x1006338f`) | the queried building only | OK: SIMUI `0x10065da8`, scheme vt+0xa4 |

- The Manager's list does not depend on the city. SIMUI `0x1001c3a8` walks the attrib cache (app vt+0x44) and keeps
  each attrib for which scheme vt+0x98 `IsReplaceableBuilding` (SIMINIT `0x10005963`, a lookup of `Key()` in the
  `[ReplaceableBuildings]` set) is true. No occupant manager is read. [CONFIRMED @ SIMUI 0x1001c3a8]
  So a slot is offered as soon as the package is installed, even before one grows.
- The query dialog creates "Sustituir" only when `IsReplaceableBuilding(attrib)` is true (SIMUI `0x1006260e`, byte
  `+0xd6`). [CONFIRMED static, and seen in game: present on a finished slot house, `t6`]. Not shown on a building
  under construction (`t10`) or abandoned (`t9`), slot or stock.
- **Footprint:** both lists of BAT buildings are filtered by lot size. The Manager's size radio feeds
  `GetBATBuildings(container, size)` (SIMINIT `0x100053be`), which keeps overrides whose lot size byte equals it, and
  its Replace button is enabled only when the BAT's lot size equals the building's `SizeInCellsX` (SIMUI
  `0x1001bb56`). The Replace dialog in game listed only The Joneses for a 1x1 slot (`t4`) and exactly the six 2x2 BAT
  buildings for a 2x2 building (`t8`). The engine side (`0x10005bde` -> attrib cache vt+0x40 `0x1000d150` ->
  `SetOverRideAttrib`) never compares sizes. [CONFIRMED @ SIMINIT 0x10005bde, 0x1000d186] So a .bld must match the
  slot's footprint, and only X is compared (BAT lots are square).
- Manager type filter: TypeId (attrib vt+0x50) tested against 3000 / 5000 / 8000 through the id manager, else reward,
  else other (SIMUI `0x1001bad8`). The slots keep their base's prop 0x65, so they land in R / C / I. What id-manager
  slot 0x24 tests is [UNCERTAIN].
- The Manager's slides show a picture only, no name (SIMUI `0x10018602`, `0x1005aaae`). The query dialog shows the
  name.

### (2) What an unassigned slot looks like and weighs

Choice: **an exact copy of its base building (same art, stats, footprint, LandUse), weight 1.**

- Weight is static: it lives in `BUILDFAM.IXF`, which a replacement does not touch. So an unassigned slot grows
  whatever its art. No data-only way makes it grow only after a player assigns it.
- With the base's art, an unused slot is a stock house that appears a little more often: in stock family 11 (12
  members at weight 1), Dingy Ave. goes from 1 draw in 12 to 2 in 13. The city looks the same until a player uses a
  slot. A distinct placeholder art (a tint, a sign)
  would show up in every city on several percent of the lots of those classes, used or not.
- Weight 1 = once assigned, the BAT building grows as often as any one stock member of that family. Measured in
  Moscow: slot counts 1 to 163 per id in save B. In save A, 16 of slot 36100 against 70 of its base 113 (the test
  tree also had growable_test's 36001 at weight 50 in family 11, which takes most of that family's draws).
- Cost of the choice: in the Manager's slides a slot and its base look alike. In the city the query dialog tells
  them apart by name (`t6`). Where the Manager puts slot slides in its order is [UNCERTAIN] (cache iteration order,
  not run). If the owner prefers a findable slot, `batslots_build.py` can pass an `art.recolor` per slot: one line.

### (3) The slot set

16 slots, 1x1 and 2x2 only. 1x1 and 2x2 are the sizes of most low and medium density growables (the families hold 136
replaceable 1x1 and 55 2x2 growables, against 44 3x3 and 11 4x4), and the game's own BAT list has 1 lot of 1x1 and
6 of 2x2 among its 15 buildings. The families come from the game's rule table, not by hand: for each LandUse,
`batslots_build.py` takes every family that is the FIRST family of that LandUse in some `[ZoneDeveloperRules]` row
(a rule Apply takes the first record whose LandUse matches, BUILDING_PICK.md 2), minus family 1 (only family of the
row-house rule `0x61f44687`). So LandUse 3500 goes into families 10 and 31, 3900 into 12 and 28, 4500 into 14 and 30.

| id | name | LandUse | size | base | families |
|---|---|---|---|---|---|
| 36100 | BAT Slot Light Residential Low Wealth 1x1 | 3100 | 1x1 | 113 Dingy Ave. | 11 |
| 36101 | BAT Slot Light Residential Mid Wealth 1x1 | 3300 | 1x1 | 116 Elm St. | 4 |
| 36102 | BAT Slot Light Residential High Wealth 1x1 | 3500 | 1x1 | 120 Fancy House | 10, 31 |
| 36103 | BAT Slot Light Residential High Wealth 2x2 | 3500 | 2x2 | 3000 Bayberry Manor | 10, 31 |
| 36104 | BAT Slot Medium Residential Low Wealth 2x2 | 3700 | 2x2 | 3018 Edgewood Apartments | 16 |
| 36105 | BAT Slot Medium Residential Mid Wealth 2x2 | 3900 | 2x2 | 3020 Goodplace Arms | 28, 12 |
| 36106 | BAT Slot Medium Residential High Wealth 2x2 | 4100 | 2x2 | 3001 Hampton's Apartments | 17 |
| 36107 | BAT Slot Dense Residential Mid Wealth 2x2 | 4500 | 2x2 | 3015 Red Brick Apartments | 30, 14 |
| 36110 | BAT Slot Light Commercial Low Wealth 1x1 | 5100 | 1x1 | 126 Ben's Diner | 7 |
| 36111 | BAT Slot Light Commercial High Wealth 1x1 | 5500 | 1x1 | 4003 Fashion Plus | 9 |
| 36112 | BAT Slot Light Commercial High Wealth 2x2 | 5500 | 2x2 | 151 Precious Shops | 9 |
| 36113 | BAT Slot Medium Commercial Low Wealth 2x2 | 5700 | 2x2 | 156 Buy and Buy Retail | 8 |
| 36114 | BAT Slot Medium Commercial High Wealth 2x2 | 6100 | 2x2 | 157 Drumm Building | 23 |
| 36115 | BAT Slot Dense Commercial Low Wealth 2x2 | 6300 | 2x2 | 155 Arbor Plaza | 24 |
| 36120 | BAT Slot Light Industrial Clean 2x2 | 8700 | 2x2 | 164 Industrial Lab | 20 |
| 36121 | BAT Slot Medium Industrial Dirty 2x2 | 8300 | 2x2 | 8014 Acid and Base Manufacturing | 6 |

Industrial low-density dirty (8100, family 5) has no 2x2 member but two "Grass Lot" entries, so its dirty slot uses
medium density 8300. Bases must use a plain `0x6300` frame table: 5020 Factory and 158 Cloth Dyeing use the animated
`0x6301` kind, which netpack's art copy does not parse (it failed with "180 frames but 3396 bytes").

### (4) Names

The query dialog shows the slot's name (`t6`). The game font draws `$` as a section sign: the first build named the
slots "Low Density $ 1x1" and the dialog showed "Low Density § 1x1" (`t10`, `t9`). The names now use the game's own
zone words (Light / Medium / Dense) and words for wealth. "High Wealth" for commercial 5500 / 6100 stands for the
families' "M-HLV" (medium to high land value). The same name is the `[ReplaceableBuildings]` row text. Names are in
English in every language folder. The renamed build was installed but not shown in game.

### Capacity of the Korea container

The 1,023 figure in `NETPACK.md` / `NEW_PIECE.md` is the stock 0x5000-byte index (1,024 slots). netpack's
`ixf_insert.new_container` grows the index past it. In the growable run, 36001 sat at slot 1,231 of
`OccupantAttribs_Korea.IXF` (index 0x6058 bytes) and grew in game. With bat_slots installed the container holds 1,248
records, and all 16 slots grew. So 1,023 is not a limit for this container. No upper limit was found or tested.

## What was built

| File | What |
|---|---|
| `re/tools/netmod/netpack_growables.py` | `family` may be a list (one Key line in each), new `replaceable` key (true or a row name) -> an ini edit adding `545184782,1406,<id>=<name>` to `SC3CityScheme.ini [ReplaceableBuildings]` (op `add`, refuses a duplicate) |
| `re/tools/netmod/netpack.py` | growables' ini edits joined into the package's ini list, report shows families + replaceable (+6 / -2 lines) |
| `re/tools/netmod/netpack.schema.json` | `family` int or list, `replaceable` |
| `re/tools/netmod/batslots_build.py` | new: slot table -> validated `examples/bat_slots/manifest.json` (base LandUse and footprint checked, families from the rule table) |
| `re/tools/netmod/examples/bat_slots/manifest.json`, `README.md` | the package, player description |
| `re/tools/batslots_lab.py` | new: `replace` / `clear` / `state` on the game thread through the scheme manager, `bats` (BAT.DAT list), `save` (replacement set + slot counts and cells from a .sc3) |

Install order checked: `growable_test` then `bat_slots` into `dev/batslots/tree` with the 20 road packages of the
staged release (`packs` + `ledger.json` from `stage/src`). Overlay result: 16 new rows (338 -> 354), one Key line first
in each of 17 families (family 11 holds both 36100 and growable_test's 36001), 17 exemplars in Korea. `netpack
uninstall bat_slots` gave back 338 rows and only 36001. The family edits are line inserts merged from stock, so a
third package with growables (stylemix) merges the same way. Not run together with stylemix's package.

## Evidence

Dev workspace `dev/batslots`, windowed, posted keys and clicks only. Overlap with stylemix: none seen. The first launch
waited for the harness claim (held by stylemix) to clear at 14:29. `harness_claim.ps1` then reported no other SC3U
process, and none was running when the last run stopped at about 14:59. Every tool got this run's own PID. Run 1: `Moscow, Russia.sc3` (copy), churn
`anarchy_res=5000`, speed 4, autosave every 150 s. Runs 2 and 3: no churn. Counts from `batslots_lab.py save`
(`occupant_layer.py`, key `{0x207EDC0E, 0x57E, id}`).

| Save | Package | Replacement set in the save | 36100 | stock family 11 | other |
|---|---|---|---|---|---|
| Moscow as shipped | - | 16 bytes, count 0 | 0 | 3,551 | |
| run 1, auto 10 min | on, replacement by lab | 40 bytes, 1 pair | 18 | 3,279 | 36001: 979 |
| run 1, save B | on | 40 bytes, 1 pair | 19 | | every slot present: 36101 163, 36104 119, 36105 58, 36120 28, 36107 25, 36102 19, 36110 19, 36113 28, 36111 34, 36115 10, 36121 4, 36112 3, 36103 2, 36106 1, 36114 1 |
| run 2 (save B reloaded), save C | on, replacement by the stock dialog | 40 bytes, 1 pair | 26 | 3,590 | 36001: 1,314 |
| run 3 (save C, package uninstalled), save D | off | 40 bytes, 1 pair (kept) | 0 | 4,432 | 36101 0, 36104 0 |

1. **Slots grow, stock keeps growing.** All 16 slot ids are in save B, R / C / I, 1x1 and 2x2. Stock family 11 kept
   growing in every save (3,118 to 3,590).
2. **The replacement path (lab).** `batslots_lab.py replace 36100 0x660041bd` calls scheme vt+0xa8 (`SIMINIT+0x5b95`
   in the live process) with `{0x207EDC0E, 0x57E, 36100}` and The Joneses' key `{0x856CD19A, 0xBA1DBF1E,
   0x660041BD}`. Returned 1. The game's map (`+0x8c`, count `+0x90`) then holds the pair. `clear` (vt+0xa4 with a
   NULL override, the call the dialogs make after Revert) empties it. A/B on one paused view: the slot lot shows The
   Joneses with the replacement and stock Dingy Ave. without it (`t2_ab_slot_on_off_crop.png`, full frames
   `t2_ab_slot_on_off_full.png`).
3. **The stock dialog, posted clicks only, on the reloaded city (run 2).** Query on a slot house: name "The Joneses",
   architect Maxis, BAT picture, button "Sustituir" (`t3`). Sustituir opens "Sustitución de edificio 1x1" with The
   Joneses as the only 1x1 BAT and as the current building (`t4`). Revertir + OK: map count 0, lot back to Dingy Ave.
   (`t5`). Query again: "BAT Slot Residential Low Density § 1x1" (first naming) with Dingy Ave.'s picture and
   Sustituir (`t6`). Sustituir, pick The Joneses, Sustituir arrow (`t7`), OK: map count 1, same pair. Save C written
   after it holds the pair.
4. **Save and reload with the package.** Save B loaded in a new process: the pair is in the map right after load
   (LoadBATReplacementSet `0x100059d7`), and the slot house queries as The Joneses (`t3`).
5. **Load without the package.** Save C loaded with `bat_slots` uninstalled: no fault (one VEH entry,
   `0xC0000096 at SC3U.exe+0x84122` about 1 s after start, the same as every run, also in growable's runs). The slot
   buildings are dropped, as in growable: 0 of each slot id in save D, stock family 11 up from 3,590 to 4,432. The
   replacement pair stays in the map and is written into save D again: `0x10005bde` calls the attrib cache (which
   finds no attrib) and records the pair anyway. Reinstalling the package and loading save D was not run, so whether
   the BAT comes back on the slot is [UNCERTAIN] (expected from the code: LoadBATReplacementSet calls
   MakeBATReplacement for each saved pair).
6. **Saved form of the set** (writer SIMINIT `0x10006328`, now read on real saves): record `{0x99F47014, 0x79F4702D,
   0}` of the `.sc3` container itself, not of the city blob. 12-byte zero key, u32 count, then per pair the building
   key and the BAT key, 3 x u32 each. Shipped cities carry the 16-byte empty form. [CONFIRMED, saves A to D]

Pictures: `MAIN\verify\batslots\owner_shots\` (not committed). t2 A/B, t3 reload query, t4 1x1 dialog, t5 revert
via the dialog, t6 unassigned slot query, t7 replacement staged, t8 2x2 dialog list, t9 abandoned 2x2 slot (no
button), t10 slot under construction (no button).

## The game's BAT list and the .bld format (for the later converter)

- **The BAT buildings the game offers live in `Apps\BARender\BAT.DAT`**, not in the `.bld` files. SIMINIT
  `0x10005ae2` (scheme vt+0x80 LoadBATSegment) opens `<dir>BAT.dat` (string `0x10037360`) as a segment and keeps its
  keys at `+0x80`. The directory comes from a service vt+0x50 and is [UNCERTAIN] by code, but `Apps\BARender\BAT.DAT`
  is the only file of that name in the install, and the dialogs listed exactly its buildings (`t4`, `t8`).
- BAT.DAT (shipped): 510 records, all group `0xBA1DBF1E`. 15 buildings, each = 16 pixel records (type 0) + 16
  anchor records (type 1) + one frame table (type `0x6300`) + one override record (type `0x856CD19A`). Override
  payload: byte lot size, sprite attrib key `{0x6300, 0xBA1DBF1E, inst}`, u32 length + name, u32 length + architect,
  then 8 bytes (zero in 14 of 15; Headquarters has `01 00 00 00 20 00 00 00`) and the instance again. The override
  key is the BAT key the replacement uses. The 17 shipped `.bld` files are 15 of these plus Tutorial House and
  Zweikky Unpainted.
- **A `.bld` is the Building Architect's editable 3D project**, an IXF container (magic `0x80C381D7`), every record
  in group `0xC3F8D4A9`:

| type | instance | what (read from the 17 files) |
|---|---|---|
| `0xE3F87B0C` | `0xA3F8D615` | the model; header bytes `08 0? 8N 0N` carry the lot size N (1..4) and 8N |
| `0xE3F87B0D` / `0xE3F87B10` | 0..k | texture header (about 90 bytes) / texture image (`F1 0E`, width, height, compressed), k = 0 to 17 per file |
| `0xE3F87B0F` | `0x63FBE1CC` | byte lot size, u8 length + name, u8 length + architect, 4 zero bytes, u32 |
| `0x644D7179` | `0xA44D71AB` | u32 0x208 / 0x209 / 0x20A / 0x20F / 0x212 / 0x217: houses (Dupont, The Joneses) 0x208, shops and offices 0x209, factories 0x20A, the school 0x20F. Reading it as a category is a hypothesis from the names [UNCERTAIN] |
| `0x644D7178`, `0xB9EC8F72`, `0x99F88B9E` | | small flags (1 to 4 bytes), meaning not read |
| `0xE3F87B0E` | `0xE3F8D655` | preview image, 200x200 |

- So a converter does not need to render `.bld` files. The game does that itself when the player adds a building
  with "Editar lista" (the in-game BAT, SIMBABLD, `sc3_bat_export_rendered_buildings_ixf`), which rewrites BAT.DAT.
  A converter then reads the player's BAT.DAT: for each override, a new growable exemplar copied from a stock
  building of the chosen class and footprint (LandUse, stats), with prop 0x67 pointing at that building's `0x6300`
  frame table (or a copy of the table and pixels in netpack's containers), plus a family line. What it needs that is
  not built: netpack art from a BAT.DAT frame table (BAT tables index 16 frames, stock building tables 20: which
  zoom or rotation the 4 missing frames are is [UNCERTAIN]), a class pick per building (the 0x644D7179 value can
  default R / C / I), and running on the player's PC, since BAT.DAT is per install.

## Not checked

- The Building Replacement Manager window itself (New City flow, City Scheme dialog): **needs owner check.** Expected
  from the code: the slots appear among the slides of their type and size from the moment the package is installed,
  looking like their base building. Where in the slide order they appear was not seen.
- The renamed build (Light / Medium / Dense names) in game. Only the first naming was seen.
- A .bld the player adds through "Editar lista". Only the 15 shipped BAT buildings were used.
- A 2x2 slot with a BAT building (only the 2x2 list was opened, on a stock building, and closed without OK).
- Reinstall + reload of save D. Running together with stylemix's package. A building style (European / Asian) active.
- `netpack selftest` (ran 15 min without output twice and was stopped). It covers the road examples. The growables
  path ran in both installs.
- `[ReplaceableBuildings]` in `re/data/syspak/SC3CityScheme.ini` has 323 rows, the staged SYS.PAK 338. Which 15
  rows were added and by what was not looked at.
