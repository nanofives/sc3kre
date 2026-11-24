# STATUS lotgrow (round 2026-11-24c, research only)

## goal
Can zone growth place non-square (w x d) lots? Map the developer path, list every square assumption, say what a
w x d growable needs, give a verdict with the size of the change and a smaller first step. Nothing built.

## verdict + deciding RVA
Feasible with code in one layer. The zone path is rectangular already (FindBuildableRect SIMRCI `0x100332e4` grows W
and D independently, PlaceBuilding `0x10032dfc` uses SizeInCellsX and SizeInCellsZ, re-place `0x10029a38`, evaluator
origin test `0x10028f12`). The square is in the 16 rule Apply bodies (vtable slot 0x1c), which read SizeInCellsX only:
6 block-fill (one algorithm), 2 corner+strip+fill, 1 com block, 4 fixed layouts, 3 airport/seaport. First step: one C
body for rule 0xa22653c0 (`0x10026b01`, slot `0x1004ccb0`+0x1c), 1x2 / 2x3 in families 11 and 4. Rules: X < Z (stand-in
SIMINIT `0x1000cb3d` asks for saved X x saved X), |X - Z| = 1 (LOTRECT draw order), LOTRECT on.

## built
Nothing.

## proven game-side vs static only
Static only. Not run: construction / abandoned art of a w x d growable `[UNCERTAIN]`, load with the package removed.

## blocked on
Nothing.

## files owned (uncommitted, in dev\lotgrow\wt)
- `re/analysis/LOT_SHAPES.md` (new section 11, line 30 verdict bullet, 5.4 heading marked superseded)
- `verify/lotgrow/RESULTS.md` (new)
- this file, `MAIN\re\sessions\STATUS_lotgrow.md` (new, hidden by .gitignore)

## game-harness need
None this round. A build round needs one tree (`dev\lotgrow\tree`, made with -NoBuild, no mods built yet).

## asks of other sessions
None.
