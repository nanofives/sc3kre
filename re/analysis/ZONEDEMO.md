# Zoning over zoned buildings demolishes them (sc3resize ZONEDEMO, task zonedemo 2026-10-29)

Owner requests (2026-10-29):

1. Zoning over zoned buildings of ANOTHER zone type (residential painted over industrial buildings) demolishes those
   buildings and zones the cells. Buildings of the SAME type (residential over residential, any density) stay, as stock.
2. The de-zone tool demolishes the zoned buildings on the cells it de-zones, every zone type.

Code: `re/harness/src/sc3resize.c`, block `ZONEDEMO` after `ROADOVER`. Behaviour follows `g_plopover` (sc3resize.ini
`[buildings] plopover=`, the mods page checkbox "Construir sobre zonas", env `SC3RESIZE_PLOPOVER`), the same switch as
PLOPOVER (`RELOCATE.md`) and ROADOVER (`ROADOVER.md`). `SC3RESIZE_ZONEDEMO=0` installs nothing. Evidence:
`verify/zonedemo/RESULTS.md`. Tool: `re/tools/zonedemo_probe.py` (zone map, CanZone / PlaceZone calls).

## 1. The zone tool path (SIMRCI)

| piece | address | what it does |
|---|---|---|
| zone tools | one class for all 13 (DeZone, R/C/I x 3 densities, airport, seaport, landfill), vtable `0x1004c06c`, ctor `0x1000ba68` (zone type at tool+0x124, zone layer interface at tool+0x11c) | read from the PE (`read_vtables.py --vt 1004c06c`) |
| Apply | vt+0x48 `0x1000b7d0` | CanZone at `0x1000b7f3` (false -> tool+0x38 = 1), cost -> tool+0x34, funds test `0x1003f621` (-> tool+0x39). Neither flag set: PlaceZone at `0x1000b8cc`, else refusal message 0x1e / no funds 0x20 `[CONFIRMED @ 0x1000b7d0, disassembly]`. sc3undo wraps this slot |
| cost | vt+0x4c `0x1000b931`, vt+0x50 `0x1000b973` | CanZone -> tool+0x34 (the cursor label), refusal -> +0x38, `0x1003f621` |
| CanZone | zone layer interface (object+0x10, vtable `0x1004d1e0`) +0x84 = `0x1003559f`, `thiscall(zoneType, rect6*, cost*)`, `ret 0xc` | per cell: zone == zoneType skipped; an occupant (city vt+0x11c vt+0x7c) other than flora 0x400 or power line 0x400000 + 0x800 rejects the cell (power lines add the per-tile price); city vt+0x13c vt+0x54(x, z) true rejects; a 1x1 rect also needs four equal corner heights. `*cost = unitPrice x counted + surcharge`. False when nothing counts, or cost > 0 and funds < cost `[CONFIRMED @ 0x1003559f]` |
| PlaceZone | +0x88 = `0x1003591f`, `thiscall(zoneType, rect6*, cost*, 0)`, `ret 0x10` | runs CanZone again through its own vtable (`0x10035a12`), then the same per-cell rule, removing only flora and power lines, writes the zone (+0x3c) and withdraws `unitPrice x placed + removals` |
| rect6 | 6 dwords `{x0<<8, z0<<8, y, x1<<8, z1<<8, y}`, cells inclusive, min/max sorted by `0x10036247` | |
| unit price | budget vt+0x58(category): 0 for 1/5/9, 1 for 2/6/10, 2 for 3/7/11, 3 landfill 17, 4 airport 14, 5 seaport 15, 6 DeZone 0 | `LAUNCH_CONTROL.md` 31.9.7. Measured in Berlin: $10 a cell for Res Low, $2 for DeZone |

Stock behaviour, measured in a `-Stock` Berlin game (CanZone called from Frida, `RESULTS.md` S): every zone tool,
DeZone included, refuses a building cell. A rect made only of zoned building cells returns false with cost 0. With some
empty cells, only those are zoned. Nothing is demolished and nothing is zoned under the buildings, so no later
abandonment or redevelopment follows. DeZone leaves the buildings standing, still zoned.

## 2. What the mod does

1. Slots +0x84 and +0x88 of the interface vtable `0x1004d1e0` are wrapped. Only calls whose return address is inside the
   zone tool (`0x1000b7d0..0x1000b9d2`: Apply and the two cost slots) change. PlaceZone's own inner CanZone, scripts
   and every other caller stay stock. sc3undo wraps +0x38 / +0x3c of the same vtable, a different pair of slots.
2. A cell is TAKEN when the stock would not skip it (its zone differs from the tool's), the city vt+0x13c vt+0x54 test
   passes, and its occupant is a zoned building (the PLOPOVER test: GeomFlag 0x100, CanUserRemove, zone 1..11 under its
   first cell) whose class differs from the tool's (R 1-3, C 5-7, I 9-11), or the tool is DeZone. Each building counts
   once, its bulldozing = per-tile price (budget vt+0x58(7)) x footprint, what the bulldozer charges.
3. CanZone: stock first, then total = stock cost + unit price x taken cells + bulldozing, ok = (stock ok or some taken
   cell) and funds >= total. The cursor label shows that total, and the stock red preview / "no funds" cover it.
4. PlaceZone: the same set again, funds test, each building removed through `rl_remove` (demolition layer vt+0x6c, no
   rubble, no charge), the stock PlaceZone then zones the freed cells and charges their zoning, then the bulldozing is
   withdrawn (budget vt+0x14). This runs inside tool Apply: sc3undo makes it one entry and one undo restores the
   buildings and the zones and refunds the whole price (measured, `RESULTS.md` T3).

Not touched, as stock: civic, reward, landmark and plopped buildings (zone 22 or 0 under them), network pieces, and
airport / seaport / landfill both ways. Those tools (14 / 15 / 17) take no building, and their own buildings sit on
14 / 15 / 17, outside 1..11, so no zone tool takes them. Allowing them is one line in `zd_collect` (`tc` for 14 / 15 /
17, or the zone range in `ro_zoned`).

A building that reaches outside the drag is removed whole and only the cells inside the drag get the new zone. Its
other cells keep their old zone, empty.

## 3. Switch choice

The existing checkbox, not a new "Zonificar demuele" row. "Construir sobre zonas" already means "an action over zoned
buildings demolishes them" for placed buildings (PLOPOVER) and network drags (ROADOVER). Zoning is the third case of
that rule. A separate row is a few lines in the mods page block (`MP_BLD_OVER` pattern) if the owner wants them apart.

## 4. Not covered

- The zone tool's single-cell click (1x1 rect) also needs level corners in stock. A building usually sits on levelled
  ground. Not run.
- PlaceZone (multi-cell) de-zones and skips a cell whose four corner heights differ (`0x10035bd0` area). A taken
  building on such a cell is demolished and that cell ends at zone 0. Not seen in the tests.
- Calling PlaceZone directly from Frida (`zonedemo_probe.py placezone`) returned true and wrote nothing, on building
  cells and on empty cells alike. Its cause was not isolated. The in-game tool path works (`RESULTS.md`), so the probe's
  `placezone` verb is not evidence of anything.
- Undo of T1 (sim running): sc3undo records an entry only while paused, so the running-sim case has no undo, as for
  every tool.
