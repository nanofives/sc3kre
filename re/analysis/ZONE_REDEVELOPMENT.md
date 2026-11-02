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
