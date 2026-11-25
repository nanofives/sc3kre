# STATUS rotplace (2026-11-25)

## goal
TAB while placing a plopped building cycles its rotation 0-3; placed turned; label line; Mover keeps it; own switch.

## verdict + deciding RVA
Done. Hook = SIMGEOM commit entry 0x10007760 (RELOCATE's detour): QI 0xc14f8955 on each new occupant, then
cISC3Occupant::SetRotationFlag vt+0x10c before the stock insert. Occupant made at 0x10006d45 (layer vt+0x20).

## built
sc3resize ROTPLACE (sc3resize_rotplace.c + small edits in sc3resize.c / sc3resize_placehints.c), lang key
resize.rotplace_label. Switch sc3resize.ini [buildings] rotate=0 / SC3RESIZE_ROTPLACE=0.

## proven game-side vs static only
Game-side: rotations 0-3 placed and read back, 4 views, City Hall, Mover keeps rotation 2, game-written save + fresh
reload, non-square 2x3 ignores TAB, TAB with no tool, switch off. Static only: 4-piece reward tool class excluded.

## blocked on
nothing

## files owned
re/harness/src/sc3resize_rotplace.c (new), re/harness/src/sc3resize.c, re/harness/src/sc3resize_placehints.c,
re/harness/lang/{es,en,fr,de,it,nl,sv}.txt, re/analysis/BUILDING_ROTATION.md (section 6), verify/rotplace/RESULTS.md,
verify/rotplace/work/{lab.py,run_place.py}, this file. Committed on child/rotplace.

## game-harness need
none now (claim released)

## asks of other sessions
owner hand check: physical TAB and Shift+TAB, shading of turned buildings, the $0 label side effect.
