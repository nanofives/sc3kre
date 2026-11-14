# STATUS xsect (child of "SC3 Simtropolis feedback triage"), 2026-11-14

## goal
Owner: "test with all possible intersections in a plain sandbox world and send me screenshots". Player report: an
avenue meeting "orthogonal" roads draws nothing, diagonal works. Test pass only, no fixes.

## verdict
DONE. 80 cases: 43 ok, 10 refused by design (stock look, log says so), 26 BROKEN, 1 not built.
Every orthogonal-only case draws. Every broken case has a diagonal avenue/boulevard in it (on screen a diagonal band
runs vertical/horizontal, so the player's "orthogonal" may mean a road meeting a DIAGONAL avenue). No cell holds a
piece that draws nothing at all; the faults are wrong/missing art next to the junction. Classes, cells and log lines:
`verify/xsect/RESULTS.md`.

## built
- Sandbox `dev/xsect/tree/Cities/xsect_sandbox_clear.sc3` (Roadless Paradise flattened, no water, trees bulldozed,
  $50M) and the built sweep `xsect_sweep_built.sc3`.
- Drivers (verify/xsect): `sweep.py` (plan/build/shots/rows/rot), `ramp.py` (on-ramp cases), `clear_trees.py`,
  `clear_boxes.py`, `logsum.py`, `sheets.py`. No mod source touched.

## proven game-side vs static only
All game-side: game-thread builds, read-back of every slot (at build and after the sweep), sc3netmod.log per case,
frame-dump pictures (rotation 0 + rotation 1 for 4 cases). Stock baselines in the same city (74..77: plain diagonal
road and road over rail / under highway) separate stock behaviour from netmod.

## blocked on
Nothing.

## files owned (nothing committed, no git add)
- `verify/xsect/RESULTS.md`, `verdicts.json`, `logsum.json`, `final_cells.json`, `sc3netmod_sweep.log`,
  `build.log`, `build2.log`, `shots.log`, `rb_lab_cam.json`
- `verify/xsect/sweep.py`, `ramp.py`, `clear_trees.py`, `clear_boxes.py`, `logsum.py`, `sheets.py`
- `verify/xsect/cases/` (80 x `<id>.json` + `<id>_grid.txt`)
- `verify/xsect/owner_shots/` (80 case PNGs, 9 `sheet_*.png`, 10 `overview_row*.png`, 4 `rot_*.png`)
- `verify/xsect/raw/` (source frame dumps as PNG, 48 MB, can be dropped from the commit)
- `re/sessions/STATUS_xsect.md`

## game-harness need
None. Game PID 5732 (mine) stopped, harness claim released. No BMP dumps left (np_drive deletes them).

## asks of other sessions
None.
