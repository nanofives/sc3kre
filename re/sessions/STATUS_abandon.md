# STATUS: child abandon (round 2026-11-15, GitHub issue #3)

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Workspace `dev\abandon` (branch `child/abandon`, from main c65b8f5).

## Goal
1. Facts: what flag 2 does live, the R/C/I evaluators branch by branch, the divisor x, the `+0x88 vt+0x68` read.
2. Sandbox: no standing R/C/I building abandoned or removed by branches (a)-(d). Default off.
3. Gentler abandonment: the negative-demand roll (c) only below a share of the demand range. Default: owner call.

## Verdict + deciding RVAs (milestone 1, done)
- Flag 2 = abandon: `0x10029a38` / ind `0x100191fe` -> ZoneLayer slot 25 PlaceBuilding replaces the building with a new
  occupant of the same attrib in state 2. States: 1 occupied, 2 abandoned, 4 under construction (SIMGEOM `0x10024d48`).
- `+0x88 vt+0x68` = trip result, SimTransit `0x10006965` (2 untried, 0 ok, 1 failed). (b) fires on a failed trip.
- x = attrib `vt+0x40` = lot width in cells (SIMGEOM `0x1002285f`, CodeView SizeInCellsX hint, live 1..3).
- (c) gate = raw valve value < 0, roll = `rand(-min) < -(net / x)`, net = value - filled demand. Valves -2000..2000.
- Full table: `re/analysis/ZONE_REDEVELOPMENT.md` section 5.

## Proven game-side vs static only
- Live (Berlin, `verify/abandon/probe_berlin_stock_1.json`): flag 2 / flag 1 state transitions, x values, trip slot
  target, layer slot targets, valve ranges, (c) and (b) roll counts.
- Static only: the farm (class 0x2454) removal paths, radioactive (a), commercial (d) (none fired in the run).

## Milestone 2 (Sandbox): done
- sc3simrun SANDBOX block (16 sites, byte-checked), default off; simrun.ini [sandbox], env SC3SIMRUN_SANDBOX.
- "Activar mods" page: new default-off row type (env prefixed '+'), rows "Sandbox: sin abandono" and "Abandono mas
  suave" under a "Simulacion" heading in the left column. 7 languages.
- In game: Berlin 3 years / Madrid 1 year, off vs on: 786 / 2,728 abandonments -> 0. Population and jobs stay
  counted (ended higher in both cities). Industrial demand stays at the minimum with Sandbox. verify/abandon/RESULTS.md.

## Milestone 3 (Gentler abandonment): done, default waiting on the owner
- GENTLE gate on the raw valve (RCI bar), stock roll below the line. share_pct 25 = valve -1000 = bar -500.
- Stock: 24% (Berlin, 2 y) and 11% (London, 1 y) of negative-demand abandonments happen with the bar above -500.
  With 25: 0 above the line; totals 332 -> 284 and 276 -> 259. Proposed default share 25; on/off default = owner call.
- Broken lower-value picker (0x100297fb / 0x10018e45) noted, not changed (owner decision).

## Built
- `re/tools/abandon_probe.py` (Frida probe, read-only except the --tax lab option), `re/tools/abandon_report.py`.
- sc3simrun.dll, sc3resize.dll, sc3mods.dll in devbandon (inst / tree).

## Blocked on
- Owner call: Gentle default (on/off) and share_pct (proposed 25).

## Files owned
- `re/analysis/ZONE_REDEVELOPMENT.md` (sections 5, 6), `functions.csv` (8 rows), `re/tools/abandon_probe.py`,
  `re/tools/abandon_report.py`, `re/harness/src/sc3simrun.c` (SANDBOX + GENTLE block), `re/harness/src/sc3resize.c`
  (MODTOGGLE '+' rows), `re/harness/lang/*.txt` (3 keys), `README.md` (2 lines),
  MAIN `re/sessions/STATUS_abandon.md` (gitignored). MAIN `verify/abandon/` (untracked: probe logs).

## Game-harness need
- Own tree only (`dev\abandon\tree`), multi-instance. No `re/harness` binaries touched.

## Asks of other sessions
- none.
