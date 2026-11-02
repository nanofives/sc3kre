# STATUS rcibars (round 2026-11-02, orchestrator "SC3 graphs tabs + Vida util/restore/query UI round")

## goal
Owner 2026-11-02: "can we modify the RCI to include Agricultural, Ports and Airports?" Owner pick: Aeropuerto + Puerto
bars now (capacity in use, not demand), agriculture after research.

## verdict + deciding RVAs (static, milestone 1)
- RCI meter = SIMUI class vtable `0x100ab274` (ctor `0x10064a0f`). Slots: `+0x0c` message handler `0x10065303`,
  `+0x24` Init `0x10064b08`, `+0xc8` SetRect `0x100651ba` (forces the size of the background raster `+0xa8`),
  `+0x144` Draw `0x10065214`, `+0x170` surface (re)create `0x1006d56c` [CONFIRMED, PE vtable + bodies].
- Demand in: every valve posts message `0x426840a0 {id, permille, 0}` at month end / load (SIMRCI `0x10042e89`,
  `0x10042bd6`, `0x10042b20`); permille = value*1000/max (or /min when negative). The RCI keeps 3000/5000/8000
  (`0x10065303`), bar height px = permille * 0.001 (`0x100ab46c`) * `this+0xe8` (= 16.0 from `0x100ab260`)
  (`0x10065cc9`, disassembly). Bars x 5..10 / 14..19 / 23..28, up from y 51 (`+0xec`), down from y 62 (`+0xf0`),
  colours (0,192,0) / (0,0,192) / (192,192,0) via `vt+0x184` [CONFIRMED @ SIMUI 0x10064b08].
- Letters R C I drawn ONCE into the background raster at Init with font `0xf` (window manager `FUN_10085065` vt+0x14),
  colour (0x1f,0x29,0x88), font vt+0x90 [CONFIRMED @ SIMUI 0x10064b08].
- The RCI's child button 0x7d1 (image 0x52fb06f0) is "Visitar Bolsa de SimCity" (string 400, group 0x41f2625), not a demand tooltip.
- Capacity in use = cap byte of valve 5000 / 8000 (`+0x3c`, getter vt+0x70), written monthly by SIMRCI `0x1000ee50` /
  `0x10016061` from valve 5001 / 8001: 0 if demand 0, 100 if supply < demand, else demand*100/supply. Same byte the
  City Planner compares with 75 (PORTS_AIRPORTS.md 5.1).

## result (milestone 2, 2026-11-02): BUILT, one in-game check done
Pictures + full write-up: verify/rcibars/RESULTS.md, verify/rcibars/owner_shots/ (4 PNGs).
Agriculture: NO bar. No farm demand or valve (farm row 9300 uses 8000/7000/8001, SC3ValveLayer.ini:31). Only number:
farm building count = BuildingLayer vt+0x60(0x2454) (SIMADV 0x100094e7). Owner call needed (options in RESULTS.md).

## plan (as built; first-build defects fixed: second globe, P under the minimap at 800x600, black key boxes, grey box)
Block RCIBARS in `re/harness/src/sc3resize_rcibars.c`, #included by sc3resize.c, `SC3RESIZE_RCIBARS=0` off.
After the stock Init: a 18 px wider background raster (gfx `FUN_10085039` vt+0x14, raster vt+0x0c, the recipe of
`0x1006d56c`), the stock art copied in, two more column strips + "A" / "P" letters with the stock font, then SetRect so the
game itself sizes the window and its surface. Draw wrap: two more fills, (A) commercial cap, (P) industrial cap, same
16 px scale, a 75% tick. A tooltip button over the two new columns with the numbers ("capacidad en uso").

## built
dev/rcibars\inst\sc3resize.dll from the worktree (clean build).

## proven game-side vs static only
Game-side (Berlin, tree dev/rcibars): 59x88 RCI, A 56% / P 17% (5001 1,078,500/614,402, 8001 1,030,800/180,069),
75% ticks, tooltip by posted hover, 800x600 / 1600x900 / 1920x1040 (HUD x1.733) layouts, NATIVETEXT wraps the RCI Draw
over RCIBARS, SC3RESIZE_RCIBARS=0 = stock RCI. Not run: a month end with the sim running, a second city load in the same
session, the English tooltip.

## blocked on
nothing

## files owned
- re/harness/src/sc3resize_rcibars.c (new; IGNORED by .gitignore `/re/*`: needs `git add -f`)
- re/harness/src/sc3resize.c (include, install, env lines, tentative g_rcibars, BARKIDS minimap clamp for the RCI)
  sc3resize.c edits, all pure insertions against main 85c127f (new-file line numbers; anchor = the line just above):
  - +949 (1 line) after `static int    g_rci_nat_ok;`: `static int g_rcibars;` tentative definition
  - +2735..2742 (8 lines) in rz_bar_children_right, after `LONG w = e[2] - e[0], want = art[2] - 1;`: minimap clamp
  - +7588 (1 line) just above `#include "sc3resize_ntext.c"`: `static void *g_rcb_drawfn;`
  - +10127 (1 line) after `#include "sc3resize_graphs.c"`: `#include "sc3resize_rcibars.c"`
  - +18548 (1 line) after `gn_install(sui);`: `rcb_install(sui);`
  - +18637..18638 (2 lines) after the `SC3RESIZE_GRAPHNEW_LOG` env line: SC3RESIZE_RCIBARS / SC3RESIZE_RCIBARS_LOG
- re/harness/src/sc3resize_ntext.c line 464, nt_rci_install: the slot check also accepts `g_rcb_drawfn` (1 line changed)
- re/sessions/STATUS_rcibars.md, verify/rcibars/RESULTS.md, verify/rcibars/owner_shots/*.png

## game-harness need
one tree run in dev\rcibars (frame dumps)

## asks of other sessions
none
