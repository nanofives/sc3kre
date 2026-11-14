# STATUS lvwrap (round 2026-11-14 Simtropolis)

## goal
Land value "past 255 turns very low" (Simtropolis). Trace every reader of the city land value average, confirm the
wrap in game, fix with an off switch if it is ours. Brief: `re/sessions/ROUND_2026-11-14_simtropolis.md`.

## verdict + deciding RVA
CAUSE FOUND (static, 2026-11-14). Stock bug, not ours (no mod source reads the average). The average byte wraps at
SIMRCI `0x1001d650` (`mov byte [esi+0xc0], al` after `div ecx`, no clamp), and the property tax formula multiplies by
that byte: SIMMISC `0x100090a7`. A true average of 256 is stored as 0, raised to the floor 35, so tax income per zone drops to
35/255 of the tax at 255 for the same valve supply (the live floor is SC3BudgetLayer.INI MinAverageLV=35, not
the image default 5; see the fix-up below). iOS (`goLandValueLayer::doDailySim`, `this+0xe0`, now a short) clamps the average to 0xff
`[iOS-HINT]`, so the fix is the same clamp on PC.

## proven static so far
- SIMRCI `0x1001deca` (compute map): per sub-cell value accumulated into layer `+0xc8` (sum) and `+0xcc` (count,
  only cells with a zone type, `local_d != 0`) BEFORE the clamp. The stored per-cell value is `local_5c/4` clamped to
  1..255 `[CONFIRMED @ 0x1001deca]`, so one cell cannot wrap.
- SIMRCI `0x1001d616`: `+0xc4 = +0xc8`; if count == 0 -> `+0xc0 = 0`, else sum < 0 -> 0, then
  `*(char*)(+0xc0) = (char)(sum / count)` (unsigned divide, no clamp), then sum/count zeroed `[CONFIRMED @ 0x1001d616]`.
  So an average of 300 is stored as 44.
- SIMRCI `0x1001d69b`: city GetDate (vt+0x1e4), pushes byte `+0xc0` into object `+0xd0` vt+0x6c; on day 1 also
  `+0xd0` vt+0x2c -> vt+0x74, and every 10th year vt+0x38 -> vt+0x7c `[CONFIRMED @ 0x1001d69b]` (history object,
  readers not traced yet).
- GetAverageValue = SIMRCI `0x1001b3b7` returns byte `this+0xa4`; it is slot `+0x44` of the cISC3LandValueLayer
  interface vtable SIMRCI `0x1004c624` (QI adjustor `0x1001f4a1` subtracts 0x1c), so the interface is at layer+0x1c
  and +0xa4 there = layer +0xc0 `[CONFIRMED @ 0x1004c668]`. Callers reach it as `city vt+0x188` -> `vt+0x44`.

## readers of the average (all traced, 2026-11-14)
- **Property tax, SIMMISC `0x100090a7`** `[CONFIRMED @ 0x100090a7, disassembly]`, `__thiscall(budget, zone 0/1/2) ret 4`:
  `avg = (budget+0x20)->vt+0x44()` (GetAverageValue `0x1001b3b7` = `movzx eax, byte [ecx+0xa4]`, so 0..255);
  `n = (budget+0x30 = valve layer, QI 0x40a42f1c)->vt+0x28/+0x2c/+0x30()` = valve `+0x40/+0x44/+0x48` (last month's
  sum of footprint area x valve 3000/5000/8000 amount, rotated in `0x1002efe8`, accumulated in `0x1002f5af`);
  if `n > 0` and `avg < byte[0x100494a8] = 5` then `avg = 5`;
  `return ftol( (int64)((rate * n) / 100 * avg) * 0.0143f )`, rate = byte `budget + zone*0x88 + 0x8c` (init writes 7),
  factor floats `0x1004949c/a0/a4` = 0.0143 for R/C/I.
  Callers: `sc3_budget_layer_tick 0x10007d88` (monthly income per zone, ring +0x90), `0x10008c7a` (rest-of-year
  projection, x (12 - month)), `sc3_budgetui_refresh_summary 0x10023fe1` (budget window).
  Frame note: budget init `0x100067c7` runs on `this-4` of the tick frame (init +0x10 city = tick +0x14 GetDate), so
  init's `+0x1c` LandValueLayer is `+0x20` in tick/tax code.
- **Graph "Valor del Terreno"** (series 11, fixed scale 260, `re/analysis/GRAPH_SERIES.md`): `0x1001d69b` pushes byte
  `+0xc0` into history `+0xd0` (vt+0x6c), handed to the Graficas page on message 0x605 by `0x1001f5e5`. Shows the
  wrapped value; old months stay wrapped in saves after a fix.
- **Scenario `cmdGetLandValue`, SCENARIO `0x10007356`**: `(this+0x28)->vt+0x44()` into a script variable (scenario
  init `0x10007bd5` stores at +0x24, same +4 frame shift). Scenario goals on land value see the wrapped value.

Not readers of the average (checked): the 3 zone developers `load_growth_table` (cache the layer at comdev/resdev
`+0x84`, inddev `+0xb4`; their `vt+0x44` is on `FUN_1003ceec()`), `evaluate_tile` / `develop_lot` (per-cell `vt+0x34`);
SIMMISC query `0x1001068c` (per-cell `vt+0x34`; its `vt+0x44` is on QI 0x4259c018, a signed char:
`(cell + 0x80 + that) / 20 * 2000`); SIMSERV `0x10001a04` (per-cell); budget tick's own `+0x1c vt+0xa4` is the traffic
layer; zone layer `+0x250`, RCI layer `+0x5c` (store/release only); effect layer `+0x14` (base pointer, no +0xc0 read);
AUDIO hit is `this+0x188`, not a city call. Second wrap: none found, per-cell values are 1..255 and the query does int math.

## fix (BUILT + A/B in game, 2026-11-14, child/lvwrap 64ae198 + fix-up 3d6b834)
sc3simrun LVWRAP block: the 10 bytes at SIMRCI `0x1001d64c` become `call lv_stub` + 5 nops (bytes
`0x1001d646..0x1001d657` checked first); the stub divides, caps at 255, stores, logs, and calls the game's own
`0x100090a7` for the R/C/I tax line. `simrun.ini [lvwrap] mode=1` default, 0 stock, 2 observe; env `SC3SIMRUN_LVWRAP`.
Install log line `### LVWRAP: mode=1 (land value average capped at 255), armed=1`.
A/B (Berlin, raised curves in my tree's netmod overlay SYS.PAK): true 259..269 -> stock byte 3..13, R tax ~1,600 a
month; cap byte 255, R tax ~12,000. Budget window Feb 2068 residential 1,803 vs 13,000. `verify/lvwrap/RESULTS.md`.
Fix-up 3d6b834 (orchestrator review): the tax is (rate*n/100) * max(avg, MinAverageLV) * LVTo*TaxTransmogrifier/1e4,
floor 35 and factors 0.0035/0.0045/0.0050 set at load by SIMMISC 0x100053bb from SC3BudgetLayer.INI (image defaults
5 / 0.0143 never run). Measured in game from those addresses, recompute = game result within 1. The tax diagnostic
only runs with SC3SIMRUN_LVWRAP_TAX=1 (or _EVERY=1); no-env launch shows the armed line + average lines, no tax line.
LAND_VALUE.md 9, source comment, README line, tracker row 0x100090a7 corrected.

## scan result (finished after the pause, 2026-11-14)
16 bodies reference `+ 0x188))(` or `LandValueLayer` (not all are city calls, the exe hits are window code):
- with a `+ 0x44))` in the same body (read these first): SIMMISC `0x1001068c` sc3_query_build_report_x110,
  SIMRCI `0x1000f6d8` comdev_load_growth_table, `0x10017649` inddev_load_growth_table, `0x10028864`
  resdev_load_growth_table.
- init-time getters that likely CACHE the layer pointer (then `vt+0x44` is called elsewhere on the cached field,
  so a same-body scan misses it; find the field each stores and scan for `field` + `0x44`): SIMRCI `0x10004559`
  rcilayer_init_acquire_services, `0x1001dbd2` effect_layer_init, `0x100314f0` zonelayer_init_attach; SIMMISC
  `0x100067c7` budget_layer_init; SIMSERV `0x10001a04`; SCENARIO `0x10007bd5`; AUDIO `0x100053e3`.
- noise: SC3U `0x00433e9d`, `0x00435c8c`, `0x00436084`; GZGraphicD `0x10010c3c`; SIMCITY `0x10002bc6` (the getter).

## next (resume here)
Done. Orchestrator: merge child/lvwrap, copy verify/lvwrap. Not run in game: mode 0. Optional: an "Activar mods" row for
SC3SIMRUN_LVWRAP (sc3resize.c MODTOGGLE, shared file, not touched here).

## built
sc3simrun.dll in dev/lvwrap/inst (LVWRAP block). Tree changes, mine only: tree Apps\Sys\SYS.PAK, Apps\SC3.cfg and
mods\netmod\overlay\Apps\Sys\SYS.PAK un-linked; the overlay one carries the raised land value curves (do not stage
this tree). The tree's Apps\Sys\SYS.PAK also has unused raised water/hill values.

## blocked on
Nothing. Harness released.

## files owned
- child/lvwrap 64ae198 + 3d6b834: `re/harness/src/sc3simrun.c`, `re/analysis/LAND_VALUE.md` (section 9), `functions.csv`
  (6 rows, 0x100090a7 re-noted in 3d6b834: SIMMISC 0x100090a7, 0x10008c7a; SIMRCI 0x1001d616, 0x1001b3b7, 0x1001d69b; SCENARIO 0x10007356),
  `README.md` (sc3simrun bullet), `re/tools/lvwrap_lab.py`
- MAIN: `verify/lvwrap/` (RESULTS.md, owner_shots/, runs/), `re/sessions/STATUS_lvwrap.md`

## game-harness need
Done (6 lab launches, claim released).

## asks of other sessions
None.
