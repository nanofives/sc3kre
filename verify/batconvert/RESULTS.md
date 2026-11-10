# batconvert: every BAT building a player has grows in zones as its own building (2026-11-10)

Verdict: **works, data only, no code, a PowerShell tool on the player's PC.** `bat_growables.ps1` reads the player's
`Apps\BARender\BAT.DAT` and turns each Building Architect building in it into a NEW growable building (ids 37000 to
37999) next to the stock members of a class the player picks in `bat_growables.ini`. Nothing stock is replaced. In
Sacramento 11 of the 15 shipped BAT buildings grew by the second autosave (809 lots), next to stock buildings, BAT
slots and both style copies. A grown lot queries as "The Joneses" with key `{0x207EDC0E, 0x57E, 37000}`. Save and
reload pass. `-Restore` gives back all 26,294 files under `mods\netmod` byte for byte. A save loaded without the
converted buildings does not crash: each lot gets a building of the same type.

Second half of the Simtropolis request whose first half is `verify/batslots`. Static RE: `re/analysis/BUILDING_PICK.md`
sections 5, 6 C and 7 (updated).

## Design decisions

### (1) Copy the art, do not point at BAT.DAT

Question: can a new exemplar's prop 0x67 point straight at the BAT.DAT frame table `{0x6300, 0xBA1DBF1E, inst}`?

- Static: `sc3_schememgr_load_bat_segment` (SIMINIT `0x10005ae2`) opens `<dir>BAT.dat` through `FUN_10005fff`, the
  same routine that registers the building set DATs (resource segment plus `cISC3CitySpriteImageMgr`). [CONFIRMED @
  0x10005ae2]
- In game (lab arm, patch undone afterwards): exemplar 37000 with prop 0x67 = `{0x6300, 0xBA1DBF1E, 0x660041BD}`
  (The Joneses' own BAT.DAT table) and nothing else changed. 797 lots of 37000 grew, the query on one reads "The
  Joneses", key `0x9088`, and the lot draws the BAT art (`t5_lab_direct_bat_table_vs_sprite_x4.png`: game frame
  against the sprite, same house, a neighbour's tree in front). **So yes, it draws** while BAT.DAT holds the building.

The tool copies anyway, for three reasons:

1. The scheme manager also unloads and reloads that segment (`sc3_schememgr_unload_bat_segment` `0x10006a8f`,
   `sc3_schememgr_update_bat_segment` `0x10006c35`, callers not traced). A converted building pointing into BAT.DAT
   depends on what that segment holds at draw time.
2. BAT.DAT instance numbers are not the `.bld` file's own: the last u32 of each `.bld` record `0xE3F87B0F` equals the
   BAT.DAT override instance for 13 of the 15 shipped buildings, not for The Joneses (`0xC5FEEC45` against
   `0x660041BD`) and Maxis Towers (`0x85FEEB97` against `0x460026F3`). Whether a rewrite of BAT.DAT keeps the
   instances was not checked. A copy makes the converted building independent of that.
3. The copy keeps each converted building as it was when the tool ran until the player runs it again.

Cost: one 1.8 MB DAT for the 15 shipped buildings (`BA7C0001_batgrow.DAT`, 1,815,753 bytes).

### (2) What one BAT building becomes

| Piece | Key / value | Container (all under `mods\netmod\overlay\`) |
|---|---|---|
| Pixels | its 16 pixel (type 0) + 16 anchor (type 1) records, verbatim, keys `(0xBA7C0001, id << 16 \| ordinal)`, ordinal = order of first use in the table | `Apps\Res\Sprites\BA7C0001_batgrow.DAT` (new, `Res\Sprites\*.DAT` is listed at startup) |
| Frame table | its BAT.DAT `0x6300` table verbatim, each entry's (group, instance) pointed at the copied pixels, key `{0x6300, 0xBA7C0001, id}` | `Apps\Res\Sprites\CSAttrib_Korea.IXF` (appended) |
| Exemplar | the TKB1 record of a stock building of the chosen class and the BAT lot size, re-keyed `{0x207EDC0E, 0x57E, id}`: prop 0x67 = the table above, prop 0x6D = `{0x2026960B, 0xA1096A4F, id}`, prop 0x64 = the BAT name | `Apps\Res\Occupant\OccupantAttribs_Korea.IXF` (appended, `[OccAttribCache]` Entry5) |
| Name | `{0x2026960B, 0xA1096A4F, id}` = the BAT name | `Apps\Res\Text\<lang>\SC3StringsNetpack.IXF`, all 7 (appended, already a `[DBSegments]` row) |
| Family line | `Key: 1406,545184782,<id>,<weight>   <name>` after `BuildingCount` (count raised), in every family that is the first family of the class in some `[ZoneDeveloperRules]` row, minus family 1 | `Apps\Res\BUILDFAM.IXF` (record replaced netpack-style: new payload appended, slot re-pointed) |

- The group `0xBA7C0001` is used by no container under `Apps\Res` (scanned).
- BAT frame tables have **20** entries like stock ones, not 16: entries 16-19 name the pixels of entries 12-15 with
  flag 2, the same pattern as stock tables. 16 distinct pixel records per building. [CONFIRMED, all 15 tables of the
  shipped BAT.DAT]. So nothing had to be added to make a BAT table a building table.
- The exemplar is copied (as growable_test and bat_slots do), so population, jobs and every other stat are the stock
  building's. The BAT override record carries only lot size, name and architect, nothing to derive stats from.

### (3) The class: a player-edited ini, defaults from the .bld

`bat_growables.ini` in the game folder, one section per BAT building, keyed by its number:

```
[37000]
name = The Joneses
bat = 660041BD
size = 1
enabled = 1
class = 3300
weight = 1
```

- `class` is a LandUse (prop 0x65). The 22 RCI classes are listed at the top of the file with the lot sizes each one
  takes, so the player sees which classes accept a 3x3 building. Airport and seaport classes are left out.
- Defaults: the `.bld` record `0x644D7179` read from `<game>\Buildings\*.bld` (matched to BAT.DAT by the instance
  above, else by name): `0x208` -> residential, `0x209` -> commercial, `0x20A` -> industrial (12 of the 15 shipped
  buildings). Anything else (Kankakee Jr. High School `0x20F`, Den Burg Bruges `0x212`, Longview Park `0x217`) starts
  `enabled = 0`, so the tool does not guess silently. Reading `0x644D7179` as a category stays [UNCERTAIN] (from the
  building names only). Default class per zone and lot size: R 3300 / 3900 / 4500 / 4500, C 5100 / 5700 / 6300 /
  6700, I 8700 / 8700 / 8900 / 9100 for 1x1 to 4x4 (each class has a stock base of that size).
- `weight` default 1 = as often as one stock member of weight 1 (the batslots choice). 1 to 1000 accepted.
- Numbers are given once and kept: on a re-run a section is matched by `bat`, then by name when that BAT instance is
  gone (a re-rendered building), and a new building gets the next free number. A section whose building left BAT.DAT
  stays in the ini (skipped), so its number is never reused for another building.
- Stats base per class and size (`batgrow.py tables`, embedded in the script, `batgrow.py check-ps` verifies it):
  the first member in family order with a plain `0x6300` table, a square footprint of that size, a name key, and
  prop `0xCA & 0x100` clear. That bit is set on filler lots (Playground 3079: `0x100`, Dingy Ave. `0x0`, Goodplace
  Arms `0xA4`), so a BAT house never copies a playground's stats. Whether prop 0xCA is the attrib flag word `+0xbc`
  of BUILDING_PICK.md 2 is [UNCERTAIN] (data only).

### (4) Ids and coexistence

37000 to 37999 (36001-36099 tests, 36100-36999 bat slots, +400000 / +1500000 style copies). Every write is an append
or a line insert: the road packages, bat_slots and style_mix records stay (family 4 after the run: 1 BAT line, 1 slot,
24 style lines, 12 stock. Family 8: 3 BAT, 1 slot, 13 style, 12 stock).

### (5) Re-runnable and reversible

- State in `mods\netmod\batgrow\state.json` (sha256 written per file, whether the file existed) with one backup per
  changed file. Each run first puts back what the last run wrote, then applies the ini. A file whose bytes changed
  since (a new sc3mods release replaced it) is taken as the new source and its old backup dropped. If a release
  replaces the whole `mods\netmod`, state and edits go together and the next run starts clean.
- Needs the road mod's overlay (`OccupantAttribs_Korea.IXF`, `CSAttrib_Korea.IXF`, `SC3StringsNetpack.IXF`), else it
  stops with a message. Refuses to run while SC3U.exe runs from that folder. Writes temp + move (hard-link safe).
- Windows PowerShell 5.1 compatible (what players have). Traps met: `h` and `cat` are built-in aliases that win over
  same-named functions, hex literals above `0x7FFFFFFF` are negative Int32, and variable names are case-insensitive
  (`$names` overwrote `$NAMES`).

## Evidence

Dev workspace `dev/batconvert`. Tree = staged release (`stage/src/mods/netmod`: 20 road packages) plus
`netpack install` of `style_mix` then `bat_slots`. Tool run with all 15 buildings enabled at weight 20 (Kankakee Jr.
High School class 4100, Longview Park and Den Burg Bruges 4500, the rest at their defaults). City: a copy of
`Sacramento, CA.sc3` (style 0), churn `anarchy_res/com/ind=5000` (`inst\simrun.ini`), speed 4, autosave every 150 s,
windowed, posted keys and clicks only. Counts: `re/tools/batgrow_count.py` (occupant_layer).

### Offline

| Check | Result |
|---|---|
| PowerShell 5.1 run against `batgrow.py compare` | 11 files + the ini, 0 differences |
| PowerShell 7 run, same | 0 differences |
| second run, same ini | identical BUILDFAM, Korea and ini hashes |
| `-Restore` against the snapshot taken before the first run | all 26,294 files under `mods\netmod` identical, 4 times (after the default run, after the game runs, after the lab arm, after the update case) |
| simulated sc3mods update (Korea file replaced by its pre-run bytes between two runs) | second run reports it, applies on it, 0 differences to python, `-Restore` identical |

### In game

| Save | Occupants | Stock | BAT slots | Converted (37xxx) | European | Asian |
|---|---|---|---|---|---|---|
| Sacramento as shipped | 16,466 | 16,379 | 0 | 0 | 0 | 0 |
| (1) first autosave | | | | 801 | | |
| (2) second autosave = save A | 16,122 | 11,588 | 102 | **809** | 1,897 | 1,639 |
| (3) A reloaded with the tool's files, next autosave = save B | 16,117 | 11,258 | 109 | **852** | 2,094 | 1,717 |
| (4) B loaded after `-Restore`, autosave while still paused | 16,117 | 11,602 | 132 | 0 | 2,344 | 1,952 |

1. **Converted buildings grow next to stock ones.** Per id in save A: The Joneses 596, North Shore Cannery 101,
   Dupont House 44, GuestHouse Building 34, Trash & Burn 11, Northeast Nonwovens 6, Garvey Plaza 5, HiTech Lab 5,
   Hotel Splash 4, Proton Building 2, Kankakee Jr. High School 1. 3x3 lots grew (Kankakee, the three factories). Stock,
   slots and both style copies kept growing in every save.
2. **Not grown in this city:** Maxis Towers and Headquarters (class 6300, 3x3) and Longview Park / Den Burg Bruges
   (class 4500, 4x4 / 3x3). Sacramento as shipped has 0 lots of type 6300 and 3 of 4500, so those classes had almost
   nothing to redevelop. Not a failure seen, not a pass either.
3. **Seen and queried** (`t1`, `t2`): an exact sprite match (RMS 4.7 on 0-255 RGB) for The Joneses at zoom 2 in the
   first autosave's view, then the query on that lot: "The Joneses", Residencial, BAT picture, and "Copiar ID" reads
   `object.key: 0x207EDC0E 0x0000057E 0x00009088`, type 3300, 1x1. No "Sustituir" button: converted buildings are not
   in `[ReplaceableBuildings]` (not needed, they carry their own art).
4. **Reload** of save A in a new process: no fault besides the `0xC0000096 at SC3U.exe+0x84122` entry every run logs
   at start, The Joneses drawn again (`t3`, exact match), growth continues (save B).
5. **Load without the converted buildings** (`-Restore`, slots and style copies kept): no new fault. In the autosave
   taken while still paused, all 852 converted lots hold a building of the **same building type** at the same cell,
   0 ids 37xxx are left, the occupant count is unchanged and no other occupant changed (`t4`). The 101 North Shore
   Cannery lots became 159 Storage Tanks, the 2x2 class-8700 building its stats come from. Same behaviour as stylemix
   case 5.
6. **The ini a player edits** is what grew: the three buildings that start disabled grew only after `enabled = 1` and
   a class were set (Kankakee 1 in save A).

Pictures: `MAIN\verify\batconvert\owner_shots\` (not committed, game art): `legend_bat_converted.png` (the 15
converted buildings drawn from the tree's overlay, zoom 3), `t1_sacramento_first_autosave_view.png` and
`t1_joneses_grown_crop_x4.png`, `t2_query_the_joneses.png`, `t3_reload_save_A.png`,
`t4_save_B_loaded_without_converted.png`, `t5_lab_direct_bat_table_query.png` and
`t5_lab_direct_bat_table_vs_sprite_x4.png` (question 1).

## What a player does by hand

- Add a building of their own to the game's BAT list first: in a city, the Replace window of a building of that size,
  "Edit list" (Editar lista), which rewrites `Apps\BARender\BAT.DAT`. Then close the game and run the tool.
- Pick a class for buildings that start disabled (schools, parks, anything the `.bld` does not mark as house, shop or
  factory), and check the guessed classes.
- Run the tool again after every sc3mods update.
- PowerShell: `powershell -ExecutionPolicy Bypass -File .\tools\bat_growables.ps1` (as community_patch.ps1).

## Not checked

- A `.bld` added by the player through "Edit list". Only the 15 shipped BAT buildings were used.
- Whether BAT.DAT keeps a building's instance when the list is edited (the ini falls back to the name).
- Classes 6300 and 4500 growing (no lots of them in Sacramento), 4x4 lots, a building style active, a European city.
- `netpack install` on a tree where the tool has run: run `-Restore` first (the ledger hashes the overlay files).
- Release staging: `stage_lan_release.py` does not copy the script into the release yet (`tools\bat_growables.ps1`
  in the README section). Not done here, no release was asked for.
- Population and demand effects of the weights. Weight 20 was used to see growth quickly.

## Files

- Commit (from `dev/batconvert/wt`): `re/scripts/bat_growables.ps1`, `re/tools/batgrow.py`,
  `re/tools/batgrow_count.py`, `re/analysis/BUILDING_PICK.md`, `verify/batconvert/RESULTS.md`, `README.md`.
  MAIN: `re/sessions/STATUS_batconvert.md`.
- Not committed: `MAIN\verify\batconvert\owner_shots\*.png`, the saves in `dev/batconvert/tree/Cities`.
