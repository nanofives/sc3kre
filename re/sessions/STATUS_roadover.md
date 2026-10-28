# STATUS roadover (child of "SC3 mods page layout + autosave rotation + load crash", 2026-10-28)

## goal
Owner 2026-10-28: "i'm not able to place road over these residential buildings". Network drags (road, highway, rail,
power line) over ZONED buildings demolish them and build, charging the bulldozing, under PLOPOVER
("Construir sobre zonas").

## verdict + deciding RVA
FIXED. Stock refusal = drag predicate vt+0xc: road SIMNTWRK `0x1001ad60` (highway `0x1001ae36`, rail `0x1001ade7`,
power `0x1001adaf`), called per cell by `0x10010731` from the drag compute `0x1000488d`. Measured in `-Stock`: all four
return 0 on zoned houses. Build = netmgr vt+0xf0 `0x10014a23`. Detail: `re/analysis/ROADOVER.md`.

## built
sc3resize ROADOVER block (after rl_install, own install thread), `dev\roadover\inst\sc3resize.dll`.

## proven game-side vs static only
Game-side (Berlin): road and rail over 3 zoned houses (6 tiles): label $100 = 70 + 30, houses removed, built, funds
-100; sc3undo restores the houses and refunds $100; civic building refused; PLOPOVER=0 red like the owner's picture;
stock predicates refuse (in a `-Stock` process). sc3netmod CROSS + ROADOVER both installed, 3 launches of 3.
Power line over 4 zoned buildings built and undone (stock power predicate refuses buildings, measured in -Stock).
Each building charged once. Funds-short drag ($80 < $100): nothing demolished, nothing built. Only cells marked 0x23
(valid) are charged or demolished (after the orchestrator's point 2).
Static only: highway building over houses (hooked, predicate measured accepting).

## blocked on
nothing

## files owned (worktree dev\roadover\wt)
- re/harness/src/sc3resize.c (ROADOVER block + install thread start after rl_install)
- re/analysis/ROADOVER.md (new)
- re/tools/roadover_probe.py (new, cell map / predicate calls / test funds setter)
- re/tools/roadover_drive.py (new, posted-input drags + frame dump)
- verify/roadover/RESULTS.md (new)
Pictures (not to commit): MAIN\verify\roadover\owner_shots\

## game-harness need
dev\roadover tree only. No game of mine is running.

## asks of other sessions
- Merge note: sc3netmod.c is unchanged. ROADOVER chains sc3netmod's CROSS predicate wrappers. Any future change to
  either mod's predicate slots must keep chaining (both skip a slot that is not stock).
- Mods page: the "Construir sobre zonas" label now also covers network drags. The text was left as is.
