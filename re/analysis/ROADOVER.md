# Network drags over zoned buildings (sc3resize ROADOVER, task roadover 2026-10-28)

Owner report (2026-10-28): "i'm not able to place road over these residential buildings" (picture: road drag red over
zoned houses, $45 label). PLOPOVER (`RELOCATE.md`) already demolishes zoned buildings under a placed BUILDING. ROADOVER
does the same for the road, highway, rail and power-line drag tools.

Code: `re/harness/src/sc3resize.c`, block `ROADOVER` after `rl_install`. Behaviour follows `g_plopover` (sc3resize.ini
`[buildings] plopover=`, the mods page checkbox "Construir sobre zonas", env `SC3RESIZE_PLOPOVER`). `SC3RESIZE_ROADOVER=0`
installs nothing. Evidence: `verify/roadover/RESULTS.md`. Tools: `re/tools/roadover_probe.py` (cell map, predicate
calls), `re/tools/roadover_drive.py` (posted-input drags).

## 1. The drag path (SIMNTWRK)

| piece | address | what it does |
|---|---|---|
| drag tools | vtables `0x1002bef8` road, `0x1002bfa0` highway, `0x1002c048` rail, `0x1002c0f0` subway, `0x1002c1d8` on-ramp, `0x1002c280` power, `0x1002c328` pipe | dumped from the PE. Init vt+0x88 (road `0x1000e537`), Apply vt+0x48 (road `0x1000e72a`), cost vt+0x4c = vt+0x50 (road `0x1000e6f9`), compute vt+0x54 `0x1000e845` |
| path object | tool+0x114, ctor `0x10010be8`, vtable `0x1002c3e8`: +0xc compute `0x1000488d`, +0x10 Init `0x100106b8` | Init stores the occupant layer (+0x3c) and three predicates (+0x40, +0x44, +0x48). Cells: 12-byte points (x<<8, z<<8, y) in a vector at +8..+0xc `[CONFIRMED @ 0x100047dd]` |
| per-cell test | `0x10010731(x, z)` | slope (`0x100108da`), water (+0x54 vt+0x54), then the occupant there (+0x3c vt+0x78) through predicate +0x40 vt+0xc. A refused cell makes the compute return 0. Then the tool sets +0x38 and Apply posts refusal 0x1e `[CONFIRMED @ 0x10010731, 0x1000e845, 0x1000e72a]` |
| paint | path+0x50 vt+0x2c(point, kind) | 0x23 valid, 0x24 refused (red). Funds short of the path price: every cell 0x24 `[CONFIRMED @ 0x1000488d tail]` |
| predicates | netmgr vt+0x54(out, `0xa1c085db`, index), switch `0x10013771` | tool init asks for road 0x1c / 0x10 / 0x16, highway 0x1d / 0x11 / 0x17, rail 0x1e / 0x12 / 0x18, subway 0x1f / 0x13 / 0x19, power 0x21 / 0x15 / 0x1b, pipe 0x20 / 0x14 / 0x1a, on-ramp 2 / 0 / 0 |
| cost | tool vt+0x4c: netmgr vt+0x78.. (road `0x10013e24`) -> tool+0x34, then `0x100259b8` | `0x100259b8` sets tool+0x39 when funds < tool+0x34. Apply then posts "no funds" 0x20 |
| build | Apply -> netmgr +0x94 road / +0x98 highway / +0x9c rail / +0xa0 subway / +0xa4 pipe / +0xa8 power -> +0xec `0x10014807(sel, netType, &cost, a4, a5)` -> +0xf0 `0x10014a23` | netType 1 road, 4 highway, 2 rail, 6 subway, 5 pipe, 3 power. +0xec reads the selection in batches of 0x500 points and calls +0xf0 `__thiscall(layer, sel, netType, cost, a4, points, count, a5)`, `ret 0x20` `[CONFIRMED @ 0x100148fe..0x1001491c, 0x100151ee]` |
| +0xf0 | `0x10014a23` | builds only the points the selection marks 0x23. Funds test against `cost`. Tiler `0x1001547b`, commit `0x100165d8`: an insert onto a taken cell removes the occupant only when the network's own predicates accept it |

Primary drag predicates (vt+0xc, `ret 4`, ecx ignored), from the vtables built in `0x10010dff`:

| tool | index | global | vtable | Test | accepts |
|---|---|---|---|---|---|
| road | 0x1c | `DAT_10032418` | `0x1002c590` | `0x1001ad60` | CanUserRemove AND (0x400 flora, or 0x8800 road, or vt+0x5c(0xffff) in {0xe, 0xf}) |
| highway | 0x1d | `DAT_10032424` | `0x1002c568` | `0x1001ae36` | same with 0x10800 |
| rail | 0x1e | `DAT_1003241c` | `0x1002c57c` | `0x1001ade7` | same with 0x20800 |
| power | 0x21 | `DAT_10032420` | `0x1002c554` | `0x1001adaf` | CanUserRemove AND (0x400 or 0x400800) |
| subway, pipe | 0x1f, 0x20 | `DAT_10032428`, `DAT_1003242c` | `0x1002c52c`, `0x1002c540` | `0x1001ad4f` | CanUserRemove only: they pass under buildings |

A building carries GeomFlag 0x104, so the first four refuse it. The secondary predicates (+0x44, +0x48, used by
`0x100107d1` on sloped cells) test network piece ids and orientation (`0x1001ae85`, `0x1001b10c`), not buildings.
Measured in a `-Stock` process (`RESULTS.md` S): all four return 0 on three zoned houses and on a civic building, road
returns 1 on a road piece.

## 2. What the mod does

1. Slot +0xc of the four predicate vtables: stock (or sc3netmod's wrapper, item 4), else 1 for a zoned building
   (GeomFlag 0x100, CanUserRemove, zone byte 1..11 under its first cell, the PLOPOVER test). Indices 0x1c / 0x1d / 0x1e /
   0x21 are asked for only by the four tools' init (`NETWORK_RULE_ENGINE.md` 12.4 census), so nothing else changes.
2. Tool vt+0x4c / +0x50 of the four tools: after the stock cost, every distinct zoned building under the path cells adds
   per-tile price (budget city vt+0x15c, vt+0x58(7)) times its footprint, what the bulldozer and PLOPOVER charge. The sum
   goes into tool+0x34 and `0x100259b8` runs again, so the cursor label shows it and the stock funds refusal covers it.
   Each building counts once however many drag cells it covers. Only cells the selection layer marks 0x23 count
   (`0x10021b37()` vt+0x8c, then vt+0x30(point, &kind), the test +0xf0 makes before building a point,
   `0x10014ab2..0x10014acb`), so a building under a cell refused for another reason is neither charged nor demolished.
3. netmgr vt+0xf0 (slot `0x1002c8ac`): for netType 1 / 2 / 3 / 4, the zoned buildings under the points are removed through
   `rl_remove` (demolition layer vt+0x6c, no rubble, no charge). Then the stock build runs, and the bulldozing is withdrawn
   (budget vt+0x14). Funds short of build + bulldozing: refused, nothing removed (measured: the game's tool+0x39 did not
   stop Apply in that case, this test did). This runs inside tool Apply, so sc3undo
   journals the removals: one undo restores the houses and refunds the whole price.
4. **sc3netmod coexistence.** sc3netmod's CROSS block wraps slot +0xc of the road / highway / rail predicates
   (`sc3netmod.c` g_preds) and skips a slot that no longer holds the stock function. ROADOVER did the same at first, so
   whichever mod patched second lost its hook (measured: 2 launches with sc3netmod skipped, 1 with ROADOVER not installed).
   The loader maps every mod at process init. `ro_install` therefore runs on its own thread, waits up to 10 s for the
   three slots to point into sc3netmod.dll, and chains them: ours, then sc3netmod's, then stock. Measured: sc3netmod wraps
   at 234 ms, ROADOVER chains at 249 ms.

## 3. Not covered

- On-ramp tool and sc3netmod templates (netmgr +0xac path, predicates 2 / 0 / 0): unchanged.
- Pipes and subway: unchanged (they already pass under buildings in stock).
- Sloped cells: `0x100107d1` uses the secondary predicates, so a zoned building on a slope cell the compute tests that way
  stays refused. Not run.
- Highway: hooked like the others, predicate measured accepting the houses, but no highway was built over zoned houses in
  game. The test line ran beside a road and a civic building, which the 2-wide highway band refuses in stock.
- Power line: built in game over zoned buildings (HUD power flyout, pylon icon). Stock refuses a power line over a
  building (predicate `0x1001adaf`, measured 0 in `-Stock`), so demolishing is new, not a change to something stock allowed.
- Roads built beside an existing road join into an sc3netmod avenue (11204), as any parallel road drag does. Those avenue
  pieces did not draw in the dev tree used here (cells read back as 11204).
