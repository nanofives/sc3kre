# STATUS restorefix (round 2026-11-02b, child of "SC3 graphs tabs + Vida util/restore/query UI round")

## goal
1. Owner bug: a restored recycling center dies ("(Muerta)", "Edad 355,419,668 años"). 2. Reconstruir a dead building in
place. 3. Vida útil list: "Vida Útil" title in the game's title font, smaller "<" ">", a clear hourglass.

## verdict + deciding RVA
- Bug: the recycling center's SetBirthdate SIMECO 0x10003441 reads date vt+0x34 (year) and vt+0x38 (day of the year),
  not vt+0x68. sc3restore's stand-in date answered both with the day number, so the year came out near 2.48 million
  (rebuilt by 0x100113a4). A second fault: a failed post-check still counted as a restore and was charged.
- Rebuild: the rubble keeps type and name, not the key. Its attrib is the rubble art (SIMECO 0x100035f7 builds it from
  occupant +0x24). The key comes from a type -> key table. Placement goes through the stock SIMGEOM 0x10006ba6 inside
  RELOCATE's context.

## built (dev\restorefix\inst, from main be42ba9)
sc3restore.dll, sc3resize.dll.

## proven game-side (Berlin, posted input, pictures in MAIN\verify\restorefix\owner_shots)
- Reproduced with the shipped code, fixed: recycling center 115 -> 0 months, date read back equal, "0 años (75 años)".
- Reconstruir from the "?" and from the list: $5,000 withdrawn by the game, new building age 0. Also from the owner's
  exact state (date broken as 11-02c did: "(Muerta) 355,443,412 años").
- Orchestrator addition: rubble with an out-of-range birthdate (the bug's victims) rebuilds FREE (game's free flag),
  every other dead building PAID, the case logged per rebuild. Run free1: the bug victim cost 0, a coal plant dead of age
  cost 5,000.
- Title "Vida Útil" and back to "Reunirse" on Volver. 24x25 arrows (game's back arrow + mirror), page 2, tooltip. New
  hourglass.
- Key table: 15 stock types measured over 12 shipped cities.

## static only
- Rebuild refused for short funds (my check before Place plus the stock check in Place): not run in game.
- Off switches SC3RESIZE_REBUILD / RSTITLE / RSARROWS / RSHG2 = 0: code paths read, not launched.
- "Reparar (gratis)" for a live broken date: the button and caption are coded, but the game killed the test building
  within seconds, so the live case was never clicked.

## not covered
A building removed altogether (bulldozed, or its rubble cleared) leaves no trace of its type, so it gets no row.

## blocked on
nothing.

## files owned (worktree dev\restorefix\wt, uncommitted)
- re/harness/src/sc3restore.c
- re/harness/src/sc3resize_restore.c   (only block file touched; sc3resize.c itself unchanged)
- re/analysis/RESTORE.md
- re/tools/restore_lab.py
- verify/restorefix/RESULTS.md
Not to stage: MAIN\verify\restorefix\owner_shots\, MAIN\verify\restorefix\runs\.

## game-harness need
none (dev tree only).

## asks of other sessions
- modlang: new inline es/en strings in sc3resize_restore.c (Reconstruir, Reconstruido, En ruinas, Reparar (gratis),
  Fecha dañada, Fin de su vida útil, Vida Útil title, Anterior / Siguiente tooltips, Hay una mudanza en curso, No disponible
  (Mover desactivado), No se puede construir ahí, Ya no está (en ruinas)) and sc3restore.c ("Fecha reparada, sin costo").
- release: `restore_keys.ini` is written at run time beside sc3restore.dll. Do not ship it (the seed is in the DLL).
