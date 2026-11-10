# BUILDING_PICK: how a zoned lot picks its building, and what the building set changes

2026-11-10. Asked by Simtropolis players: (a) all three building styles in one city, ideally chosen per zone, and
(b) custom buildings ADDED to the pool of buildings that grow in zones instead of replacing a stock one. Static reading
only (no game run, no Ghidra session). Every claim carries `[CONFIRMED @ addr]` or `[UNCERTAIN]` with what is missing.

**Verdicts (section 6):** (C) additive custom growables work with data only, proven in game on 2026-11-10
(`verify/growable/RESULTS.md`, netpack `growables` key). (A) all three sets in one city with a random mix works with
data only, proven in game on 2026-11-10 (`verify/stylemix/RESULTS.md`, netpack `style_sets` key): each set building
gets its own occupant id, its frame tables go to `CSAttrib_Korea` and its pixels to a top-level `Res\Sprites` DAT, so
no set has to be active. (B) a per-area style the player paints needs
code: one hook, a paint tool and save storage. A per-zone-type style (all residential European, say) is data only.

## 0. Corrections to the starting assumptions

1. **The occupant id does not change between sets.** In `BST_0004.dat` the FooFoo Shops TKB1 record sits at key
   `{0x207EDC0E, 0x57E, 0xFA8}` (4008), the same key as the base record in `OccupantAttribs.IXF`. What differs is prop
   0x67, the frame-table key: base `{0x6300, 0x6400, 0xFA8}`, BST `{0x6300, 0x5432D60F, 0x62A28}`, MBE
   `{0x6300, 0x547B7DF6, 0x16F308}`. So 404008 and 1504008 are frame-table instance numbers, not occupant ids. The
   `occupant` column of `re/data/sprite_objects.csv` holds the prop 0x67 instance for set archives. [CONFIRMED, read
   from the files] All 139 BST and 165 MBE occupant ids also exist in the base attrib files. Footprint X and Y are
   identical to base in all of them (only the middle value of prop 0x66 differs), and prop 0x65 is identical in all.
   [CONFIRMED, data]
2. `ZONE_REDEVELOPMENT.md` lists the byte `local_24` as `[UNCERTAIN]`. It is read from `this+0x74`, which the res
   developer init `0x10028864` fills from city `vt+0x154` (CodeView `cISC3City::PlumbingLayer`). The value is
   `PlumbingLayer vt+0x48(x,y)` and it gates density above 1. [CONFIRMED @ 0x10028f12, 0x10028864] What plumbing
   `vt+0x48` returns is [UNCERTAIN]: no CodeView interface for that layer.
3. SIMINIT `sc3_region_load_with_progress` `0x10006589` is `cISC3CitySchemeMgr::SetCityScheme` (slot `0x18` of vtable
   `0x1002f528`, the CodeView `SetCityScheme` slot). [CONFIRMED]

## 1. Call chain: a zoned tile becomes a building

| Step | What happens | Address (SIMRCI unless noted) |
|---|---|---|
| 1 | ZoneLayer `Simulate`; when interval == 2 it runs `FUN_1003372a`, which evaluates W*H/30 tiles per call | `0x10031499`, `0x1003372a` (ZONE_REDEVELOPMENT §1) |
| 2 | Each tile goes to the developer for its zone type. Res: second vtable `0x1004cd38` slot `+0x18` | res `0x10028f12`, com `0x1000fd53`, ind `0x10017fc0` |
| 3 | The evaluator reads land value, the plumbing byte, power, pollution, IsNearTransport and demand minus filled demand (ZoneLayer slot 30), then picks a **lot class** | `0x10028f12` |
| 4 | Class pickers: new / richer / denser / cheaper | `0x100295dc` / `0x1002971a` / `0x100298af` / `0x100297fb` |
| 5 | Develop: ZoneLayer `vt+0x74` (slot 29 `FindBuildableRect`, gets class byte 2 = minimum land value), then `FUN_10029962` | `0x10029666` |
| 6 | Tries up to `min(4, n)` distinct **rules**, at random without replacement, from the developer's rule vector `this+0x38`, calling rule `vt+0x1c` (Apply) until one succeeds | `0x10029962` |
| 7 | Rule Apply: the **first** family record whose LandUse == class, then a uniform random index into that record's weighted lists, then `ZoneLayer vt+0x68` | e.g. `0x10027699` (rule `0x222c9d00`) |
| 8 | ZoneLayer slot 26 `PlaceBuilding(attrib, coords, ...)`: takes the attrib's Key (`vt+0x14`), creates the occupant **from the key** via `this+0x24c vt+0x20(key, 0xe0faadc7, &occ)`, positions it, inserts it (`+0x58`) | `0x10032dfc` |

The iOS names fit the same shape (`goResZoneDeveloper::growSomething / findRicherLandUse / findDenserLandUse /
findCheaperLandUse`, `goResLDDeveloperRule::Apply / RegisterBuildingFamily`) [iOS-HINT]. The object at ZoneLayer
`+0x24c` is [UNCERTAIN]: its `+0x20` and `+0x58` slots do not match the `cISC3OccupantManager` names.

## 2. The candidate list: where it comes from, how it is keyed

### Lot classes (= LandUse = building type id = prop 0x65)

From `SC3ZoneLayer.ini [ZoneDeveloperDescriptions]` (SYS.PAK). Each row is
`devIndex=<developer GZCLSID>,<header>:<class>,<density>,<maxLV>,<minLV>;...`. One developer object per row through
`GetClassObject(clsid, 0x2108580c)`, then `dev vt+0xc(city, rest-of-row)`, registered with ZoneLayer `vt+0x58`
(slot 22 `RegisterZoneDeveloper(u8 zoneType, dev, clsid)`). [CONFIRMED @ 0x10030c5b]

The res developer init `0x10028864` discards two leading tokens; each 4-tuple goes to `FUN_10028ce0`, which stores
`record[class] = {byte0 density, byte1 maxLV, byte2 minLV}` in the map at `+0x28` plus two multimaps at `+0x10` and
`+0x1c`. [CONFIRMED @ 0x10028864, 0x10028ce0] `pick_new_class` takes the class with the highest `minLV` where
`minLV <= LV <= maxLV`, and requires `density == 1` unless the plumbing byte is set. [CONFIRMED @ 0x100295dc]

| Zone | Developer rows | Classes |
|---|---|---|
| Residential | dev 1-3 = `0x619ba64e` | 3100 / 3300 / 3500 (density 1), 3700 / 3900 / 4100 (density 2), 4300 / 4500 / 4700 (density 3) |
| Commercial | dev 5-7 = `0x41a3adc1` | 5100 ... 6700 |
| Industrial | dev 9-11 = `0xe1a53b30` | 8100 ... 9300 (rows carry an extra D / C / A token, industrial parser not read) |

### Rules

From `[ZoneDeveloperRules]`, rows `devIndex,ruleCLSID=<type>,<group>,<inst>;...`. One rule object per row:
`GetClassObject(ruleCLSID, 0xa1f3e1db)`, `Init(city)`. Each `{0x81f53d09, 0x01f58d3d, N}` key is resolved through the
resource manager `vt+0x14(key, 0xa1f592f9)` and each family found goes to rule `vt+0x14` (AddFamily). The rule is
attached with developer `vt+0x1c`; res `0x10028caa` pushes it into `+0x38` and calls rule
`vt+0x18(MaxDistFromTransport)`. [CONFIRMED @ 0x10030d64, 0x100310d3, 0x10028caa]

Sixteen rule classes exist (vtables `0x1004c10c ... 0x1004b17c`). All 16 AddFamily bodies call family `+0x10` /
`+0x14` / attrib `+0xbc`. 12 of the 16 Apply bodies select the family record by `== param_2` (the class); the
exceptions are the airport and seaport rules `0x100032d1`, `0x1002b04c`, `0x1002d27f`. [CONFIRMED]

### Families: the actual candidate list

`Apps\Res\BUILDFAM.IXF`, loaded as DB segment `0x01f58d3d` by `Default.ini [DBSegments]`: 31 records, type
`0x81f53d09`, group `0x01f58d3d`, instance 1 to 31. Each record is text:

```
TXT! <comment>
LandUse: 3500
BuildingCount: 17
Key: 1406,545184782,3077,1   Ike's House
...
```

- Parser: SIMGEOM `0x10001130` dispatches on the magic `TXT!` (`0x21545854`) or `BIN!` (`0x214e4942`); text goes to
  `0x10001250`, binary to `0x1000118f`. [CONFIRMED]
- Each Key line resolves `{type 545184782 = 0x207EDC0E, group 1406 = 0x57E, instance = occupant id}` with
  `GetResource(key, 0x21183b00)`. That iid's slots match `cISC3OccupantAttrib` (Key at `+0x14`, SizeInCellsX/Z at
  `+0x40/+0x44`). A Key whose 4th field is 0, or whose id does not resolve, is dropped and the count lowered.
  [CONFIRMED @ 0x10001250]
- Family vtable `0x10029130`: `+0xc` LandUse (`+0x18`), `+0x10` count (`+0x1c`), `+0x14` copies `{attrib*, field4}`
  pairs. [CONFIRMED]
- **The 4th Key field is a weight.** AddFamily pushes each attrib `field4` times into the record's lists, and Apply
  draws with `RandomUint32Uniform(listSize)`. [CONFIRMED @ 0x100274bb, 0x10027699] Shipped weights are 1 to 10.
- List split inside each rule record (`0x100274bb`): `+4` = attrib flag `0x100` clear; `+0x10` = flag clear and
  SizeInCellsX >= 3 (corner/edge placement); `+0x1c` = flag set. For rule `0x222c9d00` the fill pass draws from `+4`
  with probability `DAT_10058010` % (4th int of SC3Tune `[0x<clsid>] ZoneDeveloperRules`), otherwise from `+0x1c`.
  [CONFIRMED @ 0x1002713c, 0x10027699] The meaning of attrib flag `+0xbc & 0x100` is [UNCERTAIN].
- **One family per LandUse per rule.** Apply takes the first record whose LandUse matches and breaks out of the loop;
  a second family with the same LandUse on the same rule is never used. [CONFIRMED @ 0x10027699, 0x1000c3eb]

All 31 families checked against the occupant data: every RCI member's prop 0x65 equals the family LandUse. Examples:
family 11 = LandUse 3100, 12 ids, BST overrides 8, MBE 9; families 5 / 6 / 18 / 21 (industrial) 0 overrides in either
set. Across all families 264 distinct ids, BST overrides 121 and MBE 130, so a stock "set" city is a mix: ids the set
does not override keep their base art. [CONFIRMED, data]

## 3. What the building set changes

**Not the list.** Families and rules are global (BUILDFAM.IXF, SYS.PAK); neither set archive contains a type
`0x81f53d09` record (types present: 0, 1, `0x207edc0e`, `0xe223741f`, `0x6300`, `0x6301`). [CONFIRMED, census]

The set changes **which record answers an existing occupant key**. GZResourceD `RegisterDBSegment` (`vt+0x5c` =
`0x1001229f`) forwards to `RegisterDBSegmentFront` (`0x100122ab`, push_front at `0x1001348f`). `FindDBSegment(key)`
(`0x1001245c`) walks from the front and returns the first segment holding the key. `GetResource` (`0x10012c48`) checks
its cache at `+0xb0`, then loads through `FindObjectFactory` + `FindDBSegment` (`0x10012ea5`). So the most recently
registered segment wins: a set DAT registered by `SetCityScheme` shadows `OccupantAttribs.IXF` for the shared keys.
No remap table, no added ids. [CONFIRMED]

`SetCityScheme` `0x10006589` with a new building set:

1. If a set is loaded and the id changed, `FUN_10006b0a`: for each archive record (vector `+0x68`, stride `0x1c`)
   sprite image manager `vt+0x30` (`0x10006bf0`), resource manager `UnregisterDBSegment` (`vt+0x68`, `0x10006c0b`),
   collect the segment's key list, release the segment, clear `+0x58`. [CONFIRMED; the key-list call inside
   `0x10006c0b` decompiles with a garbled argument, [UNCERTAIN]]
2. `FUN_1000641b` only if `setId != 0`: `Res\Sprites\BuildingSets\%08lX\`, `FUN_10005fff(*.DAT, type 0x4522864a)`.
   Per DAT: create a segment, register the path with `cISC3CitySpriteImageMgr vt+0x28`, `RegisterDBSegment` (front),
   keep its key list. Then `+0x50 = id`, `+0x58 = 1`, post `{1, id, 0, 0}`. Set 0 loads nothing. [CONFIRMED]
3. `FUN_10006f69` passes the merged key list to `cISC3App vt+0x44` (`GetAppOccupantAttribCache`, CodeView), then
   `vt+0x38` (`0x1000c584`), in batches of 200 with a progress bar. Per key `0x1000c428` does `RemoveResource(key)` then
   `GetResource(key, 0xe075ef51)`; for a cached key `0x1000d3d3` locks the city, finds every live occupant with that key
   in three occupant managers and calls `cISC3Occupant::Init(cISC3OccupantAttrib*)` (`vt+0x1c`). **Standing buildings
   re-skin in place; nothing is demolished.** [CONFIRMED]
4. The map at `this+0x8c` is the BAT replacement map (node `+0x10` original occupant key, `+0x1c` replacement resource
   key); `this vt+0xa8` = `MakeBATReplacement(key, reskey)` (`0x10005b95`) re-applies `.bld` overrides. [CONFIRMED]
5. `FUN_10006ec9`: `GetResourceListForType(0x81f53d09)` and `RemoveResource` for every family key, then city
   `vt+0x14c` (ZoneLayer) `vt+0x90` = slot 36 `0x1003250f` `ReadZoneDeveloperDescriptions(1)`: every developer, rule and
   family is rebuilt against the new attrib objects. [CONFIRMED]

`[BuildingSets]` row fields (parser `FUN_1000467c`, struct in the map at `+0x5c`):

| Field | Meaning | Evidence |
|---|---|---|
| key (`0` / `0xe523f3fb` / `0x6523f3d5`) | set id and folder name | `0x1000641b` |
| f0, f1 (`0x85535958`, `0x300N`) | icon key `{0x62b9da24, f0, f1}`; the three icons exist in `85535958_CitySchemeUI.IXF` | `0x10005424` |
| f2 to f5 (`0`, `0x3fbX0000`, `0`, `0x3fbX0001`) | the four outputs of `GetUiImageForBuildingSet` | `0x1000575f`; meaning of each pair [UNCERTAIN] |
| f6 (`0` / `2` / `1`) | `GetSoundIdForCurrentBuildingSet` | `0x10005705` |

`e523f3fb` (`BST_0004.dat`) is the European set and `6523f3d5` (`MBE_0015.dat`) the Asian one. [CONFIRMED, data] Each
set exemplar's prop 0x6D names it in group `0x453BBDE0` (`SC3MBEStringsBuildings.IXF`, a stock `[DBSegments]` row),
English-UK: 403065 "Old Charmer", 404008 "La de da Shops" against 1503065 "Kamagaland Cottage", 1504008 "Kwang-Hwa
Computer Shops". The art agrees (half-timbering and mansards against glass towers, `verify/stylemix` legend sheets).

## 4. What the save stores

- Per building: the base occupant key and the building type id. Occupant record (`0xa0ab89f0`): `+8` = building type
  id (prop 0x65), then a 3-dword key. Berlin parsed with `occupant_layer.py`: 13,573 keys `207edc0e/0000057e/<id>`, 376
  `220055e1/0000057e`. No set id per building. [CONFIRMED, saver SIMGEOM `0x1001e226`, data]
- Style switch in game: buildings change art in place, same ids and footprints (§3 step 3). [CONFIRMED mechanism, not
  watched at runtime]
- A city saved under style X and loaded under Y renders with Y's overrides wherever Y has them; every saved key exists
  in the base files. [CONFIRMED by data]
- **Each city stores its style.** Record `{type 0x0525A6B9, group 0x4525A6E2, instance 1}`, 12 bytes, uncompressed in
  every shipped save: building set, flora set, landscape. SIMINIT `FUN_10009e1f` (called from
  `sc3_city_import_savefile` `0x10008bf8`) starts from the defaults (scheme manager `vt+0x24`, `+0x4c`, `+0x68`),
  reads the three u32 when the record exists and calls `SetCityScheme(landscape, flora, buildingSet, 0)`.
  [CONFIRMED @ 0x10009e1f] Shipped values: Berlin, Moscow, London, Liverpool, Frankfurt, Madrid, Europolis, Big One,
  Mount Herrang `e523f3fb`, Seoul and Craterville `6523f3d5`, Madison, Sacramento, Farmsville, Roadless Paradise,
  Europolis 1024 and the tutorial 0. Runtime: Moscow loads with the live set `0xE523F3FB`; a copy with only that
  dword set to 0 loads with set 0, and the game's next save of it holds 0 (`verify/stylemix` case 4).
  [CONFIRMED at runtime] Live layout: scheme manager = `*(app + 0x108)` (`cSC3App::CitySchemeManager` `0x004063cf`
  reads `[ecx+0xd8]` on the `cISC3App` subobject at app+0x30), `+0x50` current building set, `+0x54` default
  (`GetDefaultBuildingSet` `0x1000550a`), `+0x58` set archives loaded.
- The app preference `SimSettings.buildingSetId` (`cSC3AppPreferences+0x90`, `SC3.cfg` record `0xA352F1B5`) does
  not decide a loaded city's style: set to 0 in a dev tree, Moscow still loaded European. Its use (the New City
  default, probably) is [UNCERTAIN]: its readers were not traced.
- BAT replacements are saved in the city: `LoadBATReplacementSet` `0x100059d7` reads record
  `{0x99f47014, 0x79f4702d, 0}` as a count then `(origKey, batKey)` pairs, each passed to `MakeBATReplacement`.
  [CONFIRMED read side; writer `0x10006328` not read]

## 5. `.bld` replacement

- `[ReplaceableBuildings]` rows `545184782,1406,<id>` are parsed by `0x10004e42` into the set at `+0xb0` as
  `{0x207EDC0E, 0x57E, id}`; `IsReplaceableBuilding` (`0x10005963`) tests `attrib->Key()` against it. [CONFIRMED]
- `MakeBATReplacement(key, override)` (`0x10005bde`) goes to attrib-cache `vt+0x40` (`0x1000d150`): it finds the
  already-cached attrib for `key` (returns 0 if absent), calls `SetOverRideAttrib(override)` (attrib `vt+0xa4`,
  CodeView), re-Inits the live occupants and records the pair in the `+0x8c` map. [CONFIRMED @ 0x1000d150, 0x1000d186]
- So a `.bld` is a **skin on an existing occupant id**. It never enters a family and never adds a candidate. BAT
  segments load as type `0x39ef105f` into the key list `+0x80` (`0x10005ae2`); SIMUI `0x1002933f` lists `*.BLD` in a
  catalog tree. A new id can only be added through families (§6 C).

## 6. Verdicts

### (C) Additive custom growables: PROVEN in game 2026-11-10, data only

Runtime result (`verify/growable/RESULTS.md`): a red copy of Pitched Roof Cottage at new id 36001, added to family 11
at weight 50 next to the 12 stock members, grew on its own in Moscow (954 lots in the first autosave, counted with
`occupant_layer.py`), reloaded with the mod (931 in the next save), and nothing stock was replaced. Reproducible as
netpack's `growables` key (`re/tools/netmod/netpack_growables.py`, example `examples/growable_test`). The recipe:

1. An exemplar TKB1 record at a new key `{0x207EDC0E, 0x57E, newId}`: prop 0x65 = an existing class (e.g. 3100, so
   population, jobs and the developer class line up), prop 0x66 footprint, prop 0x67 pointing at a new CSAttrib frame
   table.
2. That frame table plus pixels in `Res\Sprites\*.DAT`: the same three-container pipeline netpack already runs in game
   for network pieces (`NEW_PIECE.md` §2, `NETPACK.md`: Korea pair or a new SYS.PAK `[DBSegments]` row).
3. One more line `Key: 1406,545184782,<newId>,<weight>` in the family for that LandUse, BuildingCount raised: either a
   front-registered copy of the BUILDFAM record (a later `[DBSegments]` row; rows register front in INI order,
   SIMINIT `0x1000ec96`) or a patched `BuildFam.IXF`. Do not add a second family with the same LandUse to the same rule
   (ignored). Alternative: a new `[ZoneDeveloperRules]` row, a new rule instance with a new family (instance 32+),
   which competes in the up-to-4 random rule tries.
4. No code.

Family line placement: `SIMGEOM 0x10001250` reads Key lines until `BuildingCount` of them resolved; a weight-0 or
unresolved key lowers the count instead [CONFIRMED @ 0x1000136f], so the new line goes first and the count is raised
by one.

Saves: they contain `newId`. Loading one **without** the mod does not crash: the buildings are dropped on load, their
lots show as empty zoned land and regrow with stock members (no 36001 in the next save, 896 more family-11 stock
houses). [CONFIRMED at runtime, `verify/growable/RESULTS.md` (4)]. Which branch of `SIMGEOM 0x1001e516` /
`0x10002cc2` drops the key was not traced.

`[OccAttribCache]`: needed in practice. The exemplar inside `OccupantAttribs_Korea.IXF` (Entry5) works. The same
exemplar alone in a new container reached only through a `[DBSegments]` row crashed the game twice out of two runs,
~3 s after unpause, at `SIMRCI 0x10026D6D` (`call [edx+0x40]` in `sc3_resdev_place_lots_block_v3` on an attrib
whose vtable word is not valid). Why is [UNCERTAIN]; a new container with its own `[OccAttribCache]` entry was not
tested.

### (A) All three sets at once, random mix: PROVEN in game 2026-11-10, data only

Built as netpack's `style_sets` key (`re/tools/netmod/netpack_stylesets.py`, package `examples/style_mix`, results
`verify/stylemix/RESULTS.md`). Step 2 below was not needed as proposed: the set's frame tables are copied verbatim
(keys unchanged) into `CSAttrib_Korea.IXF` and its pixel records verbatim into `Res\Sprites\<group>_netpack_set.DAT`,
the two containers netpack already proved for frames and pixels, and the re-keyed exemplars go into
`OccupantAttribs_Korea.IXF` (`[OccAttribCache]` Entry5). In Moscow 2,887 European and 2,833 Asian copies grew by the
first autosave, the three styles stand in one view, reload works, switching the style European -> 0 in one session
keeps the copies' art, and a load without the package replaces each copy with a building of the same type. The
original plan follows.

Stock blocker: one key gives one record (front segment wins) and the sets reuse the base ids, so each style variant
needs its own occupant id.

1. Re-keyed exemplars: for each set TKB1 record in an RCI family (121 BST, 130 MBE), a copy at a new id.
   `id + 400000` / `id + 1500000` follow the authoring convention and are free (base `0x207EDC0E` ids top out at
   35,005). prop 0x67 unchanged.
2. Make the set's `BIN\r` frame tables (`0x5432D60F` / `0x547B7DF6`) and pixels (`0x5432D60E` / `0x547B7DF5`)
   reachable without the set's own TKB1 records shadowing base ids. Proposed: a copy of each set DAT with only its TKB1
   index entries' instance dwords rewritten (index-only patch), registered through a `[DBSegments]` row. The pixels
   must also reach `cISC3CitySpriteImageMgr`; `SetCityScheme` does that with `vt+0x28` (`0x10005fff`), a
   `[DBSegments]` row does not. Placing the copy under `Apps\Res\Sprites\` puts it in the startup `*.DAT` listing
   (NETPACK arm F). **Unproven:** whether a top-level listed DAT also serves its `BIN\r` records to the resource
   manager [UNCERTAIN]; netpack used a separate `CSAttrib_Korea` for frames, which suggests it does not.
3. Shadow copies of the RCI families (4, 7-17, 19, 20, 22-25, 28-31) adding the new ids; weights set the mix ratio.
4. Keep the active building set at 0, or a set pick re-skins the base ids on top of the mix. The set is per city
   (§4), so this means a city saved with style 0. With a set active the mix still works, the base ids draw in that
   set's style (measured, `verify/stylemix` case 4).

Fallback if step 2 fails: hook `SetCityScheme` or `FUN_10005fff` to register the set DATs with
`RegisterDBSegmentBack` (`vt+0x64`) at startup and with the sprite image manager. Base keys keep priority, set-unique
keys still resolve.

### (B) Per-zone style chosen by the player: code needed, costliest (needs the (A) data first)

- B-lite (data only): a per-zone-type style, e.g. residential families list only Euro ids and commercial only Asian
  ids, chosen by mod ini.
- Full B: one choke point, ZoneLayer slot 26 `0x10032dfc` (or its key at `+0x24c vt+0x20`); every rule Apply ends
  there through `vt+0x68`. Swap the attrib or key for the variant of the cell's style. Safe because the variants share
  the X/Y footprint [CONFIRMED, data] and the lot layout is already done. Filter by caller or id range so plop tools
  are untouched. The choice lives in a mod-owned per-cell style grid plus a paint tool (new zone types 18-22 are
  possible through `[ZoneDeveloperDescriptions]`, but the UI, zone colours and RCI wiring for types 1-11 make that
  larger [UNCERTAIN extent]). Buildings already persist their style through their occupant key; only the paint grid
  needs saving (sidecar file, or a custom section [UNCERTAIN which the loader tolerates]).

### Runtime checks that would prove each

- **C: DONE 2026-11-10** (`verify/growable/RESULTS.md`): red houses on screen, key instance 36001 in the save, reload
  with the mod passes, load without the mod drops the buildings. "Copiar ID" on a red house was not checked.
- **A: DONE 2026-11-10** (`verify/stylemix/RESULTS.md`): all 251 set buildings at once rather than one gating
  record. Copies grow, three styles in one shot with set 0, reload passes, load without the package does not crash.

## 7. Open items and the evidence missing

- ZoneLayer `+0x24c` identity: a CodeView match for its `+0x20` / `+0x58` slots.
- Plumbing `vt+0x48` and attrib `+0xbc & 0x100` meanings.
- Industrial class rows (the D / C / A token): the industrial parser was not read.
- Loader behaviour on an unresolved occupant key. stylemix measured it on a save taken while still paused: all 6,723
  style copies were replaced on load by another building of the SAME building type (t18), 942 by their own base id,
  occupant count unchanged, no other lot changed. growable (§6 C) reported its 36001 lots as empty after load, from a
  screenshot; its save 4 counts (0 of 36001, +896 family-11 stock houses after a run) fit either reading. Recheck
  growable with a paused save. The branch in `SIMGEOM 0x1001e516` / `0x10002cc2` that substitutes is not read.
- `[OccAttribCache]`: an exemplar outside it crashes the residential developer (§6 C). Open: why, and whether a new
  container with its own cache entry works.
- Whether a top-level `Res\Sprites` DAT is also a resource-manager segment (each is registered under
  `kGZCATNAME_SC3DBSegmentSprite` by `cSC3App::LoadRegistry` `0x0040b761`; stylemix avoided the question by keeping
  frame tables in `CSAttrib_Korea`).
- `cRZIniFile::EnumEntries` order: assumed to be file order for `[DBSegments]` priority.

The one-off helper scripts used (PE vtable reader, TKB1 dumper, family coverage table) were not kept in the repo.
