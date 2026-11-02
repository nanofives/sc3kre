# STATUS sirens (child stream, round 2026-11-02 graphs_restoreui)

## goal
Owner 2026-11-02: "avoid looping sirens sounds during gameplay, lower their chances significantly".

## verdict + deciding RVA
FIXED (measured). The cause is the AUDIO Actor's shared siren field +0x90, one per sound id, not per vehicle
(vtable 0x100210ec). Event 5 slot 0x100138a8 writes it only for the tracked vehicle. The update 0x100134fb grabs any
vehicle while it is non-zero. The ctor 0x10012d97 never initializes it (live ",END" garbage). Result: back-to-back
looped sirens on every on-screen fire engine until a tracked re-roll of 0 kills the id for the session.
Roll: STRTSIM 0x100198c0 and inline at 0x1001b44c (20%). Detail: re/analysis/SIRENS.md.

## built
sc3simrun SIRENS block, three switches (orchestrator 2026-11-02): (a) per_vehicle=1 (wraps Actor slots 12/13/14/21),
(b) chance_pct=20 (roll imm8 at both sites, 100 = off), (c) cooldown_s=30 (0 = off). Env SC3SIMRUN_SIREN_PERVEH /
_PCT / _COOL. Whole block off: SC3SIMRUN_SIRENS=0 or simrun.ini [sirens] enabled=0.
Built at dev\sirens\inst\sc3simrun.dll.

## proven game-side vs static only
Game-side: verify/sirens/RESULTS.md per-part table (stock A1b/B0/C0, (a) only C1, (a)+(b)+(c) C2+B1), dev runs B1-B4.
Stock latch start value varies per run (",END" or 0): stock is either back-to-back sirens or none, per session.
Static only: police 114 / ambulance 130 (no such vehicle in Berlin runs; same actor class and code path).

## blocked on
nothing

## files owned (worktree dev\sirens\wt, uncommitted)
- re/harness/src/sc3simrun.c (SIRENS block, header docs)
- re/analysis/SIRENS.md (new)
- re/tools/siren_probe.py (new)
- functions.csv (11 rows via tracker.py batch: STRTSIM 0x100198c0, 0x100172fe; AUDIO 0x10012d97, 0x100134fb,
  0x10013730, 0x10013873, 0x100138a8, 0x10013b5a, 0x1001349f, 0x1001341d, 0x10013977)
- README.md (sc3simrun paragraph: sirens sentence)
In MAIN: verify/sirens/RESULTS.md (tracked); logs/json/run_ab.sh beside it (ignored).

## game-harness need
none further (own tree, test slot)

## asks of other sessions
orchestrator: commit the files above. A release simrun.ini, if one ships, could carry [sirens] chance_pct=20,
cooldown_s=30. The defaults are compiled in, so no ini is needed.
