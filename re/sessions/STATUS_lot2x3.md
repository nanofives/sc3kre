# STATUS lot2x3 (round 2026-11-20d)

## goal
Can SC3U place, draw, rotate, save, load, bulldoze and move a non-square (2x3) building, for hand-placed landmarks and
rewards, and could growables get one? Static evidence + one in-game probe. No importer support (brief).

## verdict + deciding RVA
Simulation side handles rectangles (placement SIMGEOM `0x10006ba6`, highlight `0x1000968b`, occupant grid `0x1000df90`,
bounds `0x1001d305`). Drawing is square: SIMSPR `0x100192aa` registers the sprite as n x n with n = SizeInCellsX
(`0x10019341`), cell map `0x10007b4d` / `0x1000c678` / `0x1000be25` carry one size byte. A data-only 2x3 (X 2, Z 3) works
but shows a cut end (half a cell at the +z end, every view). 3x2 (X > Z) is unsafe (neighbour sprites hidden, ghost
after bulldoze). Save writes X x X (SIMGEOM `0x1001cd38`), load rebuilds from the exemplar. Growables: no, SIMRCI
`0x10027699` reads SizeInCellsX only. Details: `re/analysis/LOT_SHAPES.md`, `verify/lot2x3/RESULTS.md`.

## built
- `verify/lot2x3/work/make_lot2x3.py`: test plugin (2x3 id 38900, 3x2 id 38901, diagnostic art, engine anchors) into a
  test tree; uses bldimport.py helpers read-only.
- `verify/lot2x3/work/lab.py`: lab driver (camera, arm tool, direct place, occupants, sprite cell map, vertex
  altitudes, Demolish hotkey, posted input, save reader).
- No mod code, no bldimport / bldrender / bldweb / sc4web / sc4conv edits.

## proven game-side vs static only
- Game-side (PIDs 17380, 3832, 2052, pictures `verify/lot2x3/owner_shots/00..13`): dialog entry, 2x3 highlight, placement,
  6-cell occupant, 2x2 sprite registration, clip at X x W, four rotations, query dialog, Mover, third-row refusal, 7
  neighbours, save field 2x2, reload, bulldoze from the third row; 3x2 sprite 3x3, hidden park, ghost after bulldoze,
  cleared by reload.
- Static only: zone developer square-only (SIMRCI `0x10027699`), the SIMSPR patch site list (LOT_SHAPES.md 5.2), the
  loader ignoring the saved Z (`0x10003252`).

## blocked on
Nothing.

## files owned (uncommitted, in dev\lot2x3\wt)
- `re/analysis/LOT_SHAPES.md` (new)
- `re/sessions/STATUS_lot2x3.md` (new)
- `verify/lot2x3/RESULTS.md` (new)
- `verify/lot2x3/work/make_lot2x3.py`, `verify/lot2x3/work/lab.py` (new)
- `verify/lot2x3/work/sheet_zoom2.png`, `verify/lot2x3/work/resize_run1.log`, `resize_run2.log`, `resize_run3.log`
- `verify/lot2x3/owner_shots/` (14 pictures, 2.2 MB)

`git status` shows only LOT_SHAPES.md and RESULTS.md. This file is hidden by `.gitignore:65 /re/*` and the work files by
`.gitignore:55 /verify/*/*` (deny-by-default): `git add -f` them if wanted (STATUS_plop.md was committed that way).
owner_shots are local pictures by the brief.

Test-tree only (not for commit): `dev\lot2x3\tree\Apps\PlugIn\lot2x3\` (remove with `make_lot2x3.py --game ..\tree
--restore`), saves `dev\lot2x3\tree\Cities\lot2x3_saved*.sc3`, `lot2x3_after3x2*.sc3`, `Madison, WI (auto ...).sc3`.

## game-harness need
None left. Harness claim released. No game running.

## asks of other sessions
- Orchestrator / owner: choose for SC4 2x3 lots between (a) keep the smallest square (today), (b) data-only w x d with the
  cut end, (c) the SIMSPR rectangular-sprite patch (mod code, draw loop, needs its own round).
- lot5x5 stream: unaffected (5x5 is square).
