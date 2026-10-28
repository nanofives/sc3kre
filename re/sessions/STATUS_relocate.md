# STATUS relocate (child of "SC3 mods page layout + autosave rotation + load crash", 2026-10-28)

## goal
A: "Mover" in the "?" of reward / landmark buildings: pick it up with the game's own placement tool, place it, original
demolished. B: player-placed buildings auto-demolish zoned (RCI) buildings under their footprint instead of refusing.

## verdict + deciding RVA
Built and checked in game. Refusal = SIMGEOM site check occupant loop 0x100076b4 (only flora 0x400 and power-line
0x800+0x400000 pass). Commit 0x10007760. Tool factory = building layer +0x70 0x10007e64 (key, one-shot, FREE flag).
Bulldozer per-occupant entry = demolition layer (city vt+0x194) vt+0x6c 0x1001408d. Rewards keep no built state
(SIMADV 0x10017ba8 item +0x54 only set). Landmarks track placed on occupant events (0x1000b32a / 0x1000b458).
Full: re/analysis/RELOCATE.md.

## built
sc3resize.c block RELOCATE + PLOPOVER (after qi_install), switches SC3RESIZE_RELOCATE=0 / SC3RESIZE_PLOPOVER=0.
Move cost = owner call 2026-10-28: 50% of the price (RL_PRICE_PCT / SC3RESIZE_RELOCATE_PRICEPCT) + bulldozing (original,
clearing, zoned) + levelling as the game charges (SC3RESIZE_RELOCATE_CLEARCOST=0 drops those). Cursor label = withdrawn,
parts logged per move. Business deals included, B also when moving.

## proven game-side vs static only
Game-side (Berlin): reward move (statue), landmark move (Brandenburg Gate), cost policy on 3 moves (Mayor's House $50,
Defense Contractor $12,625 = half of 25,000 + 125, Prison $125; label = funds drop each time), business-deal restart
(Prison deal active, same $250/month, total $650 before and after), police over 7 and 4 zoned buildings with
the bulldozer price, two refused cases, Escape cancel, layout next to "Sustituir", switches off.
Static only: reward / landmark menu state after a move, right-click cancel, levelling charge on a slope, sc3undo of a move.

## blocked on
nothing

## files owned (worktree dev\relocate\wt, branch child/relocate, nothing committed)
- re/harness/src/sc3resize.c (modified: RELOCATE block, qi_msg / qi_install wiring, env switches RELOCATE, PLOPOVER, RELOCATE_PRICEPCT, RELOCATE_CLEARCOST)
- re/analysis/RELOCATE.md (new)
- re/tools/relocate_probe.py (new, read-only occupant census / single-cell probe)
- verify/relocate/RESULTS.md (new)
Not for git: MAIN\verify\relocate\owner_shots\*.png, MAIN\verify\relocate\census_berlin.json, MAIN\verify\relocate\fd\

## game-harness need
none now (game stopped)

## asks of other sessions
sc3undo owner: an undo of a move or of a placement over zoned buildings was not tested (removals go through the
occupant manager Remove, so the journal should record them).
