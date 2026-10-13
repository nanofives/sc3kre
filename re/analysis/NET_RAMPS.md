# On-ramps, interchanges, tunnels and slope pieces (netmod step 4b, task netramp, 2026-10-13)

**Status: decoded, moddable, game-proven on stock DLLs** (`verify/netramp/RESULTS.md`, PRE `verify/netramp/PRE.md`).
SIMNTWRK.DLL, image base 0x10000000, Ghidra VAs. Tools: `re/tools/netmod/netramp.py` (registry, manifest section,
validation, simulator), `netpack.py` (wiring), `re/harness/src/sc3netmod.c` NETRAMP block. Fixture package:
`re/tools/netmod/examples/example_ramp_variant`.

Owner intent: a framework to add interactions and variants to highways, roads and rails. The green on-ramp is a test
fixture, not content.

## 1. Who builds what (corrects the 2026-10-12 capability map)

| piece family | ids | placed by | evidence |
|---|---|---|---|
| highway on-ramp (straight strip) | 15130..15141 | **the On-ramp tool**: netmgr vt+0xac `FUN_1000abde`, ids are imm32 operands in its code | live: called from SIMNTWRK `0x1000fa84` (tool helper, selection object vtable `0x1002c184`) <- SIMSPR `+0x495bb`; menu command `0x10004302` "Onramps" (MenuItem.INI) |
| on-ramp corner pieces | 15123..15128 | the same function, L-shaped selection (corner case); also RESULTs of HWAY rules | code `0x1000b8bd..0x1000b920`; not built live |
| interchange / merge pieces | 15107..15122, 15145..15148 | **HWAY tiling rules**, run by the tool's retile right after the strip is placed | live: the lane beside the strip becomes 15120/15116/15147 (or 15119/15115/15148) |
| On Ramp Intersection (road side) | 15045, 15046, 15047 | **ROAD tiling rules**, same retile | live: the road cell becomes 15046 / 15045, 15047 with a strip on both sides |
| tunnel entrances | 63/64, 18019/18024, 18027..18030, 18088..18091 | **tunnel builders** `FUN_1001c102` (road/rail, netType 1/2) and `FUN_1001ca1a` (highway, netType 4), from the drag path | live: a road drag calls `FUN_1001c102` from `0x10014fa9`, a highway drag `FUN_1001ca1a` from `0x10014f1c` (both returned 0 on flat land) |
| slope pieces | per network, `netramp.py tables` | `FUN_1001a2c0`, the slope pass of `FUN_1001547b` | `[CONFIRMED @ 0x1001a2c0]`, reproduced by tiler.py (TILER_SIM.md) |

The capability map called `0x1001ca1a` the "onramp builder" and `0x1001c102` the "slope-ramp builder". Both are
tunnel builders. Both read terrain corner heights (terrain vt+0x48) of the entry cells and refuse unless a corner
height expression reaches 7 (`0x1001ca1a`, two expressions of the form `(h1 - h0) * 2 - h2 + h3`) or 4
(`0x1001c102`); then walk forward while the lowest corner of the next cells stays at least entry + 8 (highway) /
entry + 4 (road, rail); refuse a run under 3 cells; charge `price(0x3e86) x length x 2` (highway) or
`price(0x3e86) x (length - 1)` (road, rail) through `this vt+0x140(0x253, cost)` (refusal message 0x284); and place
the entrance pieces from the tables at `0x10031fd8..0x10032028` through `FUN_10009613` / `FUN_10008919`
`[CONFIRMED @ 0x1001ca1a, 0x1001c102]`. The removal side `FUN_1001d761` compares ids against the same tables.

### 1.1 The On-ramp tool, step by step

1. **Hover.** The tool helper (`0x1000f72c`) calls selection vt+0x38 = `FUN_10009d20` with the cursor cell. It tries
   the cell and its four neighbours, each along both axes: three cells in a row that are empty (or flora,
   `FUN_10009c65`: occupant major type 5), the three lane cells beside them hold the straight highway (0x49 for a
   strip along z, 0x3acb along x) at one height, the lane cell past one end holds the highway or its crossing
   (0x2bfa / 0x3afa), a cell past an end passes the predicate held at helper +0x40 (`FUN_10009cc5`, which predicate
   is not identified), and two more calls succeed (`FUN_10021b24()` vt+0x13c then vt+0xfc, and vt+0x194 then
   vt+0x50; not decoded). Found: the three cells become the selection; not found: the cursor cell alone. The cost preview is netmgr vt+0x90 `FUN_100145aa` = points x price of agent type
   0x4332 (17202 OffRamp) `[CONFIRMED @ 0x10014678]`.
2. **Click.** netmgr vt+0xac `FUN_1000abde(sel, &cost)`: funds check, reads up to 5 points (sel vt+0xc), needs
   exactly 3. Straight case below; three points not in one line take the corner case.
3. **Straight case.** The two outer points are ordered by the swap at `0x1000add5` (swap when p1.x < p2.x or
   p2.z < p1.z), so `d0` is the larger-x end of an x-strip but the SMALLER-z end of a z-strip. Highway side: the lane
   one step across holds the straight highway (`local_29`: -x for a z-strip, +z for an x-strip; else `local_2a`, the
   other side), with equal heights. Road end: `local_12` if the lane cell past `d0` holds the highway or its road
   crossing (0x2bfa / 0x3afa), the lane cell past the other end holds the plain highway, and `FUN_1000ab5b` (road
   predicate `DAT_100323c0`, not Protected) accepts the cell past `d0`; else `local_13`, the same test from the other
   end `[CONFIRMED @ 0x1000b4b8..0x1000b5a2]` (lane reads `FUN_1000aaba`, road tests `FUN_1000ab5b` at
   `0x1000b514` / `0x1000b5a2`). A strip with a crossing past both ends fails both.
4. **Pieces.** 8 cases x 3 slots = the 24 `onramp` table slots (section 2), placed with `FUN_10008919`
   (`[ebp+8]` at `d0`, `[ebp-0x1c]` at the middle, `[ebp-0x20]` at the other end; calls `0x1000b81e`,
   `0x1000b834`, `0x1000bb65`).
5. **Retile.** `FUN_10016a25` + `FUN_1001547b` for HWAY (netType 4) then ROAD (netType 1) over the strip's box
   (`0x1000bc46` / `0x1000bc6d`, then `0x1000bc95` / `0x1000bcbb`). The rules then make the merge pieces and the On
   Ramp Intersection.

Check: `netramp.py check-saves` predicts every straight on-ramp strip of the 16 shipped cities from step 3 and the
table: **601 of 601 strips (1,803 tiles) match**, 0 mismatch. `netramp.py build-onramp` replays steps 3-5 on a save
through `tiler.py`: from the pre-build state of the test city it gives the in-game result with **0 of 80 cells
different** (both strips, the 4 merge cells, both road cells).

### 1.2 Stock quirk: the selection point cap

`FUN_10004754` (adds a point to the selection) only adds while the global `DAT_100322a4 < 0x200` and increments it
`[CONFIRMED @ 0x10004754]`; only `FUN_1000488d` (the drag path builder) resets it to 0 `[CONFIRMED @ 0x1000488d:154]`.
Every hover adds 1 or 3 points, so after about 500 hovers the On-ramp tool selects nothing (cost $0, click does
nothing) until a road or rail drag tool is used. Measured during setup (a click with 0 points returned 0).

## 2. The tables (all `netramp.py tables`)

| table | slots | storage | read by |
|---|---:|---|---|
| `onramp` | 24 | imm32 at site+3 of `mov [ebp+d8], imm32` in `FUN_1000abde`, `0x1000b5cd..0x1000b6b0` | the On-ramp tool |
| `onramp_corner` | 12 | imm32, `0x1000b8bd..0x1000b920` | the same, corner case |
| `slope.ROAD/RAIL/SUBW/PIPE` | 8 each | `.data` u32[8] `0x1003195c/197c/199c/19bc` | `FUN_1001a2c0` only |
| `slope.POWR_line`, `slope.POWR_pole` | 8 each | `0x100319dc`, `0x100319fc` | `FUN_1001a2c0` |
| `slope.HWAY_absent`, `slope.HWAY_present` | 8 each | `0x10031a1c`, `0x10031a3c` | `FUN_1001a2c0` (probe of the side cell) |
| `tunnel.ROAD/RAIL`, `tunnel.HWAY_a..d` | 4 each | `.data` u32[4] `0x10031fd8..0x10032028` | `FUN_1001c102`, `FUN_1001ca1a`, `FUN_1001d761` |

Every value is `id << 8 | state`. Inside one table each value occurs once, so `[id, state]` names one slot; `id`
alone names every state of that piece in the table. Slot labels give the cell by coordinate (lo / mid / hi).
The `.data` tables are written in place, which keeps the builders and the removal path (`FUN_1001d761` compares
against the same tunnel tables) consistent. All tables are in `.data` (RW) except the imm32 sites (`.text`).

## 3. Making them moddable

### 3.1 Manifest section `ramps` (netpack)

```json
"ramps": [
  {"table": "onramp", "from": [15139, 0], "to": [25139, 0]},
  {"table": "onramp", "from": 15135, "to": 25135},
  {"table": "slope.ROAD", "from": 11201, "to": 21201, "slots": [1, 3]}
]
```
`to` is a variant of the merged packages whose `base` is the `from` id, or a stock piece in exactly the same Set
files. Refused: an unknown table, a value no slot holds, two packages changing one slot, a variant of another base, a
stock piece of other networks. netpack writes `ramp <table> <slot> <from> <to>` lines into the package's
`mods\netmod\tables\<package>.txt` (the variant table sc3netmod already reads).

### 3.2 What a table variant needs besides the table

- **Data** (netpack's variant inheritance, task netbridge, `"inherit"` on by default): every Set the base is in,
  its Protected lists, Convert / Complex_Convert rows (rules see the base) and its Collapse.txt groups. Without these
  the HWAY retile of step 5 deletes the strip: `build-onramp` with only the Set membership turns the three cells into
  highway pieces (15149/15051), because the variant is neither Protected nor seen as an on-ramp by the rules.
  netbridge's inheritance writes byte-identical files to what this task first wrote itself (9 TilingRules files for
  the fixture), so the in-game arms hold for either.
- **Piece class** (sc3netmod): the classifier `FUN_1001a5f2` special-cases ids 15130..15141 (kind 14 / 15 instead of
  6 / 2). The only vtable difference is the occupant flag getter (secondary vt+0x48): kind 14 `0x21c804` vs kind 6
  `0x1c804`, kind 15 `0x214804` vs kind 2 `0x14804` `[CONFIRMED @ 0x1000c5f6, 0x1000c62e, 0x1000c49e, 0x1000c33e]`.
  Flag 0x200000 is tested by SIMTRANSIT `FUN_10005983` (`vt+0x3c(0x200000)`, line 155). So the DLL hands the
  classifier the base id for every variant a `ramp` line places (calls at `0x10013643`, `0x100136ce`), and nothing
  else changes class.

### 3.3 sc3netmod NETRAMP block

At SIMNTWRK map time: reads the `ramp` lines of `mods\netmod\tables\*.txt` (name order; `SC3NETMOD_TABLE` alone in
tests), checks each `(table, slot)` is in the compiled registry (124 slots), that the line's `from` is the slot's stock
value and that memory still holds it, then writes the new value. Variants among the targets get the class mapping.
Opt-out `SC3NETMOD_RAMPS=0` (measured: the strip is stock with the pack installed). Log lines `ramp: ...`. It runs
before the variant-count early return, so a pack that only swaps stock pieces also works.

## 4. Simulator and agreement

- `netramp.py check-saves CITY...`: 601 / 601 straight strips (section 1.1).
- `netramp.py build-onramp SAVE X,Z [--rules DIR] [--table FILE]`: the On-ramp tool offline (straight case, table,
  HWAY + ROAD retile through tiler.py). With the fixture pack's merged rules and table it predicts the live A1/A2 grid
  cell for cell. Not modelled: the hover search of `FUN_10009d20` (give the middle cell), heights, funds, the corner case.
- `netrules validate` over the 16 shipped cities, ROAD and HWAY, before and after this task: agreement unchanged
  (ROAD 99.83%, HWAY 99.71%; tiler.py's retile was not changed). One class added, `onramp-area` (within 2 cells of a
  piece the On-ramp tool places, 15123..15141), placed after `diag`. Per class (16 cities):

  | net | before | after |
  |---|---|---|
  | ROAD | arm-missing 114, water 31, diag 20, interior 19, gap 12, arm-to-empty 9, slope 5, near-slope 1 | unchanged |
  | HWAY | interior 21, arm-missing 13, near-slope 8 | **onramp-area 29**, arm-missing 13 |

  So every HWAY disagreement that had no mechanism (21 interior + 8 near-slope) sits within 2 cells of a piece the
  On-ramp tool places; the 8 "near-slope" ones are all next to the corner pieces 15123..15128 (Frankfurt). Why the
  saved neighbours differ from a from-scratch retile there is `[UNCERTAIN]` (candidate: the order of the tool's two
  retiles and later edits; one explain, Frankfurt HWAY (119,14), shows Complex rule #21 firing after its neighbour
  changed in the same retile).

## 5. Not covered / open

- Corner case (`onramp_corner`, L-shaped selection at an interchange): decoded from code, slots exposed, never built
  live and absent from every shipped save as a 3-piece L.
- Tunnel tables: exposed and patched the same way, not built live (needs a hill; Roadless Paradise is flat).
- Slope tables with a variant: exposed, not built live.
- Traffic: see RESULTS arm T.

## 6. Cómo agregar una variante de rampa o intercambiador (para el dueño)

1. Ver las tablas y elegir la pieza: `py -3.12 re/tools/netmod/netramp.py tables`. Cada fila es una ranura: la
   pieza que el juego pone ahí (id.estado) y en qué caso (orientación de la rampa, de qué lado está la autopista,
   de qué lado llega la calle). Para la rampa de autopista la tabla es `onramp`, para pendientes `slope.<RED>`, para
   túneles `tunnel.<RED>`.
2. Crear el paquete: `py -3.12 re/tools/netmod/netpack.py new <carpeta> --id <nuevo id> --base <pieza de la tabla>`.
   En `manifest.json` dejar la variante (id nuevo, `base` = la pieza original, la red la completa el scaffold) con su
   arte (`recolor` o PNG en `png_dir`, ver `netpack.py export-art`). Borrar los `rule_edits` que trae el scaffold: a
   esta pieza no la pone una regla sino la tabla.
3. Agregar la sección `ramps`: `{"table": "onramp", "from": 15139, "to": 25139}` cambia esa pieza en todas sus
   ranuras, `{"table": "onramp", "from": [15139, 0], "to": [25139, 0]}` solo en una orientación. Dejar `inherit`
   como viene (activado): sin eso la autopista borra la rampa al construirla.
4. Probar sin abrir el juego: `netpack.py validate <carpeta>`, y `netramp.py build-onramp <ciudad> X,Z --rules
   <reglas armadas> --table <build>\tables\<paquete>.txt --show x0,z0,x1,z1` muestra qué piezas pone la herramienta.
5. Instalar: `netpack.py install <carpeta> --tree <juego>` (modo overlay, no toca `Apps`). El juego tiene que
   arrancar con `sc3netmod.dll` (mods_launch). En el juego: autopista, una calle que la cruce, y la herramienta de
   rampas de autopista (menú de transporte, comando 0x10004302 "Onramps") al costado de la autopista, pegada al cruce.
6. Guardados: la ciudad se guarda con las piezas originales más una sección aparte. Sin el mod carga con rampas
   grises normales, con el mod vuelven las variantes. Desinstalar: `netpack.py uninstall <nombre> --tree <juego>`.

Los intercambiadores (piezas 15107..15122, 15145..15148) y la intersección de la calle (15045..15047) no salen de
tablas: los ponen las reglas de HWAY y ROAD después de la rampa. Para variar esos se usan `rule_edits` sobre las
reglas que los colocan (`netcat.py show <id>` lista las reglas con su número).
