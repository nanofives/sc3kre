# Multi-cell templates: new intersections placed as one block (netmod, task multitile, 2026-10-13)

**Status: game-proven on stock DLLs** (`verify/multitile/RESULTS.md`, PRE `verify/multitile/PRE.md`). A template is a
fixed block of network pieces (a 2x2 roundabout, a cloverleaf, an interchange) that the player places with one click,
that keeps its pieces afterwards, connects to the networks around it, saves stock-safe and is demolished as one block.
SIMNTWRK.DLL, image base 0x10000000, Ghidra VAs.

Files: `re/tools/netmod/netpack_templates.py` (format, checks, rotation, table lines, `place` simulator),
`netpack.py` (wiring), `netpack.schema.json` (`templates`, `template`, `template_cell`), `re/harness/src/sc3netmod_tmpl.c`
(TMPL block of sc3netmod.dll), `sc3netmod_bridge.c` (two lines), fixture `re/tools/netmod/examples/example_template_rotonda`,
A/B packs `verify/multitile/packs/`, driver `re/tools/netmod/mt_drive.py`.

Owner intent: bring NEW ramps and intersections that stock does not have. Single-cell pieces go through the tiling
rules (netrules, netpack `rule_edits`); a junction bigger than one cell is a set of pieces that must be placed
together, keep their pieces and connect outward. This is that framework. Siblings: `artkit` (art for new geometry),
`lanekit` (connectivity and traffic lanes of new pieces). The demo uses stock T (39) and curve (35) pieces as tinted
variants until their piece exists; a template references ids, so swapping in a new piece is a manifest edit.

## 1. The format (`templates` in a netpack manifest)

```json
"templates": [{
  "name": "rotonda3", "label": {"*": "Rotonda 2x2 (3 salidas)"},
  "size": [2, 2],                         // [W along x, H along z], each 1..16
  "network": "ROAD",                      // default network of the cells
  "rows": [[[21039, 3], [21039, 0]],      // H rows (z = 0..), W cells (x = 0..): [piece, state],
           [[21035, 2], [21039, 1]]],     //   {"piece", "state", "network"} or null (a hole)
  "edges": [{"at": [0, 0], "dir": "W", "need": "optional"}, ...],   // optional: the exits
  "terrain": {"flat": true, "water": false},
  "cost": 350,                            // charged once per placement
  "rotate": "generate",                   // or "none"
  "protect": true,                        // default: pieces go into the network's Protected list
  "collapse": true                        // default: the package's template pieces form one Collapse.txt group
}]
```

Checks (`netpack.py validate`, `build`, `install`; a failure refuses the package):

| check | rule | basis |
|---|---|---|
| shape | rows x cells = size, at least one cell | |
| piece | in the network's Set (stock + merged variants) | `TILER_SIM.md` 1 |
| state | a state some rule places for that piece (variants: their base's) | `tiler.Rules.arms` keys |
| arms | ROAD / RAIL / SUBW: from the exemplar connectivity matrix (props 310 / 311 / 312): side f is an arm when row (f - state) mod 4 is non-zero; other networks: rule geometry | the final stage reads these masks through `FUN_1000d73d` (`tiler.Tiler.conn_bits`) |
| inner arms | an arm toward another template cell needs that cell's arm back; an arm into a hole is refused | |
| edges | each listed edge is an outward arm; when `edges` is given it names every outward arm | |
| rotation | cell (x, z) -> (H-1-z, x), state + 1 (arms W->N->E->S); when (piece, state+1) is not a placed state, the placed state with the same arm set (straight 29: 2 == 0); none -> refused | state s = state 0 turned s quarters: `_perm` closed form of `0x1003123c` in tiler.py, and road T 39 states 0..3 = WNS, WNE, NES, WES |
| protect | every cell piece must be a variant: a stock id in the Protected list would be protected everywhere | |
| collapse | a template piece already in a Collapse group (inherited from its base) is refused; at most 28 ids per package | `FUN_1001da5f` takes the first group holding the id and returns when a group's count is over 0x1d |

What install writes, beside the variants: the template pieces added to `<NET>_GRND_Protected.txt`, one Collapse.txt
group per package, and `tmpl` lines in `mods\netmod\tables\<package>.txt`:

```
tmpl <package>/<name> <orientations> <cost> <flags: 1 flat, 2 no water>
tori <k> <W> <H>
tcel <x> <z> <netType 1..6> <piece> <state>
tedg <x> <z> <dir 0..3 = W N E S> <netType> <0 optional | 1 required>
tend
```
The DLL never rotates or validates shapes: every orientation arrives precomputed.

`netpack_templates.py place PACK SAVE X,Z [--template N] [--orient K] [--road x0,z0,x1,z1 ...] [--no-protect]`
simulates the click on a save with tiler.py (stock rules + the package's merged rules): cell checks, cell writes, the
footprint retile, and later road lines with their retile. Every in-game cell it predicted matched (RESULTS arms P, C,
N, AB).

## 2. How it works in game (sc3netmod TMPL block)

The game's highway On-ramp tool is borrowed while template mode is on. Its path, read for this task:

| step | code | what |
|---|---|---|
| tool | `FUN_1000fafe` builds it (0x12c bytes, tool vtable 0x1002c1d8); command Execute `FUN_1000f79c` makes the selection (0x98 bytes, vtables 0x1002c1b0 / 0x1002c184 at +0 / +4) | `[CONFIRMED @ 0x1000fafe, 0x1000f79c]` |
| hover | framework mouse move `FUN_10025c93` -> tool vt+0x54 `FUN_1000f760` -> selection vt+0xc = **`FUN_10009d20`** (slot 0x1002c1bc), then vt+0x50 `FUN_1000f72c` -> manager vt+0x90 (cost, `FUN_100145aa`) | `[CONFIRMED @ 0x10025c93, 0x1000f760, 0x1000f72c]` |
| hover body | clears: highlighter (+0x50) vt+0x40(0), point vector erase `FUN_100041e4(+8, begin, end)`; adds points with `FUN_10004754(pt, dedupe)` (cap `DAT_100322a4 < 0x200`, highlighter vt+0x2c(pt, 0x23/0x24) per cell, push); ends with highlighter vt+0x58(old box U new box), stores the box at +0x78, QI 0x62c0838e into arg 3 | `[CONFIRMED @ 0x10009d20, 0x10004754]` (ret 0x10 and ret 8 read from the PE) |
| click | mouse up `FUN_10025b3c`: vt+0x54 (the hover generator again, with the end point) then vt+0x48 `FUN_1000f9b7` -> manager vt+0xac = `FUN_1000abde(sel iface, &cost, ., .)` | `[CONFIRMED @ 0x1000f9b7]` |
| money | funds = manager+0x38 (city vt+0x15c, cISC3BudgetLayer) vt+0x10 (int64); refused when funds < 2^32 and (negative or < cost) `[0x1000ad3e..ad4d]`; spent with vt+0x14(cost) `[CONFIRMED @ 0x1000bcd2]`. No confirm dialog (that is manager vt+0x140, used by the tunnel builders) | |
| write | `FUN_10008919(layer, &pos, id << 8 \| state, -1, 8, 0)`: factory 0xc14f8955, removes a removable incumbent, height from terrain, position, layer insert, side table +0x34 | `[CONFIRMED @ 0x10008919]` |
| retile | manager vt+0xb0 = `FUN_100151f1(rect, mask)`, rect `{x0<<8, z0<<8, 0, x1<<8, z1<<8, 0}`, the handler of GZ message 0x637c0dab | `[CONFIRMED @ 0x10013afe]` |

The TMPL block swaps three slots (each checked against the shipped value first, all or nothing):
- **0x1002c1bc** (selection vt+0xc): in template mode it runs the hover body above with the template's cells
  (anchor = cursor - ((W-1)/2, (H-1)/2)), resets the add-point cap first, and returns 1. Outside template mode, stock.
- **manager vt+0x90**: calls the stock cost first (so tools that watch it still see the selection), then returns the
  template cost.
- **manager vt+0xac**: in template mode: per cell, in map, flat (`FUN_10016ccd`), not water (`FUN_10016d69`), and the
  occupant is none, major type 5 (vt+0x54), or one the manager's network test vt+0x14c accepts that is not Protected
  (`FUN_1001a7f7`) (the rule `FUN_10009613` applies); `required` exits need a network occupant outside; the funds test
  of `FUN_1000abde`; then `FUN_10008919` per cell, budget vt+0x14(cost), `FUN_100151f1` over the footprint with the
  networks' mask bits. The anchor comes from the last template hover, because the build receives the selection's
  point-list interface (object + 4), not the object (first launch: reading it as the object gave a garbage anchor).
- Keys (game window subclass): **T** cycles the templates (off -> 1 -> .. -> off) and selects the On-ramp tool (GZ
  message `{0x025F0A91, 0x10004302}`, as `np_drive.py cmd`); **R** turns the template a quarter (only in template mode).
  Without Ctrl / Alt. With TMPL off the game did nothing on T (RESULTS arm X).

Opt-outs: `SC3NETMOD_TMPL=0` (whole block), `SC3NETMOD_TMPL_KEYS=0` (no subclass), `SC3NETMOD_TMPL_RETILE=0` (no
footprint retile; tests only).

### 2.1 Why the cells stay: the Protected list (proven, arm AB)

`FUN_1001547b` removes and re-places every predicate-A occupant its flood reaches, except Protected ones, which leave
the removal and the work lists, and `FUN_10016327` refuses any rule whose result would land on a Protected cell
(`TILER_SIM.md` 3 and 4). So the template's own footprint retile and every later retile nearby keep the pieces, while
the neighbours still see them (through Convert, as their base) and connect to their arms. A/B in game: the same
template with its pieces outside the list was re-tiled by the click's own retile into the stock 2x2 loop
`11203.3/0/2/1` (predicted by the simulator), with the list it stayed `21039.x`. No DLL guard is needed.

### 2.2 Why demolish takes the whole block: a Collapse group (proven, arms B / B0)

Survey of the removal path: none of `FUN_1001d6ef`, `FUN_1001d761`, `FUN_1001da5f`, `FUN_1001e3cc`, `FUN_1001e2ea`
calls `FUN_1001a7f7`, so Protected pieces can always be demolished. `FUN_1001da5f` finds the first Collapse.txt group
holding the clicked id, then walks from the clicked cell along +-x and +-z while the cells hold ids of that group, and
floods 4-connected through a 16x16 window (x-8..x+7, z-8..z+7), removing each reached cell with `FUN_1001e3cc`
`[CONFIRMED @ 0x1001da5f]`. netpack gives each package one group with its template pieces. netbridge's INHERIT maps a
variant to its base in that walk (wrapper of manager vt+0x104 and the 5 id sites), which would look the template
pieces up as 39 / 35; `g_tmpl_keep` (set from the `tcel` lines) keeps template ids as they are there. In game: one
click removed all 4 cells (B); with `"collapse": false` only the clicked cell went (B0).

Consequence: two templates of one package that touch, or that sit in one row or column with template cells between
them, are demolished together.

### 2.3 Saves

Template pieces are variants, so the existing SAVEBASE / load path applies unchanged (`NETVARIANT.md` 4): base ids in
the tile words, the variant ids in section 0x4E56. Measured: 20 tiles saved as base, all 20 restored on load with the
mod, grey T / curve pieces on the same cells without it (arm S).

## 3. Limits and open points

- Template mode borrows the On-ramp tool: while it is on, that tool builds templates, not ramps (T until off).
- No new menu entry yet. The survey found how: MenuItem.INI COMM lines are created by class id through SIMNTWRK's
  class switch `FUN_10010521` (Onramps = class 0x02b5debb -> `FUN_1000fafe`); a new command id needs that switch
  hooked (or a sub-factory added) plus a per-tool copy of the selection vtable. `[UNCERTAIN]` how GZCOM routes a
  class id to that factory (`FUN_10010dff` / `FUN_1001b4ff` not decoded). Not built.
- A road drawn into a closed side ends as a straight pointing at the side (29.1 in arm N): that is what the stock
  Simple stage gives for a road end next to a road piece, simulator and game agree. A rule edit could end it instead.
- The anchor follows the cursor cell; for even sizes the cursor sits on cell ((W-1)/2, (H-1)/2).
- `required` exits are implemented and not exercised in game. Water, building and protected-piece refusals: code only
  (slope refusal measured).
- Multi-network templates (a highway + road interchange) are accepted by the format (per-cell network, HWAY arms
  from rule geometry, retile mask 1|2 runs HWAY then ROAD) and not tried in game.
- Traffic over a template: not measured (the variants copy their bases' TrBlkAtt).
- Cost is one number per template, not derived from piece prices.

## 4. Cómo definir y colocar una intersección de varias casillas (para el dueño)

1. **Las piezas.** Cada casilla de la plantilla es una pieza de red. Tiene que ser una variante (id nuevo con `base`
   = una pieza del juego), porque la variante entra en la lista Protected y una pieza del juego no (quedaría protegida
   en todo el mapa). Para probar sirve copiar una pieza existente: `{"id": 21039, "base": 39, "network": "ROAD",
   "art": {"from": 39}}`. Con arte nuevo (artkit) va el id de esa pieza. Ver los estados de una pieza:
   `py -3.12 re/tools/netmod/netcat.py show 39` (estado 0..3 = la pieza girada 0..3 cuartos).
2. **La plantilla.** En `manifest.json`, sección `templates`: nombre, `size` [ancho, alto], `rows` con `[pieza,
   estado]` por casilla (fila por fila, `null` para un hueco), `cost`. Opcional `edges` para fijar las salidas y
   marcar alguna como `required`. Ejemplo completo: `re/tools/netmod/examples/example_template_rotonda/manifest.json`.
3. **Validar sin abrir el juego.** `py -3.12 re/tools/netmod/netpack.py validate <carpeta>` dibuja las 4 rotaciones
   con las salidas de cada una y rechaza brazos que no se encuentran, estados que no existen y piezas sin proteger.
   `py -3.12 re/tools/netmod/netpack_templates.py place <carpeta> <ciudad.sc3> X,Z --template <nombre> --road
   x0,z0,x1,z1` muestra qué casillas quedan después del click y de una calle nueva al lado.
4. **Instalar.** `py -3.12 re/tools/netmod/netpack.py install <carpeta> --tree <juego>` (modo overlay, no toca
   `Apps`). El juego tiene que arrancar con `sc3netmod.dll` (mods_launch).
5. **En el juego.** Tecla **T**: elige la plantilla siguiente y abre la herramienta de rampas en modo plantilla (T otra
   vez pasa a la siguiente, y después de la última vuelve a la herramienta normal). El cursor marca las casillas y el
   costo. Tecla **R**: gira un cuarto. Click: la coloca si todas las casillas están en el mapa, planas, sin agua y
   libres (árboles sí, edificios u otra red no) y si alcanza la plata. Las calles que se tiran después hasta una
   salida se unen solas. Demoler una casilla saca la plantilla entera.
6. **Guardado.** La ciudad se guarda con las piezas base más una sección aparte: sin el mod abre con piezas grises
   normales, con el mod vuelven las variantes.
