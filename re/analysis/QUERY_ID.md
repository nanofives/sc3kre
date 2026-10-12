# "Copiar ID" in the query (?) dialog (sc3resize QUERYID, task queryid 2026-10-12)

Owner request 2026-10-12: "necesito modificar el juego en profundidad para agregar tipos de caminos, más diseños, tipos
de conexiones y texturas que no están, pero para eso me gustaría señalar con ID el elemento que quiero trabajar,
podemos implementar un botón en el menú de '?' para que copie el ID de lo seleccionado?"

What it does: every query dialog ("Indagar") gets a "Copiar ID" button ("Copy ID" on an English install) on its bottom
row, left of the game's check button. One click puts a labelled text block on the Windows clipboard (CF_TEXT and
CF_UNICODETEXT) and writes the same block to `sc3resize.log`. The dialog stays open. `SC3RESIZE_QUERYID=0`: no detour,
no button, stock dialog.

Evidence: `verify/queryid/PRE.md` (pre-registration) and `verify/queryid/RESULTS.md`. Checker:
`py -3.12 re/tools/query_id_check.py <city.sc3> --clip` compares the block on the clipboard with a save.

## 1. The query dialog, as read for this task

| fact | value |
|---|---|
| class | SIMUI ctor `FUN_10061f53` (0x118 bytes), allocated by `FUN_1006ace3`; vtables `0x100aadc8`, and `0x100aadb8` at `+4` |
| open on an occupant | `FUN_10062cee(occ, mode)`: `+0xd8` = occ (AddRef), occ `vt+0xb8` GetLocation fills `+0xdc` `[CONFIRMED @ SIMUI 0x10062cee]` |
| open on a point | `FUN_10062cba(coord, mode)`: `+0xd8` = 0, coord copied to `+0xdc..+0xe4` `[CONFIRMED @ SIMUI 0x10062cba]` |
| coord | `+0xdc` x, `+0xe0` z, `+0xe4` altitude, each `cell << 8`; the dialog reads cell = `>> 8` `[CONFIRMED @ SIMUI 0x1006255a]`, altitude matched the occupant altitude in every sample |
| mode | `+0x14`: 1 = 308x280, 2 = 308x395, 3 = 423x320 `[CONFIRMED @ SIMUI 0x100621d8]`; network pieces open with 0 (measured) |
| message handler | slot 3 of the `+4` vtable, `FUN_1006338f`, `ret 0x14`, the only reference to it in SIMUI is `0x100aadc4` |
| content build | message `0xa2bf8ace` -> `FUN_100634a6` |
| button clicks | message 3, p3 = 1 (p3 2 = press, 17 follows), p4 = button id; 0 and 4 are the game's, `0x42b7c353` the close box `[CONFIRMED @ SIMUI 0x1006338f]` |
| the game's OK | factory image button id 0, placed at `(w - 0x32, h - 0x25)` `[CONFIRMED @ SIMUI 0x1006260e]`, measured `[258 358 300 390]` at 308x395 |

### The button

The game's own text-button recipe `[CONFIRMED @ SIMUI 0x1003f16b, 0x1003f900, 0x1003a303]`: widget factory
(`FUN_10085065`) `+0x2c(id, str, 0, 0, 0)`, button `+0x24(4, 1)` and `+0x24(0x20, 0)`, caption = window `vt+0x10c(str)`
(as GZWIND's message-box buttons set theirs, `GZWIND 0x100150aa`), rect = window `vt+0xc8` (parent-local), window
`vt+0xf4(2, 1)`, dialog `vt+0x34` AddChild. Id `0x02F95B50` (no hit in the SIMUI or GZWIND exports).

Two dead ends, measured: factory `+0x30` is the image button, and with no image it draws an empty pill with no caption,
font and colour calls included. Window `vt+0xc0` does not resize that class.

Placement: bottom row, right edge 8 px left of the OK button, 92x33. Measured child rects in the first dialog of each
mode are in `RESULTS.md`.

## 2. The block, line by line

Lines appear only when they apply (no `object.*` without an occupant, `network.*` only on network pieces). Keys are
stable English labels so the block can be parsed. A `?` after a key marks a value read through a slot whose meaning
is not yet confirmed.

| line | source | status |
|---|---|---|
| `cell: x= z= alt=` | query coord `>> 8` | x, z `[CONFIRMED @ 0x1006255a]`; equal to the save's occupant and network position in every sample |
| `zone:` | city `vt+0x14c` ZoneLayer, `vt+0x34` GetValue(x, z, &byte) (the call `FUN_1006255a` makes) | 12/12 against the save, name from the zone-tool table (`LAUNCH_CONTROL.md`); 22 = plopped building, no name |
| `terrain.water:` | city `vt+0x13c` DirtBag, `vt+0x54` IsWater(x, z) (the call `FUN_1006255a` makes) | 1 on two water cells, 0 on every dry one |
| `terrain.corner_alt:` | DirtBag `vt+0x48` at vertices (x,z) (x+1,z) (x,z+1) (x+1,z+1) | dry corners equal the save's terrain grid, all 112 sampled; on water it reads the water surface |
| `terrain.ground_alt:` | DirtBag `vt+0x4c`, same four vertices | equals the save's ground grid on water too (21 22 24 25 under a 30 surface) |
| `object.name:` | occupant `vt+0x7c` GetName into SIMUI's string class, `vt+0x14` ToChar | the dialog's own title in every sample |
| `object.type_id:` | occupant `vt+0x88` TypeId | = save occupant record `+8` (the `[AgentTypes]` id) on every building; 12810 water pump, 12111 coal plant; 16000 road, 16001 highway = the network factory ids of `NETWORK_TYPES.md` |
| `object.key:` | the key block 0x10 before the pointer in the occupant's first field | = save record `+12` key on every building, including an abandoned one; for a network piece = `{0xE223741F, 0xA317745F, piece id}`, the exemplar key `[CONFIRMED @ SIMNTWRK 0x1000c80b]` |
| `object.attrib_key:` | occupant `vt+0x80` GetAttribData, attrib `vt+0x14` Key | the attrib in use now. Differs from `object.key` when the building is abandoned (`0xA4` Industrial Lab vs `0xAD` Abandoned Industrial Building, `Occupant.ini`) |
| `attrib.type_id:` | attrib `vt+0x50` TypeId | = `object.type_id` except on the abandoned building (15100) |
| `object.cell:` | occupant `vt+0xbc` GetLocationInCellCoords, `vt+0xc0` GetAlt | = save record position bits on every building |
| `object.size: AxB height=H` | occupant `vt+0xd4` / `vt+0xd8` / `vt+0xdc` | AxB = save record footprint; coal plant 4x4 height 5 = its OccupantAttribs prop `0x66` (4, 5, 4) |
| `object.rotation:` | occupant `vt+0xb4` (the 2-bit index getter, `NETWORK_RULE_ENGINE.md` 11.4) | = save record bits 30-31 |
| `object.class:` | the occupant's vtable as module + RVA | a pointer read. SIMGEOM `+0x2BBE8` and `+0x2A578` buildings, `+0x29BCC` flora; SIMUTIL `+0x20A68` coal plant; SIMNTWRK `+0x2B5DC` (kind 1, road) and `+0x2ABD4` (kind 5, road + rail crossing), the 22 kinds of `NETWORK_RULE_ENGINE.md` 11.2 |
| `object.packed:` | occupant `+0x10` | x bits 0-10, z 11-21, altitude 22-29, rotation 30-31: = the save record word on every building, = the save network word0 on every piece |
| `attrib.clsid?:` | attrib `vt+0x0c` GetOccupantGZCLSID | raw, not checked against anything (0x62B9DA80 on buildings, 0 on pieces) |
| `network.piece_id:` | piece (`occupant - 4`) `+0x18` low 16 bits `[CONFIRMED @ SIMNTWRK 0x1000c80b]` | = save tile piece id |
| `network.sets:` | which `TilingRules\<NET>_GRND_Set.txt` id lists hold the id (SIMNTWRK globals `0x10032348..5c`) | road 29 ROAD, rail 44 RAIL, highway 11223 HWAY, power 10033 POWR, level crossing 69 ROAD RAIL, 15098 ROAD HWAY |
| `network.state:` | piece `+0x14` bits 30-31 (quarter turns, `NETWORK_RULE_ENGINE.md` 13) | part of word0, matches the save |
| `network.tile:` | piece `+0x14` x / y / z | = `cell` and the save tile |
| `network.trblkatt_key:` | `{0x625C6226, 0x825C6289, id * 0x100 + state}`, the key `FUN_1000d225` loads `[CONFIRMED @ SIMNTWRK 0x1000d225]` | a TrBlkAtt.IXF exemplar (`NETWORK_RULE_ENGINE.md` 13.7) |
| `network.words:` | piece `+0x14`, `+0x18` raw | word0 = save word0. word1 high half is NOT the save's (runtime 0, save 0x3000 on Berlin roads): the saver writes a layer-side record, `SIMNTWRK 0x1000d594` |
| `query.mode:`, `query.coord:` | dialog fields | raw, for debugging |

Which SIMNTWRK list is which network: `FUN_10016d87` opens `ROAD/HWAY/RAIL/SUBW/PIPE/POWR/DIAG_Set.txt` into stream
objects and feeds them to the list filler `FUN_1001746e` in the order `0x10032348` ROAD, `4c` HWAY, `50` RAIL, `54` SUBW,
`5c` POWR, `58` PIPE, `60` DIAG `[CONFIRMED @ SIMNTWRK 0x1001726e..0x10017312, disassembly]`. Each entry is the 12-byte key
`{0xE223741F, 0xA317745F, id}` (`0x1001746e` builds it). The six predicates `+0x11c..+0x130` of vtable `0x1002c7bc`
scan `48 / 4c / 50 / 54 / 58 / 5c`.

## 3. From an ID to the file you edit

| you want to change | take | then |
|---|---|---|
| a building's art | `object.key` | its instance names the object in `Occupant.ini` / `OccupantAttribs*.IXF`; `py -3.12 re/tools/sprite_patch.py Apps/Res/Sprites --find-art "<object.name in English>"` or `--objects --object <instance>` (`formats/SPRITE_MODDING.md`). Coal plant `0xCF` is the worked example there |
| a building's type (sim behaviour) | `object.type_id` | `[AgentTypes]` in SYS.PAK (`formats/SYSPAK.md`) |
| which road/rail piece a junction uses | `network.piece_id` + `network.sets` | the `<NET>_GRND_*Rules.txt` RESULT lines, `re/tools/tilingrules.py` (`formats/TILINGRULES_MODDING.md`) |
| a piece's art | `network.piece_id` -> `object.key` exemplar | piece id -> exemplar -> sprite (`TILINGRULES_MODDING.md`, reskin lever) |
| a placed tile in one save | `network.tile` + `network.words` word0 | `re/tools/network_layer.py` NetworkEditor, save instance 1 (surface) |
| zone or terrain in one save | `cell` | see section 4 for the save indexing |

Not read live: the sprite record ids (group/instance of the pixels) of a building. The occupant's sprite interface is
not in the SDK headers and was not decoded; the offline chain key -> attrib table -> frames is exact (`SPRITE_MODDING.md`).

## 4. Findings about the save made on the way (outside the button, they affect other tools)

1. **The zone raster is not indexed in the game's cell frame.** Game cell (x, z) is byte `(N-1-x)*N + z`, i.e.
   `city_write.City.zone_get(z, N-1-x)`. 12 of 12 live readings fit; no other of the 8 axis orders fits more than 3.
   `city_write.zone_get(x, y)` reads `y*N + x`, so a tool that uses one shared (x, y) for zones and for network/occupant
   positions rotates the zones against them.
2. **The terrain corner grid A (`city_flatten.py`) is indexed the same way:** vertex (x, z) is row `N - x`, column `z`
   of the (N+1)x(N+1) grid. All 112 sampled dry corners match, including a slope (33 32 32 32); no other order passes
   107. This settles `city_flatten.py`'s `[UNCERTAIN]` corner alignment (it did not try a flipped row).
3. **Save network instance 2 is PIPE, not rail.** Every piece id in instance 2 of six shipped cities is in
   `PIPE_GRND_Set.txt` only; instance 1 holds road, highway, rail and power line together; instance 3 is SUBW.
   `network_layer.py` calls instance 2 "rail" (its Farmsville "rail 545" are pipes).
4. Berlin's piece 11204 is named "Avenida" in game (ROAD set), a road piece, not a separate network.

## 5. Samples (stock DLLs, Berlin, final build)

Road, straight piece:

```
SC3 query id v1
cell: x=77 z=116 alt=32
zone: 0 (none)
terrain.water: 0
terrain.corner_alt: 32 32 32 32
terrain.ground_alt: 32 32 32 32
object.name: Carretera
object.type_id: 16000
object.key: 0xE223741F 0xA317745F 0x0000001D
object.attrib_key: 0xE223741F 0xA317745F 0x0000001D
attrib.type_id: 16000
object.cell: x=77 z=116 alt=32
object.size: 1x1 height=1
object.rotation: 0
object.class: SIMNTWRK.DLL+0x2B5DC
object.packed: 0x0803A04D
attrib.clsid?: 0x00000000
network.piece_id: 29
network.sets: ROAD
network.state: 0
network.tile: x=77 y=116 z=32
network.trblkatt_key: 0x625C6226 0x825C6289 0x00001D00
network.words: 0x0803A04D 0x0000001D
query.mode: 0
query.coord: 0x00004D00 0x00007400 0x00002000
```

Building, coal power plant (object `0xCF`, the `SPRITE_MODDING.md` worked example):

```
SC3 query id v1
cell: x=59 z=222 alt=32
zone: 0 (none)
terrain.water: 0
terrain.corner_alt: 32 32 32 32
terrain.ground_alt: 32 32 32 32
object.name: Central Térmica de Carbón
object.type_id: 12111
object.key: 0x207EDC0E 0x0000057E 0x000000CF
object.attrib_key: 0x207EDC0E 0x0000057E 0x000000CF
attrib.type_id: 12111
object.cell: x=59 z=222 alt=32
object.size: 4x4 height=5
object.rotation: 0
object.class: SIMUTIL.DLL+0x20A68
object.packed: 0x0806F03B
attrib.clsid?: 0x814A0FBD
query.mode: 2
query.coord: 0x00003B00 0x0000DE00 0x00002000
```

## 6. Code

`re/harness/src/sc3resize.c`, block `QUERYID` after `ho_install`: `qi_install` (detour on SIMUI `0x1006338f`, prologue
`55 8b ec 56 8b f1` checked first, through HUDOPT's `ho_hook`), `qi_msg` (after the build message adds the button; on
our id with p3 1 copies and returns handled), `qi_add_button`, `qi_build`, `qi_copy`. Every virtual call in `qi_build`
is inside `__try`. Not covered by a test: pipes and subway (underground view), 1024 cities, an English install.
