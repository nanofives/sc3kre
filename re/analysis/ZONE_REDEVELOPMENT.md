# Zone redevelopment: why working buildings keep getting rebuilt (task churn, 2026-11-01)

Owner question: with demand, buildings are constantly rebuilt even when they already work. Why?

Short answer: every zoned lot is evaluated once per ~30 game days, and with demand > 0 a working building is
replaced on three random rolls. One of them ("anarchy") rebuilds it as the **same lot class** for no reason
other than the roll. Anarchy is the largest source of residential rebuilds in a mature city (Moscow, below).
sc3simrun CHURN turns it off.

## 1. How often each lot is evaluated `[CONFIRMED @ SIMRCI 0x10031499, 0x100314ae, 0x100314f0, 0x1003372a]`

- Zone layer vtable `0x1004d140`: slot `0x10031499` = `Simulate(interval)`, runs `FUN_1003372a` only when
  interval == 2. The next slot `0x100314ae` (iOS `MinimumExecutionInterval`) returns 2.
  iOS names the same pair `goZoneLayer::Simulate` -> `doDailySim` `[iOS-HINT]`.
- `FUN_1003372a` evaluates `layer+0x270` tiles per call. Setup `FUN_100314f0` sets that to `W*H/30`
  (`this+0x25c`, `this` = layer+0x14). Tiles come from the traversal object at layer+0x280 (`FUN_10031a78`,
  PERFORMANCE.md Finding 9); when a pass ends it re-arms and the same call continues.
- For each tile it calls the zone's developer, slot `+0x18` of the developer's second vtable
  (res `0x1004cd38`, com `0x1004c2f4`, ind `0x1004c528`): `0x10028f12` / `0x1000fd53` / `0x10017fc0`.
  A multi-tile building returns 0 at once on every tile except its anchor, so **each building is evaluated
  once per pass**.
- Runtime (re/tools/churn_probe.py, Moscow 256x256, speed 3): 134 zone ticks in 134 game days, 2,184 tiles
  each tick = 65,536 / 30. **One full pass every 30 game days**, the same for any map size (W*H/30 per day;
  sc3bigcity TRAVERSE keeps that rule).

## 2. What the evaluator does with a built, working lot (res `0x10028f12`, com `0x1000fd53` same shape)

Order of tests for a completed building (state 1) that passes the service/transport gates:

1. Demand < 0: random demolish (status 3).
2. Land value under half the building's floor: try a cheaper class (`0x100297fb`). **That picker always returns
   0** (it computes a candidate and drops it), so `LowerLandValueRedevelopmentPct` never applies; the lot is
   demolished (status 2) and refilled later `[CONFIRMED @ 0x100297fb; ind 0x10018e45]`.
3. Demand > 0 and a higher-value class fits the cell (`0x1002971a`): `rand(100) < HigherLandValueRedevelopmentPct`.
4. Else, only if the tile byte `local_24` (`+0x74` vt `+0x48`, meaning `[UNCERTAIN]`; when it is 0 the class
   pickers only accept classes whose record byte 0 is 1) is set:
   a. demand > 0 and `rand(cap/x) < demand`: density+1 class (`0x100298af`), `rand(100) <
      HigherDensityRedevelopmentPct`. The pass ends here whatever that roll gives.
   b. otherwise, demand > 0: **anarchy**, `rand(10000) < AnarchyFactor`, new class = current class.

Steps 3-4 call develop (res `0x10029666`, com `0x1001049e`, ind `0x10018bc1`, args `coords*, newClass,
oldClass, ...`). The cmp sites: res `0x1002946e / 0x100294cf / 0x10029503`, com `0x100102a6 / 0x10010307 /
0x1001033b`, ind `0x10018749 / 0x100187a2 / 0x100187cb`, each `3B 05 <abs32>`.

SC3Tune.INI values: AnarchyFactor res 300 (3% per pass), com 100, ind 100 (1%). Upgrade and density 30%.

## 3. Industrial (`0x10017fc0`, tunables `DAT_100576cc..0x10057717`, ctor `0x10016290`)

Same skeleton and the same three rolls (`d8` higher value 30, `e0` density 30, `e4` anarchy 100), plus:

- Lower-value picker `0x10018e45` has the same always-0 bug. `LowerLandValueRedevelopmentPct` (10) never applies.
- Lot class `0x2454` (by the Ag keys, farms `[UNCERTAIN]`: the class id is not tied to a name) is kept apart:
  it is removed (status 7) when the tile's two pollution reads (`+0xc0` vt `+0x58` / `+0x5c`) exceed
  `MaxAgAirPollution` / `MaxAgWaterPollution` (451), and in the low-value / negative-demand paths it is handed
  to `+0x9c` vt `+0x5c` instead of being demolished. New ag lots are allowed only while both reads are at or
  under `MinAg*Pollution` (450).
- A clean-industry year window (`MinCleanIndFlatYear` 2100 .. `MaxCleanIndFlatYear` 2200, `FUN_10018843`) and the
  ordinance byte effects (`DAT_1005770c..`) feed the class choice. Not read further here.

## 4. Measured churn and the CHURN mod

Moscow, 120 s at speed 3 each run, develop calls that succeeded:

| | stock (179 days) | CHURN default (180 days) |
|---|---|---|
| res same-class rebuild (anarchy) | 343 | 0 |
| res upgrade | 170 | 130 |
| res new lot | 119 | 96 |
| com same-class rebuild | 133 | 0 |
| com upgrade | 394 | 145 |
| com new lot | 154 | 16 |
| ind (not hooked in the stock run) | | 0 same, 8 upgrade, 4 new |

Two different games, so only the anarchy row is a controlled result (it is zero by construction).

sc3simrun CHURN: `simrun.ini [churn]` `anarchy_res|com|ind` (default 0), `upgrade_X`, `density_X` (default -1 =
the game's value), `enabled=1`; `SC3SIMRUN_CHURN=0` = stock. Each enabled site's operand is repointed at the
mod's own DWORD after a byte check; log lines `CHURN>`.

## 5. Abandonment: what takes a standing R/C/I building down (task abandon, 2026-11-15)

GitHub issue #3 (Sandbox mode, gentler abandonment). Static read of the three evaluators branch by branch, then a
live run (Berlin 256x256, speed 3, 179 game days, `re/tools/abandon_probe.py`, read-only Frida;
`verify/abandon/probe_berlin_stock_1.json`). This corrects §2 above where they differ.

### 5.1 The evaluator's inputs `[CONFIRMED @ 0x10028864 (members), live module of each slot]`

Members are city layers, stored by the developer's init (res `0x10028864`, slot `+0xc`) from city slots
(`cISC3City` CodeView names). Res and com use the same offsets; ind keeps its own (`0x10017649`).

| res/com | ind | city slot | read in the evaluator | live target |
|---|---|---|---|---|
| `+0x6c` | `+0x9c` | `BuildingLayer` | `vt+0x5c(bldg)` removes a building (state-4 lots; ind farms) | |
| `+0x70` | `+0xa0` | `PowerLayer` | `vt+0x34(x, z, &byte)` powered | SIMUTIL `0x10005e41` |
| `+0x74` | `+0xa4` | `PlumbingLayer` | `vt+0x48(x, z)` watered byte (iOS `IsWatered`) | SIMUTIL `0x1000df02` |
| `+0x78` | `+0xa8` | `SurfaceOccupantManager` | `vt+0x7c GetOccupantAtCell` | |
| `+0x7c` | `+0xac` | demand valve 3000 / 5000 / 8000 (`0x10028c49`) | `vt+0x30` value, `+0x38` max, `+0x3c` min, `+0x20` id | |
| `+0x80` | `+0xb0` | `ZoneLayer` (vtable `0x1004d1e0`) | slot 27 `IsNearTransport(coords, MaxDistFromTransport + ord)`, slot 30 `GetFilledDemand`, slot 25 `PlaceBuilding` | SIMRCI `0x100330b7`, `0x1003306d` |
| `+0x84` | `+0xb4` | `LandValueLayer` | `vt+0x34` land value byte | |
| `+0x88` | `+0xbc` | `TrafficLayer` | `vt+0x68(x, z)` trip result | SimTransit `0x10006965` |
| `+0x8c` | `+0xc0` | `PollutionLayer` | `vt+0x54` radioactive (iOS `IsRadioactive`), `vt+0x6c` garbage (iOS `IsGarbageAccumulated`); ind also `vt+0x58/+0x5c` air / water | SIMECO `0x10008db8`, `0x10008eab` |
| `+0x90` | `+0xc4` | `OrdinanceLayer` | `vt+0xc(0xa2bf1de5)`: +1 to MaxDistFromTransport when on | |

**The `+0x88 vt+0x68` read is the trip result** `[CONFIRMED @ SimTransit 0x10006965, live slot target]`: grid
`+0x7c` bit clear (no trip tried from the cell) returns 2, else grid `+0x80` bit set (trip succeeded) returns 0,
else 1 (trip failed). iOS twin `goTrafficLayer::GetTripSuccess`. Branch (b) fires on `== 1`, a failed trip.

### 5.2 Building state and the flag `[CONFIRMED live]`

The building is the occupant's QI `0xe0faadc7` view (SIMGEOM vtable `0x1002bb80`); `vt+0x4c` (`0x10024d48`,
byte `+0x1c`) is its state. `sc3_resdev_post_state_change` (`0x10029a38`, ind copy `0x100191fe`) calls ZoneLayer
slot 25 `PlaceBuilding(attrib = bldg vt+0x60, coords, flags, rotation, 1)`: slot 26 (`0x10032dfc`) removes the
occupants in the footprint and **creates a new occupant from the same attrib**, then sets `flags` on it
(`vt+0x50`) and inserts it. So the flag is the new building's state, plus the `0x100` / `0x200` occupancy bits
the caller carries (`0x100` = garbage, from pollution `vt+0x6c`).

Measured, 400 posts, the cell re-read after each call (always a new object, always the same attrib):

| flags | state before -> after | from | count |
|---|---|---|---|
| `2` | 1 -> 2 | (b), (c), (d) | 98 |
| `1` | 4 -> 1 | construction finished: `rand(x * 100) < ConstructionTimeFactor` (`DAT_1005801c`) | 262 |
| `1` | 2 -> 1 | abandoned building re-occupied (state-2 branch, the class picker returns the same class) | 25 |

So **flag 2 = abandon**, not demolish: state 1 occupied, 2 abandoned, 4 under construction. The zone layer's
`GetAbandonedTileCount` (slot 21, `+0x15c`) moved 64 -> 0 -> 3 over the run. An abandoned building comes back two
ways: with power, transport, no failed trip, not radioactive and raw and net demand > 0, the class picker runs;
the same class -> flag 1 (re-occupied), another class -> develop a new building (res `0x10029666`). Removal
(`BuildingLayer vt+0x5c`) happens only to state-4 lots with no class record and to industrial farms (5.4).

### 5.3 Residential `0x10028f12` and commercial `0x1000fd53`, state 1

Identical code apart from frame offsets and one record byte. Order:

| | test | action | status |
|---|---|---|---|
| (a) | radioactive (`+0x8c vt+0x54`) | flag 2, no roll | 1 |
| (b) | unpowered, OR not `IsNearTransport`, OR trip failed (`== 1`), OR (not watered AND class density byte > 1) | `rand(100) < NoServicePercentage / x` -> flag 2 | 4 unpowered, 5 water, 6 transport or trip |
| (c) | raw demand `vt+0x30 < 0` | `rand(-min) < -(net / x)` -> flag 2. net = demand - `GetFilledDemand` | 3 |
| (d) | lot class known and land value < class minimum LV / 2 (record byte 2 res, byte 1 com: the parsers `0x10028ce0` / `0x1000fb21` store minLV there) | `pick_lower_value` (always 0, §2) -> flag 2 | 2 |
| | else | redevelopment rolls of §2 (demand > 0 only) | |

Sites (call `rel32`): res (a) `0x1002934f`, (b) roll `0x1002951b` / post `0x1002953b`, (c) roll `0x1002939d` /
post `0x100293bc`, (d) post `0x1002942a`. Com (a) `0x10010187`, (b) `0x10010353` / `0x10010373`, (c) `0x100101d5`
/ `0x100101f4`, (d) `0x10010262`. NoServicePercentage: res `DAT_10058014` (15), com `DAT_1005753c` (35).

### 5.4 Industrial `0x10017fc0`, state 1

Same (a)-(d) with ind tunables (`DAT_100576cc` NoServicePercentage 30), plus farms. A farm here = lot class
`0x2454` whose attrib flags (QI `0x21183b00` `vt+0xbc`) have bits 8 and 10 set (`local_b`).

| | farm | non-farm |
|---|---|---|
| (a) radioactive | removed (`+0x9c vt+0x5c`, site `0x10018508`) when CanSimRemove and no `0x200` bit | flag 2 (`0x10018523`) |
| (b) no service | skipped | roll `0x10018557`, flag 2 (`0x1001857c`) |
| (p) class `0x2454` and air > MaxAgAirPollution or water > MaxAgWaterPollution | removed (`0x100185fb`), status 7 | flag 2 (`0x10018616`), status 7 |
| (c) negative demand | the roll is drawn, the post skipped | roll `0x10018630`, flag 2 (`0x10018656`) |
| (d) low land value | removed (`0x100186e7`) | flag 2 (`0x10018705`) |

### 5.5 The divisor x, and the demand roll

x = the building's attrib `vt+0x40` (bldg `vt+0x60` -> attrib, QI `0xe075ef51` view, SIMGEOM vtable `0x1002b7b0`,
slot `0x10023486` returns field `+0x24`) `[CONFIRMED @ SIMGEOM 0x10023486]`. CodeView names `cISC3OccupantAttrib`
`+0x40` `SizeInCellsX` and `+0x44` `SizeInCellsZ` [CV-HINT: the SIMGEOM vtable's interface is not identified]. Live,
x was 1, 2 or 3 and equal to `vt+0x44` on all 400 lots; iOS reads the same value as a `ushort` of the attrib.
So **x is the lot width in cells**: (b) and (c) divide the chance by it, the construction / recovery roll
multiplies its range by it, the density roll divides its range by it.

(c), worked: chance per pass = `(-net / x) / (-min)`. The valves read min -2000 / max 2000 for R, C and I. The gate
is the raw valve value (the HUD bar) but the roll uses net = value - filled demand, and filled demand can be
negative: Berlin industry read value -1680 with filled -1602..-1687, so net sat at -10..+7 most of the run and the
roll fired 87 times in 5,327 draws. Of the first 4,000 draws (days 0..40, the ones recorded one by one), 57
fired, 56 of them before day 30, all at net -1680..-735. A city whose HUD
shows strongly negative demand can abandon slowly or not at all once filled demand has caught up.

### 5.6 Not abandonment inputs

Crime: not read. Garbage: pollution `vt+0x6c` only toggles occupancy bit `0x100` (a re-post with the same state).
Pollution: radioactivity (a) for all three, air / water only for farms (p). Disasters (SIMDSTR) are separate.

## 6. Mods built on section 5 (sc3simrun, task abandon 2026-11-15)

**SANDBOX** (`simrun.ini [sandbox] enabled=0`, env `SC3SIMRUN_SANDBOX`, row "Sandbox: no abandonment"): the six
(b) / (c) roll calls (`0x1002951b`, `0x10010353`, `0x10018557`, `0x1002939d`, `0x100101d5`, `0x10018630`) go through a
stub that calls `cRZRandom::RandomUint32Uniform` `0x10039a9a` and, when the stock roll would fire, returns a value that
misses (`0xffffffff` for the unsigned (b) compare, `0x7fffffff` for the signed (c) compare); the game then carries on
as after a miss. The seven (a) / (d) / (p) post calls are skipped; where the game would next re-post the building
for a changed garbage bit (its byte at `[ebp+0xb]` res/com, `[ebp-1]` ind), the stub makes that re-post with state 1.
The three 14-byte farm removals become `push [ebp-0x10]; call stub`. Measured: `verify/abandon/RESULTS.md` (0
abandonments in 3 Berlin years and 1 Madrid year; population and jobs stay counted; industrial demand stays at the
valve minimum because filled demand no longer goes negative).

**GENTLE** (`[gentle] enabled=0 share_pct=25`, env `SC3SIMRUN_GENTLE`, `SC3SIMRUN_GENTLE_SHARE`, row "Gentler
abandonment"): at the three (c) roll calls, when the stock roll fires and the raw valve value (the RCI bar, not the
net value the roll uses) is at or above `min + (max - min) * share_pct / 100`, the roll is made to miss. Below that
line the stock roll is unchanged. With the valves at -2000..2000: 50 = stock, 25 = only below -1000 (the bar under
half of its negative side), 0 = never. Measured with 25 (`verify/abandon/RESULTS.md` M3): Berlin 2 years 332 -> 284
industrial negative-demand abandonments, London 1 year 276 -> 259, none left with the bar above -500 (stock: 80 and
30 there). Only industry went negative in the test cities.

**Not changed:** the always-0 lower-value pickers (`0x100297fb`, `0x10018e45`), owner decision 2026-11-15.
