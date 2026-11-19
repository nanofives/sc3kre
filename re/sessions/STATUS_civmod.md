# STATUS civmod (round 2026-11-19j) - done, waiting for merge

## goal
Civic looks cycled on the stock button (CIVVAR), new rewards unlocked at their population (NEWREWARD), Mover for
bldimport landmarks (type 18000), bldimport kinds `civic` and `reward`.

## verdict + deciding RVA
- CIVVAR: SIMGEOM call at 0x1000b1a3 (rel32 -> cv_call). The proposed 0x1000b19d sees 1 of 17 cases (measured).
- NEWREWARD: SIMADV 0x10006f80 (rows, game's own ini class reads the loose file: no SYS.PAK), 0x1000a7fa (unlock),
  SC3U 0x0040bc80 / 0x0040bccb (reward types declared like CitySim.ini rows; undeclared = fault at SIMADV 0x1000b392).
- Mover: rl_movable 18000..18999 + 38000..38999.

## built
sc3resize.dll in dev\civmod\inst (clean build 15:19). bldimport kinds civic / reward, check 0 of 4 failed.

## proven game-side vs static only
All checks in verify/civmod/RESULTS.md ran in game. Open: stock game + plugin + city with a placed new reward exits on
load (owner's call: SYS.PAK CitySim.ini overlay, or reuse declared-unused types).

## blocked on
nothing

## files owned (dev\civmod\wt)
- re/harness/src/sc3resize_civic.c (new, ignored by /re/*: needs `git add -f`)
- re/harness/src/sc3resize.c, re/harness/src/sc3resize_placehints.c
- re/harness/lang/de.txt en.txt es.txt fr.txt it.txt nl.txt sv.txt
- re/tools/bldimport/bldimport.py, re/tools/bldimport/make_testmodels.py
- re/tools/civmod_lab.py (new)
- re/analysis/CIVIC_REWARD.md, verify/civmod/RESULTS.md (new)
Pictures (not committed): MAIN\verify\civmod\owner_shots\ (16 jpg).

## game-harness need
none now

## asks of other sessions
plop2 / next round: page side (classifier.html, bldweb.js) for kinds civic and reward, incl. bldimport_types.ini.
