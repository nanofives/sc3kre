# PLOPPABLES: landmark menu, the 2000 add-on plugins, and new landmarks as data (plop, 2026-11-19)

Round 2026-11-19h, stream plop. Static reading of SC3U.exe (`re/ghidra_export/`, CodeView names), SIMINIT, SIMADV,
SIMSPR, SIMGEOM and the SYS.PAK inis (`re/data/syspak/`), plus runtime checks in `dev\plop\tree` (verify/plop/RESULTS.md).
Every claim carries an address, a measurement or `[UNCERTAIN]`.

**Verdict.** Landmarks are data only. SC3U still loads Maxis' 2000 add-on plugins (.pin + .dat) by itself from
`Apps\PlugIn\`, lists their buildings in the stock landmark dialog and places, saves and reloads them. It does not draw
their art: the 2000 pixel records use LZO1X, which SC3U's sprite decoder dropped. Converting those records to SC3U's
QFS records fixes that (`re/tools/bldimport/sc3plugin.py`). A new landmark of ours is the same kind of plugin
(`bldimport.py` kind `landmark`). Civic buildings and rewards do not take this path (section 6).

## 1. Where SC3U looks for plugins

| step | code | what it does |
|---|---|---|
| plugin root | SC3U.exe `cGZFileSystem::PlugInDirectory` `0x00482532` | reads `[Directories] PlugIn=` from `<AppDirectory><AppName>.ini` (= `Apps\SC3U.ini`), keeps it at `this+0x6c`; when empty, the AppDirectory (vt+0x10). GOG's `SC3U.ini` has no `[Directories]` section, so the root is `Apps\` [CONFIRMED by data] |
| manager init | SIMINIT `sc3_schememgr_init` `0x1000583e` | creates class `0x852beaa1` / interface `0xa52bea7e` (cISC3PluginBuildingMgr) and calls its Init (vt+0xc) with `FS->PlugInDirectory()` (vt+0x20) + `"PlugIn\"` (`0x10037368`) |
| Init | SIMINIT `0x1000ec52` | stores the path at `this+8` (vt+0x24), then CheckForPluginBuildings(false) (vt+0x14) |
| scan | SIMINIT `sc3_pluginbuildingmgr_check_for_plugin_buildings` `0x1000ea2a` | `cRZDirectory` on `this+8`, filter `"*.pin"` (`0x10037554`), `ReadDirectorySpecificEntriesIntoStringListRecursive`: every .pin at any depth, then `0x1000e8d1` per file |
| one .pin | SIMINIT `0x1000e8d1` | `cRZIniFile` on the .pin, `EnumEntries` of `[DBSegments]` -> `0x1000ec96`, `[OccupantKeys]` -> `0x1000edfb`, `[SpriteSegments]` -> `0x1000eeef` |
| `[DBSegments]` | SIMINIT `0x1000ec96` | key -> `ConvertToUint32`; value split at `;`: class id (`0x80C381D7`) + path; creates that class with interface `0xc019963e`, Init(key, path) (vt+0xc), open (vt+0x1c(1,0)), registers it with the resource manager (vt+0x5c) |
| `%PluginDirectory%` | SC3U.exe `cGZDBSegmentIndexedFile::Init` `0x00464368` | finds the token and rebuilds the path with `RZ::FS()->PlugInDirectory()` (vt+0x20) |
| `[SpriteSegments]` | SIMINIT `0x1000eeef` | builds `FS vt+0x20 + "Plugin\" + <key> + "\"`, lists `*.DAT` there and registers each file (sprite manager vt+0x28) |
| `[OccupantKeys]` | SIMINIT `0x1000edfb` / `0x1000ee62` | with the scan flag false (startup): registers the entry in registry category `"sc3occattrib"` (vt+0x18, vt+0xc); with the flag true: parses `0x%x,0x%x,0x%x` into a key list at `this+0x28` |

Measured (memory scan of the running game, PID 3688): with `LandmarkPack1\LandmarkPack1.pin/.dat` and
`LandmarkPack2\...` copied into `dev\plop\tree\Apps\PlugIn\`, the game holds the strings
`...\Apps\PlugIn\LandmarkPack1\LandmarkPack1.dat`, `...\Apps\PlugIn\LandmarkPack1\LandmarkPack1.pin` and
`...\Apps\Plugin\LandmarkPack2\*.DAT`. So `%PluginDirectory%` expands to `Apps\PlugIn\`, and the sprite path is the same
folder (Windows paths ignore case). [CONFIRMED, runtime]

`MaxisAddOn.dll`: GOG ships the 2.0.949 build in `Apps\` (28,672 bytes, sha256 `1f5c73b4...`). The 1999 installer's
copy (45,568 bytes, sha256 `cad237dd...`) is the 1999 game's plugin loader (it imports
`GetPrivateProfileSectionA` / `FindFirstFileA`); SC3U does that work in SIMINIT, so the installer is not needed. What the
2.0.949 MaxisAddOn.dll still does was not read [UNCERTAIN].

## 2. The landmark menu

| item | code / data |
|---|---|
| menu entry | `MenuItem.INI` `0x10006008` "Landmarks" = `COMM 0xE2ED3560, 0x22e92581`, button `Root\Special\Landmarks` |
| the dialog | SIMUI catalog picker `0x10067620` (`Select a Landmark Building`, `SIMUI.md`), shown in Spanish as "Elige un Edificio Destacado" |
| the list | SIMADV `0x10008ef2`: iterates every occupant exemplar (attrib manager vt+0x2c, iterator vt+0x10) and keeps those whose type (vt+0x50) IsA 18000 (`type hierarchy vt+0x24(18000, type)`); per entry a 0x60-byte record with the key (vt+0x14), two flags (+0x40/+0x44) and the name |
| the types | `CitySim.ini [AgentTypeHierarchy]`: 18001..18045 = 18000 ("Landmarks"); the type is the exemplar's prop 0x65 |
| line 2 of the entry | the exemplar's prop 0x7C, a text key (`SIMGEOM_PROPERTIES.md`: catalog string table `0x62e69238`); stock landmarks hold their place there ("San Francisco, California USA" is instance 0x64) |
| one per city | placed entries are greyed and show "Ya existente"; SIMADV insert / remove handlers `0x1000b32a` / `0x1000b458` set the placed flag (`RELOCATE.md`) |

So any exemplar of type 18000..18045 that the game has loaded is in the dialog, at the end of the list for plugin
exemplars (loaded last). Measured: the five pack landmarks and our two test landmarks are the last seven rows.

The tool: OK in the dialog starts the game's building tool for that key (`RELOCATE.md`: SIMGEOM building layer, site
check `0x100072f6` / `0x100076b4`, commit `0x10007760`; sc3resize's RELOCATE log line "building placement (kind 0) ...
placed" is that commit). Landmarks cost nothing to place (price 0 in the log for flat land, 5 / 120 for clearing).

## 3. Why the 2000 art does not draw

A 2000 pixel record (type 0, group `0x43B843E2` in Landmark Pack 1):

```
+0x00 0x107 (format 1, decoder arg 7)   +0x04 0x00008000   +0x08 width   +0x0C height
+0x10 decoded length                    +0x14 len(record) - 0x10        +0x18 LZO1X-1 stream (ends 11 00 00)
```

SC3U's SIMSPR `sc3spr_decode_record` `0x1001de49` decodes format 1 only when `(dword1 & 0x8000) == 0 &&
(dword1 & 0x80000) != 0` (QFS). The 2000 records have 0x8000 set, so they fall through without pixels. The raw
dispatcher `sc3spr_dispatch_pixel_format` `0x1001e086` has the cases `0x8000` and `0xC000`, and both call
`0x1004efdd`, which is `return 0`. [CONFIRMED @ 0x1001de49, 0x1001e086, 0x1004efdd]. In game, MOMA (9505) placed from
the unconverted pack showed a pale blue grid on its 4x4 lot and the no-power bolt, no building (owner_shots/02).

The stream format was found against a known plaintext: the pack's Palace of Fine Arts (instance 9510) is also stock in
SC3U (`552D8025_Landmarks_2.DAT`), and each pack record's decoded length equals the stock record's QFS-decoded block.
Literal runs `n+3` (bytes 1..15), `00 n` = `n+18`, 2-byte matches for bytes 0x40-0xFF (length `(b0>>5)+1`, distance
`((b1<<3)|((b0>>2)&7))+1`, `b0&3` trailing literals), 3-byte matches for 0x20-0x3F and the `11 00 00` end marker: this
is LZO1X-1. With a full LZO1X decoder all 80 pixel records of both packs decode to their stated length using the whole
stream, and all 16 Palace frames are byte-identical to SC3U's stock blocks. Re-encoded with the QFS encoder bldimport
uses (`qfs_encode.compress_stream`, quick 1), the 16 Palace records are byte-identical to SC3U's own records.
[CONFIRMED, data] SC3U.exe `cRZFastCompression2` (`0x0046b208`) is RefPack (`decoderef`), not this.

## 4. What the packs hold

| pack | exemplars (type 0x207EDC0E) | group | prop 0x65 | lot (prop 0x66 x) |
|---|---|---|---|---|
| Landmark Pack 1 | 9505 Museum Of Modern Art, 9506 Transamerica Tower, 9510 Palace Of Fine Arts | `0x43B843E4` | 18040 San Francisco | 4x4 each |
| Landmark Pack 2 | 9569 NY Public Library, 9517 Guggenheim | `0x53E119D5` | 18036 New York | 4x4, 5x5 |

Names are text records in the same .dat (prop 0x6D: groups `0x43B843E5` / `0x53E119D6`), frame tables 0x6300 (groups
`0x43B843E3` / `0x53E119D4`) with 20 entries (16 frames, 12..15 repeated with flag 2, as stock landmarks), pixels
groups `0x43B843E2` / `0x53E119D3`. Only 9510 is also in SC3U; the four others are new to SC3U players. A save stores the full key
(`{0x207EDC0E, 0x43B843E4, 9505}`, type 18040), so the pack's 9510 and the stock 9510 are different buildings.

## 5. A new landmark as data (bldimport kind `landmark`)

`Apps\PlugIn\bldimport\bldimport.pin` + `bldimport.dat`, the packs' layout:

```
[Admin]            Enabled=ON
[DBSegments]       0x00000001=0x80C381D7;%PluginDirectory%bldimport\bldimport.dat
[SpriteSegments]   bldimport=addon-enabled
[OccupantKeys]     0x207EDC0E,0xB1D10002,0x00009470=38000 Test obelisk   (one line per landmark)
```

Per landmark in the .dat: the exemplar `{0x207EDC0E, 0xB1D10002, id}` = the first stock landmark by id with that square
lot (1x1 Big Ben 9543, 2x2 Coit Tower 9507, 3x3 Arc de Triomphe 9528, 4x4 Palace of Fine Arts 9510) with prop 0x65 =
18000, 0x64 = the name, 0x6D -> `{0x2026960B, 0xB1D10004, id}` (name), 0x7C -> `{0x2026960B, 0xB1D10005, id}` (the
entry's `description`, else the name), 0x67 -> `{0x6300, 0xB1D10003, id}` (20-entry frame table), and the 40 pixel /
anchor records `(0xB1D10001, id << 16 | frame)` bldimport renders for every building. No overlay file, so no road mod
is needed: the plugin is stock game data. Both Maxis packs use `[DBSegments]` key 1 and load side by side, so ours uses
1 too.

Measured (verify/plop/RESULTS.md): both test landmarks in the dialog with their own preview, placed (2x2 at (177, 207),
3x3 at (175, 209)), drawn at zoom 3 and 4 in all four view rotations, saved (keys and type 18000 in the save), reloaded,
greyed as "Ya existente" after the reload. Loaded with no plugin installed: no crash, the landmarks are gone (no
occupant on their cells) and their lots show orange-brown ground.

## 6. Civic buildings and rewards: not this path

- **Civic** (police, fire, hospital, school, parks): each building is its own menu entry with its own command in
  `MenuItem.INI` (`0x10006201` Police Station `COMM 0x42ff052f`, `0x10006401` Hospital `0xe2ff0555`, `0x10006402` School
  `0xc2ff0563`, `0x10006601` Small Park `0x02ff05aa`, ...). A new civic building needs a new entry and a command the game
  turns into a building tool: mod code. Not built (brief: describe and stop). The RELOCATE tool factory (building layer
  +0x70 / +0x54, `RELOCATE.md`) is the call such a command would make. Which stats a civic copy needs to work as its base
  (coverage radius, budget slot) was not read [UNCERTAIN].
- **Rewards** (Rewards & Opportunities, catalog mode `0x62e92553`): the list is `Advisor-CityPlanner.ini
  [REWARD_BUILDINGS]`, type id = cost; year; ?; ? per line, and `[REWARD_BUILDINGS_2]` holds per-reward thresholds by
  name. The SIMADV reward advisor (`RELOCATE.md`: ctor `0x10017ba8`, items vtable `0x10031178`) sets "unlocked" from
  conditions per reward; whether a new type id line unlocks without code was not read [UNCERTAIN]. A new reward also
  needs a new type id in `CitySim.ini` and a SYS.PAK edit (an overlay SYS.PAK, the netmod route). Not built.
- **Power / water / garbage catalogs** use the same picker with modes `0x62e925a2`, `0xe2e92527`, `0xC2F291A9`;
  how those lists are built was not read [UNCERTAIN].

## 7. Open

- What GOG's 2.0.949 `MaxisAddOn.dll` does (119 functions, not read).
- `[OccupantKeys]`: what the `sc3occattrib` registry entry is used for. Our .pin carries the lines the packs carry;
  whether a landmark loads without them was not tested.
- The orange-brown lots left after loading without the plugin: whether the cells can be built on again (zone byte 22
  under civic / landmark buildings, `RELOCATE.md` 1) was not tested.
- Landmarks 5x5 (78 stock landmarks are 5x5): bldimport offers 1x1 to 4x4 because its renderer and lot checks stop at 4.
