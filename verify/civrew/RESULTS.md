# civrew results (round 2026-11-19i): civic buildings and rewards, research + proposal

Research only, no mod built, no game run. Full evidence: `re/analysis/CIVIC_REWARD.md`.

**Verdict.**

- **New civic building (a second police station look, a new school):** it does not need a new menu entry. The sim
  treats a building as a police station by its type id (13130), and the stock tool places any key. Only the choice is
  missing: each civic button builds one hard-coded exemplar. Smallest change: bldimport writes a copy of the stock
  exemplar (same type and stats, own key, art and name) into the existing plugin, and a 5-byte detour in SIMGEOM swaps
  the key when the button is pressed (cycle through the looks, name shown in the cost label).
- **New reward:** a new `[REWARD_BUILDINGS]` row is parsed but can never unlock, because every unlock path is a
  hard-coded list of type ids. Smallest change: the row (in our own ini, read with the game's own parser) plus a
  6-byte detour at SIMADV `0x1000a7fa` that adds our type ids to the "unlock when population and year are met" set.

## 1. Checks run

| check | how | result |
|---|---|---|
| civic command -> exemplar key | read SIMGEOM `sc3_geom_dispatch_command_handler` `0x1000a896` (export + PE disassembly) | 20 command class ids -> `{0x207edc0e, 0x57e, instance}`, 17 through one call to the plain tool at `0x1000b1a3` |
| those keys exist, with the right types | probe over `stage\release\Apps\Res\Occupant\*.IXF` with `batgrow.stock_buildings` (prop 0x65 / 0x66) | 20 of 20 found, all in `OccupantAttribs.IXF`, types match `CitySim.ini` (Police 0xd2 = 13130, School 0x1f94 = 13010, ...) |
| the menu click path | SIMUI menu item vtable `0x100a317c` +0xc = `FUN_10016329`, SC3U `cRZGameCommandFactory::GetCommand` `0x0047477b` / `AddCommandFactory` `0x004747bd` (CV names), SIMGEOM vtable `0x10029200` +0xc = `0x1000a896` (pointer found in `.rdata`) | a new command object per click, the service asks every factory in order |
| civic function by type | SIMSERV `0x1000f006` (`IsA(13130, type)`), SIMGEOM `0x10008599`, `SC3BudgetLayer.ini` | police, fire, news, price follow the type id |
| reward rows | SIMADV `0x10007989` (EnumEntries), callback stubs `0x100089bf` / `0x100089d3` (disassembly: `push 0` / `push 1`), parser `FUN_100089e7`, item vtable `0x10030614` (getter offsets from the PE) | type id is the map key, columns = population, year, petition id, own-rule flag |
| unlock rules | SIMADV `FUN_1000a324` + `FUN_1000abb2` against the ini | the 11 rows with own-rule 1 = the 11 switch cases. The 12 petition ids in the answer handler = column 3 of those 12 rows. 7 types unlock directly (`0x1000a7fa` chain) |
| new type unlock | same code | not in the 7-id set, no petition case: never unlocked |
| reward save / load | SIMADV `0x100073b3` / `0x100071ed` | saved by exemplar key, unknown keys skipped on load |
| patch windows clean | linear disassembly of the whole function + absolute-dword search of the file | no branch or table entry into `0x1000a7fb..a7ff` (SIMADV, 390 insns) or `0x1000b19e..b1a1` (SIMGEOM, 620 insns) |
| no mod already hooks these | grep of `re/harness/src` for the RVAs | none |
| DLLs are stock | sha256 of `Apps\SIMGEOM.DLL`, `Apps\SIMADV.DLL` vs `stage\release\Apps\` | identical (`17a76e83...`, `c1183ae8...`) |

Throwaway probes (scratch only, not kept): a PE disassembler (`x86dump.py`, `vtdump.py`, capstone 5.0.7), the
`.text` operand scan for `+0x30d]`, and the IXF key check `civkeys.py`.

## 2. What each needs

| | new civic building | new reward |
|---|---|---|
| exemplar | copy of the base command's exemplar, SAME type, own key / art / name, `[OccupantKeys]` line | copy of a stock reward of the same lot, NEW unique type id, own key / art / name, `[OccupantKeys]` line |
| list / menu data | `bldimport_civic.ini` `[Variants] <base instance>=<variant ids>` | `[REWARD_BUILDINGS]` row `<type>=<name> ;<population>;<year>;0;0` |
| code | SIMGEOM `0x1000b19d` detour: base instance at `[ebp-0x34]` -> chosen variant (and group) | SIMADV `0x1000a7fa` detour: our types -> `0x1000a832` (unlocked). Load our ini after `0x10007989` with the game's `cSC3CompressibleINIFile` + stock callback `0x100089bf` |
| other mods | none needed | add the type block to sc3resize `rl_types` (Mover, picker refusal) |

## 3. Risks (detail in CIVIC_REWARD.md 3)

- Saves: both are saved by their plugin key. Without the plugin the lot is empty (measured for landmarks in plop).
  Civic variants then lose their coverage silently. Reward unlock bytes for unknown keys are ignored on load.
- Menus at other UI scales: no menu or window changes. The variant name rides placehints' cost label, the reward shows
  in the stock Rewards dialog (DLGSCALE).
- A variant with a smaller lot than its base keeps the base's coverage radius.
- An undeclared reward type id passes every path read, but the query dialog / newscast handling of it was not read.
- Loading our ini with the game's ini class without a compressed path was not run. Fallback: netpack's SYS.PAK
  `ini[]` edit (needs sc3netmod's overlay).

## 4. Side findings

- `RELOCATE.md` 3 names the wrong advisor for rewards (`0x10017ba8` / `0x10031178` are the Utilities advisor's plant
  lists). The reward advisor is the City Planner (`0x10006656`, items `0x10030614`) and it does track insert / remove.
  RELOCATE's conclusion (a move cannot lose a reward) still holds.
- sc3resize `rl_movable` (`sc3resize.c:10411`) tests `18000 < t < 19000`. bldimport's landmarks have type 18000, so
  they get no "Mover" and the picker would offer their tool (a second copy). Read, not run.
- Stock has a hidden all-buildings catalog: with cheat codes enabled, opening Power Plants, Rewards, Garbage, then
  Landmarks lists every building (SIMUI `0x10011919`, mode `0xa2f7d03a`) and marks the city cheated
  (`SetCheatHasBeenSet(0xe37fb7b8, 1)`). Read, not run.
- The three 4-piece rewards (Theme Park, Military Base, Generic University) use a 4-key tool that only rotates which
  piece goes where. It is not a variant mechanism.

## 5. Not done

No mod, no bldimport change, no in-game test (brief: research, then propose). The proposal needs one in-game check per
part when it is built: a police variant placed, covered and saved, and a reward row unlocked at its population.
