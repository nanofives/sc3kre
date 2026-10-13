# Highways, bridges and crossings as moddable data (netmod framework step 4a, task netbridge, 2026-10-13)

**Status: game-proven on stock DLLs** (`verify/netbridge/RESULTS.md`, PRE `fefa46d`). A variant of a highway piece is
placed by the rules, crossed by road and rail exactly like its base, and saved stock-safe. A package can add a new
bridge style (its own piece ids and art, chosen by a Bridges record it inserts), and give a variant its own crossing
art. One thing was not measurable: highway traffic, because the per-cell traffic grids hold 0 on highway tiles in every
shipped save.

Files: `re/tools/netmod/netpack_bridges.py` (inheritance, `replace_base`, Bridges and Collapse files, crossings, used by
`netpack.py`), `re/harness/src/sc3netmod_bridge.c` (INHERIT + XCROSS, included by `sc3netmod.c`),
`re/tools/netmod/nb_drive.py` and `nb_map.py` (in-game driving without the mouse), examples `example_hway_variant`,
`example_bridge_style`, `example_blue_crossing`. SIMNTWRK.DLL, image base 0x10000000, Ghidra VAs.

## 1. A variant inherits its base: data first, then the DLL

`NETVARIANT.md` gave a road variant its base's crossings and save behaviour. A variant of any network piece needs
more. Most of it is data, so netpack writes it at install (`"inherit"`, default true):

| what the game reads by piece id | where | inheritance |
|---|---|---|
| piece class (one of 22) | the six `<NET>_GRND_Set.txt` lists, `FUN_1001a5f2` | the variant joins EVERY Set that holds the base, and `DIAG_Set.txt`. Crossing 69 is in ROAD and RAIL, so its variant gets the ROAD+RAIL class only this way |
| kept out of re-tiling and clearing | `<NET>_GRND_Protected.txt`, `FUN_1001a7f7` (sites in `FUN_1001547b`, `FUN_10016327`, `FUN_100167d4`, ...) | joins every Protected list that holds the base (bridges, crossings, tunnel ends) |
| what a rule condition sees at a neighbour | `<NET>_GRND_Convert.txt` / `Complex_Convert.txt`, `FUN_1001a85a` (last matching row wins), `TILER_SIM.md` 6 | rows `(variant, s) -> what the base reads as` for s = 0..3, in every network whose Set holds the base |
| removal of multi-tile pieces | `Collapse.txt` groups, `FUN_1001da5f` | joins every group that holds the base, while the group stays within 0x1d entries (`FUN_1001da5f` returns when a count is over 0x1d); a full group is skipped with a WARNING |

Offline arm S1 (simulator, `PRE.md`): replacing a base by its variant in every rule RESULT changes only base -> variant
tiles when the Convert rows exist (highway 73 in 5 cities, rail 44, power 14, road 29: 0 other tiles), and breaks the
neighbours without them (road 29 in Berlin: 818 other tiles changed, highway 18-36 per city). In game the Berlin
retile changed exactly the 74 tiles the simulator predicted (`RESULTS.md` H1).

`"replace_base": true` on a variant generates the rule edits: every stage-rule RESULT of the variant's network that
places the base places the variant (107 rules for highway 73). Without it the package's own `rule_edits` decide where
the variant appears, as before.

What data cannot reach, `sc3netmod.dll` maps in code (block INHERIT, `SC3NETMOD_INHERIT=0` turns it off):

| code | id reads | what the variant gets |
|---|---|---|
| `FUN_10009d20` (19 calls of `FUN_10009bc7`), `FUN_1000abde` (10 calls of `FUN_1000aaba`) | highway diagonals and onramps, literals 0x49 / 0x2bfa / 0x3acb / 0x3afa / 0x3b07..0x3b0a | the base id at each call (thunks). Static only: no arm built a diagonal |
| manager vt+0x104 `FUN_1001da5f` (argument + 5 `FUN_1001a93d` sites), vt+0xfc `FUN_1001e2ea` (site 0x1001e377), vt+0xf4 `FUN_1001e3cc` (site 0x1001e454) | Collapse group walk, exact id + state for 0x3acc / 0x2bd7, the 16-id list at 0x10031f94 | the base's group and walk, whatever Collapse.txt says |

Both layers were measured alone: with the DLL mapping and no Collapse data (G1) and with the data and no mapping
(AB1), removing one tile of a variant bridge removes the whole bridge as in stock. With neither (AB0) nothing is
removed, not even the tile that was clicked: `FUN_1001da5f` returns before its walk when the id is in no group.

Not mapped on purpose: `FUN_1000de17` (road wear decorations, `NETVARIANT.md`) and `FUN_1001d761`'s ramp partner site
0x1001d96d (ramps belong to the sibling task `netramp`).

## 2. Bridges

**The path.** Drag/build is manager vt+0xf0 = `FUN_10014a23` (manager vtable 0x1002c7bc, read from the PE). For netType 1,
2, 3 it calls vt+0x144 = `FUN_1000122a`, for 4 vt+0x148 = `FUN_10002693`, when that network's Bridges vector is not empty
and the path holds more than 3 cells `[CONFIRMED @0x10014a23]`. Only ROAD, RAIL, HWAY and POWR Bridges files are loaded
(`FUN_10017f98`); `FUN_100196ce` drops the first token and pushes every other one (delimiters `" ,\n\t"`).

**Record choice.** Road / rail / power: the first record whose axis matches and whose minLen is at most the crossing
length `[CONFIRMED @0x1000122a]`. Highway: the first record whose axis key matches, 0 / 2 for the two lanes of an x
run, 3 / 1 for a z run; minLen is never read `[CONFIRMED @0x10002693]`. So file order is priority, and a package
puts its record before the stock record it should beat.

**Placement.** Every tile goes through `FUN_10008919` -> manager vt+0x48(`0xc14f8955`, id, state): the class comes from
the Sets, so a bridge piece variant must be in its base's Set (inheritance does it). The span loop compares each
span value with the 16 raw ids at 0x10031120 before calling world vt+0x15c(x, z, 1); the values are `id << 8 | state`
and the list holds bare ids, so with shipped data that call never fires (netcat's U-candidate, confirmed here from the
decompilation). The only other call of vt+0x15c on the same terrain object (manager +0x30) in SIMNTWRK is the removal's
flag-0 call in `FUN_1001e3cc`.

**Limits a package must respect** (checked by netpack and the schema): A, B, D, E at most 5 entries and C (span) at
most 20 (stack buffers copied without a bound in both builders), at least 1 each (the builders read entry 0), states
0..3, every piece in the network's merged Set, file under 0x20000 bytes (the loader's buffer).

**Measured** (`RESULTS.md`): a road across 4 water cells builds the package's red style (28051 / 20087 / 20088, the
same layout as the stock plain bridge), a road across 10 keeps the stock layered style, removal collapses as stock,
the save stores the stock ids.

**Reskinning a stock style** needs nothing new: `reskins` on its pieces (layered pieces have 40 frames,
`l1_zZ_rR.png` names for the second layer).

## 3. Crossing art for variants (XCROSS)

`FUN_100167d4` takes the matrix cell at 0x100318ac for (existing piece, new network) and decodes it with
`FUN_1002207c(value, &id, &state)` at 0x10016953; the existing occupant is `[ebp-8]` of that frame
`[CONFIRMED @0x100167d4, disassembly]`. The DLL routes that call through a thunk: when the existing piece's raw id is a
variant that a crossing table names for this crossing piece, the value becomes the package's piece, same state. The
package piece is a variant of the stock crossing, so saves keep the stock crossing and every id list treats it as one.

Only the EXISTING piece can choose the art: the new network enters the matrix as its netType, never as a piece id. So
"rail over a blue road" can be blue, "blue road dragged over an existing rail" gets the stock 69. Measured: rail across
20029 builds 20069; with `SC3NETMOD_XCROSS=0` the same drag builds 69.

## 4. Manifest

```json
"variants": [{"id": 20073, "base": 73, "network": "HWAY", "art": {"recolor": "yellow"}, "replace_base": true}],
"bridges": [{"op": "insert", "network": "ROAD", "at": 6,
             "record": {"axis": 0, "min_len": 1, "a": [[28051, 2]], "b": [[20088, 0]],
                        "span": [[20087, 0], [20088, 0]], "d": [[20088, 0]], "e": [[28051, 0]]}},
            {"op": "delete", "network": "ROAD", "record": 0, "expect": {...}}],
"crossings": [{"over": 20029, "crossing": 69, "piece": 20069}]
```

`at` / `record` are 0-based STOCK record indexes, as in `rule_edits`; all packages' edits to one file go in one pass, in
package name order. `validate` prints which record the builder picks per axis and crossing length. Crossing tables go
to `mods\netmod\cross\<package>.txt`. Selftest U8 (Bridges and Collapse round trip byte for byte, the example's record
choice, 7 refusals), U9 (highway inheritance and `replace_base`), U10 (crossing table and 2 refusals).

## 5. Open points (UNCERTAINTIES candidates)

1. Highway traffic is invisible to `transit_layer.py`: `surf_live` and `surf_snap` are 0 on every 73 tile of the 15
   shipped saves (about 2,700 tiles) while roads carry traffic. Whether highway density lives elsewhere or the grid
   index differs for highways is not known. So "routes traffic" is unproven for a highway variant.
2. Highway diagonals / onramps with a variant: thunks in place, never exercised.
3. What a crossing turns back into when one of its networks is removed (open since `NETVARIANT.md`), now also for
   variant crossings.
4. The 0x10031120 span list never matching shipped tokens (section 2): either dead code or a flag nobody sets; what
   world vt+0x15c's flag does is not traced.

## 6. Cómo añadir un estilo de puente (guía para el dueño)

1. Elegir el puente de origen. `py -3.12 re/tools/netmod/netcat.py list --name bridge` muestra las piezas y
   `netcat.py tables` los registros de `ROAD_GRND_Bridges.txt` con sus piezas (rampas A/E, relleno B/D, tramo C).
   Ejemplo: el puente simple usa 87 y 88 en x, 11265 y 11271 en z, rampas 18051 y 18050.
2. Crear el paquete con una variante por pieza: `netpack.py new mi_puente --id 20087 --base 87` y añadir a mano las
   demás piezas en `variants` (ids libres entre 1 y 65535, sin exemplar propio). Arte: `"art": {"recolor": "red"}` para
   probar, o `netpack.py export-art 87 carpeta`, pintar los PNG sin cambiar su tamaño y poner `"png_dir"`. Los puentes
   colgantes tienen dos capas: los PNG de la segunda se llaman `l1_zZ_rR.png`.
3. Añadir el registro en `bridges`: `"op": "insert"`, la red (`ROAD`, `RAIL`, `HWAY` o `POWR`), `"at"` = el número del
   registro de serie delante del cual va, y `record` con `axis` (0 = a lo largo de x, 1 = de z; en autopista 0..3, un
   registro por carril), `min_len` y las cinco listas de `[pieza, estado]`. El juego toma el primer registro del eje
   que cumpla `min_len <= largo del cruce`, así que el orden decide. Límites: hasta 5 piezas en a, b, d, e y hasta 20
   en span.
4. `netpack.py validate mi_puente` dice qué registro gana para cada largo de cruce y avisa de cualquier límite roto.
5. `netpack.py install mi_puente --tree <juego>` y jugar con `sc3netmod.dll` (probado así). Sin la DLL (modo
   `--mode direct`) no se probó en el juego, y en ese modo las partidas guardadas no son seguras para un juego sin
   el mod (`NEW_PIECE.md` 4).
6. Para cambiar solo el aspecto de un puente de serie no hace falta nada de esto: basta un `reskins` sobre sus piezas.
