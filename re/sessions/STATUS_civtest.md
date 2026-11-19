# STATUS civtest (round 2026-11-19k)

## goal
Close what 2026-11-19b (civmod) left untested: civic looks on other bases, rewards on 1x1 / 3x3 / 4x4 lots, a 3x3
importer growable, fix what breaks.

## verdict
Done. No bug found, no game code changed.
- Civic looks: 17 of 17 buttons cycle stock / look / stock (51 of 51 log lines). Fire, school, hospital, college looks
  placed with the stock tool, each reports its service in the query window, survive save + reload; removing the fire
  look removes one circle from the fire coverage map (258 cyan pixels gone, 0 new).
- Rewards 1x1 / 3x3 / 4x4: unlocked, listed, placed (one-shot), gone from the list, saved, reloaded, moved (Mover $5 /
  $57 / $117, one copy each).
- 3x3 growable (class 6300): grows in Frankfurt, 16 lots in about 11 min, stock 3x3 members growing in the same run.
  Europolis, Europolis 1024, Madison (and sc3compat-a's Sacramento) build no 3x3 commercial lot of any kind.

Deciding evidence: `verify/civtest/RESULTS.md` (log lines, save read-backs, pictures 01-19).

## built
- `re/tools/bldimport/make_testmodels.py --civtest`: 17 civic looks, rewards 1x1 / 3x3 / 4x4, growable 3x3 class 6300.
- `re/tools/civmod_lab.py`: jobs `command` (GetCommand of a button with no hotkey) and `empty` (free squares), modal note.

## proven game-side vs static only
All claims game-side (RESULTS.md). Static only: none.

## blocked on
Nothing.

## files owned (to commit)
- `re/tools/bldimport/make_testmodels.py` (dev\civtest\wt)
- `re/tools/civmod_lab.py` (dev\civtest\wt, CRLF kept)
- `verify/civtest/RESULTS.md` (MAIN)
- `re/sessions/STATUS_civtest.md` (MAIN)
- Pictures `verify/civtest/owner_shots/` (MAIN, local, game art: not committed)

## game-harness need
None left. No game running. dev\civtest\tree keeps the civtest plugin + overlay and three test saves for civdlg.

## asks of other sessions
civdlg: the test data (17 looks) and `civmod_lab.py command` are ready to drive every civic button.
