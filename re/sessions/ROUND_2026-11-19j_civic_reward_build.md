# Round 2026-11-19j: civic variants + new rewards + landmark Mover fix (build)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main 61be5ab+.
Research: re/analysis/CIVIC_REWARD.md, verify/civrew/RESULTS.md (round 2026-11-19i, read both first).
Owner (2026-11-19): civic "Cycle looks", rewards "Yes, build it", Mover fix "Yes, with the next build".
plop2 (same round family) is editing the importer PAGE (classifier.html, bldweb.js, sc4web.js) and sc4conv.py right
now. Do not touch those files in this round: the page side of civic / reward comes after plop2 is merged.

## Stream civmod (opus / high)

Code goes in existing mods (no new DLL: a new DLL needs the loader list, sc3wait.py's fixed list and the mods page).
Suggested home: sc3resize (it already owns placehints' cost label, the picker and the Mover). Put each feature behind
its own sc3resize.ini / mods page switch like the other rows (on by default), with a log line at start.

1. Civic variants, "cycle looks": the 5-byte detour at SIMGEOM 0x1000b19d. Data: a variants file written by
   bldimport (CIVIC_REWARD.md proposes `bldimport_civic.ini` `[Variants] <base instance>=<variant ids>`, decide the
   final form and where it lives), exemplar copies in the existing plugin (same type and stats as the base, own key,
   art, name). Each press of the stock button builds the next look (stock first, then the variants, wrap). The
   variant's name in placehints' cost label. No variants = stock behaviour exactly.
2. New rewards: the 6-byte detour at SIMADV 0x1000a7fa adds our type ids to the "unlock when population and year are
   met" set. Our reward rows read with the game's own ini parser after the stock list (0x10007989). If the parser
   refuses a loose file, stop and report before taking the SYS.PAK fallback. Add our reward types to rl_types so they
   get Mover. Pick the type id block and record it next to ids.json (bldimport ids 38000+).
3. Mover fix: rl_movable (sc3resize.c:10409) skips type 18000 exactly, the type bldimport gives landmarks. Make
   imported landmarks movable and keep the picker from offering a second copy of a placed one if that is stock
   behaviour for landmarks.
4. bldimport.py: kinds `civic` (base = a stock civic command, e.g. police / fire / school, written as the variant
   copy + variants file) and `reward` (population, year, lot from a stock reward of the same size), with build /
   restore / check covering the new files. models.json fields documented in the tool's help. Python side only.
5. In-game checks (windowed, posted input or Frida game calls, sc3dev run civmod), pictures local only:
   - a police variant placed with the stock button, second press = stock look again, coverage shown in the Ver datos
     police view, saved and reloaded
   - a new reward unlocked at its population (use a test city or set population by a game call), placed, saved,
     reloaded, Mover works on it
   - an imported landmark has Mover and moves
   - with the variants file and reward ini removed: stock behaviour, no crash on load of a city that used them
   - all mods on, one start and one load per check at least, no VEH FAULT in sc3resize.log
6. Build every changed mod with build_mod.ps1 into dev\civmod\inst. Results verify/civmod/RESULTS.md (checks run,
   numbers, what stays open), analysis updates in CIVIC_REWARD.md.

## Rules

Windowed game, never the real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add /
commit. EA content (exemplars copied from stock, art) only in the test tree, never in the repo.
