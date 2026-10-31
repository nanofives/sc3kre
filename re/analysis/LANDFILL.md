# Landfill and garbage: how it works, and options for independent landfills (child/landfill, 2026-10-30)

Owner request 2026-10-30: "Each landfill should be independent, and it should be possible to empty one."
Owner choice the same day: A2 + E1 with the A1 readout (section 3). Built as `sc3landfill.dll` plus a LANDFILL block in
sc3resize's query dialog, section 4. Results: `verify/landfill/RESULTS.md`.

Modules: SIMECO.DLL (`cSC3PollutionLayer`, the garbage ledger and the per-cell garbage map, plus the garbage valve),
SIMRCI.DLL (the landfill zone developer, iOS `goLandfillDeveloper`). Addresses are Ghidra VAs of each DLL (base
`0x10000000`). iOS names are `[iOS-HINT]` until an SC3U body confirms them, and every one used below has been.

## 1. Summary

- **Fill is already per cell.** Every landfill cell holds its own garbage amount, 0..32767 (`0x7fff`), in the low 15
  bits of the pollution layer's garbage cell map. Bit `0x8000` of the same cell is the ACTIVE LANDFILL flag.
- **Capacity is one city-wide pool.** The garbage valve (SIMECO vtable `0x1001bdfc`) holds the city's free landfill
  room at `+0x10` and the garbage waiting to be put down at `+0x0c`. Producers anywhere in the city draw on that one
  number. A landfill zone has no capacity, owner or service area of its own.
- **Where garbage lands has no link to where it came from.** The developer puts waiting garbage onto the cells of one
  city-wide heap list, whichever landfill those heaps are in.
- **A cell is "full" at 32767.** When the pool has no room left, garbage that is not recycled, burned, converted or
  exported stays on the producing cells as standing garbage (up to 32767 per cell). That is what the garbage map shows
  and what the advisors complain about.
- **Garbage decays.** Each landfill cell loses `fill * LandfillDecayRate` per update (at least 1), and the room comes
  back to the pool. When a cell reaches 0 its heap art occupant is removed.

Measured game-side (Craterville, 3 landfills, 115 cells, `re/sessions/STATUS_landfill.md` has the run):

| zone (first cell) | cells | fill | capacity | fill % |
|---|---:|---:|---:|---:|
| (61, 227) | 27 | 6,770 | 884,709 | 0.8 |
| (71, 222) | 56 | 1,049,841 | 1,834,952 | 57.2 |
| (83, 226) | 32 | 377,319 | 1,048,544 | 36.0 |

At two separate instants, available capacity was exactly total capacity minus the sum of the fills on active cells
(3,768,205 - 1,389,703 = 2,378,502, then 3,768,205 - 1,383,181 = 2,385,024). The pool is the sum of the cells' room,
and the bookkeeping is exact.

## 2. Mechanism with RVAs

### 2.1 The per-cell garbage map (SIMECO, `cISC3PollutionLayer`, vtable `0x1001b984`, city `+0xd4`)

| slot | RVA | what it does |
|---:|---|---|
| 24 `GetGarbageValue(x, z, &out)` | `0x10008e3a` | cell map `this+0x128` vt+0x34, `out = cell & 0x7fff` `[CONFIRMED @ 0x10008e3a]` |
| 40 `SetGarbageValue(x, z, v)` | `0x10009151` | clamps `v` to `0x7fff`, keeps bit `0x8000`, writes through vt+0x3c `[CONFIRMED @ 0x10009151]` |
| 41 `GetTotalLandfillCapacity()` | `0x1000a719` | `this+0x468 * 0x7fff`, where `+0x468` = active landfill cell count `[CONFIRMED @ 0x1000a719]` |
| 42 `GetAvailableLandfillCapacity()` | `0x100093ba` | garbage valve (`this+0x13c`) vt+0x2c = valve `+0x10` `[CONFIRMED @ 0x100093ba, 0x100185ee]` |
| 46..52 totals, 53..59 last month | `0x1000a75d..`, `0x100091a5..` | int64 ledger: produced, imported, exported, recycled, incinerated, converted to energy, landfilled (GZCOM_INTERFACE_CATALOGUE §15) |
| 65 `IsActiveLandfill(x, z)` | `0x100093c5` | `cell >> 15` `[CONFIRMED @ 0x100093c5]` |
| 66 `SetIsActiveLandfill(x, z, on)` | `0x100093ec` | sets only if the zone byte is `0x11` (landfill), ORs/ANDs `0x8000`, `+0x468` +1/-1 `[CONFIRMED @ 0x100093ec]` |
| 67 `GarbagePutInLandfill(n)` | `0x1000a7ea` | adds `n` to the int64 "landfilled" ledger total `[CONFIRMED @ 0x1000a7ea]` |

Game-side: the vtable at city `+0xd4` is `0x1001b984` and slots 24/41/42/65 resolve to the RVAs above (Frida, both
cities). The game cell `(x, z)` = `(n-1-y, x)` of the save zone raster as read by `re/tools/city_write.py`
(101 of 101 Frankfurt landfill cells match under that mapping, 0 under the identity).

### 2.2 The garbage valve (SIMECO, ctor `0x1000a32e`, vtable `0x1001bdfc`, pollution layer `this+0x13c`) `[iOS-HINT goGarbageValve, confirmed by body shape]`

| field / slot | RVA | meaning |
|---|---|---|
| `+0x0c` | | garbage accepted but not yet put on a landfill cell ("supply", iOS `+0x58`) |
| `+0x10` | | free landfill room ("demand", iOS `+0x5c`) |
| vt+0x28 | `0x100182ce` | returns `+0x0c` |
| vt+0x2c | `0x100185ee` | returns `+0x10` |
| vt+0x30 | `0x1000a344` | `+0x10 - +0x0c`, clamped to `[+0x28, +0x24]`: room still free after the waiting garbage |
| vt+0x40 | `0x1000a376` | `+0x0c += n` (AddToSupplyValue) |
| vt+0x44 | `0x1000a392` | `+0x10 += n` (AddToDemandValue) |

### 2.3 Where garbage comes from and where it goes (SIMECO tick `0x10008249`, router `0x100094a2`)

The tick walks the map in 2x2 blocks (block origin at layer `param_1[0x123]`, `param_1[0x124]`). Per non-landfill
cell (zone byte `!= 0x11`) it computes produced garbage from the block's input maps (with the ordinance modifiers
of SIMECO.md §5), adds the cell's standing garbage, clears the cell, and calls the router with that amount
`[CONFIRMED @ 0x10008249]`. The router drains it in order `[CONFIRMED @ 0x100094a2]`:

1. recycling reserve (`*param_3`), ledger `+0x470`
2. incinerator reserve (`*param_2`), ledger `+0x468`
3. **landfill: valve vt+0x30 (room after waiting garbage), then vt+0x40 adds the amount to the waiting garbage.**
   This is the only landfill check, and it looks at the city-wide number.
4. neighbour deal object `+0x4c` vt+0x8c(4): if a garbage export deal exists, all the rest goes there, ledger `+0x458`
5. abduction: up to `GarbageAbductionAmount` (`DAT_10020270`) minus `+0x480`

Whatever the router does not take goes back onto the producing cell as standing garbage (capped at `0x7fff`, the
excess goes to the valve) `[CONFIRMED @ 0x10008249, the iVar5 branch after the router call]`. If the valve's room
has gone negative, the tick moves garbage back out of the valve onto the streets.

In the same tick, a cell whose zone byte is no longer `0x11` but still carries the active bit has its bit cleared
and the valve's room cut by `0x7fff` (vt+0x44 with `0xffff8001`) `[CONFIRMED @ 0x10008249]`. That is the dezone or
bulldoze path.

### 2.4 The landfill developer (SIMRCI, ctor `0x100194cf`, init `0x10019843`) `[iOS-HINT goLandfillDeveloper]`

Fields: `+0x3c` garbage valve, `+0x44` occupant manager, `+0x48` zone layer, `+0x4c` pollution layer (QI
`0x80a814ac`), `+0x5c` heap list (entries hold the cell at `[2]`, `[3]`), `+0x64..+0x78` `LandfillRules0..5.t`,
`+0x7c` `LandfillStartRule.t` `[CONFIRMED @ 0x10019843]`. `LandfillDecayRate` from `[LandfillZoneDeveloper]` in
`Sys\SC3Tune.INI`, capped at 10000, times a float constant into `_DAT_10057930` `[CONFIRMED @ 0x100194cf]`.

| SC3U RVA | iOS name | what it does |
|---|---|---|
| `0x10019de1` | `UpdateCell` | per landfill cell: active check, decay, set active, then **put waiting garbage on the heap cells** (below) `[CONFIRMED @ 0x10019de1]` |
| `0x1001aa11` | `isCellActive` | road and trip checks for the cell (tracker name `sc3_zonedev_check_road_frontage`) |
| `0x1001a549` | `decay` | `fill -= max(1, fill * rate)`; at 0 removes the occupant (occupant manager vt+0x4c) and the heap entry; if active, valve vt+0x44(+decayed) `[CONFIRMED @ 0x1001a549]` |
| `0x1001accb` | `setCellActive` | SetIsActiveLandfill on/off and valve vt+0x44(+/- room), room = `0x1001a9e5` `[CONFIRMED @ 0x1001accb]` |
| `0x1001a9e5` | (room) | `0x7fff - fill`, or 0 `[CONFIRMED @ 0x1001a9e5]` |
| `0x1001a447` | `createNewHeap` | called when the heap list is empty and the cell is active |
| `0x1001a62f` | `findNewDumpPoint` | next cell for the current heap (tracker name `sc3_zonedev_find_growable_neighbor`) |

The deposit step inside `0x10019de1`: `pending = valve vt+0x28` (`+0x0c`). While `pending > 0`, for each heap in the
city-wide list `+0x5c`, if the heap's cell is active: `d = min(pending, room)`, `SetGarbageValue(fill + d)`, valve
vt+0x40(`-d`) and vt+0x44(`-d`), pollution `GarbagePutInLandfill(d)`, and place the heap occupant (key
`{0x207edc0e, 0x57e, 0x2716}`, zone layer vt+100) if the cell has none `[CONFIRMED @ 0x10019de1]`. Nothing in this
loop looks at which landfill the cell belongs to or where the garbage was made.

**Art.** Heap art is landfill-tile occupants: key `{0x207edc0e, 0x57e, id}`, TypeId `0x3232`, placed through the zone
layer (`+0x48` vt+100). After the deposit loop, every changed cell gets a 5x5 tile neighbourhood (`0x1001a25d`: for
each neighbour, an occupant of type `0x3232` contributes its tile identity, an empty or flag-`0x400` cell an empty
entry). The six rule sets `LandfillRules0..5.t` (`+0x64..+0x78`) are tried in order through `0x100409eb`, the first
match with a non-empty result is placed by `0x1001a186` (iOS `insertLandfillTile`), and `LandfillStartRule.t`
(`+0x7c`) is the fallback `[CONFIRMED @ 0x10019de1, 0x1001a25d, 0x1001a186]`. The rules read neighbouring tiles, not
the fill value. A new heap starts as the piece `0x2716` (`0x1001a447`). When decay takes a cell to 0 it calls the
occupant manager's `RemoveOccupantAtCell` (SIMGEOM slot 19, `0x1000e310`) through `+0x44` vt+0x4c, and the cell shows
the bare landfill zone `[CONFIRMED @ 0x1001a549]`. That is the emptied-cell art: no rule needs to run.

### 2.5 Save file

- **The per-cell garbage map, active bits included, is saved** in the SIMECO pollution section (`0xc0a81498`,
  CITY_SAVE.md). Writer `0x10006abb` calls the cell map's vt+0x28 at `this+0x124`, reader `0x100062b4` calls vt+0x24
  (`this` = layer interface + 4, so this is the interface's `+0x128` map) `[CONFIRMED @ 0x10006abb:92, 0x100062b4:66]`.
  If that block fails to read, the reader rebuilds the active count by scanning IsActiveLandfill over the grid
  `[CONFIRMED @ 0x100062b4:257-280]`.
- The ledger totals are in the same section's scalar block (`this+0xcc..0x45c`, SIMECO_CLUSTER1).
- Heap art is ordinary occupants (key `{0x207edc0e, 0x57e, 0x2716}`) in the occupant layer, saved like any building.
- No per-landfill identity exists in the save, and none is needed: a landfill is a group of zone-17 cells.

So a mod that only changes fills through `SetGarbageValue` and the valve's own adders writes nothing a stock game
cannot read.

### 2.6 Who reads it (UI, advisors, data views)

From the tracker and SIMECO notes:
- City totals through the pollution-layer slots 41/42 and the ledger slots 46..59. Budget and advisors read these.
- SIMMISC `0x1000d398` `sc3_query_build_garbage_report`: advisor text built from landfill/garbage counts.
- SIMECO `0x1000c95c` data-view categories 1 and 2 on tile type `0x11`: garbage tonnage (`this+0x1c` vt+0xa4 x
  GarbageScalingFactor) and shortfall % (vt+0xa4 / vt+0xa8) (SIMECO_PASS2).
- SIMECO `0x10008eab` IsGarbageAccumulated: cell value against `GarbagePollutedThreshold`, the garbage map.
- SIMADV environment advisor `GARBAGE_BUILDINGS` list (SIMADV.md).

None of them has a per-landfill number. A per-landfill readout has to be added (A1).

## 3. What "independent" can mean, and the options

The stock game already has per-cell fill. What it lacks is a per-landfill identity. A landfill here means one
4-connected group of landfill-zone cells (`zone == 17`), recomputed from the zone raster on load and whenever a cell
turns active or inactive (`0x1001accb`). Nothing new needs saving to know which cells form which landfill.

Counts in the shipped cities: Berlin 8 separate landfills, Craterville 3, Liverpool 3, Frankfurt / Madrid / Seoul 2,
the rest 1.

### (a) Independence

**A1. Per-landfill view only.** The shared pool stays. Querying a landfill cell shows that landfill's fill, room and
percentage next to the city totals. Effort: half a day, inside the E1 work. Risk: low. It does not change gameplay:
garbage still lands wherever the heap list points, and emptying one landfill just adds room to the shared pool.

**A2. Each landfill serves its own area (recommended).** Each producing 2x2 block sends its garbage to the nearest
landfill (straight-line distance to the landfill's nearest cell) that still has room, within an optional maximum
distance (`max_distance` in the ini, 0 = no limit). If none has room, the garbage stays on the street as it does today
when the pool is full. The garbage then lands on that landfill's own cells.
- Mechanics: hook the landfill step of the router (`0x100094a2`, the valve vt+0x30 / vt+0x40 pair) to check and charge
  the chosen landfill's own room, using the block origin the tick is on. Keep a per-landfill waiting amount. Hook the
  deposit loop in `0x10019de1` so a cell only takes its own landfill's waiting garbage.
- The valve keeps the city totals (sum over landfills), so the budget, advisors, graphs and garbage map keep reading
  the same numbers.
- Effort: 2 to 3 days. Risks: the valve bookkeeping must stay exact (measured, so checkable every tick in a debug log).
  A landfill with no heap yet must still start one (`0x1001a447` runs from a cell's own update). A city with one
  landfill behaves as stock.
- Saves: per-landfill waiting garbage is transient (it is put down within a few updates). On load it is re-split by
  nearest landfill. Without the mod the save loads as stock and the pool is shared again.

**A3. Service area by road connection.** Like A2, but a landfill only serves blocks reachable on the same road network
(connected component of the road graph, or a trip within N tiles). Effort: 4 to 5 days. Risks: connectivity has to be
rebuilt on every road change, plus the cost of computing it on 1024 maps. A2 with `max_distance` gets most of the
effect for half the work.

### (b) Emptying one landfill

**E1. "Vaciar vertedero" button in the query dialog (recommended).** Shown only when the queried cell is a landfill
cell, next to "Copiar ID" (sc3resize QUERYID button recipe, `QUERY_ID.md` §1). One click empties every cell of that
landfill the way `decay` does at 0, all at once: `SetGarbageValue(0)`, valve vt+0x44(+fill) on active cells, remove the
heap occupants and heap-list entries, re-tile to the start art. The cost is charged to the budget at `cost_per_ton` from
the ini. The default is the owner's call: 0, a flat amount per landfill, or the garbage export deal rate
(`DEAL_RATE_CONSTANTS`, SIMMISC.md). If the city cannot pay, the button says so and does nothing.
- Effort: 1 to 1.5 days. Risks: the re-tile call for the start art still needs reading, and the heap occupants must be
  removed through the occupant manager (the same call decay makes), not by poking memory.
- Saves: writes only stock fields, so a save made after emptying loads the same without the mod.

**E2. Close and empty gradually.** The button switches a landfill to "emptying": it stops taking garbage and loses
`X` tons a month at `Y` per ton until empty, then reopens. Effort: 2 days. Needs per-landfill state kept in a small
sidecar file next to the save, keyed by the landfill's first cell. Without the mod the landfill just works as stock.

**E3. A toolbar tool.** Click a landfill with a new "Vaciar" tool. Effort: 3 days or more (new tool slot, cursor, art).
No gameplay gain over E1.

### Recommendation

A2 + E1, with A1's per-landfill readout included in the query dialog. Each block behind its own
`SC3RESIZE_LANDFILL=0` / `[landfill]` ini switch, so emptying and independent service can be switched off one at a
time.

Open calls for the owner: the price of emptying (free, per ton, or the export rate), and whether A2 should have a
maximum service distance by default.

## 4. Built (Phase B, 2026-10-30)

`re/harness/src/sc3landfill.c` -> `sc3landfill.dll` (new mod, in the loader's default list after sc3autosave), and a
LANDFILL block in `sc3resize.c` (query dialog). Config `landfill.ini` beside the DLL, written with these defaults when
missing:

```
[landfill]
independent=1          ; A2. 0 = stock router and deposit (SC3LANDFILL_INDEPENDENT=0)
max_distance=0         ; cells; 0 = no limit (nearest landfill with room, whole city)
empty=1                ; E1 button. 0 = no button, readout only (SC3LANDFILL_EMPTY=0)
fee_per_1000_tons=50   ; SC3LANDFILL_FEE
```

`SC3LANDFILL=0` patches nothing (stock game, no readout). `SC3RESIZE_LANDFILL=0` removes the dialog lines and button.

**Fee default.** The game's own price for getting rid of garbage is the neighbour export deal, `GARBAGE_EXPORT_RATE=5`
(`NeighborDeals.ini`). The deal cost is `q * rate / 1000` for `q` garbage units `[CONFIRMED @ SIMMISC 0x1001761c]`, so
$5 per 1,000 units. One unit is 0.1 t (`GarbageScalingFactor` 100 x `0.001f` at SIMECO `0x1001bdec`), and the game's
own query panel confirms the scale: Craterville's "Capacidad total: 376,821 ton." = 115 cells x 32,767 x 0.1. So $5 per
100 t = **$50 per 1,000 t**. A full cell (3,277 t) costs $164. Craterville's 56-cell landfill at 54% cost $4,997.

**A2, independent landfills.**
- Landfill = 4-connected group of zone-17 cells, relabelled when the active landfill count (pollution iface `+0x468`)
  changes. Each keeps room (sum of `0x7fff - fill` over its active cells) and pending (accepted, not yet put down).
- The router SIMECO `0x100094a2` is replaced by an exact C copy (entry `jmp`; head bytes and the tick's three call
  sites checked first). Its landfill step charges the nearest landfill with room (distance from the tick's 2x2 block,
  `+0x48c/+0x490`, to the landfill's bounding box), then the next. The import and end-pass calls (return addresses
  `0x10008492`, `0x10008c5c`) carry no cell and go to the freest landfill.
- `UpdateCell` SIMRCI `0x10019de1` is wrapped (trampoline replays `mov eax, imm32`). For a cell of landfill g, the
  other landfills' heaps are unlinked, valve `+0x0c` is set to g's pending, the stock function runs, then the list and
  valve are put back and g's pending drops by what was put down. A landfill with no heap gets one from the stock code
  (it starts a heap when the visible list is empty).
- Valve `+0x0c` is reconciled against the sum of pendings every update: garbage the tick pushes in directly (unrouted
  imports, cells over `0x7fff`) is assigned to the cell's landfill, and garbage pulled out is taken from the largest.
- Router and UpdateCell run on the sim thread (measured 4876, the window thread was 20540), so no lock is needed.

**E1, emptying.** Per cell with fill f: `SetGarbageValue(1)`, valve vt+0x44(f - 1) if active, then the game's own decay
`0x1001a549`, which takes the last unit, removes the heap occupant and heap entries and returns the unit to the valve.
The fee is withdrawn through the budget (vt+0x14), and the request is refused when funds are short. The sim is stopped
while the query dialog is open: city `+0x144` = 2 (hold), `+0x140` = 0 (measured). The empty then runs on the UI
thread. If the sim were running it would be queued to the next UpdateCell.

**Readout (A1).** Three lines in the query dialog of any landfill cell, flooded from the queried cell on the UI thread:
"Este vertedero: 54% completo" / "99,939 de 183,495 ton. (libre 83,556)" / "Vaciarlo cuesta $4,997", plus a
"(N sin acceso)" note when some cells are inactive. Numbers use commas and "ton." like the game's own panel above them.

