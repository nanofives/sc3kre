# STATUS airsea (round 2026-11-19g)

## goal
Imported buildings that grow in airport and seaport zones: static RE of the airport / seaport developers' pick,
a proof in game (one new building in each zone, counts from saves, pictures), then kinds `airport` / `seaport` in
bldimport.py + the page, byte identity, run_all.sh passing.

## verdict + deciding RVA
**DONE. Works in game, data only, no mod code** (static, `re/analysis/PORT_PICK.md` in the worktree).
- Airport: airpark rule `0x2207d9ee` (family 3). AddFamily SIMRCI `0x10003022` puts every member with size 1 and
  (flag 0x100 or no piece type) into the filler list `+0x3c`, and ignores the Key weight. Apply `0x100032d1` draws a
  filler uniformly when no tower / terminal / hangar is placed. So an import = 1x1 copy of Parked Airplane 231 in
  family 3, weight = repeated Key lines.
- Seaport: dockyard rule `0xe2d3fd92` (family 27). AddFamily `0x1002bfec` pushes each member `weight` times into list
  `+4` (flag 0x100 clear) or `+0x10`; Apply `0x1002c12a` takes the record with LandUse `0x302a` (passed by
  `0x1002cc5b`) and draws 35% / 65% from the two lists on pier-served cells. Import = copy of 224 (1x1) or 240 (2x2).
- Runway family 2 is not a target: its filler list is read only at entry 0 (`0x1002b2f0`).

## built
- `bldimport.py`: kinds airport / seaport (PORTS, rule_families, port_table, target_of), plan / pack / list / check /
  preview. Weight of an airport = copies (max 20).
- `bldweb.js`: the same, transcribed. `classifier.html`: port lot suggestions and warnings.
- `make_testmodels.py --ports`: fuel depot (airport 1x1), container stack (seaport 1x1), warehouse (seaport 2x2), two
  entries that must be refused.
- golden case `ports` (golden_setup.py) + run_all.sh steps (golden.mjs and pagetest.mjs on ports).
- `port_clear.py`: test city = a city with its airpark and dockyard buildings dropped from the port zones.

## proven game-side vs static only
- **Game-side (verify/airsea/RESULTS.md):** Sacramento with its 134 airpark / dockyard buildings dropped
  (port_clear.py), first autosave at 2.5 min: 10 x 38000 fuel depot in the airport zone, 15 x 38001 container stack
  and 14 x 38002 warehouse 2x2 in the seaport zone, saved type 12310 / 12330. Pictures zoom 3 / 4, four rotations.
  Restore = overlay byte-identical to stage\release. Load without the package: no crash, each import lot becomes a
  stock building of the same type and size (1x1 airport -> runway strip 221, 1x1 seaport -> pier 223 on land,
  2x2 seaport -> Loading Bay 240).
- Offline: golden.mjs ports 13/13, pagetest.mjs ports 15/15, bldimport check 3/3 (20/20 frames).
  **run_all.sh with all six args: 26 of 26 steps passed.**
- Static only: prop 0xCA -> attrib +0xbc and prop 0x1F4 -> piece type (data-consistent, loader not read);
  pier rule detail; which stock member the loader substitutes.

## blocked on
(nothing)

## files owned (worktree dev\airsea\wt)
- re/tools/bldimport/bldimport.py, bldweb.js, classifier.html, make_testmodels.py
- re/tools/bldimport/webtest/golden_setup.py, webtest/run_all.sh
- new: re/tools/bldimport/port_clear.py (hidden by the deny-by-default .gitignore: needs `git add -f`),
  re/analysis/PORT_PICK.md (shows as untracked)
- MAIN: verify/airsea/ (RESULTS.md, owner_shots/, runs/), re/sessions/STATUS_airsea.md

## game-harness need
One windowed game in dev\airsea\tree (bld_lab.py, test slot). No sc3probe / harness edits.

## asks of other sessions
sc4props: run_all.sh and golden_setup.py got small additive edits here (ports case, base steps 18 -> 19, 26 with all six args); merge by hand
if you also touched them.
