# STATUS restore (child/restore, from main 5b5de31) - DONE, ready to merge

## goal
Owner 2026-11-02: "Restaurar" button in the building query dialog for buildings with a lifespan (cost = build price x
fraction of life used), plus a list of every such building opened from a button next to the Reunirse close X.

## verdict + deciding RVAs
Age = `IBuildingMortal`, QI **0x43680ca9**, same slots in SIMUTIL (plants, water) and SIMECO (incinerator, recycling):
+0x10 GetMaxAge, +0x18 GetDeclineAge, +0x1c GetAge (SIMUTIL 0x100120a1: months, city date minus birthdate), +0x28
IsDefunct. Birthdate set through the building interface QI 0xe0faadc7 **vt+0x44 SetBirthdate** (SIMUTIL 0x10006b86,
SIMECO 0x100013dc; the game uses it for rubble, SIMUTIL 0x1000690c). Price = budget vt+0x54(type id), withdraw vt+0x14.
Reunirse list page handler SIMUI FUN_100042f7 takes FIVE stack args (`ret 0x14` @ 0x10004402).
Full write-up: `re/analysis/RESTORE.md`. Results: `verify/restore/RESULTS.md`.

## built
- sc3restore.dll (mechanism, exports, nothing patched). Off: `SC3RESTORE=0`.
- sc3resize RESTORE block (sc3resize_restore.c #included): query-dialog "Restaurar $N" with close+reopen after a restore;
  Reunirse "Vida útil" button -> list page (7 two-line rows/page, per-row Restaurar, Restaurar todos, < >, Volver,
  periodic refresh, price-rose guard). Off: `SC3RESIZE_RESTORE=0`.

## proven game-side vs static only
Game-side (Berlin, dev/restore tree): query restore of the coal plant (age, funds, reopen), list of 216 buildings in
24 ms, one row, restore all (§102,832), Volver, close box + reopen, price guard, petition rows hidden, RESTORE=0 stock.
Game-side also (orchestrator checks): aged plant output 1788 -> 6000 after restore, IsDefunct 0, rounded cost 4,702, dead plant has no button.
Static only: "Sin fondos" caption in the query dialog; incinerator / recycling (none in Berlin; slots read from the PE).

## blocked on
-

## files owned (no commits made)
- NEW (ignored by `/re/*`, need `git add -f`): `re/harness/src/sc3restore.c`, `re/harness/src/sc3resize_restore.c`
- NEW: `re/analysis/RESTORE.md`, `re/tools/restore_lab.py`, `verify/restore/RESULTS.md`
- CHANGED: `re/harness/src/sc3resize.c`, `re/harness/src/sc3mods.c` (default list), `re/scripts/build_mod.ps1`,
  `re/scripts/sc3dev.ps1`, `re/tools/sc3wait.py`, `re/scripts/lan_release/stage_lan_release.py`
- Local only: `MAIN\verify\restore\owner_shots\1..9*.png`, `MAIN\verify\restore\runs\` (PNGs, BMPs deleted)

## game-harness need
None left running (all my games stopped).

## asks of other sessions
- Release: ship sc3restore.dll with the other mods (already in MOD_BINS / the loader's default list on this branch).
- GitHub README "The mods (sc3mods)" section: add the restore feature when it ships.
